#!/usr/bin/env python3
"""
EoD Options Analyzer — Test Runner
==================================

Run the full test suite with clear, readable pass/fail output.

Usage:
    python run_tests.py            # run everything (offline + live Alpaca)
    python run_tests.py --offline  # only offline logic (no network needed)
    python run_tests.py --live     # only live Alpaca data-pull tests

Notes:
  • Offline tests validate all math, dates, parsing, backtester payoff
    logic, and the trade logger. They run anywhere.
  • Live tests pull REAL data from Alpaca to confirm everything works with
    live feeds. They need ALPACA_API_KEY + ALPACA_API_SECRET in .env and
    network access to data.alpaca.markets. If unavailable, they SKIP (not
    fail) with a clear reason.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tests.harness import Suite, bold, cyan, yellow  # noqa: E402


def main() -> int:
    args = sys.argv[1:]
    run_offline = "--live" not in args
    run_live = "--offline" not in args

    suite = Suite("EoD OPTIONS ANALYZER  —  TEST SUITE")
    suite.banner()

    if run_offline:
        print()
        print(bold(cyan("══ OFFLINE TESTS (no network required) ══")))
        from tests import test_offline
        test_offline.run(suite)

    if run_live:
        print()
        print(bold(cyan("══ LIVE ALPACA TESTS (real data pulls) ══")))
        print(yellow("   Skipped automatically if credentials/network unavailable."))
        from tests import test_alpaca_live
        test_alpaca_live.run(suite)

    return suite.summary()


if __name__ == "__main__":
    sys.exit(main())
