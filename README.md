# EoD_OptionTrading

Systematic end-of-day (3–4 PM ET) 0DTE option trading research. This repository
combines three separate strategy lines, each kept in its own self-contained
directory:

| Directory         | Strategy                                                                                   |
|-------------------|--------------------------------------------------------------------------------------------|
| [`calls/`](calls/)                     | **Call options** — MWF (Mon/Wed/Fri) 0DTE call backtesting across the 3–4 PM window. |
| [`puts/`](puts/)                       | **Put options** — MWF (Mon/Wed/Fri) 0DTE put backtesting across the 3–4 PM window.   |
| [`thursday-friday/`](thursday-friday/) | **Thursday → Friday calls** — buy the ATM weekly call the day before expiry (3:55–3:59 PM) and measure the expiry-day session-high return probability. |

Each directory is a standalone project with its own `README.md`,
`requirements.txt`, and `.env.example`. See the README inside each directory for
setup and usage.

## Setup

Each strategy needs its own environment file. From within a strategy directory:

```bash
pip install -r requirements.txt
cp .env.example .env        # add your ALPACA_API_KEY + ALPACA_API_SECRET
```

> **Note:** `.env` files are git-ignored in every directory. Never commit real
> API keys.
