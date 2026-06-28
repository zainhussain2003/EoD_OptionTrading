"""Offline tests — no network needed. Validates all math, dates, parsing,
backtester payoff logic, and the trade logger/reporter round-trip.

These run anywhere. The live Alpaca tests are in test_alpaca_live.py.
"""
import math
import os
import tempfile
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pandas as pd

from tests.harness import Suite

UTC = ZoneInfo("UTC")
ET = ZoneInfo("America/New_York")


def run(suite: Suite) -> None:
    _test_black_scholes(suite)
    _test_probability(suite)
    _test_dates_and_symbols(suite)
    _test_backtester_math(suite)
    _test_data_provenance(suite)
    _test_alpaca_parsing(suite)
    _test_logger_reporter(suite)


# ──────────────────────────────────────────────────────────────────────────
def _test_black_scholes(suite: Suite) -> None:
    from utils.math_utils import black_scholes_call, norm_cdf

    with suite.section("Black-Scholes Math (vs known reference values)") as s:
        # Reference: S=100,K=100,T=1,r=0,sigma=0.2 -> call=7.9656, delta=0.5398
        p, d, _, _ = black_scholes_call(100, 100, 1.0, 0.0, 0.2)
        s.check("ATM 1yr call price = 7.9656 (textbook value)",
                abs(p - 7.9656) < 0.01, f"got {p:.4f}")
        s.check("ATM 1yr call delta = 0.5398",
                abs(d - 0.5398) < 0.01, f"got {d:.4f}")

        s.check("norm_cdf(0) = 0.5", abs(norm_cdf(0) - 0.5) < 1e-9)
        s.check("norm_cdf(1.96) = 0.975", abs(norm_cdf(1.96) - 0.975) < 0.001)

        # Edge: expiry now (T=0) -> intrinsic value only
        p, d, _, _ = black_scholes_call(105, 100, 0.0, 0.05, 0.3)
        s.check("T=0 ITM call = intrinsic 5.0, delta 1.0", p == 5.0 and d == 1.0)
        p, d, _, _ = black_scholes_call(95, 100, 0.0, 0.05, 0.3)
        s.check("T=0 OTM call = 0.0, delta 0.0", p == 0.0 and d == 0.0)

        # Edge: zero volatility
        p, _, _, _ = black_scholes_call(105, 100, 0.5, 0.05, 0.0)
        s.check("sigma=0 returns intrinsic (no crash)", p == 5.0)

        # Edge: zero/negative underlying
        p, d, _, _ = black_scholes_call(0, 100, 0.5, 0.05, 0.3)
        s.check("S=0 handled gracefully", p == 0.0 and d == 0.0)

        # Deep ITM/OTM delta bounds
        _, d_itm, _, _ = black_scholes_call(1000, 100, 0.02, 0.05, 0.5)
        _, d_otm, _, _ = black_scholes_call(50, 100, 0.02, 0.05, 0.5)
        s.check("Deep ITM delta ~ 1.0", d_itm > 0.99, f"got {d_itm:.4f}")
        s.check("Deep OTM delta ~ 0.0", d_otm < 0.01, f"got {d_otm:.4f}")


def _test_probability(suite: Suite) -> None:
    from utils.math_utils import calc_pop, calc_theta_hourly, realized_vol

    with suite.section("Probability of Profit & Theta") as s:
        pop = calc_pop(100, 100, 2.0, 0.1, 0.05, 0.3)
        s.check("PoP with premium < 0.5 (breakeven above strike)",
                pop < 0.5, f"got {pop:.4f}")
        s.check("PoP T=0 below breakeven = 0.0",
                calc_pop(100, 100, 2.0, 0.0, 0.05, 0.3) == 0.0)
        s.check("PoP T=0 above breakeven = 1.0",
                calc_pop(105, 100, 2.0, 0.0, 0.05, 0.3) == 1.0)

        th = calc_theta_hourly(100, 100, 0.1, 0.05, 0.3)
        s.check("Theta/hour is negative (decay cost)", th < 0, f"got {th:.4f}")
        s.check("Theta/hour T=0 = 0 (no crash)",
                calc_theta_hourly(100, 100, 0.0, 0.05, 0.3) == 0.0)

        rv = realized_vol([100, 101], window=20)
        s.check("Realized vol too-short series falls back to 0.30", rv == 0.30)
        steady = [100 * math.exp(0.005 * i) for i in range(30)]
        rv2 = realized_vol(steady)
        s.check("Realized vol computes on 30-point series (>=0)", rv2 >= 0)


