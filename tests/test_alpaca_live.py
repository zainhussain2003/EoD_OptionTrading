"""LIVE Alpaca tests — these hit the real Alpaca API and require:
  1. ALPACA_API_KEY + ALPACA_API_SECRET in your .env
  2. Network access to data.alpaca.markets (NOT available in the sandbox,
     but works on your local machine)
  3. Options data enabled on your Alpaca account

They validate that real data pulls work end-to-end and that the formatting
is correct, so the backtest results will be accurate.

If credentials/network/options-entitlement are missing, each check is
SKIPPED with a clear reason — the suite will not hard-fail.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from tests.harness import Suite

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

# Reasonable sanity ranges so we catch garbage data (prices of 0 or 99999)
PRICE_RANGES = {
    "AAPL": (50, 1000),
    "NVDA": (20, 1000),
    "TSLA": (50, 2000),
    "MSFT": (100, 2000),
}


def run(suite: Suite) -> None:
    fetcher, reason = _get_fetcher()

    with suite.section("Alpaca Connectivity & Credentials") as s:
        if fetcher is None:
            s.skip("Alpaca fetcher unavailable", reason)
            s.info("Action", "Add ALPACA_API_KEY + ALPACA_API_SECRET to .env "
                             "and run locally (sandbox blocks Alpaca)")
            return
        s.check("Credentials loaded and client constructed", True)

    _test_spot_prices(suite, fetcher)
    _test_live_option_chain(suite, fetcher)
    _test_historical_stock_bars(suite, fetcher)
    _test_historical_option_bars(suite, fetcher)
    _test_mini_backtest(suite, fetcher)


def _get_fetcher():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    try:
        from data.alpaca_fetcher import AlpacaFetcher, ALPACA_AVAILABLE
    except Exception as e:
        return None, f"import error: {e}"
    if not ALPACA_AVAILABLE:
        return None, "alpaca-py not installed"
    fetcher = AlpacaFetcher.from_env()
    if fetcher is None:
        return None, "missing/invalid ALPACA_API_KEY or ALPACA_API_SECRET"
    # Probe one call to detect network/entitlement issues early
    try:
        fetcher.fetch_spot_price("AAPL")
    except Exception as e:
        msg = str(e)
        if "allowlist" in msg or "egress" in msg:
            return None, "network blocked (run locally, not in sandbox)"
        return None, f"probe failed: {msg[:80]}"
    return fetcher, ""


def _test_spot_prices(suite: Suite, fetcher) -> None:
    with suite.section("Live Spot Prices (real-time quotes)") as s:
        for ticker, (lo, hi) in PRICE_RANGES.items():
            try:
                spot = fetcher.fetch_spot_price(ticker)
                s.info(f"{ticker} spot", f"${spot:.2f}")
                s.check(f"{ticker} price is a sane number (${lo}-${hi})",
                        lo < spot < hi, f"got ${spot:.2f}")
            except Exception as e:
                s.check(f"{ticker} spot fetch", False, str(e)[:80])


def _test_live_option_chain(suite: Suite, fetcher) -> None:
    from datetime import date
    from utils.date_utils import get_next_mwf_dates

    with suite.section("Live Option Chain (strikes, IV, greeks)") as s:
        today = date.today()
        expiries = get_next_mwf_dates(3)
        ticker = "AAPL"
        chain = None
        used_expiry = None
        for exp in expiries:
            try:
                c = fetcher.fetch_option_chain(ticker, exp)
                if c:
                    chain, used_expiry = c, exp
                    break
            except Exception as e:
                s.info("chain error", str(e)[:80])

        if not chain:
            s.skip("No option chain returned for next 3 MWF expiries",
                   "account may lack options entitlement, or market closed")
            return

        s.info("Expiry used", str(used_expiry))
        s.info("Contracts returned", len(chain))
        sample = chain[len(chain) // 2]
        s.info("Sample contract", sample.contract_symbol or f"{ticker} {sample.strike}")
        s.info("  strike / mid", f"${sample.strike} / ${sample.mid_price:.2f}")
        s.info("  IV / delta", f"{sample.implied_volatility:.1%} / {sample.delta:.3f}")

        s.check("Chain has contracts", len(chain) > 0)
        s.check("All strikes positive", all(c.strike > 0 for c in chain))
        s.check("All mids non-negative", all(c.mid_price >= 0 for c in chain))

        has_iv = any(c.implied_volatility > 0 for c in chain)
        if used_expiry == today:
            # Same-day (0DTE) expiry: Alpaca does not compute Greeks after/near market
            # close — IV=0 is expected and not a data problem.
            if has_iv:
                s.check("IV values present (same-day expiry, greeks still live)", True)
            else:
                s.info("IV / delta = 0 on same-day expiry",
                       "expected — Alpaca drops Greeks for 0DTE after market close; "
                       "bid/ask/mid prices are still valid for scanning")
        else:
            s.check("At least some IV values present (>0)", has_iv)

        s.check("Bid <= Ask for all quoted contracts",
                all(c.bid <= c.ask for c in chain if c.ask > 0))


def _test_historical_stock_bars(suite: Suite, fetcher) -> None:
    from utils.date_utils import get_past_mwf_dates, window_start_utc, window_end_utc

    with suite.section("Historical Stock Bars (3-4 PM window)") as s:
        past = get_past_mwf_dates(30)
        if not past:
            s.skip("No past MWF dates found", "")
            return

        got = False
        for mwf in reversed(past):  # most recent first
            start = window_start_utc(mwf)
            end = window_end_utc(mwf)
            try:
                bars = fetcher.fetch_historical_stock_bars("AAPL", start, end, minutes=1)
            except Exception as e:
                s.info("bar error", str(e)[:80])
                continue
            if bars is not None and not bars.empty:
                s.info("Date sampled", str(mwf))
                s.info("Bars in 3-4 PM window", len(bars))
                s.info("First close", f"${float(bars['close'].iloc[0]):.2f}")
                s.info("Last close", f"${float(bars['close'].iloc[-1]):.2f}")
                s.check("Stock bars returned for a past MWF window", True)
                s.check("Bars have OHLCV columns",
                        all(col in bars.columns
                            for col in ["open", "high", "low", "close", "volume"]))
                s.check("All closes positive", (bars["close"] > 0).all())
                got = True
                break
        if not got:
            s.skip("No historical stock bars in any recent MWF window",
                   "check data feed entitlement (IEX vs SIP)")


def _test_historical_option_bars(suite: Suite, fetcher) -> None:
    """THE critical test for backtest accuracy: real historical option bars."""
    from utils.date_utils import (
        get_past_mwf_dates, window_start_utc, window_end_utc,
        get_atm_strikes, format_contract_symbol,
    )

    with suite.section("Historical Option Bars (★ backtest accuracy)") as s:
        past = get_past_mwf_dates(45)
        if not past:
            s.skip("No past MWF dates", "")
            return

        found = False
        for mwf in reversed(past):
            start = window_start_utc(mwf)
            end = window_end_utc(mwf)
            try:
                stock = fetcher.fetch_historical_stock_bars("AAPL", start, end, minutes=1)
            except Exception:
                continue
            if stock is None or stock.empty:
                continue
            spot = float(stock["close"].iloc[0])
            lo, hi = get_atm_strikes(spot)
            for strike in (lo, hi):
                # 0DTE: the contract expires on the same MWF date
                sym = format_contract_symbol("AAPL", mwf, strike)
                try:
                    opt = fetcher.fetch_historical_option_bars(sym, start, end)
                except Exception as e:
                    s.info("option bar error", str(e)[:80])
                    opt = None
                if opt is not None and not opt.empty:
                    s.info("Contract", sym)
                    s.info("Spot at 3 PM", f"${spot:.2f}")
                    s.info("Option bars in window", len(opt))
                    s.info("Option open / close",
                           f"${float(opt['close'].iloc[0]):.2f} -> "
                           f"${float(opt['close'].iloc[-1]):.2f}")
                    s.check("Real historical option bars retrieved", True)
                    s.check("Option prices non-negative", (opt["close"] >= 0).all())
                    s.check("Multiple intraday bars (can simulate entry/exit)",
                            len(opt) >= 2)
                    found = True
                    break
            if found:
                break

        if not found:
            s.skip("No historical OPTION bars retrieved",
                   "backtest will use Black-Scholes simulation fallback instead "
                   "of real prices — enable options historical data on Alpaca")


def _test_mini_backtest(suite: Suite, fetcher) -> None:
    """Run the real backtester on 1 ticker over a short window end-to-end."""
    from config import Config
    from analysis.backtester import Backtester

    with suite.section("End-to-End Mini Backtest (AAPL, real data)") as s:
        cfg = Config()
        cfg.tickers = ["AAPL"]
        cfg.backtest_days = 20
        try:
            result = Backtester(fetcher, cfg).run(["AAPL"])[0]
        except Exception as e:
            s.check("Backtest ran without crashing", False, str(e)[:100])
            return

        s.info("Dates analyzed", result.n_dates)
        s.info("Entry/exit pairs evaluated", len(result.all_pairs))
        s.info("Data source verdict", result.primary_source)
        s.info("  real option-bar pulls", result.n_real_pulls)
        s.info("  simulated (BS) pulls", result.n_sim_pulls)
        s.info("  skipped dates (no stock)", result.n_skipped_dates)
        if result.all_pairs:
            from utils.date_utils import minute_to_str
            s.info("Optimal entry", minute_to_str(result.best_entry_minute))
            s.info("Optimal exit", minute_to_str(result.best_exit_minute))
            s.info("Win rate", f"{result.win_rate:.1%}")
            s.info("Avg payoff", f"${result.avg_payoff:+.3f}")

        s.check("Backtest completed end-to-end", True)
        s.check("At least one date was analyzed", result.n_dates > 0)
        if result.primary_source == "REAL":
            s.check("Backtest uses REAL Alpaca option prices (most accurate)", True)
        elif result.primary_source == "MIXED":
            s.check("Backtest uses MIXED real + simulated prices", True,
                    f"{result.n_real_pulls} real / {result.n_sim_pulls} sim")
        elif result.primary_source == "SIMULATED":
            s.skip("Backtest used Black-Scholes simulation only",
                   "no real option bars — enable Alpaca options history for accuracy")
        if result.all_pairs:
            s.check("Win rate is a valid probability [0,1]",
                    0.0 <= result.win_rate <= 1.0)
            s.check("Entry time is before exit time",
                    result.best_entry_minute < result.best_exit_minute)
            s.check("All pairs have >= 3 samples (statistical floor)",
                    all(p.n_trades >= 3 for p in result.all_pairs))
        else:
            s.skip("No valid entry/exit pairs",
                   "insufficient historical data in the window")
