"""Tests for the FastAPI server and WebSocket match stream."""

from fastapi.testclient import TestClient

from arena.server import app

client = TestClient(app)


def test_serves_ui_and_assets():
    page = client.get("/")
    assert page.status_code == 200
    assert "AGENT ARENA" in page.text
    app_js = client.get("/static/app.js")
    assert app_js.status_code == 200
    assert "WebSocket" in app_js.text


def test_websocket_streams_a_full_match():
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json({"type": "catalog"})
        catalog = websocket.receive_json()
        assert catalog["type"] == "catalog"
        assert {"random", "tactical", "jev", "clm"} <= set(catalog["agents"])

        websocket.send_json(
            {
                "type": "start",
                "agent_a": "random",
                "agent_b": "tactical",
                "games": 1,
                "seed": 7,
                "min_move_delay": 0,
            }
        )
        types = []
        while True:
            message = websocket.receive_json()
            types.append(message["type"])
            if message["type"] == "match_end":
                result = message["result"]
                break

        assert types[0] == "match_start"
        assert types[1] == "game_start"
        assert "move" in types
        assert types[-2] == "game_end"
        assert types[-1] == "match_end"
        assert set(result["stats"]) == {"random", "tactical"}
        assert result["stats"]["random"]["invalid_moves"] == 0
        assert result["stats"]["tactical"]["invalid_moves"] == 0


def test_websocket_reports_unknown_agent():
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json({"type": "start", "agent_a": "nope", "agent_b": "random"})
        message = websocket.receive_json()
        assert message["type"] == "error"
        assert "unknown agent" in message["message"]
