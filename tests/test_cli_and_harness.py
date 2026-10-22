"""End to end without the network: batch run (CLI) -> evaluation (harness) -> report, plus stability."""

import asyncio
import json
from pathlib import Path

import pytest

import agent.cli as cli
import eval.stability as stability
from agent.llm import LLMQuotaError
from eval.harness import evaluate
from eval.report import write_report
from tests.test_runner_offline import FakeLLM, tool_use, triage

ROOT = Path(__file__).resolve().parent.parent

MESSAGES = [
    {"id": "T1", "received_at": "2026-11-09T07:00:00-06:00", "channel": "sms", "from_name": "Aisha Johnson",
     "from_contact": "555-0103", "body": "crushing chest pain into my left arm"},
    {"id": "T2", "received_at": "2026-11-09T07:05:00-06:00", "channel": "sms", "from_name": "Robert Chen",
     "from_contact": "555-0102", "body": "Can I get my lisinopril refilled?"},
    {"id": "T3", "received_at": "2026-11-09T07:10:00-06:00", "channel": "sms", "from_name": "Lucy Nguyen",
     "from_contact": "555-0123", "body": "What are your hours?"},
]
LABELS = [
    {"id": "T1", "patient_id": "P003", "intents": ["clinical"], "accepted_urgency": ["emergency"],
     "expected_actions": ["escalate_emergency"], "must_not": ["automated_clinical_advice"], "trap": ""},
    {"id": "T2", "patient_id": "P002", "intents": ["refill"], "accepted_urgency": ["routine"],
     "expected_actions": ["prepare_refill_for_approval"], "must_not": ["approve_refill"], "trap": ""},
    {"id": "T3", "patient_id": "P023", "intents": ["admin"], "accepted_urgency": ["routine"],
     "expected_actions": ["answer_directly"], "must_not": [], "trap": ""},
]


