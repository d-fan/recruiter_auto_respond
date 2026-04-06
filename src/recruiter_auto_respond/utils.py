from datetime import datetime, timezone


def iso_to_ms(iso_str: str) -> int:
    """Convert ISO-8601 string to Unix milliseconds."""
    # datetime.fromisoformat handles Z and ms
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return int(dt.timestamp() * 1000)


def ms_to_iso(ms: int) -> str:
    """Convert Unix milliseconds to ISO-8601 string with MS precision."""
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    # Use ISO format with millisecond precision
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def unix_to_iso(seconds: int) -> str:
    """Convert Unix seconds to ISO-8601 string."""
    dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def iso_to_unix(iso_str: str) -> int:
    """Convert ISO-8601 string to Unix seconds."""
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return int(dt.timestamp())
