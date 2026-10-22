"""Security properties, pinned as tests (audit 2026-10-22)."""

import pytest
from starlette.testclient import TestClient

from clinic_mcp.store import load_store
from clinic_mcp.tools import Tools
from console.app import create_app
from tests.test_runner_offline import FakeLLM

OK = {"from_name": "A", "from_contact": "1", "channel": "sms", "body": "hi"}


@pytest.fixture
def client(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>app</html>")
    (tmp_path / "secret.txt").write_text("TOP SECRET")
    with TestClient(create_app(results_dir=tmp_path, static_dir=dist, llm_factory=lambda: FakeLLM())) as c:
        yield c


# SEC-1: an invalid received_at made the tool fail and left the PREVIOUS message's clock in place.
@pytest.mark.parametrize("bad", ["yesterday", "2026-13-40T10:00", "10:00"])
def test_live_api_rejects_a_malformed_timestamp(client, bad):
    assert client.post("/api/live/process", json={**OK, "received_at": bad}).status_code == 422


def test_begin_message_never_keeps_a_stale_clock():
    tools = Tools(load_store())
    tools.admin_begin_message("A", "x", "1", "sms", "2026-11-09T15:00:00-06:00")
    r = tools.admin_begin_message("B", "x", "1", "sms", "not a time")
    assert r["ok"] is False and tools.store.now is None and tools.message == {}


@pytest.mark.parametrize("path", ["/../secret.txt", "/assets/../../secret.txt", "/%2e%2e/secret.txt", "/assets/%2e%2e/%2e%2e/secret.txt"])
def test_static_server_never_serves_files_outside_the_build(client, path):
    assert "TOP SECRET" not in client.get(path).text


def test_oversized_and_wrongly_typed_bodies_are_rejected(client):
    assert client.post("/api/live/process", json={**OK, "body": "x" * 4001}).status_code == 422
    assert client.post("/api/live/process", json={**OK, "channel": "fax"}).status_code == 422
    assert client.post("/api/live/process", content=b"not json", headers={"content-type": "application/json"}).status_code == 422
    assert client.post("/api/live/process", json=[1, 2]).status_code == 422


def test_no_cross_origin_access_is_granted(client):
    r = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}
