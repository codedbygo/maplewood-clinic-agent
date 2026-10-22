"""Resolve relative date phrases against the clinic's fixed 'today'. The LLM never does date maths."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
    "mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3, "thurs": 3, "fri": 4, "sat": 5, "sun": 6,
    "lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6,
}
MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "a": 1, "dos": 2, "tres": 3}
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

_WD = "|".join(sorted(WEEKDAYS, key=len, reverse=True))
_MO = "|".join(sorted(MONTHS, key=len, reverse=True))


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s/-]", " ", text)).strip()


def _hol(holidays) -> set[date]:
    return {h if isinstance(h, date) else date.fromisoformat(h) for h in holidays}


def business_days(start: date, end: date, holidays) -> list[date]:
    hol = _hol(holidays)
    out, d = [], start
    while d <= end:
        if d.weekday() < 5 and d not in hol:
            out.append(d)
        d += timedelta(days=1)
    return out


def next_business_days(start: date, n: int, holidays) -> list[date]:
    hol = _hol(holidays)
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5 and d not in hol:
            out.append(d)
        d += timedelta(days=1)
    return out


def _week(monday: date) -> tuple[date, date]:
    return monday, monday + timedelta(days=4)


def _thanksgiving(year: int) -> date:
    first = date(year, 11, 1)
    first_thu = first + timedelta(days=(3 - first.weekday()) % 7)
    return first_thu + timedelta(weeks=3)


def _day_in_month(day: int, today: date) -> date:
    y, m = today.year, today.month
    if day < today.day:
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return date(y, m, day)


def _parse(expr: str, today: date, anchor: date | None) -> tuple[date, date, str] | str:
    """Return (start, end, label) or an error string."""
    t = _norm(expr)
    this_monday = today - timedelta(days=today.weekday())
    next_monday = this_monday + timedelta(weeks=1)

    if m := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", t):
        d = date(*map(int, m.groups()))
        return d, d, d.isoformat()

    if m := re.search(rf"\b({_MO})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", t) or re.search(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+|de\s+)?({_MO})\b", t
    ):
        a, b = m.groups()
        month, day = (MONTHS[a], int(b)) if a in MONTHS else (MONTHS[b], int(a))
        try:
            d = date(today.year, month, day)
            if d < today:
                d = date(today.year + 1, month, day)
        except ValueError:
            return f"There is no day {day} in that month. Ask the sender which date they meant."
        return d, d, d.isoformat()

    if "thanksgiving" in t or "accion de gracias" in t:
        tg = _thanksgiving(today.year)
        if re.search(r"\b(day after|after|despues)\b", t):
            d = tg + timedelta(days=1)
            return d, d, "day after Thanksgiving"
        return tg, tg, "Thanksgiving"

    if re.search(r"\b(day after tomorrow|pasado manana)\b", t):
        d = today + timedelta(days=2)
        return d, d, "day after tomorrow"
    if re.search(r"\btomorrow\b|(?<!esta )(?<!la )(?<!por )\bmanana\b", t):
        d = today + timedelta(days=1)
        return d, d, "tomorrow"
    if re.search(r"\b(today|hoy|this afternoon|this morning)\b", t):
        return today, today, "today"

    if re.search(r"\b(following week|week after|semana siguiente)\b", t):
        base = anchor or today
        mon = base - timedelta(days=base.weekday()) + timedelta(weeks=1)
        return (*_week(mon), "the following week")
    if m := re.search(r"\bin (\d+|one|two|three|four|a|dos|tres) weeks?\b", t) or re.search(
        r"\ben (\d+|dos|tres) semanas\b", t
    ):
        n = int(m.group(1)) if m.group(1).isdigit() else NUMBERS[m.group(1)]
        return (*_week(this_monday + timedelta(weeks=n)), f"in {n} weeks")
    if re.search(r"\b(next week|proxima semana|semana que viene|semana proxima)\b", t):
        return (*_week(next_monday), "next week")
    if re.search(r"\b(this week|esta semana)\b", t):
        if today.weekday() >= 5:  # at the weekend, "this week" means the coming week
            return (*_week(next_monday), "this week")
        return today, this_monday + timedelta(days=4), "this week"

    # "<weekday> the 18th", "the 18th", "el 18"
    # A day number after a weekday ("Wednesday 18th", "miercoles 18") or after "the"/"el"; never a clock time.
    if m := re.search(rf"\b({_WD})\s+(?:the\s+|el\s+)?(\d{{1,2}})(?:st|nd|rd|th)?\b(?!\s*(?:am|pm|a m|p m|\d|h\b))", t) or re.search(
        r"\b()(?:the\s+|el\s+)(\d{1,2})(?:st|nd|rd|th)?\b(?!\s*(?:am|pm|a m|p m|\d|h\b))", t
    ):
        wd, day = m.group(1) or None, int(m.group(2))
        try:
            d = _day_in_month(day, today)
        except ValueError:
            return f"There is no day {day} in the coming month."
        if wd and WEEKDAYS[wd] != d.weekday():
            return (
                f"'{expr}' is inconsistent: {d.isoformat()} is a {DAY_NAMES[d.weekday()]}, "
                f"not a {DAY_NAMES[WEEKDAYS[wd]]}. Ask the sender which they meant."
            )
        return d, d, d.isoformat()

    if m := re.search(rf"\b(next|proximo|proxima)\s+({_WD})\b", t) or re.search(rf"\b({_WD})\s+(proximo|que viene)\b", t):
        wd = m.group(2) if m.group(1) in ("next", "proximo", "proxima") else m.group(1)
        d = next_monday + timedelta(days=WEEKDAYS[wd])
        return d, d, f"next {DAY_NAMES[WEEKDAYS[wd]]}"
    if m := re.search(rf"\b({_WD})\b", t):
        wd = WEEKDAYS[m.group(1)]
        d = today + timedelta(days=(wd - today.weekday()) % 7)
        return d, d, DAY_NAMES[wd]

    return f"Could not resolve '{expr}'. Ask the sender for a specific date."


def resolve_date(expr: str, today: date, holidays, anchor: date | None = None) -> dict:
    parsed = _parse(expr, today, anchor)
    if isinstance(parsed, str):
        return {"ok": False, "start": None, "end": None, "business_days": [], "label": None, "reason": parsed}
    start, end, label = parsed
    hol = _hol(holidays)
    days = business_days(start, end, holidays)
    notes = []
    d = start
    while d <= end:
        if d in hol:
            notes.append(f"{d.isoformat()} ({DAY_NAMES[d.weekday()]}) is a clinic holiday")
        elif d.weekday() >= 5:
            if start == end:
                notes.append(f"{d.isoformat()} is a {DAY_NAMES[d.weekday()]}; the clinic is closed at weekends")
        d += timedelta(days=1)
    if start < today:
        notes.append(f"{start.isoformat()} is in the past")
    span = start.isoformat() if start == end else f"{start.isoformat()} to {end.isoformat()}"
    reason = f"'{expr}' resolves to {span} ({label}), relative to today {today.isoformat()}."
    if notes:
        reason += " Note: " + "; ".join(notes) + "."
    if not days:
        reason += " No clinic business days in this range."
    return {
        "ok": True,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "business_days": [x.isoformat() for x in days],
        "label": label,
        "reason": reason,
    }


_WEEKDAY_WORDS = (r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
                  r"lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo")
_MONTH_WORDS = (r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|"
                r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?")
# Most specific first; a later pattern never claims text an earlier one matched.
_PHRASES = [
    r"(?:the\s+)?day\s+after\s+thanksgiving|thanksgiving",
    r"(?:the\s+)?following\s+week|the\s+week\s+after",
    rf"(?:{_WEEKDAY_WORDS})(?:\s+the)?\s+\d{{1,2}}(?:st|nd|rd|th)?\b",
    rf"(?:this|next|el\s+pr[oó]ximo|el)\s+(?:{_WEEKDAY_WORDS})\b",
    r"(?:this|next)\s+week|la\s+pr[oó]xima\s+semana|esta\s+semana|la\s+semana\s+que\s+viene|in\s+(?:two|three|2|3)\s+weeks",
    r"day\s+after\s+tomorrow|pasado\s+ma[nñ]ana|tomorrow|today|hoy|(?<!la\s)(?<!por\s)(?<!esta\s)ma[nñ]ana",
    rf"(?:{_MONTH_WORDS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?\b",
    r"\d{4}-\d{2}-\d{2}",
    rf"\b(?:{_WEEKDAY_WORDS})\b",
    r"\bthe\s+\d{1,2}(?:st|nd|rd|th)\b",
]


def find_date_phrases(text: str) -> list[str]:
    """Date expressions in a message, in order, for resolve_date to turn into real dates.

    "por la mañana" (in the morning) is not "mañana" (tomorrow). Overlaps go to the more specific phrase.
    """
    taken: list[tuple[int, int]] = []
    for pattern in _PHRASES:
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            if not any(m.start() < e and s < m.end() for s, e in taken):
                taken.append((m.start(), m.end()))
    return [text[s:e] for s, e in sorted(taken)]
