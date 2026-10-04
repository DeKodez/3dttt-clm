"""FastAPI server — serves the web arena UI and streams matches over WebSocket."""

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from arena.agents.base import Agent
from arena.agents.registry import AGENT_NAMES, build_agent
from arena.match import play_match

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
BASELINE_NAMES = ("random", "tactical")

app = FastAPI(title="Agent Arena")


@app.get("/")
def index() -> FileResponse:
    """Serve the arena UI."""
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


def _build_agent(name: str, seed: int, side: str) -> Agent:
    """Instantiate one side's agent, seeding deterministic baselines apart."""
    kwargs = {"seed": seed + (0 if side == "a" else 100)} if name in BASELINE_NAMES else {}
    return build_agent(name, **kwargs)


async def _stream_match(websocket: WebSocket, request: dict[str, Any]) -> None:
    """Run one match in a worker thread, pacing events to the client."""
    agent_a_name = str(request.get("agent_a", "random"))
    agent_b_name = str(request.get("agent_b", "tactical"))
    games = max(1, min(int(request.get("games", 1)), 50))
    seed = int(request.get("seed", 7))
    min_move_delay = max(0.0, min(float(request.get("min_move_delay", 0.8)), 5.0))
    session = request.get("session", 0)

    agent_a = _build_agent(agent_a_name, seed, "a")
    agent_b = _build_agent(agent_b_name, seed, "b")

    await websocket.send_json(
        {
            "type": "match_start",
            "session": session,
            "agents": [agent_a.name, agent_b.name],
            "games": games,
            "min_move_delay": min_move_delay,
        }
    )

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    def on_event(event: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)

    match_task = asyncio.create_task(
        asyncio.to_thread(play_match, agent_a, agent_b, games, seed, on_event)
    )

    while True:
        if match_task.done() and queue.empty():
            break
        try:
            event = await asyncio.wait_for(queue.get(), timeout=0.25)
        except asyncio.TimeoutError:
            continue
        await websocket.send_json(event)
        if event["type"] == "move" and min_move_delay:
            await asyncio.sleep(min_move_delay)
        elif event["type"] == "game_end":
            await asyncio.sleep(1.0)

    result = await match_task
    await websocket.send_json(
        {"type": "match_end", "session": session, "result": result.to_dict()}
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Accept commands and stream match events for one client."""
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "invalid JSON"})
                continue
            kind = message.get("type")
            if kind == "catalog":
                await websocket.send_json({"type": "catalog", "agents": AGENT_NAMES})
            elif kind == "start":
                try:
                    await _stream_match(websocket, message)
                except Exception as exc:
                    await websocket.send_json(
                        {"type": "error", "message": f"{type(exc).__name__}: {exc}"}
                    )
            else:
                await websocket.send_json(
                    {"type": "error", "message": f"unknown message type {kind!r}"}
                )
    except WebSocketDisconnect:
        return


def main() -> None:
    """Run the arena server with uvicorn."""
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("arena.server:app", host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
