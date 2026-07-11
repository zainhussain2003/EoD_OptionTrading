"""
Configuration for the 0DTE / short-dated option threshold-timing study.

This is a DESCRIPTIVE historical study — no live trading, no orders. For each
long option (call and put) we measure, over historical minute data, WHEN it
reaches a ladder of profit thresholds and HOW LONG that exit window stays open.

Everything a run needs is a plain dataclass field so the whole configuration is
easy to diff and reason about. Times are ET minutes-of-day (e.g. 09:35 = 575).
"""
from __future__ import annotations

from dataclasses import dataclass, field


def _mod(h: int, m: int) -> int:
    """ET hour:minute → minute-of-day."""
    return h * 60 + m


@dataclass
class Config:
    # ── Universe (Mag 7 + Oracle + AMD) ──────────────────────────────────────
    tickers: list = field(default_factory=lambda: [
        "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "ORCL", "AMD",
    ])

    # Expiry-cadence SANITY CHECK ONLY. The pipeline detects same-day-expiry
    # availability from the data itself (see core/expiry.py); these constants are
    # a fallback used only when a trade_date is absent from the dataset.
    daily_0dte_names: list = field(default_factory=lambda: [
        "AAPL", "NVDA", "TSLA", "AMZN", "META",
    ])
    mon_wed_fri_names: list = field(default_factory=lambda: ["MSFT", "GOOGL"])
    friday_weekly_names: list = field(default_factory=lambda: ["ORCL", "AMD"])

    # ── History window ───────────────────────────────────────────────────────
    lookback_days: int = 365            # ~12 months of sessions
    timezone: str = "America/New_York"

    # ── Threshold ladder T (percent) ─────────────────────────────────────────
    # Reported as fractions internally (0.20 == +20%).
    thresholds_pct: list = field(default_factory=lambda: [
        20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 100,
    ])
    # Targets the optimal-entry surface is ranked for.
    optimal_entry_targets_pct: list = field(default_factory=lambda: [30, 50, 75, 100])
    # Thresholds highlighted in the Mode-B narrative.
    highlight_pct: list = field(default_factory=lambda: [20, 30, 50])

    # ── Strike coverage per session ──────────────────────────────────────────
    # We fetch ATM ± strike_band strikes for each right, enough to fill the
    # ITM / ATM / OTM1 / OTM2+ moneyness buckets without pulling the whole chain.
    strike_band: int = 4

    # ── Entry sweep (ET minutes-of-day) ──────────────────────────────────────
    entry_start_min: int = _mod(9, 35)   # 09:35 ET
    entry_end_min: int = _mod(15, 30)    # 15:30 ET (inclusive)
    entry_step_min: int = 5              # candidate entry every 5 minutes
    session_close_min: int = _mod(16, 0)  # 16:00 ET — path built to here

    # entry_bucket granularity for grouping / optimizer windows (minutes).
    entry_bucket_min: int = 30

    # ── Fill modes (run BOTH) ────────────────────────────────────────────────
    #   mid    : mark = (bid+ask)/2, entry at mid.
    #   market : open at ask, close at bid  (long-option realism).
    fill_modes: list = field(default_factory=lambda: ["mid", "market"])

    # ── Mode C walk-forward ──────────────────────────────────────────────────
    train_weeks: int = 6
    test_weeks: int = 2
    expanding_window: bool = False      # False = rolling train window
    # MAX_EXIT_TIME: default = session close (hold to end if never hit).
    # Alternatives: ("fixed_minutes", N) or ("median_last_hold", None).
    max_exit_rule: tuple = ("session_close", None)
    min_test_trades: int = 30           # combos below this flagged unreliable

    # ── Guardrails ───────────────────────────────────────────────────────────
    min_bucket_n: int = 30              # buckets below this flagged low-sample

    # ── Data contract column names (configurable adapter target) ─────────────
    col_ts: str = "ts"
    col_symbol: str = "symbol"
    col_right: str = "right"
    col_strike: str = "strike"
    col_expiry: str = "expiry"
    col_bid: str = "bid"
    col_ask: str = "ask"
    col_underlying: str = "underlying"

    # ── Alpaca (paper / market-data, read-only) ──────────────────────────────
    alpaca_paper: bool = True
    option_feed: str = "indicative"     # historical option-quote feed
    risk_free_rate: float = 0.05        # kept for fetcher compatibility

    # ── Reproducibility ──────────────────────────────────────────────────────
    random_seed: int = 7

    # ── Convenience ──────────────────────────────────────────────────────────
    @property
    def thresholds(self) -> list:
        """Threshold ladder as fractions (0.20, 0.25, …)."""
        return [t / 100.0 for t in self.thresholds_pct]

    @property
    def entry_grid(self) -> list:
        """The 5-min candidate-entry minutes-of-day."""
        return list(range(self.entry_start_min, self.entry_end_min + 1, self.entry_step_min))
