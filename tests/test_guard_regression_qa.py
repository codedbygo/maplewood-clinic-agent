"""Regression tests from /qa on 2026-10-22. Report: .gstack/qa-reports/qa-report-localhost-2026-10-22.md"""

from datetime import date

import pytest

from agent.safety import FALLBACK_REPLIES, post_guard
from agent.schema import FinalAnswer
from clinic_mcp.policy.dates import find_date_phrases

UNVERIFIED = {"status": "unverified", "patient_id": None, "candidate_patient_ids": []}
VERIFIED = {"status": "verified_patient", "patient_id": "P018", "candidate_patient_ids": ["P018"]}
NO_FLAG = {"tier": "none", "matches": [], "language": "en"}
PROVIDERS = ["Dr. Maya Patel", "Dr. James Okafor", "Sarah Kim, NP"]


def draft(text, language="en"):
    return {"name": "draft_reply", "input": {"text": text, "language": language}, "ok": True, "output": {"ok": True}}


def run(reply, verification=VERIFIED, actions=("acknowledge",), context=None):
    ctx = {"providers": PROVIDERS, "other_patient_names": [], **(context or {})}
    return post_guard(
        "Q1", FinalAnswer(intents=["schedule"], urgency="routine", actions=list(actions)), [draft(reply)], NO_FLAG, verification, ctx
    )


# Regression: ISSUE-004 — a third-party decline said "have Grace reach out for her schedule details",
# confirming that the person is a patient. Found by /qa on 2026-10-22.
def test_unverified_reply_naming_another_patient_becomes_a_neutral_decline():
    out = run(
        "I can't share appointment information for Grace Park. Please have Grace reach out for her schedule.",
        verification=UNVERIFIED,
        actions=["decline_disclosure"],
        context={"other_patient_names": ["Grace Park", "Grace"]},
    )
    assert out.result.reply_draft == FALLBACK_REPLIES["decline"]["en"]
    assert "Grace" not in out.result.reply_draft
    assert "decline_disclosure" in out.result.actions
    assert any("names another patient" in v for v in out.violations)


def test_name_check_is_word_bounded_and_skips_verified_senders():
    assert run("Thanks, we will be in touch.", verification=UNVERIFIED, context={"other_patient_names": ["Ann"]}).violations == []
    assert run("Your appointment with Grace Park is noted.", context={"other_patient_names": ["Grace Park"]}).violations == []


# Regression: ISSUE-005 — the reply called "Sarah Kim, NP" "Dr. Kim". Found by /qa on 2026-10-22.
@pytest.mark.parametrize("wrong", ["Dr. Kim", "Dr Kim", "Dr. Sarah Kim", "Dra. Kim"])
def test_non_doctor_provider_never_gets_a_doctor_title(wrong):
    out = run(f"You can see {wrong} at 9:00.")
    assert "Sarah Kim, NP" in out.result.reply_draft
    assert "Dr" not in out.result.reply_draft.replace("Dr. Maya", "")


def test_real_doctor_titles_are_left_alone():
    assert run("Dr. Patel and Dr. Okafor are available.").result.reply_draft == "Dr. Patel and Dr. Okafor are available."


# Regression: ISSUE-006 — Markdown (**bold**, headings) reached an SMS reply. Found by /qa on 2026-10-22.
def test_reply_is_plain_text():
    out = run("**See another provider:**\n## Options\n- Dr. Patel at __9:00__")
    assert out.result.reply_draft == "See another provider:\nOptions\n- Dr. Patel at 9:00"


# Regression: ISSUE-002 — the reply invented a 24-hour cancellation policy. Found by /qa on 2026-10-22.
@pytest.mark.parametrize(
    "claim",
    [
        "Please cancel at least 24 hours in advance.",
        "avísanos con al menos 24 horas de antelación",
        "There is a $25 late fee.",
        "We need 48 hours notice.",
    ],
)
def test_unsupported_policy_claims_are_flagged(claim):
    assert any("unsupported policy" in v for v in run(f"Booked for Tuesday. {claim}").violations)


# Regression: ISSUE-003 — the model did date arithmetic for "el martes" instead of calling resolve_date.
# The runner now finds date phrases and resolves them with the clinic calendar first. Found by /qa on 2026-10-22.
@pytest.mark.parametrize(
    "text,phrases",
    [
        ("Hola, ¿puedo ver a la doctora Patel el martes por la mañana?", ["el martes"]),
        ("Can I book a follow-up with Dr. Patel next week, ideally Tuesday morning?", ["next week", "Tuesday"]),
        ("Are you open the day after Thanksgiving?", ["the day after Thanksgiving"]),
        ("move my physical from Monday the 16th to any morning the following week", ["Monday the 16th", "the following week"]),
        ("cancel my appointment tomorrow", ["tomorrow"]),
        ("Booking a follow-up with Dr. Okafor on Wednesday the 18th please.", ["Wednesday the 18th"]),
        ("Necesito más metformina por favor.", []),
    ],
)
def test_find_date_phrases(text, phrases):
    assert find_date_phrases(text) == phrases


def test_found_phrases_resolve_with_the_calendar():
    from clinic_mcp.policy.dates import resolve_date

    for p in find_date_phrases("el martes por la mañana, or next week, or the day after Thanksgiving"):
        assert resolve_date(p, date(2026, 11, 9), ["2026-11-26", "2026-11-27"])["ok"], p
