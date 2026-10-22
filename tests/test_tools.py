import pytest

from clinic_mcp.store import load_store
from clinic_mcp.tools import Tools


@pytest.fixture
def tools():
    return Tools(load_store())


def begin(tools, name, contact, received_at="2026-11-09T08:00:00-06:00", mid="MX"):
    tools.admin_begin_message(message_id=mid, from_name=name, from_contact=contact, channel="sms", received_at=received_at)


def token_for(tools, name, contact):
    begin(tools, name, contact)
    r = tools.verify_sender()
    assert r["verification_token"], r
    return r["verification_token"]


def test_every_tool_returns_reason(tools):
    begin(tools, "Robert Chen", "555-0102")
    for r in [
        tools.verify_sender(),
        tools.get_clinic_info(),
        tools.resolve_date("tomorrow"),
        tools.list_medications("bogus"),
        tools.find_available_slots("follow_up"),
    ]:
        assert r.get("reason")


def test_verify_uses_message_sender_not_llm_arguments(tools):
    begin(tools, "Mike", "555-0888")
    r = tools.verify_sender()
    assert r["status"] == "unverified" and r["verification_token"] is None


def test_verify_with_stated_dob_from_unknown_contact(tools):
    begin(tools, "Robert Chen", "rchen.new@example.org")
    assert tools.verify_sender(stated_dob="1971-11-20")["status"] == "unverified"
    assert tools.verify_sender(stated_dob="1971-11-02")["status"] == "verified_patient"


def test_phi_tools_refuse_without_valid_token(tools):
    for r in [
        tools.list_medications("bogus"),
        tools.get_patient_appointments("bogus"),
        tools.get_patient_summary("bogus"),
        tools.check_refill_eligibility("bogus", "lisinopril"),
    ]:
        assert r["ok"] is False
        assert "verif" in r["reason"].lower()


def test_token_from_previous_message_is_rejected(tools):
    tok = token_for(tools, "Robert Chen", "555-0102")
    begin(tools, "Mike", "555-0888", mid="MY")
    assert tools.list_medications(tok)["ok"] is False


def test_caregiver_token_reads_child_medications(tools):
    tok = token_for(tools, "Anna Rossi", "555-0109")
    meds = tools.list_medications(tok)
    assert [m["medication"] for m in meds["medications"]] == ["Cetirizine 5 mg"]


def test_patient_summary_is_minimal(tools):
    tok = token_for(tools, "Linda Morales", "555-0101")
    s = tools.get_patient_summary(tok)["patient"]
    assert s["preferred_language"] == "Spanish"
    assert "dob" not in s and "phone" not in s and "email" not in s


def test_prepare_refuses_when_not_eligible(tools):
    tok = token_for(tools, "Fatima Hassan", "fatima.hassan@example.com")
    r = tools.prepare_refill_for_approval(tok, "omeprazole")
    assert r["ok"] is False and r["decision"] == "too_early"
    assert tools.store.refill_requests == []


def test_prepare_writes_pending_request_and_routes_to_provider_refills(tools):
    tok = token_for(tools, "Robert Chen", "555-0102")
    r = tools.prepare_refill_for_approval(tok, "lisinopril")
    assert r["ok"] is True
    [req] = tools.store.refill_requests
    assert req["status"] == "pending_provider_approval"
    assert req["patient_id"] == "P002" and req["message_id"] == "MX"
    assert [x["queue"] for x in tools.store.routes] == ["provider_refills"]


def test_prepare_never_bulk_prepares_controlled(tools):
    tok = token_for(tools, "Marcus Bell", "555-0106")
    assert tools.prepare_refill_for_approval(tok, "all my medications")["ok"] is False
    assert tools.store.refill_requests == []


def test_cannot_touch_another_patients_appointment(tools):
    tok = token_for(tools, "Grace Park", "555-0113")
    r = tools.cancel_appointment(tok, appointment_id="A017")  # belongs to P011
    assert r["ok"] is False
    assert next(a for a in tools.store.appointments if a["id"] == "A017")["status"] == "booked"


def test_cancel_by_date_refuses_when_ambiguous(tools):
    tok = token_for(tools, "Hannah Lee", "555-0111")
    r = tools.cancel_appointment(tok, date="2026-11-10")
    assert r["ok"] is False and len(r["candidates"]) == 2


def test_cancel_by_date_and_provider_succeeds(tools):
    tok = token_for(tools, "Hannah Lee", "555-0111")
    r = tools.cancel_appointment(tok, date="2026-11-10", provider="KIM")
    assert r["ok"] is True and r["appointment"]["id"] == "A017"


def test_book_on_leave_refused(tools):
    tok = token_for(tools, "Nora Fitzgerald", "nora.fitzgerald@example.com")
    r = tools.book_appointment(tok, "OKAFOR", "follow_up", "2026-11-18", "10:00")
    assert r["ok"] is False and "provider_leave" in r["violations"]


def test_route_to_unknown_queue_refused(tools):
    begin(tools, "X", "1")
    assert tools.route_to_queue("pharmacy", "x", "routine")["ok"] is False
    assert tools.route_to_queue("billing", "x", "routine")["ok"] is True


def test_sick_visit_slots_default_to_today_and_next_business_day(tools):
    begin(tools, "X", "1", received_at="2026-11-09T08:26:00-06:00")
    r = tools.find_available_slots("sick_visit")
    assert r["slots"]
    assert {s["date"] for s in r["slots"]} <= {"2026-11-09", "2026-11-10"}


def test_slots_respect_message_time(tools):
    begin(tools, "X", "1", received_at="2026-11-09T10:44:00-06:00")
    r = tools.find_available_slots("sick_visit", date_from="2026-11-09", date_to="2026-11-09", limit=50)
    assert all(s["start"] >= "10:44" for s in r["slots"])


def test_draft_reply_records_text(tools):
    begin(tools, "X", "1")
    assert tools.draft_reply("Hello", "en")["ok"]
    assert tools.store.drafts[-1]["text"] == "Hello"


def test_appointments_for_unverified_caregiver_refused(tools):
    begin(tools, "Mike", "555-0888")
    tok = tools.verify_sender()["verification_token"]
    assert tok is None


def test_reschedule_records_message_id(tools):
    tok = token_for(tools, "Fatima Hassan", "fatima.hassan@example.com")
    slots = tools.find_available_slots(
        "annual_physical", "2026-11-23", "2026-11-25", provider="PATEL", part_of_day="morning", verification_token=tok
    )["slots"]
    r = tools.reschedule_appointment(tok, slots[0]["date"], slots[0]["start"], appointment_id="A073")
    assert r["ok"], r["reason"]
    assert next(a for a in tools.store.appointments if a["id"] == "A073")["message_id"] == "MX"


def test_cancel_records_message_id(tools):
    tok = token_for(tools, "Hannah Lee", "555-0111")
    assert tools.cancel_appointment(tok, appointment_id="A017")["ok"]
    assert next(a for a in tools.store.appointments if a["id"] == "A017")["message_id"] == "MX"
