import math
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo


ET = ZoneInfo('America/New_York')
UTC = timezone.utc

MWF = {0, 2, 4}  # Monday=0, Wednesday=2, Friday=4


def get_past_mwf_dates(days_back: int = 60) -> list[date]:
    """All MWF trading dates in the past `days_back` calendar days, oldest first."""
    today = date.today()
    result = []
    for i in range(1, days_back + 1):
        d = today - timedelta(days=i)
        if d.weekday() in MWF:
            result.append(d)
    return list(reversed(result))


def get_next_mwf_dates(count: int = 3) -> list[date]:
    """Next `count` MWF dates starting from today."""
    today = date.today()
    result = []
    d = today
    while len(result) < count:
        if d.weekday() in MWF:
            result.append(d)
        d += timedelta(days=1)
    return result


def is_mwf(d: date | None = None) -> bool:
    if d is None:
        d = date.today()
    return d.weekday() in MWF


def window_start_utc(d: date) -> datetime:
    """3:00 PM ET as UTC datetime for date d."""
    local = datetime(d.year, d.month, d.day, 15, 0, 0, tzinfo=ET)
    return local.astimezone(UTC)


def window_end_utc(d: date) -> datetime:
    """4:00 PM ET as UTC datetime for date d."""
    local = datetime(d.year, d.month, d.day, 16, 0, 0, tzinfo=ET)
    return local.astimezone(UTC)


def now_et() -> datetime:
    return datetime.now(ET)


def compute_T(expiry_date: date, now_dt: datetime | None = None) -> float:
    """Time to expiry in fractional trading years. Minimum floor ~15 trading minutes."""
    T_FLOOR = 1.0 / (252.0 * 6.5 * 4.0)
    if now_dt is None:
        now_dt = datetime.now(ET)
    expiry_close = datetime(expiry_date.year, expiry_date.month, expiry_date.day,
                            16, 0, 0, tzinfo=ET)
    if now_dt >= expiry_close:
        return 0.0
    seconds_remaining = (expiry_close - now_dt).total_seconds()
    T = seconds_remaining / (252.0 * 6.5 * 3600.0)
    return max(T, T_FLOOR)


def format_contract_symbol(ticker: str, expiry: date, strike: float,
                            call_put: str = 'P') -> str:
    """OCC symbol: AAPL260612P00212500"""
    date_str = expiry.strftime('%y%m%d')
    strike_int = round(strike * 1000)
    return f"{ticker}{date_str}{call_put}{strike_int:08d}"


def detect_strike_interval(spot: float) -> float:
    """Estimate standard strike interval for a given price level."""
    if spot >= 500:
        return 5.0
    elif spot >= 200:
        return 2.5
    elif spot >= 100:
        return 5.0
    elif spot >= 50:
        return 2.5
    else:
        return 1.0


def get_atm_strikes(spot: float, interval: float | None = None) -> tuple[float, float]:
    """Return (strike_below_or_at, strike_above) nearest to spot."""
    if interval is None:
        interval = detect_strike_interval(spot)
    lower = math.floor(spot / interval) * interval
    upper = lower + interval
    if abs(lower - spot) < 0.001:
        lower -= interval
    return round(lower, 2), round(upper, 2)


def minute_to_str(minute_of_day: int) -> str:
    """Convert 915 → '3:15 PM'"""
    h = minute_of_day // 60
    m = minute_of_day % 60
    period = 'AM' if h < 12 else 'PM'
    display_h = h if h <= 12 else h - 12
    if display_h == 0:
        display_h = 12
    return f"{display_h}:{m:02d} {period}"