def _test_dates_and_symbols(suite: Suite) -> None:
    from utils.date_utils import (
        get_past_mwf_dates, get_next_mwf_dates, compute_T,
        format_contract_symbol, get_atm_strikes, minute_to_str,
        window_start_utc, window_end_utc,
    )

    with suite.section("Dates, OCC Symbols & Strike Selection") as s:
        past = get_past_mwf_dates(30)
        s.check("All past dates are Mon/Wed/Fri",
                all(d.weekday() in {0, 2, 4} for d in past))
        s.check("Past dates sorted ascending (oldest first)", past == sorted(past))

        nxt = get_next_mwf_dates(3)
        s.check("Next 3 MWF dates are all M/W/F",
                len(nxt) == 3 and all(d.weekday() in {0, 2, 4} for d in nxt))

        # OCC contract symbol format
        sym = format_contract_symbol("AAPL", date(2026, 6, 16), 212.50)
        s.check("OCC symbol AAPL 212.50 = AAPL260616C00212500",
                sym == "AAPL260616C00212500", sym)
        sym2 = format_contract_symbol("NVDA", date(2026, 1, 3), 130.0)
        s.check("OCC symbol NVDA 130.00 = NVDA260103C00130000",
                sym2 == "NVDA260103C00130000", sym2)
        symp = format_contract_symbol("MSFT", date(2026, 6, 12), 415.0, "P")
        s.check("OCC put symbol MSFT 415 = MSFT260612P00415000",
                symp == "MSFT260612P00415000", symp)

        # ATM strikes bracket the spot
        lo, hi = get_atm_strikes(213.60)
        s.check("ATM strikes bracket spot 213.60 -> (212.5, 215.0)",
                lo == 212.5 and hi == 215.0, f"({lo},{hi})")
        lo2, hi2 = get_atm_strikes(131.40)
        s.check("ATM strikes bracket spot 131.40 -> (130.0, 135.0)",
                lo2 == 130.0 and hi2 == 135.0, f"({lo2},{hi2})")

        # compute_T edges
        s.check("compute_T after close = 0.0",
                compute_T(date(2026, 6, 12),
                          datetime(2026, 6, 12, 16, 30, tzinfo=ET)) == 0.0)
        floor = 1.0 / (252.0 * 6.5 * 4.0)
        Tf = compute_T(date(2026, 6, 12),
                       datetime(2026, 6, 12, 15, 59, 59, tzinfo=ET))
        s.check("compute_T near expiry respects 15-min floor", Tf >= floor * 0.99)

        # minute formatting
        s.check("minute_to_str(915) = '3:15 PM'", minute_to_str(915) == "3:15 PM")
        s.check("minute_to_str(959) = '3:59 PM'", minute_to_str(959) == "3:59 PM")

        # DST-aware UTC window conversion
        ws_jun = window_start_utc(date(2026, 6, 12))   # EDT -> 19:00 UTC
        ws_jan = window_start_utc(date(2026, 1, 7))    # EST -> 20:00 UTC
        s.check("June 3PM ET -> 19:00 UTC (EDT handled)", ws_jun.hour == 19)
        s.check("Jan 3PM ET -> 20:00 UTC (EST handled)", ws_jan.hour == 20)


