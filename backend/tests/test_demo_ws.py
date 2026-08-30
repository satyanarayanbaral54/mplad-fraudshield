import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from main import app


def test_demo_start_endpoint():
    client = TestClient(app)
    response = client.post("/api/v1/demo/start")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    assert data["expected_events"] == 10


def test_websocket_connect():
    client = TestClient(app)
    with client.websocket_connect("/ws/live-flags") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "CONNECTED"
