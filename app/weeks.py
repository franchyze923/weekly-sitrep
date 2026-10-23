"""Week arithmetic and time display. A week is identified by its Monday as an
ISO date string. 'Today' and all displayed times are in APP_TZ; the database
stores naive UTC datetimes."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import config

TZ = ZoneInfo(config.APP_TZ)


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def today() -> date:
    if config.FAKE_TODAY:
        return datetime.strptime(config.FAKE_TODAY, "%Y-%m-%d").date()
    return datetime.now(TZ).date()


def current_week() -> date:
    return monday_of(today())


def parse_week(text: str) -> date:
    """Parse YYYY-MM-DD and snap to that week's Monday. Raises ValueError on junk."""
    return monday_of(datetime.strptime(text, "%Y-%m-%d").date())


def week_label(monday: date) -> str:
    sunday = monday + timedelta(days=6)
    if monday.month == sunday.month:
        return "{} {}–{}, {}".format(monday.strftime("%b"), monday.day, sunday.day, monday.year)
    return "{} – {}".format(monday.strftime("%b %-d"), sunday.strftime("%b %-d, %Y"))


def localtime(utc_naive: datetime) -> str:
    """Format a stored UTC datetime for display, e.g. 'Oct 22, 8:55 PM EDT'."""
    local = utc_naive.replace(tzinfo=timezone.utc).astimezone(TZ)
    return local.strftime("%b %-d, %-I:%M %p %Z")
