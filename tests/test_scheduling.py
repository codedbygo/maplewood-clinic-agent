from datetime import datetime

import pytest

from clinic_mcp.policy.scheduling import book, cancel, find_slots, match_appointments, reschedule, validate_slot
from clinic_mcp.store import load_store


@pytest.fixture
def store():
    return load_store()


def violations(store, provider, visit_type, day, start, appts=None, **kw):
    appts = store.appointments if appts is None else appts
    return validate_slot(store.clinic, appts, provider, visit_type, day, start, **kw)["violations"]


def test_valid_slot_on_empty_schedule(store):
    assert violations(store, "PATEL", "follow_up", "2026-11-17", "11:40", appts=[]) == []


def test_forty_minute_visit_running_into_lunch_is_refused(store):
    assert "lunch" in violations(store, "PATEL", "annual_physical", "2026-11-17", "11:40", appts=[])


def test_start_during_lunch_is_refused(store):
    assert "lunch" in violations(store, "PATEL", "follow_up", "2026-11-17", "12:20", appts=[])


def test_holiday_is_refused(store):
    assert "holiday" in violations(store, "KIM", "follow_up", "2026-11-26", "10:00", appts=[])


def test_provider_leave_is_refused(store):
    assert "provider_leave" in violations(store, "OKAFOR", "follow_up", "2026-11-18", "10:00", appts=[])


def test_off_grid_start_is_refused(store):
    assert "off_grid" in violations(store, "KIM", "follow_up", "2026-11-17", "10:10", appts=[])


def test_visit_ending_after_close_is_refused(store):
    assert "outside_hours" in violations(store, "KIM", "annual_physical", "2026-11-17", "16:40", appts=[])


def test_start_before_opening_is_refused(store):
    assert "outside_hours" in violations(store, "KIM", "follow_up", "2026-11-17", "08:40", appts=[])


def test_weekend_is_refused(store):
    assert "closed_day" in violations(store, "KIM", "follow_up", "2026-11-14", "10:00", appts=[])


def test_overlap_with_existing_booking_is_refused(store):
    # A059: OKAFOR 2026-11-12 14:00-14:20
    assert "provider_overlap" in violations(store, "OKAFOR", "follow_up", "2026-11-12", "14:00")


def test_forty_minute_visit_overlapping_next_booking_is_refused(store):
    assert "provider_overlap" in violations(store, "OKAFOR", "annual_physical", "2026-11-12", "13:40")


def test_adjacent_slot_is_allowed(store):
    appts = [a for a in store.appointments if a["id"] == "A059"]
    assert violations(store, "OKAFOR", "follow_up", "2026-11-12", "13:40", appts=appts) == []


def test_patient_cannot_be_in_two_places(store):
    appts = [{"id": "X", "patient_id": "P001", "provider": "KIM", "date": "2026-11-17", "start": "10:00", "end": "10:20", "visit_type": "follow_up", "status": "booked"}]
    assert "patient_overlap" in violations(store, "PATEL", "follow_up", "2026-11-17", "10:00", appts=appts, patient_id="P001")


def test_cancelled_bookings_do_not_block(store):
    appts = [{"id": "X", "patient_id": "P001", "provider": "KIM", "date": "2026-11-17", "start": "10:00", "end": "10:20", "visit_type": "follow_up", "status": "cancelled"}]
    assert violations(store, "KIM", "follow_up", "2026-11-17", "10:00", appts=appts) == []


def test_time_already_passed_today_is_refused(store):
    now = datetime.fromisoformat("2026-11-09T10:44:00-06:00")
    assert "in_past" in violations(store, "KIM", "sick_visit", "2026-11-09", "09:00", appts=[], now=now)
    assert "in_past" in violations(store, "KIM", "sick_visit", "2026-11-06", "11:00", appts=[], now=now)
    assert violations(store, "KIM", "sick_visit", "2026-11-09", "11:00", appts=[], now=now) == []


def test_unknown_provider_and_visit_type(store):
    assert "unknown_provider" in violations(store, "HOUSE", "follow_up", "2026-11-17", "10:00", appts=[])
    assert "unknown_visit_type" in violations(store, "KIM", "massage", "2026-11-17", "10:00", appts=[])


