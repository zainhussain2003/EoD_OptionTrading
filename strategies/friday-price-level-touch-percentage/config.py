from dataclasses import dataclass, field


@dataclass
class Config:
    # ── Tickers and their per-ticker percentage move thresholds ──────────────
    # The study asks, for each ticker: starting from Thursday's near-close price
    # R, how often does Friday touch (R × (1 ± pct))? Each ticker is evaluated at
    # several percentage levels so the move is volatility-normalized and directly
    # comparable across names (unlike the earlier fixed-dollar thresholds).
    # Each list is independently editable; the default is 2%, 2.5% and 3%.
    ticker_pcts: dict = field(default_factory=lambda: {
        'TSLA': [0.02, 0.025, 0.03],
        'AAPL': [0.02, 0.025, 0.03],
        'NVDA': [0.02, 0.025, 0.03],
        'MSFT': [0.02, 0.025, 0.03],
        'ORCL': [0.02, 0.025, 0.03],
    })

    backtest_days: int = 730           # lookback window (calendar days)
    bar_minutes: int = 1               # 1-minute interval data throughout
    timezone: str = 'America/New_York'
    risk_free_rate: float = 0.05       # kept for fetcher compatibility (unused here)

    # ── Thursday reference minutes (minutes-of-day, ET) ──────────────────────
    # 3:50–3:55 PM, captured minute-by-minute, so we can compare which near-close
    # minute is the steadiest baseline. 950 = 3:50 PM … 955 = 3:55 PM.
    thursday_ref_minutes: list = field(
        default_factory=lambda: [950, 951, 952, 953, 954, 955])
    # Also evaluate the average of the 3:50–3:55 range as a 7th "baseline".
    include_avg_baseline: bool = True

    # ── Friday scan window in minutes-of-day (ET) ────────────────────────────
    # 570 = 9:30 AM (market open) → 960 = 4:00 PM (market close).
    friday_start_minute: int = 570
    friday_end_minute: int = 960

    # ── Inert metadata ───────────────────────────────────────────────────────
    # target_spend / outlier_max are option-P&L concepts from the pipeline
    # template. They have NO meaning in this stock price-level study (there is no
    # premium to spend and no trade P&L to cap). They are carried through to
    # config and metrics.json purely to document the requested run parameters and
    # do not affect any calculation.
    target_spend: float = 1.00
    outlier_max: float = 2000.0