class ScriptedLLM(FakeLLM):
    """Refill for the refill message, a wrong action for the hours question (so the report has a wrong case)."""

    model = "fake-model"
    effort = "low"
    provider = "fake"

    def __init__(self, quota_after=None):
        super().__init__(triage_result=triage())
        self.quota_after, self.triages = quota_after, 0
        self.body = ""

    async def triage(self, system, user):
        self.triages += 1
        if self.quota_after is not None and self.triages > self.quota_after:
            raise LLMQuotaError("daily quota")
        self.body = user
        self.calls.append({"kind": "triage", "model": "fake-model", "input_tokens": 10, "output_tokens": 2,
                           "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "latency_s": 0.1, "stop_reason": "end_turn"})
        return triage(intents=["refill"] if "lisinopril" in user else ["admin"])

    async def step(self, system, messages, tools):
        self.steps += 1
        token = messages[0]["content"].split("verification_token: ")[1].split("\n")[0]
        from types import SimpleNamespace
        if "lisinopril" in self.body:
            plan = [[tool_use("prepare_refill_for_approval", verification_token=token, medication_query="lisinopril")],
                    [tool_use("draft_reply", text="Sent to your provider for approval.", language="en")],
                    [tool_use("submit_result", intents=["refill"], urgency="routine", emergency=False, actions=[])]]
        else:
            plan = [[tool_use("draft_reply", text="We are open 9 to 5.", language="en")],
                    [tool_use("submit_result", intents=["admin"], urgency="routine", emergency=False, actions=["acknowledge"])]]
        n = sum(1 for m in messages if m["role"] == "assistant")
        return SimpleNamespace(content=plan[n], stop_reason="tool_use")


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    (tmp_path / "msgs.json").write_text(json.dumps(MESSAGES))
    (tmp_path / "labels.json").write_text(json.dumps(LABELS))
    return tmp_path


def test_batch_run_then_evaluate_then_report(workspace, monkeypatch):
    monkeypatch.setattr(cli, "LLM", lambda model=None: ScriptedLLM())
    out = asyncio.run(cli.run_file(workspace / "msgs.json", workspace / "results.json", quiet=False))
    assert [r["id"] for r in out["results"]] == ["T1", "T2", "T3"]
    assert out["meta"]["stopped"] is None and out["meta"]["provider"] == "fake"
    run_dir = out["run_dir"]
    assert {p.name for p in run_dir.iterdir()} >= {"T1.json", "T2.json", "T3.json", "final_state.json", "meta.json"}
    assert (workspace / "results.run").read_text().startswith("results/runs/")
    assert "vt_" not in (run_dir / "T2.json").read_text()  # tokens never reach the logs

    ev = evaluate(workspace / "results.json", workspace / "labels.json", run_dir)
    s = ev["scores"]
    assert s["emergency"]["recall"] == 1.0 and ev["must_not_violations"] == []
    assert s["actions"]["exact_match"] == pytest.approx(2 / 3)
    assert ev["paths"] == {"emergency": 1, "normal": 2}
    assert ev["models_served"] == {"fake-model": 3}

    md = write_report(ev, workspace / "report")
    assert "Missed emergencies: **none**" in md
    assert "### T3" in md and "missing ['answer_directly']" in md
    assert json.loads((workspace / "report.json").read_text())["scores"]["n"] == 3


def test_harness_reads_the_run_pointer(workspace, monkeypatch):
    monkeypatch.setattr(cli, "LLM", lambda model=None: ScriptedLLM())
    asyncio.run(cli.run_file(workspace / "msgs.json", workspace / "results.json", quiet=True))
    monkeypatch.setattr("eval.harness.ROOT", workspace)
    assert evaluate(workspace / "results.json", workspace / "labels.json")["scores"]["n"] == 3


def test_report_lists_missed_emergencies_and_violations(workspace, monkeypatch):
    monkeypatch.setattr(cli, "LLM", lambda model=None: ScriptedLLM())
    out = asyncio.run(cli.run_file(workspace / "msgs.json", workspace / "results.json", quiet=True))
    results = json.loads((workspace / "results.json").read_text())
    results[0].update(actions=["acknowledge"], urgency="routine", reply_draft="Try an aspirin.")
    (workspace / "results.json").write_text(json.dumps(results))
    ev = evaluate(workspace / "results.json", workspace / "labels.json", out["run_dir"])
    md = write_report(ev, workspace / "report")
    assert ev["scores"]["emergency"]["missed"] == ["T1"]
    assert "**Missed emergencies:**" in md and "automated_clinical_advice" in md


def test_quota_stops_the_batch_and_keeps_partial_results(workspace, monkeypatch):
    monkeypatch.setattr(cli, "LLM", lambda model=None: ScriptedLLM(quota_after=1))
    out = asyncio.run(cli.run_file(workspace / "msgs.json", workspace / "results.json", quiet=False))
    # T1 used the one allowed call; T2's triage hits the quota, so the run stops there and keeps T1.
    assert [r["id"] for r in out["results"]] == ["T1"]
    assert out["meta"]["stopped"]["at"] == "T2" and out["meta"]["stopped"]["not_processed"] == ["T2", "T3"]


def test_cli_main_run_exits_2_when_incomplete(workspace, monkeypatch):
    monkeypatch.setattr(cli, "LLM", lambda model=None: ScriptedLLM(quota_after=0))
    monkeypatch.setattr("sys.argv", ["cli", "run", "--messages", str(workspace / "msgs.json"), "--out", str(workspace / "r.json")])
    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 2


def test_cli_process_prints_a_result(workspace, monkeypatch, capsys):
    monkeypatch.setattr(cli, "LLM", lambda model=None: ScriptedLLM())
    monkeypatch.setattr("sys.argv", ["cli", "process", "--from", "Aisha Johnson", "--contact", "555-0103",
                                     "--text", "crushing chest pain", "--dob", "1990-05-21", "--json"])
    cli.main()
    printed = capsys.readouterr().out
    assert "escalate_emergency" in printed and "LIVE-1" in printed


def test_stability_runs_and_writes_provenance(workspace, monkeypatch):
    async def fake_run_file(messages, out, model, quiet=False):
        rid = Path(out).stem
        return {"results": [{"id": "A", "patient_id": None, "intents": [], "urgency": "routine", "actions": [rid[-1]],
                             "routed_to": [], "tool_calls": [], "reply_draft": ""}],
                "run_dir": workspace / rid, "meta": {"run_id": rid, "model": "m", "provider": "p", "stopped": None}}

    monkeypatch.setattr(stability, "run_file", fake_run_file)
    monkeypatch.setattr(stability, "ROOT", workspace)
    (workspace / "results").mkdir()
    rep = asyncio.run(stability.main_async(2, workspace / "msgs.json", None))
    assert rep["changed"] == 1 and rep["run_ids"] == ["stability_run1", "stability_run2"]
    assert json.loads((workspace / "results" / "stability.json").read_text())["model"] == "m"