def _test_backtester_math(suite: Suite) -> None:
    from config import Config
    from analysis.backtester import Backtester
    import analysis.backtester as bt

    class MockFetcher:
        """Returns a known option price series for every strike so we can
        verify payoff/win-rate arithmetic by hand."""
        def __init__(self, series):
            self.series = series

        def fetch_historical_stock_bars(self, ticker, start, end, minutes=5):
            idx = [start + timedelta(minutes=i) for i in range(60)]
            c = [100.0] * 60
            return pd.DataFrame(
                {"open": c, "high": c, "low": c, "close": c, "volume": [1000] * 60},
                index=pd.to_datetime(idx, utc=True))

        def fetch_historical_option_bars(self, sym, start, end):
            idx = [start + timedelta(minutes=i) for i in range(60)]
            c = [self.series[900 + i] for i in range(60)]
            return pd.DataFrame(
                {"open": c, "high": c, "low": c, "close": c, "volume": [10] * 60},
                index=pd.to_datetime(idx, utc=True))

    cfg = Config()
    cfg.tickers = ["TEST"]
    orig = bt.get_past_mwf_dates
    bt.get_past_mwf_dates = lambda days: [date(2026, 6, 1), date(2026, 6, 3),
                                          date(2026, 6, 5)]

    try:
        with suite.section("Backtester Payoff & Win-Rate (synthetic series)") as s:
            # Monotonically rising option price 1.00 -> 2.00
            up = {900 + i: 1.00 + (i / 55.0) for i in range(60)}
            res = Backtester(MockFetcher(up), cfg).run(["TEST"])[0]
            s.check("Rising market: 100% win rate", res.win_rate == 1.0,
                    f"got {res.win_rate:.0%}")
            s.check("Rising market: optimal entry = earliest (3:00 PM)",
                    res.best_entry_minute == 900)
            best = [p for p in res.all_pairs
                    if p.entry_minute == 900 and p.exit_minute == 955][0]
            s.check("Buy 3:00 / Sell 3:55 payoff = +1.00 (exact)",
                    abs(best.avg_payoff - 1.00) < 0.001, f"got {best.avg_payoff:.4f}")
            s.check("Sample count = 6 (3 dates × 2 ATM strikes)",
                    best.n_trades == 6, f"got {best.n_trades}")

            # Monotonically falling price 2.00 -> 1.00
            down = {900 + i: 2.00 - (i / 55.0) for i in range(60)}
            res2 = Backtester(MockFetcher(down), cfg).run(["TEST"])[0]
            s.check("Falling market: 0% win rate across all pairs",
                    max(p.win_rate for p in res2.all_pairs) == 0.0)

            # Flat then a mid-window spike
            mixed = {900 + i: (1.0 if 900 + i < 930 else 1.5) for i in range(60)}
            res3 = Backtester(MockFetcher(mixed), cfg).run(["TEST"])[0]
            ba = [p for p in res3.all_pairs
                  if p.entry_minute < 930 and p.exit_minute >= 930]
            s.check("Spike scenario: pre-spike buy / post-spike sell = +0.50, 100% win",
                    all(abs(p.avg_payoff - 0.5) < 1e-6 and p.win_rate == 1.0
                        for p in ba))

            # Statistical floor: <3 samples is filtered out
            bt.get_past_mwf_dates = lambda days: [date(2026, 6, 1)]
            res4 = Backtester(MockFetcher(up), cfg).run(["TEST"])[0]
            s.check("Single date (2 samples) filtered by 3-sample minimum",
                    len(res4.all_pairs) == 0)
    finally:
        bt.get_past_mwf_dates = orig


