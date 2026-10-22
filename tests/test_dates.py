from datetime import date

import pytest

from clinic_mcp.policy.dates import business_days, next_business_days, resolve_date

TODAY = date(2026, 11, 9)  # Monday
HOLIDAYS = ["2026-11-26", "2026-11-27", "2026-12-25"]


@pytest.mark.parametrize(
    "expr,start,end",
    [
        ("tomorrow", "2026-11-10", "2026-11-10"),
        ("today", "2026-11-09", "2026-11-09"),
        ("this week", "2026-11-09", "2026-11-13"),
        ("next week", "2026-11-16", "2026-11-20"),
        ("this Thursday", "2026-11-12", "2026-11-12"),
        ("Wednesday", "2026-11-11", "2026-11-11"),
        ("on Friday", "2026-11-13", "2026-11-13"),
        ("next Tuesday", "2026-11-17", "2026-11-17"),
        ("Wednesday the 18th", "2026-11-18", "2026-11-18"),
        ("Monday the 16th", "2026-11-16", "2026-11-16"),
        ("the 23rd", "2026-11-23", "2026-11-23"),
        ("the day after Thanksgiving", "2026-11-27", "2026-11-27"),
        ("Thanksgiving", "2026-11-26", "2026-11-26"),
        ("mañana", "2026-11-10", "2026-11-10"),
        ("la próxima semana", "2026-11-16", "2026-11-20"),
        ("esta semana", "2026-11-09", "2026-11-13"),
        ("el viernes", "2026-11-13", "2026-11-13"),
        ("2026-11-20", "2026-11-20", "2026-11-20"),
        ("Nov 18", "2026-11-18", "2026-11-18"),
        ("November 30th", "2026-11-30", "2026-11-30"),
        ("in two weeks", "2026-11-23", "2026-11-27"),
    ],
)
def test_resolve_date(expr, start, end):
    r = resolve_date(expr, TODAY, HOLIDAYS)
    assert r["ok"], r
    assert (r["start"], r["end"]) == (start, end)


def test_following_week_uses_anchor():
    r = resolve_date("the following week", TODAY, HOLIDAYS, anchor=date(2026, 11, 16))
    assert (r["start"], r["end"]) == ("2026-11-23", "2026-11-27")
    assert r["business_days"] == ["2026-11-23", "2026-11-24", "2026-11-25"]


def test_weekday_and_day_number_mismatch_is_refused():
    r = resolve_date("Tuesday the 18th", TODAY, HOLIDAYS)
    assert not r["ok"]
    assert "Wednesday" in r["reason"]


def test_unknown_expression_is_refused_with_reason():
    r = resolve_date("sometime soonish", TODAY, HOLIDAYS)
    assert not r["ok"]
    assert r["reason"]


def test_result_flags_holiday():
    r = resolve_date("the day after Thanksgiving", TODAY, HOLIDAYS)
    assert r["business_days"] == []
    assert "holiday" in r["reason"].lower()


def test_business_day_helpers_skip_weekends_and_holidays():
    assert business_days(date(2026, 11, 25), date(2026, 11, 30), HOLIDAYS) == [
        date(2026, 11, 25),
        date(2026, 11, 30),
    ]
    assert next_business_days(date(2026, 11, 13), 2, HOLIDAYS) == [
        date(2026, 11, 13),
        date(2026, 11, 16),
    ]
