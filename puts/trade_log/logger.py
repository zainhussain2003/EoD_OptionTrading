import csv
import os
from datetime import datetime

from models import TradeRecord

FIELDNAMES = [
    'date', 'ticker', 'strike', 'expiry', 'entry_time', 'exit_time',
    'premium_paid', 'exit_price', 'payoff', 'profitable', 'contract_symbol',
]


def log_trade(record: TradeRecord, csv_path: str = 'trades.csv') -> None:
    file_exists = os.path.isfile(csv_path)
    with open(csv_path, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            'date': record.date,
            'ticker': record.ticker,
            'strike': record.strike,
            'expiry': record.expiry,
            'entry_time': record.entry_time,
            'exit_time': record.exit_time,
            'premium_paid': record.premium_paid,
            'exit_price': record.exit_price,
            'payoff': record.payoff,
            'profitable': record.profitable,
            'contract_symbol': record.contract_symbol,
        })


def log_scan_targets(tickers_contracts: list[tuple], entry_time_str: str,
                     exit_time_str: str, csv_path: str = 'trades.csv') -> None:
    """Log all contracts shown in a scan session as pending trades."""
    from utils.date_utils import now_et
    today = now_et().strftime('%Y-%m-%d')

    for ticker, contract in tickers_contracts:
        record = TradeRecord(
            date=today,
            ticker=ticker,
            strike=contract.strike,
            expiry=str(contract.expiry),
            entry_time=entry_time_str,
            exit_time=exit_time_str,
            premium_paid=contract.mid_price,
            contract_symbol=contract.contract_symbol,
        )
        log_trade(record, csv_path)
