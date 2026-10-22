"""Runner paths the main runner tests do not reach."""

import asyncio
from types import SimpleNamespace

from agent.runner import _other_patient_names, _phi_terms, open_clinic, process_message
from tests.test_runner_offline import FakeLLM, msg, tool_use, triage


async def _with_clinic(fn):
    async with open_clinic() as clinic:
        await clinic.reset()
        return await fn(clinic)


def test_phi_terms_cover_dates_times_and_meds_but_not_words_the_sender_used():
    state = {
        "appointments": [
            {"patient_id": "P013", "status": "booked", "date": "2026-11-11", "start": "13:00"},
            {"patient_id": "P013", "status": "cancelled", "date": "2026-11-12", "start": "09:00"},
        ]
    }
    terms = _phi_terms(state, ["P013"], "Is she in on Nov 11?")
    assert {"2026-11-11", "13:00", "1:00 pm", "1 pm", "November 11"} <= set(terms)
    assert "Nov 11" not in terms and "2026-11-12" not in terms
    assert "metformin" in _phi_terms({"appointments": []}, ["P013"], "hello")


def test_other_patient_names_excludes_the_sender_and_adds_first_names_mentioned():
    names = _other_patient_names({"from_name": "Mike", "body": "Is my wife Grace Park in?"})
    assert "Grace Park" in names and "Grace" in names and "Robert Chen" in names
    assert "Robert Chen" not in _other_patient_names({"from_name": "Robert Chen", "body": "hi"})


def test_following_week_is_anchored_on_the_previous_date_phrase():
    def script(step, token):
        return [[tool_use("submit_result", intents=["reschedule"], urgency="routine", actions=[])]][step]

    async def go(clinic):
        return await process_message(
            msg("move it from Monday the 16th to the following week", name="Fatima Hassan", contact="fatima.hassan@example.com"),
            clinic,
            FakeLLM(script=script),
        )

    _, log = asyncio.run(_with_clinic(go))
    resolved = [c for c in log["trace"] if c["name"] == "resolve_date"]
    assert resolved[1]["input"] == {"expression": "the following week", "anchor_date": "2026-11-16"}
    assert resolved[1]["output"]["start"] == "2026-11-23"


def test_model_that_never_submits_is_nudged_then_falls_back():
    llm = FakeLLM(script=lambda step, token: [SimpleNamespace(type="text", text="thinking")])

    async def go(clinic):
        return await process_message(msg("hello there"), clinic, llm)

    result, log = asyncio.run(_with_clinic(go))
    assert llm.steps == 2 and log["path"] == "fallback" and "without submit_result" in log["error"]
    assert result.reply_draft


def test_invalid_submission_falls_back():
    async def go(clinic):
        return await process_message(msg("hello"), clinic, FakeLLM(script=lambda s, t: [tool_use("submit_result", urgency="routine")]))

    _, log = asyncio.run(_with_clinic(go))
    assert log["path"] == "fallback" and "invalid submit_result" in log["error"]


def test_bad_tool_arguments_come_back_as_an_error_the_model_can_fix():
    seen = []

    class Watch(FakeLLM):
        async def step(self, system, messages, tools):
            if len(messages) > 1:
                seen.append(messages[-1]["content"][0])
            return await super().step(system, messages, tools)

    def script(step, token):
        return [
            [tool_use("resolve_date", wrong_arg="x")],
            [tool_use("submit_result", intents=["admin"], urgency="routine", actions=["acknowledge"])],
        ][step]

    asyncio.run(_with_clinic(lambda c: process_message(msg("hi"), c, Watch(script=script))))
    assert seen[0]["is_error"] is True


def test_fallback_with_clinical_concern_routes_to_a_clinician():
    llm = FakeLLM(
        triage_result=triage(clinical_concern=True, urgency="urgent"), script=lambda step, token: [SimpleNamespace(type="text", text="...")]
    )

    result, _ = asyncio.run(_with_clinic(lambda c: process_message(msg("my rash is spreading"), c, llm)))
    assert "clinician_urgent" in result.routed_to


def test_unverified_sender_with_candidates_gets_phi_checked():
    def script(step, token):
        return [
            [tool_use("draft_reply", text="Robert has an appointment on 2026-11-12 at 15:20.", language="en")],
            [tool_use("submit_result", intents=["records"], urgency="routine", actions=["answer_directly"])],
        ][step]

    async def go(clinic):
        return await process_message(msg("when is my appointment", contact="rchen.new@example.org"), clinic, FakeLLM(script=script))

    result, log = asyncio.run(_with_clinic(go))
    assert result.patient_id is None and "2026-11-12" not in result.reply_draft
    assert any("PHI" in v for v in log["guard_violations"])
