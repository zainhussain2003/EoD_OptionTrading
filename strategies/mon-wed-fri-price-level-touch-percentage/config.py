from dataclasses import dataclass, field


@dataclass
class Config:
    # ── Tickers and their per-ticker percentage move thresholds ──────────────
    # The study asks, for each ticker and each scan day: starting from the prior
    # trading day's near-close price R, how often does the scan day touch
    # (R × (1 ± pct))? Each ticker is evaluated at several percentage levels so the
    # move is volatility-normalized and directly comparable across names.
    # Each list is independently editable; the default is 1%, 1.5%, 2%, 2.5% and 3%.
    ticker_pcts: dict = field(default_factory=lambda: {
        'TSLA': [0.01, 0.015, 0.02, 0.025, 0.03],
        'AAPL': [0.01, 0.015, 0.02, 0.025, 0.03],
        'NVDA': [0.01, 0.015, 0.02, 0.025, 0.03],
        'MSFT': [0.01, 0.015, 0.02, 0.025, 0.03],
        'ORCL': [0.01, 0.015, 0.02, 0.025, 0.03],
    })

    # ── Scan days ─────────────────────────────────────────────────────────────
    # Each scan day is analyzed against the close of the trading day immediately
    # before it: Monday ← prior Friday, Wednesday ← prior Tuesday, Friday ← prior
    # Thursday. Results are reported one day after another, then summarized in a
    # combined per-ticker day-comparison table.
    scan_days: list = field(default_factory=lambda: ['Monday', 'Wednesday', 'Friday'])

    backtest_days: int = 730           # lookback window (calendar days)
    bar_minutes: int = 1               # 1-minute interval data throughout
    timezone: str = 'America/New_York'
    risk_free_rate: float = 0.05       # kept for fetcher compatibility (unused here)

    # ── Baseline reference minutes (minutes-of-day, ET) ──────────────────────
    # 3:50–3:55 PM on the prior trading day, captured minute-by-minute, so we can
    # compare which near-close minute is the steadiest baseline. 950 = 3:50 PM …
    # 955 = 3:55 PM.
    thursday_ref_minutes: list = field(
        default_factory=lambda: [950, 951, 952, 953, 954, 955])
    # Also evaluate the average of the 3:50–3:55 range as a 7th "baseline".
    include_avg_baseline: bool = True

    # ── Scan-day session window in minutes-of-day (ET) ───────────────────────
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
