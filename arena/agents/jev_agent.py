"""JevAgent — plays via TypeSafe's SystemOne API (model jev-latest)."""

import time
from typing import Any, Optional

import httpx

from arena.agents.base import Agent
from arena.agents.text import move_options, state_text, turn_questions
from arena.engine import Engine, Move
from arena.env import get_env
from game.enums import Player

JEV_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-latest"
RETRY_STATUSES = {429, 529}
MAX_ATTEMPTS = 4
BACKOFF_BASE = 1.0
BACKOFF_CAP = 8.0


class JevClient:
    """Thin HTTP client for the TypeSafe SystemOne API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = JEV_MODEL,
        timeout: float = 60.0,
    ) -> None:
        key = api_key or get_env("TYPESAFE_API_KEY")
        if not key:
            raise RuntimeError(
                "TYPESAFE_API_KEY is not set. Add it to .env or export it."
            )
        self.model = model
        self.endpoint = JEV_ENDPOINT
        self._client = httpx.Client(
            timeout=timeout,
            headers={"Authorization": f"Bearer {key}"},
        )

    def system_one(self, state: str, questions: dict[str, Any]) -> dict[str, Any]:
        """POST one state plus typed questions and return the parsed response."""
        for attempt in range(MAX_ATTEMPTS):
            response = self._client.post(
                self.endpoint,
                json={"state": state, "model": self.model, "questions": questions},
            )
            if response.status_code not in RETRY_STATUSES:
                break
            if attempt == MAX_ATTEMPTS - 1:
                break
            time.sleep(self._retry_delay(response, attempt))
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        """Seconds to wait before the next attempt, honoring Retry-After."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), BACKOFF_CAP)
            except ValueError:
                pass
        return min(BACKOFF_BASE * (2**attempt), BACKOFF_CAP)

    def ask_choice(
        self,
        state: str,
        instructions: str,
        options: dict[str, Optional[str]],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Ask a single Choice question; returns (answer, usage)."""
        questions = {
            "answer": {
                "type": "choice",
                "instructions": instructions,
                "criteria": options,
            }
        }
        payload = self.system_one(state, questions)
        return payload["answers"]["answer"], payload.get("usage", {})

    def ask_questions(
        self, state: str, questions: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Ask several typed questions in one call; returns (answers, usage)."""
        payload = self.system_one(state, questions)
        return payload["answers"], payload.get("usage", {})

    def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        self._client.close()


class JevAgent(Agent):
    """Chooses moves by asking Jev one multiple-choice question per turn."""

    def __init__(
        self,
        name: str = "jev",
        api_key: Optional[str] = None,
        client: Optional[JevClient] = None,
        model: str = JEV_MODEL,
    ) -> None:
        super().__init__(name)
        self.client = client or JevClient(api_key=api_key, model=model)

    def ask_choice(
        self,
        state: str,
        instructions: str,
        options: dict[str, Optional[str]],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Generic Choice question, shared by matches and the probe quiz."""
        return self.client.ask_choice(state, instructions, options)

    def _choose(self, engine: Engine) -> tuple[Optional[Move], dict[str, Any]]:
        table = move_options(engine)
        if not table:
            raise RuntimeError("no legal moves available")
        player = engine.current_player
        opponent = Player.O if player == Player.X else Player.X
        questions = turn_questions(table, player, opponent)
        answers, usage = self.client.ask_questions(state_text(engine), questions)
        answer = answers["answer"]
        choice = answer.get("choice")
        move = table.get(choice)
        if move is None:
            raise ValueError(f"Jev chose an unknown option: {choice!r}")
        probabilities = answer.get("probabilities") or {}
        top = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)[:3]
        meta = {
            "confidence": answer.get("confidence"),
            "top_probabilities": top,
            "threat_check": answers.get("threat_check"),
            "usage": usage,
        }
        return move, meta
