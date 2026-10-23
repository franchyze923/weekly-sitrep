import sys
from datetime import datetime


def _weeks(monkeypatch, tz, fake_now_utc):
    """Load app.weeks with APP_TZ=tz and the clock frozen at fake_now_utc."""
    monkeypatch.setenv("APP_TZ", tz)
    monkeypatch.delenv("FAKE_TODAY", raising=False)
    for m in [m for m in list(sys.modules) if m == "app" or m.startswith("app.")]:
        del sys.modules[m]
    from app import weeks

    class FakeDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return fake_now_utc.astimezone(tz)
    monkeypatch.setattr(weeks, "datetime", FakeDT)
    return weeks


def test_sunday_night_new_york_is_still_last_week(monkeypatch):
    from datetime import timezone
    # 2026-10-26 02:30 UTC == Sunday 2026-10-25 22:30 EDT
    now = datetime(2026, 10, 26, 2, 30, tzinfo=timezone.utc)
    assert _weeks(monkeypatch, "America/New_York", now).current_week().isoformat() == "2026-10-19"
    assert _weeks(monkeypatch, "UTC", now).current_week().isoformat() == "2026-10-26"


def test_localtime_formats_in_app_tz(monkeypatch):
    from datetime import timezone
    weeks = _weeks(monkeypatch, "America/New_York", datetime(2026, 10, 22, tzinfo=timezone.utc))
    assert weeks.localtime(datetime(2026, 10, 23, 0, 55)) == "Oct 22, 8:55 PM EDT"


def test_bad_tz_refused(monkeypatch):
    import pytest
    monkeypatch.setenv("APP_TZ", "Mars/Olympus")
    for m in [m for m in list(sys.modules) if m == "app" or m.startswith("app.")]:
        del sys.modules[m]
    from app import config
    with pytest.raises(SystemExit):
        config.validate()
