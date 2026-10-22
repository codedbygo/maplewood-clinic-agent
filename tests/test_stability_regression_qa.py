"""Regression tests from /qa on 2026-10-22. Report: .gstack/qa-reports/qa-report-localhost-2026-10-22.md"""

from eval.stability import build_report


def _res(mid, actions):
    return {
        "id": mid,
        "patient_id": None,
        "intents": [],
        "urgency": "routine",
        "actions": actions,
        "routed_to": [],
        "tool_calls": [],
        "reply_draft": "",
    }


# Regression: ISSUE-010 — the Evaluation page showed a stability result from a run made without any LLM
# next to the free model's results; the report did not say which model or runs it measured.
# Found by /qa on 2026-10-22
def test_stability_report_records_model_and_runs():
    metas = [
        {"run_id": "R1", "model": "m:free", "provider": "openrouter", "stopped": None},
        {"run_id": "R2", "model": "m:free", "provider": "openrouter", "stopped": None},
    ]
    rep = build_report([[_res("A", ["acknowledge"])], [_res("A", ["acknowledge"])]], metas)
    assert rep["model"] == "m:free" and rep["provider"] == "openrouter"
    assert rep["run_ids"] == ["R1", "R2"]
    assert rep["changed"] == 0 and rep["complete"] is True


def test_stability_report_marks_incomplete_runs():
    metas = [{"run_id": "R1", "model": "m", "provider": "p", "stopped": {"at": "M020"}}]
    assert build_report([[_res("A", [])]], metas)["complete"] is False
