"""CLMAgent — plays via a self-hosted Contrastive LM server (SystemOne API)."""

from typing import Any, Optional

import httpx

from arena.agents.base import Agent
from arena.agents.text import move_options, state_text, turn_questions
from arena.engine import Engine, Move
from arena.env import get_env
from game.enums import Player

DEFAULT_CLM_URL = "http://127.0.0.1:8700"
CLM_MODEL = "clm-latest"


class CLMClient:
    """Thin HTTP client for the clm-serve SystemOne API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: str = CLM_MODEL,
        timeout: float = 120.0,
    ) -> None:
        base = base_url or get_env("CLM_BASE_URL") or DEFAULT_CLM_URL
        self.base_url = base.rstrip("/")
        self.model = model
        key = api_key or get_env("CLM_API_KEY")
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers=headers,
        )

    def system_one(self, state: str, questions: dict[str, Any]) -> dict[str, Any]:
        """POST one state plus typed questions and return the parsed response."""
        response = self._client.post(
            "/v1/systemone",
            json={"state": state, "model": self.model, "questions": questions},
        )
        response.raise_for_status()
        return response.json()

    def ask_questions(
        self, state: str, questions: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Ask several typed questions in one call; returns (answers, usage)."""
        payload = self.system_one(state, questions)
        return payload["answers"], payload.get("usage", {})

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
        answers, usage = self.ask_questions(state, questions)
        return answers["answer"], usage

    def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        self._client.close()


class CLMAgent(Agent):
    """Chooses moves by asking the self-hosted CLM server typed questions."""

    def __init__(
        self,
        name: str = "clm",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        client: Optional[CLMClient] = None,
        model: str = CLM_MODEL,
    ) -> None:
        super().__init__(name)
        self.client = client or CLMClient(
            base_url=base_url, api_key=api_key, model=model
        )

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
            raise ValueError(f"CLM chose an unknown option: {choice!r}")
        probabilities = answer.get("probabilities") or {}
        top = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)[:3]
        meta = {
            "confidence": answer.get("confidence"),
            "top_probabilities": top,
            "threat_check": answers.get("threat_check"),
            "usage": usage,
        }
        return move, meta
