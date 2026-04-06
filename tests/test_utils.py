from recruiter_auto_respond.utils import iso_to_ms, iso_to_unix, ms_to_iso, unix_to_iso


def test_iso_to_ms() -> None:
    iso = "2026-03-18T12:00:00.123Z"
    ms = iso_to_ms(iso)
    # 2026-03-18 12:00:00 is 1773835200 seconds
    assert ms == 1773835200123


def test_ms_to_iso() -> None:
    ms = 1773835200123
    iso = ms_to_iso(ms)
    assert iso == "2026-03-18T12:00:00.123Z"


def test_unix_to_iso() -> None:
    seconds = 1773835200
    iso = unix_to_iso(seconds)
    assert iso == "2026-03-18T12:00:00Z"


def test_iso_to_unix() -> None:
    iso = "2026-03-18T12:00:00Z"
    seconds = iso_to_unix(iso)
    assert seconds == 1773835200