def _test_data_provenance(suite: Suite) -> None:
    """Verify the backtester correctly labels REAL vs SIMULATED data sources."""
    from config import Config
    from analysis.backtester import Backtester
    import analysis.backtester as bt

    class RealOnly:
        def fetch_historical_stock_bars(self, ticker, start, end, minutes=5):
            idx = [start + timedelta(minutes=i) for i in range(60)]
            c = [100.0 + 0.1 * i for i in range(60)]
            return pd.DataFrame({"open": c, "high": c, "low": c, "close": c,
                                 "volume": [1000] * 60}, index=pd.to_datetime(idx, utc=True))
        def fetch_historical_option_bars(self, sym, start, end):
            idx = [start + timedelta(minutes=i) for i in range(60)]
            c = [1.0 + 0.02 * i for i in range(60)]
            return pd.DataFrame({"open": c, "high": c, "low": c, "close": c,
                                 "volume": [10] * 60}, index=pd.to_datetime(idx, utc=True))

    class SimOnly(RealOnly):
        def fetch_historical_option_bars(self, sym, start, end):
            return None  # forces Black-Scholes simulation
        def get_daily_closes(self, ticker, days=40):
            return [100.0 + 0.5 * i for i in range(40)]

    class NoStock:
        def fetch_historical_stock_bars(self, ticker, start, end, minutes=5):
            return None
        def fetch_historical_option_bars(self, sym, start, end):
            return None

    cfg = Config()
    cfg.tickers = ["T"]
    orig = bt.get_past_mwf_dates
    bt.get_past_mwf_dates = lambda days: [date(2026, 6, 1), date(2026, 6, 3),
                                          date(2026, 6, 5)]
    try:
        with suite.section("Data Provenance Tracking (REAL vs SIMULATED)") as s:
            r = Backtester(RealOnly(), cfg).run(["T"])[0]
            s.check("Real option bars -> primary_source = 'REAL'",
                    r.primary_source == "REAL", r.primary_source)
            s.check("Real path: 6 real pulls, 0 simulated",
                    r.n_real_pulls == 6 and r.n_sim_pulls == 0,
                    f"{r.n_real_pulls}/{r.n_sim_pulls}")

            sim = Backtester(SimOnly(), cfg).run(["T"])[0]
            s.check("No option bars -> primary_source = 'SIMULATED'",
                    sim.primary_source == "SIMULATED", sim.primary_source)
            s.check("Sim path records the volatility used",
                    sim.sim_sigma > 0, f"σ={sim.sim_sigma:.3f}")
            s.check("Sim path: 0 real pulls, 6 simulated",
                    sim.n_real_pulls == 0 and sim.n_sim_pulls == 6)

            nd = Backtester(NoStock(), cfg).run(["T"])[0]
            s.check("No stock bars -> primary_source = 'NONE'",
                    nd.primary_source == "NONE", nd.primary_source)
            s.check("No-data path: all 3 dates skipped",
                    nd.n_skipped_dates == 3, f"{nd.n_skipped_dates}")

            s.check("pull_details captures every (date, strike) pull",
                    len(r.pull_details) == 6, f"{len(r.pull_details)}")
    finally:
        bt.get_past_mwf_dates = orig


