"""Console API tests: real MCP server, scripted LLM, temporary results directory."""

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from console.app import create_app
from tests.test_runner_offline import FakeLLM, tool_use, triage

ROOT = Path(__file__).resolve().parent.parent


def _script(step, token):
    return [
        [tool_use("draft_reply", text="Our hours are 9 to 5.", language="en")],
        [tool_use("submit_result", intents=["admin"], urgency="routine", actions=["answer_directly"])],
    ][step]


@pytest.fixture
def results_dir(tmp_path):
    run = tmp_path / "runs" / "R1"
    run.mkdir(parents=True)
    result = {
        "id": "M003",
        "patient_id": "P003",
        "intents": ["clinical"],
        "urgency": "emergency",
        "actions": ["escalate_emergency"],
        "routed_to": ["clinician_urgent"],
        "tool_calls": ["verify_sender", "route_to_queue", "draft_reply"],
        "reply_draft": "Call 911",
    }
    (tmp_path / "results_sample.json").write_text(json.dumps([result]))
    (tmp_path / "results_sample.run").write_text(str(run))
    (run / "M003.json").write_text(
        json.dumps(
            {
                "id": "M003",
                "path": "emergency",
                "trace": [],
                "screen": {"tier": "emergency"},
                "guard_violations": [],
                "latency_s": 0.1,
                "llm_calls": [],
            }
        )
    )
    (run / "final_state.json").write_text(
        json.dumps(
            {
                "appointments": [],
                "routes": [{"queue": "clinician_urgent", "message_id": "M003"}],
                "refill_requests": [],
                "flags": [],
                "drafts": [],
            }
        )
    )
    (run / "meta.json").write_text(json.dumps({"run_id": "R1", "model": "fake", "effort": "medium", "n": 1, "wall_s": 1.0}))
    (tmp_path / "eval_report.json").write_text(json.dumps({"scores": {"urgency_accuracy": 1.0}}))
    return tmp_path


@pytest.fixture
def client(results_dir):
    app = create_app(results_dir=results_dir, llm_factory=lambda: FakeLLM(triage_result=triage(intents=["admin"]), script=_script))
    with TestClient(app) as c:
        yield c


def _sse(text: str) -> list[dict]:
    events = []
    for block in text.strip().split("\n\n"):
        data = [line[6:] for line in block.splitlines() if line.startswith("data: ")]
        if data:
            events.append(json.loads("".join(data)))
    return events


def test_health(client):
    body = client.get("/api/health").json()
    assert body["ok"] is True and "model" in body and "llm_configured" in body


def test_datasets_lists_sample_and_holdout(client):
    ds = {d["id"]: d for d in client.get("/api/datasets").json()}
    assert ds["sample"]["messages"] == 40 and ds["sample"]["has_results"] is True
    assert ds["holdout"]["messages"] == 13 and ds["holdout"]["has_results"] is False


def test_inbox_joins_message_label_result_and_log(client):
    body = client.get("/api/datasets/sample/inbox").json()
    assert body["run"]["run_id"] == "R1"
    items = {i["message"]["id"]: i for i in body["items"]}
    assert len(items) == 40
    m3 = items["M003"]
    assert m3["label"]["expected_actions"] == ["escalate_emergency"]
    assert m3["result"]["actions"] == ["escalate_emergency"]
    assert m3["log"]["path"] == "emergency"
    assert items["M001"]["result"] is None


def test_inbox_without_results_still_lists_messages(client):
    body = client.get("/api/datasets/holdout/inbox").json()
    assert body["run"] is None and len(body["items"]) == 13


def test_unknown_dataset_is_404(client):
    assert client.get("/api/datasets/nope/inbox").status_code == 404


def test_eval_and_run_state(client):
    assert client.get("/api/datasets/sample/eval").json()["scores"]["urgency_accuracy"] == 1.0
    assert client.get("/api/datasets/holdout/eval").status_code == 404
    assert client.get("/api/datasets/sample/state").json()["routes"][0]["queue"] == "clinician_urgent"


def test_clinic_reference_data(client):
    body = client.get("/api/clinic").json()
    assert body["clinic"]["today"] == "2026-11-09"
    assert {"id": "P001", "name": "Linda Morales", "primary_provider": "PATEL"} in body["patients"]
    assert "dob" not in body["patients"][0]


def test_live_process_streams_events_and_result(client):
    payload = {"from_name": "Lucy Nguyen", "from_contact": "555-0123", "channel": "sms", "body": "What are your clinic hours?"}
    with client.stream("POST", "/api/live/process", json=payload) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        events = _sse(r.read().decode())
    types = [e["type"] for e in events]
    assert types[:2] == ["message", "stage"] and types[-1] == "result"
    assert events[-1]["data"]["reply_draft"] == "Our hours are 9 to 5."
    assert events[-1]["data"]["id"].startswith("LIVE-")


def test_live_emergency_streams_template(client):
    payload = {"from_name": "Aisha Johnson", "from_contact": "555-0103", "channel": "sms", "body": "crushing chest pain into my arm"}
    with client.stream("POST", "/api/live/process", json=payload) as r:
        events = _sse(r.read().decode())
    assert events[-1]["data"]["actions"] == ["escalate_emergency"]


def test_live_process_validates_input(client):
    assert client.post("/api/live/process", json={"from_name": "x", "channel": "fax", "body": "hi"}).status_code == 422
    assert client.post("/api/live/process", json={"from_name": "x", "from_contact": "1", "channel": "sms", "body": ""}).status_code == 422
    bad_dob = {"from_name": "x", "from_contact": "1", "channel": "sms", "body": "hi", "stated_dob": "11/02/1971"}
    assert client.post("/api/live/process", json=bad_dob).status_code == 422


def test_live_state_and_reset(client):
    payload = {"from_name": "Aisha Johnson", "from_contact": "555-0103", "channel": "sms", "body": "I can't breathe"}
    with client.stream("POST", "/api/live/process", json=payload) as r:
        r.read()
    assert any(x["queue"] == "clinician_urgent" for x in client.get("/api/live/state").json()["routes"])
    assert client.post("/api/live/reset").json()["ok"] is True
    assert client.get("/api/live/state").json()["routes"] == []


def test_spa_fallback_serves_index(tmp_path, results_dir):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>console</html>")
    (dist / "assets").mkdir()
    (dist / "assets" / "app.js").write_text("js")
    app = create_app(results_dir=results_dir, static_dir=dist, llm_factory=lambda: FakeLLM())
    with TestClient(app) as c:
        assert c.get("/inbox").text == "<html>console</html>"
        assert c.get("/assets/app.js").text == "js"
        assert c.get("/api/nope").status_code == 404


def test_health_reports_provider(client):
    body = client.get("/api/health").json()
    assert "provider" in body
