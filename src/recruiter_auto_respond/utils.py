from datetime import datetime, timedelta, timezone

_UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _truncate_toward_zero(value: int, divisor: int) -> int:
    """Integer division truncated toward zero."""
    if value >= 0:
        return value // divisor
    return -((-value) // divisor)


def _iso_to_utc_datetime(iso_str: str) -> datetime:
    """Parse an ISO-8601 string and normalize it to UTC."""
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def iso_to_ms(iso_str: str) -> int:
    """Convert ISO-8601 string to Unix milliseconds."""
    dt = _iso_to_utc_datetime(iso_str)
    delta = dt - _UNIX_EPOCH
    total_microseconds = (
        (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
    )
    return _truncate_toward_zero(total_microseconds, 1000)


def ms_to_iso(ms: int) -> str:
    """Convert Unix milliseconds to ISO-8601 string with MS precision."""
    dt = _UNIX_EPOCH + timedelta(milliseconds=ms)
    # Use ISO format with millisecond precision
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def unix_to_iso(seconds: int) -> str:
    """Convert Unix seconds to ISO-8601 string."""
    dt = _UNIX_EPOCH + timedelta(seconds=seconds)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def iso_to_unix(iso_str: str) -> int:
    """Convert ISO-8601 string to Unix seconds."""
    dt = _iso_to_utc_datetime(iso_str)
    delta = dt - _UNIX_EPOCH
    total_microseconds = (
        (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
    )
    return _truncate_toward_zero(total_microseconds, 1_000_000)
