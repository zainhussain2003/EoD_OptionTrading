from dataclasses import dataclass, field


@dataclass
class Config:
    # ── Tickers and their per-ticker percentage move thresholds ──────────────
    # The study asks, for each ticker and each scan day: starting from the prior
    # trading day's near-close price R, how often does the scan day touch
    # (R × (1 ± pct))? Each ticker is evaluated at several percentage levels so the
    # move is volatility-normalized and directly comparable across names.
    # Each list is independently editable.
    #
    # Basket and ladder follow the v2 run (TSLA + AAPL, dense percentage ladder),
    # not the original 5-ticker / 5-level study. The 11 v2 levels are carried over
    # UNCHANGED so every v2 row stays directly comparable:
    #   0.5% / 0.75% / 1.25% — dense sampling of the steep part of the curve,
    #                          where the hit rate falls fastest (mainly AAPL).
    #   3.5% / 4% / 5%       — the tail, which only TSLA reaches regularly.
    # Both tickers use the SAME ladder on purpose: TSLA saturates near 100% at the
    # low end and AAPL decays to ~0% at the high end, so each name still gets a
    # full curve and the two are read on one x-axis.
    #
    # NEW HERE — 7% / 10% / 15%. The v2 ladder stopped at 5%, which RIGHT-CENSORED
    # every larger move: any session past 5% was recorded as just "5%", however
    # much further it actually went. AAPL 2026-07-31 fell 9.84% and was logged as
    # 5% (understated by 4.84pp); 3 of 99 AAPL Fridays exceeded the old cap. The
    # true magnitude always survived in max_*_swing_pct, but the hit-rate curve —
    # the view used to pick a level — went artificially flat at the bottom
    # because the ladder stopped, not because the risk did. Adding rungs is purely
    # additive: it cannot change any existing level's hit rate, so v2
    # comparability is preserved exactly. Observed maxima over the v2 window were
    # ~12% (TSLA down), ~9.8% (AAPL down) and 24.8% (TSLA up), so 15% captures
    # nearly everything; read max_*_swing_pct for the rare move beyond it.
    ticker_pcts: dict = field(default_factory=lambda: {
        'TSLA': [0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.025, 0.03, 0.035,
                 0.04, 0.05, 0.07, 0.10, 0.15],
        'AAPL': [0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.025, 0.03, 0.035,
                 0.04, 0.05, 0.07, 0.10, 0.15],
    })

    # ── Scan days ─────────────────────────────────────────────────────────────
    # All five weekdays (v2 covered only Mon/Wed/Fri). Each scan day is analyzed
    # against the close of the trading day immediately before it:
    #   Monday ← prior Friday      (3 calendar days — spans the weekend)
    #   Tuesday ← Monday           (NEW)
    #   Wednesday ← Tuesday
    #   Thursday ← Wednesday       (NEW)
    #   Friday ← Thursday
    # Only Monday's baseline crosses a weekend; the other four are 1-day gaps and
    # so are directly comparable to each other. Results are reported one day after
    # another, then summarized in a combined per-ticker day-comparison table.
    scan_days: list = field(default_factory=lambda: [
        'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])

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
