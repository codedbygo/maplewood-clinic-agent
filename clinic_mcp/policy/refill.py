"""Refill eligibility per clinic.json refill_policy. Rules run in a fixed order; the first failure decides."""

from __future__ import annotations

import difflib
import re
import unicodedata
from datetime import date, timedelta
from typing import Any

# Brand (and common Spanish) names to the generic names used in medications.json.
ALIASES = {
    "xanax": "alprazolam",
    "ambien": "zolpidem",
    "adderall": "amphetamine",
    "glucophage": "metformin",
    "metformina": "metformin",
    "zoloft": "sertraline",
    "sertralina": "sertraline",
    "lexapro": "escitalopram",
    "escitalopram": "escitalopram",
    "synthroid": "levothyroxine",
    "levoxyl": "levothyroxine",
    "levotiroxina": "levothyroxine",
    "lipitor": "atorvastatin",
    "atorvastatina": "atorvastatin",
    "prilosec": "omeprazole",
    "omeprazol": "omeprazole",
    "norvasc": "amlodipine",
    "amlodipino": "amlodipine",
    "zestril": "lisinopril",
    "prinivil": "lisinopril",
    "zestoretic": "lisinopril",
    "coumadin": "warfarin",
    "jantoven": "warfarin",
    "warfarina": "warfarin",
    "lantus": "insulin",
    "basaglar": "insulin",
    "toujeo": "insulin",
    "insulina": "insulin",
    "aricept": "donepezil",
    "zyrtec": "cetirizine",
    "cetirizina": "cetirizine",
    "ventolin": "albuterol",
    "proair": "albuterol",
    "salbutamol": "albuterol",
    "oxycontin": "oxycodone",
    "roxicodone": "oxycodone",
    "percocet": "oxycodone",
    "oxicodona": "oxycodone",
    "alprazolam": "alprazolam",
    "zolpidem": "zolpidem",
}
STOPWORDS = {
    "all",
    "medications",
    "my",
    "the",
    "refill",
    "please",
    "mg",
    "mcg",
    "pills",
    "meds",
    "medication",
    "medicine",
    "of",
    "for",
    "a",
    "mi",
    "mis",
    "de",
    "la",
    "el",
}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in text if not unicodedata.combining(c))


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z]+", _norm(text)) if len(t) > 2 and t not in STOPWORDS]


def resolve_medication(query: str, meds: list[dict]) -> dict | None:
    """Match a free-text medication mention to one of the patient's active medications."""
    q = [ALIASES.get(t, t) for t in _tokens(query)]
    if not q:
        return None
    best, best_score = None, 0.0
    for med in meds:
        names = _tokens(med["medication"])
        for t in q:
            if t in names:
                return med
            close = difflib.get_close_matches(t, names, n=1, cutoff=0.8)
            if close:
                score = difflib.SequenceMatcher(None, t, close[0]).ratio()
                if score > best_score:
                    best, best_score = med, score
    return best


def _months_ago(today: date, months: int) -> date:
    y, m = divmod(today.month - 1 - months, 12)
    year, month = today.year + y, m + 1
    day = min(today.day, 28 if month == 2 else 30 if month in (4, 6, 9, 11) else 31)
    return date(year, month, day)


def check_refill_eligibility(patient: dict, meds: list[dict], query: str, today: date) -> dict:
    med = resolve_medication(query, meds)
    out: dict[str, Any] = {
        "decision": None,
        "eligible": False,
        "medication": med["medication"] if med else None,
        "prescriber": med["prescriber"] if med else None,
        "run_out_date": None,
        "earliest_date": None,
        "reasons": [],
        "reason": "",
    }
    if med is None:
        on_list = ", ".join(m["medication"] for m in meds) or "none"
        out["decision"] = "not_on_list"
        out["reasons"].append({"rule": "on_active_list", "passed": False, "detail": f"'{query}' is not on the active list ({on_list})."})
        out["reason"] = (
            f"'{query}' is not on this patient's active medication list (active: {on_list}). "
            "Do not prepare a refill; route to the provider if the patient needs a new prescription."
        )
        return out

    run_out = date.fromisoformat(med["last_filled"]) + timedelta(days=med["days_supply"])
    earliest = run_out - timedelta(days=7)
    cutoff = _months_ago(today, 12)
    last_visit = date.fromisoformat(patient["last_visit"])
    out["run_out_date"], out["earliest_date"] = run_out.isoformat(), earliest.isoformat()

    rules = [
        ("on_active_list", True, f"{med['medication']} is on the active list.", None, None),
        (
            "not_controlled",
            med["controlled_schedule"] is None,
            f"Controlled substance: {med['controlled_schedule'] or 'no'}.",
            "controlled_route_provider",
            f"{med['medication']} is a controlled substance ({med['controlled_schedule']}). The agent never prepares "
            f"controlled refills; route to the prescribing provider ({med['prescriber']}).",
        ),
        (
            "seen_within_12_months",
            last_visit >= cutoff,
            f"Last visit {patient['last_visit']}; must be on or after {cutoff.isoformat()}.",
            "needs_visit",
            f"Last visit was {patient['last_visit']}, more than 12 months ago. Do not prepare the refill; offer an "
            f"appointment and route to the provider ({med['prescriber']}).",
        ),
        (
            "refills_remaining",
            med["refills_remaining"] > 0,
            f"Refills remaining: {med['refills_remaining']}.",
            "zero_refills_route_provider",
            f"{med['medication']} has 0 refills remaining. Route to the provider ({med['prescriber']}) for a new prescription.",
        ),
        (
            "within_7_days_of_run_out",
            today >= earliest,
            f"Supply runs out {run_out.isoformat()}; a request can be prepared from {earliest.isoformat()}.",
            "too_early",
            f"Too early: the current supply of {med['medication']} lasts until {run_out.isoformat()}. "
            f"The earliest date the request can be prepared is {earliest.isoformat()}.",
        ),
    ]
    for rule, passed, detail, decision, reason in rules:
        out["reasons"].append({"rule": rule, "passed": passed, "detail": detail})
        if not passed and out["decision"] is None:
            out["decision"], out["reason"] = decision, reason
    if out["decision"] is None:
        out["decision"], out["eligible"] = "prepare", True
        out["reason"] = (
            f"All refill rules pass for {med['medication']} (supply runs out {run_out.isoformat()}). "
            "The agent may prepare a request for provider approval; it never approves."
        )
    return out
