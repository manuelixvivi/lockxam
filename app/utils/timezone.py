from datetime import datetime, timezone, timedelta

# WIB (Waktu Indonesia Barat / Asia/Jakarta) = UTC+7
WIB = timezone(timedelta(hours=7))


def get_now_wib() -> datetime:
    """
    Return current timezone-aware datetime in WIB (Asia/Jakarta / UTC+7).
    """
    return datetime.now(WIB)


def ensure_wib(dt: datetime | None) -> datetime | None:
    """
    Ensure a datetime object is in WIB timezone.
    If naive, assume it represents local WIB time and attach tzinfo=WIB.
    If timezone-aware, convert to WIB timezone.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=WIB)
    return dt.astimezone(WIB)
