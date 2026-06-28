from dataclasses import dataclass, field


@dataclass
class Config:
    """Configuration for the weekly-move-probability study.

    For each ticker we measure, week over week, the terminal (close-to-close)
    return from one Friday's near-close reference price to the next Friday's, and
    bucket it as up / down / flat around a symmetric ±threshold band.
    """

    # ── Universe ─────────────────────────────────────────────────────────────
    tickers: list = field(default_factory=lambda: [
        'TSLA', 'AAPL', 'NVDA', 'ORCL', 'MSFT',
    ])

    # ── The ±band that defines up / down / flat (PARAMETER) ──────────────────
    # A week is `up` if the weekly return >= +threshold, `down` if <= -threshold,
    # else `flat` (inside the band). 0.015 = ±1.5%.
    threshold: float = 0.015

    # ── Lookback window (PARAMETER) ──────────────────────────────────────────
    backtest_days: int = 730           # calendar days of Fridays to test
    bar_minutes: int = 1               # 1-minute interval data throughout
    timezone: str = 'America/New_York'
    risk_free_rate: float = 0.05       # kept for fetcher compatibility (unused here)

    # ── Reference window: 3:50–4:00 PM ET, minutes-of-day ────────────────────
    # 950 = 3:50 PM … 960 = 4:00 PM. The window is [ref_start, ref_end), i.e. the
    # ten 1-minute bars 3:50, 3:51, … 3:59 (the 4:00 PM bar is excluded). The
    # reference price is the AVERAGE of those bars' CLOSE prices (not VWAP).
    ref_start_minute: int = 950        # 3:50 PM ET
    ref_end_minute: int = 960          # 4:00 PM ET (exclusive)

    # A reference window needs at least this many 1-minute bars to be usable.
    # Below `min_ref_bars_thin` the window is accepted but flagged as "thin" so
    # the caveat is surfaced rather than silently trusted.
    min_ref_bars: int = 1
    min_ref_bars_thin: int = 5

    # ── Holiday rule ─────────────────────────────────────────────────────────
    # If a Friday is a market holiday / closed (no usable 3:50–4:00 window), step
    # back to the prior Thursday's window (then Wed, Tue …). Applied to BOTH the
    # entry and exit legs. max_baseline_lookback caps how far back we walk.
    max_baseline_lookback: int = 4
