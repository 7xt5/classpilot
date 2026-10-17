"""
utils.py - Small helper functions used everywhere (dates, formatting, grades).

Dates are stored in JSON as ISO strings, e.g. "2026-10-20T23:59".
"""

import re
from datetime import date, datetime, time

URL_PATTERN = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")


# --------------------------------------------------------------------------
# Dates and times
# --------------------------------------------------------------------------
def now():
    """Current local time without seconds (keeps comparisons simple)."""
    return datetime.now().replace(second=0, microsecond=0)


def now_iso():
    """Current time as an ISO string with seconds (for 'created_at' fields)."""
    return datetime.now().isoformat(timespec="seconds")


def parse_dt(value):
    """Turn an ISO string into a ``datetime``. Returns ``None`` if invalid."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time(0, 0))
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def combine(day, clock):
    """Join a ``date`` and a ``time`` into an ISO string (minutes precision)."""
    return datetime.combine(day, clock).isoformat(timespec="minutes")


def fmt_dt(value):
    """Friendly date + time, e.g. 'Tue 20 Oct, 23:59'."""
    moment = parse_dt(value)
    return moment.strftime("%a %d %b, %H:%M") if moment else "—"


def fmt_date(value):
    """Friendly date, e.g. '20 Oct 2026'."""
    moment = parse_dt(value)
    return moment.strftime("%d %b %Y") if moment else "—"


def relative_due(value):
    """Describe a deadline relative to now, e.g. 'in 3 days' or 'overdue by 2 days'."""
    due = parse_dt(value)
    if not due:
        return "no deadline"
    seconds = (due - datetime.now()).total_seconds()
    days = (due.date() - date.today()).days
    if seconds < 0:
        late_days = (date.today() - due.date()).days
        if late_days == 0:
            return "overdue (today)"
        return f"overdue by {late_days} day{'s' if late_days != 1 else ''}"
    if days == 0:
        return f"today at {due.strftime('%H:%M')}"
    if days == 1:
        return f"tomorrow at {due.strftime('%H:%M')}"
    return f"in {days} days"


def is_past(value):
    """True if the given ISO date/time is already in the past."""
    moment = parse_dt(value)
    return bool(moment and moment < datetime.now())


# --------------------------------------------------------------------------
# Numbers and grades
# --------------------------------------------------------------------------
def percent(score, maximum):
    """Safe percentage (returns ``None`` instead of dividing by zero)."""
    if score is None or not maximum:
        return None
    return round(100.0 * float(score) / float(maximum), 1)


def mean(values):
    """Average of a list, ignoring ``None``. Returns ``None`` for an empty list."""
    clean = [v for v in values if v is not None]
    return round(sum(clean) / len(clean), 1) if clean else None


def letter_grade(pct, scale):
    """Convert a percentage to a letter using the school's grade scale."""
    if pct is None:
        return "—"
    for band in sorted(scale, key=lambda b: b["min"], reverse=True):
        if pct >= band["min"]:
            return band["letter"]
    return scale[-1]["letter"] if scale else "—"


def fmt_pct(value):
    """Format a percentage for display, e.g. '87.5%' or '—'."""
    return "—" if value is None else f"{value:.1f}%"


# --------------------------------------------------------------------------
# Text and validation
# --------------------------------------------------------------------------
def clean(text, max_length=5000):
    """Strip whitespace and cut overly long input."""
    return (text or "").strip()[:max_length]


def is_valid_url(url):
    """Very small URL check: must start with http:// or https://."""
    return bool(URL_PATTERN.match((url or "").strip()))


def is_valid_email(email):
    """Simple e-mail format check."""
    return bool(EMAIL_PATTERN.match((email or "").strip()))


def matches(query, *fields):
    """Case-insensitive 'contains' search across several text fields."""
    query = (query or "").strip().lower()
    if not query:
        return False
    return any(query in str(field or "").lower() for field in fields)