def _test_alpaca_parsing(suite: Suite) -> None:
    """Verify the Alpaca snapshot/bar parsing path WITHOUT network, using
    mock objects shaped like real Alpaca responses."""
    from data.alpaca_fetcher import AlpacaFetcher, ALPACA_AVAILABLE
    from analysis.backtester import Backtester
    from config import Config

    with suite.section("Alpaca Response Parsing (mocked objects)") as s:
        if not ALPACA_AVAILABLE:
            s.skip("alpaca-py not installed", "pip install alpaca-py")
            return

        # Build a fetcher without real credentials by bypassing __init__
        f = AlpacaFetcher.__new__(AlpacaFetcher)

        def snap(bid, ask, iv, vol, oi, delta, theta, under):
            return SimpleNamespace(
                latest_quote=SimpleNamespace(bid_price=bid, ask_price=ask),
                implied_volatility=iv, volume=vol, open_interest=oi,
                greeks=SimpleNamespace(delta=delta, theta=theta),
                underlying_price=under)

        chain = {
            "AAPL260616C00212500": snap(1.38, 1.52, 0.41, 1200, 5000, 0.51, -1.9, 213.6),
            "AAPL260616C00215000": snap(0.62, 0.72, 0.50, 800, 3000, 0.31, -1.2, 213.6),
            "AAPL260616C00210000": snap(0.0, 0.0, 0.0, 0, 0, 0, 0, 213.6),  # no market
        }
        f._option_client = SimpleNamespace(get_option_chain=lambda req: chain)
        contracts = f.fetch_option_chain("AAPL", date(2026, 6, 16))

        s.check("No-market contract (bid=ask=0) skipped", len(contracts) == 2,
                f"got {len(contracts)}")
        c = {round(x.strike, 1): x for x in contracts}
        s.check("Strike parsed from OCC symbol (212.5 present)", 212.5 in c)
        s.check("Mid price = (bid+ask)/2 = 1.45",
                abs(c[212.5].mid_price - 1.45) < 0.001, f"got {c[212.5].mid_price}")
        s.check("Theta/hour = theta/6.5",
                abs(c[212.5].theta_hourly - (-1.9 / 6.5)) < 0.001)
        s.check("ITM flag correct (212.5 < spot 213.6 = ITM)",
                c[212.5].in_the_money is True)
        s.check("OTM flag correct (215.0 > spot 213.6 = OTM)",
                c[215.0].in_the_money is False)

        # UTC -> ET minute bucketing
        base = datetime(2026, 6, 10, 19, 0, tzinfo=UTC)  # 19:00 UTC = 3:00 PM EDT
        idx = [base + timedelta(minutes=i) for i in range(6)]
        df = pd.DataFrame(
            {"open": [1] * 6, "high": [1] * 6, "low": [1] * 6,
             "close": [1.0, 1.1, 1.2, 1.3, 1.4, 1.5], "volume": [10] * 6},
            index=pd.to_datetime(idx, utc=True))
        mp = Backtester(f, Config())._bars_to_minute_prices(df)
        s.check("Bar at 19:00 UTC -> minute 900 (3:00 PM ET)", mp.get(900) == 1.0)
        s.check("Bar at 19:05 UTC -> minute 905 = 1.5", mp.get(905) == 1.5)


def _test_logger_reporter(suite: Suite) -> None:
    from models import TradeRecord, OptionContract
    from trade_log.logger import log_trade, log_scan_targets
    from trade_log.reporter import load_trades

    with suite.section("Trade Logger & Reporter Round-Trip") as s:
        tmp = tempfile.mktemp(suffix=".csv")
        try:
            recs = [
                TradeRecord("2026-06-01", "AAPL", 212.5, "2026-06-01",
                            "3:15 PM", "3:50 PM", 1.45, "S", 2.10, 0.65, True),
                TradeRecord("2026-06-03", "NVDA", 130.0, "2026-06-03",
                            "3:15 PM", "3:50 PM", 1.00, "S", 0.70, -0.30, False),
            ]
            for r in recs:
                log_trade(r, tmp)
            loaded = load_trades(tmp)
            s.check("Wrote 2, loaded 2", len(loaded) == 2)
            s.check("Boolean 'profitable' round-trips True/False",
                    loaded[0]["profitable"] is True and loaded[1]["profitable"] is False)
            s.check("Float 'payoff' round-trips exactly",
                    abs(loaded[0]["payoff"] - 0.65) < 1e-9)

            with open(tmp) as fh:
                lines = fh.readlines()
            s.check("CSV header written exactly once",
                    lines.count(lines[0]) == 1)

            os.remove(tmp)
            c = OptionContract("AAPL", "AAPL260612C00212500", 212.5,
                               date(2026, 6, 12), 1.38, 1.52, 1.45, 1200, 5000,
                               0.41, 0.51, -0.29, True)
            log_scan_targets([("AAPL", c)], "3:15 PM", "3:50 PM", tmp)
            pending = load_trades(tmp)
            s.check("Scan target logged with payoff=0 (pending outcome)",
                    len(pending) == 1 and pending[0]["payoff"] == 0.0)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
