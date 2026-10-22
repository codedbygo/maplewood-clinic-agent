from datetime import date

from clinic_mcp.store import load_store


def test_today_comes_from_clinic_json():
    assert load_store().today == date(2026, 11, 9)


def test_reset_discards_mutations():
    store = load_store()
    store.appointments.append({"id": "AX"})
    store.refill_requests.append({"id": "R1"})
    store.reset()
    assert len(store.appointments) == 170
    assert store.refill_requests == []


def test_reset_does_not_share_state_with_source_data():
    store = load_store()
    store.appointments[0]["status"] = "cancelled"
    store.reset()
    assert store.appointments[0]["status"] == "booked"
