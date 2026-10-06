from datetime import timedelta, datetime, timezone

TIME_FORMAT = "%Y%m%d_%H"
TIME_FORMAT_DISPLAY = "%Y-%m-%d %H:%M"
DEFAULT_DATATIME_DELTA = timedelta(hours=6)


def get_datatime_delta_to_now_h(d2: datetime, time_delta: timedelta) -> int:
    now = datetime.now(timezone.utc)

    if d2.tzinfo is None:
        d2 = d2.replace(tzinfo=timezone.utc)

    hours_step = int(time_delta.total_seconds() // 3600)

    rounded_hour = (now.hour // hours_step) * hours_step
    d1 = now.replace(hour=rounded_hour, minute=0, second=0, microsecond=0)

    diff = int((d2 - d1).total_seconds() / 3600)
    return max(0, diff)

def safe_year_replace(dt, target_year):
    """Replaces the year with target_year safely (Avoids February 29th problems)"""
    try:
        return dt.replace(year=target_year, minute=0, second=0, microsecond=0)
    except ValueError:
        # Fallback for Feb29
        return dt.replace(year=target_year, month=2, day=28, minute=0, second=0, microsecond=0)
