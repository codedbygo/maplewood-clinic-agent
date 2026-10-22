"""Remaining edges: calendar corner cases, must_not evidence paths, and the eval entry points."""

import asyncio
import json
from datetime import date

import pytest

import agent.cli as cli
import eval.harness as harness
import eval.stability as stability
from clinic_mcp.policy.dates import resolve_date
from eval.must_not import check_must_not, global_safety_checks
from tests.test_cli_and_harness import LABELS, MESSAGES, ScriptedLLM

HOL = ["2026-11-26", "2026-11-27", "2026-12-25"]


@pytest.mark.parametrize(
    "today,expr,start",
    [
        (date(2026, 11, 9), "the 5th", "2026-12-05"),  # already passed this month -> next month
        (date(2026, 12, 20), "the 5th", "2027-01-05"),  # ... across the year boundary
        (date(2026, 11, 9), "Jan 5", "2027-01-05"),  # month-day already passed this year
        (date(2026, 11, 9), "day after tomorrow", "2026-11-11"),
        (date(2026, 11, 14), "this week", "2026-11-16"),  # at the weekend, "this week" is the coming week
    ],
)
def test_calendar_corners(today, expr, start):
    assert resolve_date(expr, today, HOL)["start"] == start


def test_impossible_day_and_notes():
    assert "no day 31" in resolve_date("the 31st", date(2026, 11, 9), HOL)["reason"]
    assert "closed at weekends" in resolve_date("Saturday", date(2026, 11, 9), HOL)["reason"]
    assert "in the past" in resolve_date("2026-11-02", date(2026, 11, 9), HOL)["reason"]


STATE = {"appointments": [], "refill_requests": []}
UNVERIFIED_LOG = {"verification": {"status": "unverified", "candidate_patient_ids": []}, "trace": []}
LABEL = {"patient_id": "P013", "accepted_urgency": ["routine"], "expected_actions": []}


def res(**kw):
    base = {
        "id": "Q",
        "patient_id": None,
        "intents": [],
        "urgency": "routine",
        "actions": [],
        "routed_to": [],
        "tool_calls": [],
        "reply_draft": "ok",
    }
    return {**base, **kw}


def test_disclose_phi_paths():
    assert check_must_not("disclose_phi", res(reply_draft="She has an appointment this week."), UNVERIFIED_LOG, STATE, LABEL)
    used = {**UNVERIFIED_LOG, "trace": [{"name": "list_medications", "ok": True}]}
    assert "PHI tools" in check_must_not("disclose_phi", res(), used, STATE, LABEL)
    verified = {"verification": {"status": "verified_patient"}, "trace": []}
    assert check_must_not("disclose_phi", res(reply_draft="She has an appointment."), verified, STATE, LABEL) is None


def test_bulk_with_one_request_falls_through_to_the_approval_check():
    state = {"appointments": [], "refill_requests": [{"message_id": "Q", "status": "approved"}]}
    assert "not pending" in check_must_not("bulk_approve", res(), {}, state, LABEL)


def test_global_checks_report_every_kind():
    state = {"refill_requests": [{"message_id": "Q", "status": "approved"}], "appointments": []}
    found = global_safety_checks(
        [res(actions=["escalate_emergency"], reply_draft="Take ibuprofen and rest; she has an appointment.")], {"Q": UNVERIFIED_LOG}, state
    )
    assert {f["check"] for f in found} == {"approve_refill", "emergency_template", "clinical_advice_keyword", "phi_to_unverified"}


def test_harness_main_writes_the_report(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "LLM", lambda model=None: ScriptedLLM())
    (tmp_path / "m.json").write_text(json.dumps(MESSAGES))
    (tmp_path / "l.json").write_text(json.dumps(LABELS))
    out = asyncio.run(cli.run_file(tmp_path / "m.json", tmp_path / "r.json", quiet=True))
    monkeypatch.setattr(
        "sys.argv",
        [
            "harness",
            "--results",
            str(tmp_path / "r.json"),
            "--labels",
            str(tmp_path / "l.json"),
            "--run-dir",
            str(out["run_dir"]),
            "--out",
            str(tmp_path / "rep"),
        ],
    )
    harness.main()
    assert "Emergency recall" in capsys.readouterr().out and (tmp_path / "rep.md").exists()


def test_stability_main_parses_arguments(monkeypatch):
    seen = {}

    async def fake(n, messages, model):
        seen.update(n=n, messages=str(messages), model=model)

    monkeypatch.setattr(stability, "main_async", fake)
    monkeypatch.setattr("sys.argv", ["stability", "--runs", "2", "--model", "m"])
    stability.main()
    assert seen == {"n": 2, "messages": "data/messages_sample.json", "model": "m"}
