"""Booking rules from clinic.json, enforced inside every write so the agent cannot break them."""

from __future__ import annotations

from datetime import date, datetime, timedelta

GRID_MINUTES = (0, 20, 40)
PARTS_OF_DAY = ("morning", "afternoon")


def _min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _provider(clinic: dict, provider_id: str) -> dict | None:
    return next((p for p in clinic["providers"] if p["id"] == provider_id), None)


def _on_leave(provider: dict, day: date) -> bool:
    return any(date.fromisoformat(a) <= day <= date.fromisoformat(b) for a, b in provider.get("leave", []))


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


DAY_CODES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def validate_slot(
    clinic: dict,
    appointments: list[dict],
    provider: str,
    visit_type: str,
    day: str,
    start: str,
    patient_id: str | None = None,
    ignore_appointment_id: str | None = None,
    now: datetime | None = None,
) -> dict:
    v: list[str] = []
    notes: list[str] = []
    prov = _provider(clinic, provider)
    duration = clinic["visit_types"].get(visit_type)
    if prov is None:
        v.append("unknown_provider")
        notes.append(f"No provider '{provider}' (known: {', '.join(p['id'] for p in clinic['providers'])}).")
    if duration is None:
        v.append("unknown_visit_type")
        notes.append(f"No visit type '{visit_type}' (known: {', '.join(clinic['visit_types'])}).")
        duration = 20
    try:
        d = date.fromisoformat(day)
        s = _min(start)
    except ValueError:
        return {"ok": False, "violations": ["bad_input"], "reason": f"Could not parse date '{day}' / time '{start}'."}
    if d.isoformat() != day or _hhmm(s) != start:
        # Every later check compares strings, so only the canonical forms may pass (no "20261126", no "9:00").
        return {"ok": False, "violations": ["bad_input"], "reason": "Use date YYYY-MM-DD and time HH:MM."}
    e = s + duration
    hours = clinic["hours"]

    if DAY_CODES[d.weekday()] not in hours["days"]:
        v.append("closed_day")
        notes.append(f"{day} is a {DAY_CODES[d.weekday()]}; the clinic is open {'-'.join([hours['days'][0], hours['days'][-1]])}.")
    if day in clinic["holidays"]:
        v.append("holiday")
        notes.append(f"{day} is a clinic holiday.")
    if prov and _on_leave(prov, d):
        v.append("provider_leave")
        notes.append(f"{prov['name']} is on leave on {day}.")
    if s % 60 not in GRID_MINUTES:
        v.append("off_grid")
        notes.append("Appointments start on the hour or at :20 / :40.")
    if s < _min(hours["open"]) or e > _min(hours["close"]):
        v.append("outside_hours")
        notes.append(f"A {duration}-minute visit at {start} ends {_hhmm(e)}; hours are {hours['open']}-{hours['close']}.")
    l0, l1 = map(_min, hours["lunch"])
    if _overlaps(s, e, l0, l1):
        v.append("lunch")
        notes.append(f"A {duration}-minute visit at {start} runs into lunch ({hours['lunch'][0]}-{hours['lunch'][1]}).")
    if now is not None and (d < now.date() or (d == now.date() and s < now.hour * 60 + now.minute)):
        v.append("in_past")
        notes.append(f"{day} {start} has already passed.")

    for a in appointments:
        if a.get("status") != "booked" or a["id"] == ignore_appointment_id or a["date"] != day:
            continue
        if not _overlaps(s, e, _min(a["start"]), _min(a["end"])):
            continue
        if a["provider"] == provider and "provider_overlap" not in v:
            v.append("provider_overlap")
            notes.append(f"{provider} is already booked {a['start']}-{a['end']} on {day}.")
        if patient_id and a["patient_id"] == patient_id and a["provider"] != provider and "patient_overlap" not in v:
            v.append("patient_overlap")
            notes.append(f"The patient already has an appointment {a['start']}-{a['end']} on {day}.")

    ok = not v
    reason = f"{provider} {visit_type} {day} {start}-{_hhmm(e)} is available." if ok else " ".join(notes)
    return {"ok": ok, "violations": v, "reason": reason}