def test_find_slots_only_returns_valid_slots(store):
    slots = find_slots(store.clinic, store.appointments, "annual_physical", "2026-11-09", "2026-11-13", provider="KIM")
    assert slots
    for s in slots:
        assert violations(store, s["provider"], "annual_physical", s["date"], s["start"]) == []
        assert s["start"] not in ("11:40", "12:00", "12:20", "12:40", "16:40")


def test_find_slots_part_of_day(store):
    pm = find_slots(store.clinic, store.appointments, "follow_up", "2026-11-13", "2026-11-13", provider="KIM", part_of_day="afternoon")
    am = find_slots(store.clinic, store.appointments, "follow_up", "2026-11-13", "2026-11-13", provider="KIM", part_of_day="morning")
    assert pm and all(s["start"] >= "13:00" for s in pm)
    assert am and all(s["end"] <= "12:00" for s in am)


def test_find_slots_skips_leave_and_holidays(store):
    slots = find_slots(store.clinic, store.appointments, "follow_up", "2026-11-16", "2026-11-27", provider="OKAFOR", limit=500)
    dates = {s["date"] for s in slots}
    assert dates == {"2026-11-23", "2026-11-24", "2026-11-25"}


def test_find_slots_without_provider_spans_providers(store):
    slots = find_slots(store.clinic, store.appointments, "sick_visit", "2026-11-10", "2026-11-10", limit=500)
    assert {s["provider"] for s in slots} == {"PATEL", "OKAFOR", "KIM"}


def test_book_then_double_book_is_refused(store):
    slot = find_slots(store.clinic, store.appointments, "follow_up", "2026-11-17", "2026-11-17", provider="KIM")[0]
    first = book(store, "P001", "KIM", "follow_up", slot["date"], slot["start"])
    assert first["ok"] and first["appointment"]["id"] == "A171"
    again = book(store, "P002", "KIM", "follow_up", slot["date"], slot["start"])
    assert not again["ok"]
    assert "provider_overlap" in again["violations"]


def test_book_on_leave_is_refused_and_store_unchanged(store):
    n = len(store.appointments)
    r = book(store, "P025", "OKAFOR", "follow_up", "2026-11-18", "10:00")
    assert not r["ok"] and "provider_leave" in r["violations"]
    assert len(store.appointments) == n


def test_reschedule_ignores_own_slot(store):
    r = reschedule(store, "A073", "2026-11-16", "09:00")
    assert r["ok"], r["reason"]


def test_reschedule_moves_and_keeps_visit_type(store):
    slot = find_slots(store.clinic, store.appointments, "annual_physical", "2026-11-24", "2026-11-24", provider="PATEL", patient_id="P015")[0]
    r = reschedule(store, "A073", slot["date"], slot["start"])
    assert r["ok"], r["reason"]
    appt = next(a for a in store.appointments if a["id"] == "A073")
    assert (appt["date"], appt["start"], appt["end"], appt["visit_type"]) == ("2026-11-24", slot["start"], slot["end"], "annual_physical")


def test_reschedule_into_holiday_is_refused(store):
    r = reschedule(store, "A073", "2026-11-26", "10:00")
    assert not r["ok"] and "holiday" in r["violations"]
    appt = next(a for a in store.appointments if a["id"] == "A073")
    assert appt["date"] == "2026-11-16"


def test_cancel_unknown_is_refused(store):
    assert not cancel(store, "A999")["ok"]


def test_cancel_marks_cancelled_and_frees_slot(store):
    assert cancel(store, "A059")["ok"]
    assert violations(store, "OKAFOR", "follow_up", "2026-11-12", "14:00") == []
    assert not cancel(store, "A059")["ok"]  # already cancelled


def test_match_appointments_filters(store):
    assert len(match_appointments(store.appointments, "P011", date="2026-11-10")) == 2
    assert [a["id"] for a in match_appointments(store.appointments, "P007", weekday=2)] == ["A035"]
    assert [a["id"] for a in match_appointments(store.appointments, "P015", date="2026-11-16", visit_type="annual_physical")] == ["A073"]
