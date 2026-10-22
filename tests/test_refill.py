from datetime import date

import pytest

from clinic_mcp.policy.refill import check_refill_eligibility, resolve_medication
from clinic_mcp.store import load_store

STORE = load_store()
TODAY = date(2026, 11, 9)


def check(pid, query, today=TODAY):
    return check_refill_eligibility(STORE.patients[pid], STORE.meds_for(pid), query, today)


@pytest.mark.parametrize(
    "pid,query,decision",
    [
        ("P002", "lisinopril", "prepare"),
        ("P012", "levothyroxine", "prepare"),
        ("P001", "metformina", "prepare"),
        ("P022", "insulin", "prepare"),
        ("P024", "atorvastatin", "prepare"),
        ("P015", "omeprazole", "too_early"),
        ("P017", "donepezil", "too_early"),
        ("P004", "metformin", "needs_visit"),
        ("P016", "escitalopram", "needs_visit"),
        ("P006", "Xanax", "controlled_route_provider"),
        ("P014", "Ambien", "controlled_route_provider"),
        ("P014", "zolpidem", "controlled_route_provider"),
        ("P021", "oxycodone", "controlled_route_provider"),
        ("P011", "Adderall", "controlled_route_provider"),
        ("P008", "Amlodipine", "zero_refills_route_provider"),
        ("P002", "ibuprofen", "not_on_list"),
        ("P003", "metformin", "not_on_list"),
    ],
)
def test_decisions(pid, query, decision):
    r = check(pid, query)
    assert r["decision"] == decision, r["reasons"]
    assert r["eligible"] is (decision == "prepare")


def test_prepare_reports_run_out_date():
    r = check("P002", "lisinopril")
    assert r["run_out_date"] == "2026-11-13"
    assert r["medication"] == "Lisinopril 10 mg"


@pytest.mark.parametrize("pid,query,earliest", [("P015", "omeprazole", "2026-11-17"), ("P017", "donepezil", "2026-11-21")])
def test_too_early_gives_earliest_date(pid, query, earliest):
    r = check(pid, query)
    assert r["earliest_date"] == earliest
    assert earliest in r["reason"]


def test_brand_name_resolves_to_generic():
    assert check("P006", "Xanax")["medication"] == "Alprazolam 0.5 mg"


def test_partial_name_matches_combination_product():
    assert resolve_medication("lisinopril", STORE.meds_for("P018"))["medication"] == "Lisinopril-HCTZ 20/12.5 mg"


def test_misspelling_matches_by_fuzzy_fallback():
    assert resolve_medication("levothyroxin", STORE.meds_for("P012"))["medication"] == "Levothyroxine 75 mcg"


def test_twelve_month_boundary_is_inclusive():
    patient = dict(STORE.patients["P002"], last_visit="2025-11-09")
    r = check_refill_eligibility(patient, STORE.meds_for("P002"), "lisinopril", TODAY)
    assert r["decision"] == "prepare"
    patient = dict(patient, last_visit="2025-11-08")
    assert check_refill_eligibility(patient, STORE.meds_for("P002"), "lisinopril", TODAY)["decision"] == "needs_visit"


def test_all_five_rules_reported_in_order():
    r = check("P006", "Xanax")
    assert [x["rule"] for x in r["reasons"]] == [
        "on_active_list",
        "not_controlled",
        "seen_within_12_months",
        "refills_remaining",
        "within_7_days_of_run_out",
    ]
    failed = [x["rule"] for x in r["reasons"] if not x["passed"]]
    assert failed == ["not_controlled", "refills_remaining"]


def test_controlled_takes_precedence_over_other_failures():
    # Alprazolam: controlled AND zero refills; controlled decides the route.
    assert check("P006", "alprazolam")["decision"] == "controlled_route_provider"
