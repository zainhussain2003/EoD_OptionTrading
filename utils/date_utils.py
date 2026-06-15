import math
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo


ET = ZoneInfo('America/New_York')
UTC = timezone.utc

MWF = {0, 2, 4}  # Monday=0, Wednesday=2, Friday=4


# ── US (NYSE) market-holiday calendar — deterministic, no external deps ─────
def _easter(year: int) -> date:
    """Gregorian Easter Sunday (anonymous algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The nth (1-based) given weekday in a month, e.g. 4th Thursday of November."""
    d = date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """The last given weekday in a month, e.g. last Monday of May."""
    if month == 12:
        d = date(year, 12, 31)
    else:
        d = date(year, month + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d: date, shift_saturday: bool = True) -> date:
    """NYSE weekend observation: Sat→preceding Fri, Sun→following Mon."""
    if d.weekday() == 5 and shift_saturday:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


_HOLIDAY_CACHE: dict[int, set] = {}


def nyse_holidays(year: int) -> set:
    """Set of NYSE full-closure dates for a year (the ones that matter for
    weekly Thu/Fri expiries; intraday half-days are treated as open)."""
    if year in _HOLIDAY_CACHE:
        return _HOLIDAY_CACHE[year]
    h = set()
    # New Year's Day — NYSE does NOT pull a Saturday Jan 1 back to Dec 31.
    h.add(_observed(date(year, 1, 1), shift_saturday=False))
    h.add(_nth_weekday(year, 1, 0, 3))      # MLK Day — 3rd Monday Jan
    h.add(_nth_weekday(year, 2, 0, 3))      # Presidents' Day — 3rd Monday Feb
    h.add(_easter(year) - timedelta(days=2))  # Good Friday
    h.add(_last_weekday(year, 5, 0))        # Memorial Day — last Monday May
    if year >= 2021:
        h.add(_observed(date(year, 6, 19)))  # Juneteenth
    h.add(_observed(date(year, 7, 4)))       # Independence Day
    h.add(_nth_weekday(year, 9, 0, 1))       # Labor Day — 1st Monday Sep
    h.add(_nth_weekday(year, 11, 3, 4))      # Thanksgiving — 4th Thursday Nov
    h.add(_observed(date(year, 12, 25)))     # Christmas
    _HOLIDAY_CACHE[year] = h
    return h


def is_market_holiday(d: date) -> bool:
    return d in nyse_holidays(d.year)


def is_trading_day(d: date) -> bool:
    """A weekday that isn't a full NYSE closure."""
    return d.weekday() < 5 and not is_market_holiday(d)


def previous_trading_day(d: date) -> date:
    """The most recent trading day strictly before d."""
    p = d - timedelta(days=1)
    while not is_trading_day(p):
        p -= timedelta(days=1)
    return p


def get_past_mwf_dates(days_back: int = 60) -> list[date]:
    """All MWF trading dates in the past `days_back` calendar days, oldest first."""
    today = date.today()
    result = []
    for i in range(1, days_back + 1):
        d = today - timedelta(days=i)
        if d.weekday() in MWF:
            result.append(d)
    return list(reversed(result))


def get_past_weekly_pairs(days_back: int = 365) -> list[tuple[date, date]]:
    """(entry_day, expiry_day) per week in the past `days_back` days, oldest first.

    The weekly expiry is Friday. When that Friday is a market holiday (e.g. Good
    Friday) the option expires the prior trading day instead — normally Thursday
    — so no week is skipped and we stay on REAL data:

        normal week        →  buy Thursday,  expiry Friday
        Friday closed       →  buy Wednesday, expiry Thursday

    Entry is always the trading day immediately before the expiry day, so other
    gaps (e.g. a closed Thursday with Friday open) resolve sensibly too.
    """
    today = date.today()
    result = []
    for i in range(1, days_back + 1):
        d = today - timedelta(days=i)
        if d.weekday() != 4:                  # iterate one anchor per Friday
            continue
        if is_trading_day(d):                 # normal week: Friday expiry
            expiry = d
        else:                                 # Friday closed: roll to Thursday
            expiry = previous_trading_day(d)
        entry = previous_trading_day(expiry)  # trading day before expiry
        result.append((entry, expiry))
    return list(reversed(result))


def session_start_utc(d: date) -> datetime:
    """9:30 AM ET (market open) as a UTC datetime for date d."""
    local = datetime(d.year, d.month, d.day, 9, 30, 0, tzinfo=ET)
    return local.astimezone(UTC)


def entry_window_start_utc(d: date) -> datetime:
    """3:50 PM ET as a UTC datetime — a small cushion before the 3:55 entry."""
    local = datetime(d.year, d.month, d.day, 15, 50, 0, tzinfo=ET)
    return local.astimezone(UTC)


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
                            call_put: str = 'C') -> str:
    """OCC symbol: AAPL260612C00212500"""
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


def get_strike_at_or_above(spot: float, interval: float | None = None) -> float:
    """Smallest standard strike that is >= spot — the call you'd actually buy.

    Picks the at-the-money strike when spot sits exactly on one, otherwise the
    first strike ABOVE spot. Never returns a strike below spot. Examples
    (interval 2.5): spot 400.25 -> 402.5;  spot 400.00 -> 400.0.
    """
    if interval is None:
        interval = detect_strike_interval(spot)
    # round() first so float noise (e.g. 160.00000004) doesn't bump us a strike up.
    n = math.ceil(round(spot / interval, 6))
    return round(n * interval, 2)


def minute_to_str(minute_of_day: int) -> str:
    """Convert 915 → '3:15 PM'"""
    h = minute_of_day // 60
    m = minute_of_day % 60
    period = 'AM' if h < 12 else 'PM'
    display_h = h if h <= 12 else h - 12
    if display_h == 0:
        display_h = 12
    return f"{display_h}:{m:02d} {period}"