def find_slots(
    clinic: dict,
    appointments: list[dict],
    visit_type: str,
    date_from: str,
    date_to: str,
    provider: str | None = None,
    part_of_day: str | None = None,
    patient_id: str | None = None,
    now: datetime | None = None,
    limit: int = 12,
) -> list[dict]:
    providers = [provider] if provider else [p["id"] for p in clinic["providers"]]
    duration = clinic["visit_types"].get(visit_type, 20)
    open_, close = _min(clinic["hours"]["open"]), _min(clinic["hours"]["close"])
    lunch_start, lunch_end = map(_min, clinic["hours"]["lunch"])
    out: list[dict] = []
    d, end = date.fromisoformat(date_from), date.fromisoformat(date_to)
    while d <= end and len(out) < limit:
        for s in range(open_, close, 20):
            e = s + duration
            if part_of_day == "morning" and e > lunch_start:
                continue
            if part_of_day == "afternoon" and s < lunch_end:
                continue
            for prov in providers:
                r = validate_slot(clinic, appointments, prov, visit_type, d.isoformat(), _hhmm(s), patient_id=patient_id, now=now)
                if r["ok"]:
                    out.append({"provider": prov, "date": d.isoformat(), "start": _hhmm(s), "end": _hhmm(e), "visit_type": visit_type})
                    if len(out) >= limit:
                        return out
        d += timedelta(days=1)
    return out


def _next_id(appointments: list[dict]) -> str:
    n = max((int(a["id"][1:]) for a in appointments if a["id"][1:].isdigit()), default=0)
    return f"A{n + 1:03d}"


def book(store, patient_id: str, provider: str, visit_type: str, day: str, start: str) -> dict:
    check = validate_slot(store.clinic, store.appointments, provider, visit_type, day, start, patient_id=patient_id, now=store.now)
    if not check["ok"]:
        return {"ok": False, "violations": check["violations"], "reason": "Not booked. " + check["reason"]}
    end = _hhmm(_min(start) + store.clinic["visit_types"][visit_type])
    appt = {
        "id": _next_id(store.appointments),
        "patient_id": patient_id,
        "provider": provider,
        "date": day,
        "start": start,
        "end": end,
        "visit_type": visit_type,
        "status": "booked",
    }
    store.appointments.append(appt)
    return {
        "ok": True,
        "violations": [],
        "appointment": appt,
        "reason": f"Booked {appt['id']}: {provider} {visit_type} {day} {start}-{end}.",
    }


def _find(store, appointment_id: str) -> dict | None:
    return next((a for a in store.appointments if a["id"] == appointment_id), None)


def reschedule(store, appointment_id: str, day: str, start: str, provider: str | None = None) -> dict:
    appt = _find(store, appointment_id)
    if appt is None or appt["status"] != "booked":
        return {"ok": False, "violations": ["not_found"], "reason": f"No active appointment {appointment_id}."}
    provider = provider or appt["provider"]
    check = validate_slot(
        store.clinic,
        store.appointments,
        provider,
        appt["visit_type"],
        day,
        start,
        patient_id=appt["patient_id"],
        ignore_appointment_id=appointment_id,
        now=store.now,
    )
    if not check["ok"]:
        return {"ok": False, "violations": check["violations"], "reason": "Not moved. " + check["reason"]}
    old = f"{appt['provider']} {appt['date']} {appt['start']}"
    appt.update(provider=provider, date=day, start=start, end=_hhmm(_min(start) + store.clinic["visit_types"][appt["visit_type"]]))
    return {
        "ok": True,
        "violations": [],
        "appointment": dict(appt),
        "reason": f"Moved {appointment_id} from {old} to {provider} {day} {start}-{appt['end']}.",
    }


def cancel(store, appointment_id: str) -> dict:
    appt = _find(store, appointment_id)
    if appt is None or appt["status"] != "booked":
        return {"ok": False, "violations": ["not_found"], "reason": f"No active appointment {appointment_id}."}
    appt["status"] = "cancelled"
    return {
        "ok": True,
        "violations": [],
        "appointment": dict(appt),
        "reason": f"Cancelled {appointment_id} ({appt['provider']} {appt['date']} {appt['start']}).",
    }


def match_appointments(
    appointments: list[dict],
    patient_id: str,
    date: str | None = None,
    provider: str | None = None,
    weekday: int | None = None,
    visit_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    from datetime import date as _date

    out = []
    for a in appointments:
        if a["patient_id"] != patient_id or a.get("status") != "booked":
            continue
        if date and a["date"] != date:
            continue
        if date_from and a["date"] < date_from:
            continue
        if date_to and a["date"] > date_to:
            continue
        if provider and a["provider"] != provider:
            continue
        if visit_type and a["visit_type"] != visit_type:
            continue
        if weekday is not None and _date.fromisoformat(a["date"]).weekday() != weekday:
            continue
        out.append(a)
    return sorted(out, key=lambda a: (a["date"], a["start"]))
