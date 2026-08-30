# Bracketology Football v2

Read-only football prediction-market analysis for Kalshi. Development occurs on
`codex/football-v2`; the production `main` service remains unchanged.

## Initial scope

- NFL and NCAA football
- Moneylines and point spreads
- Public Kalshi market data
- Consensus prices from The Odds API
- Paper tracking only
- No Kalshi credentials, account access, or order placement

## How value is estimated

The scanner matches an exact Kalshi contract to the corresponding sportsbook
game and market. It removes the two-way sportsbook vig at each bookmaker, takes
the median fair probability, and compares that result with the executable Kalshi
YES ask. A configurable cost buffer is deducted before an opportunity qualifies.

This is a screening method, not a guarantee of profit. Ambiguous team matches,
mismatched spread lines, missing prices, and comparisons supported by fewer than
two sportsbooks are rejected.

## Run a paper scan

From the football-v2 worktree, use the existing production virtual environment
until v2 receives its own deployment environment:

```bash
/home/vandal/bots/marchmadnessbot/.venv/bin/python football_board.py --sport all
```

Use `--no-save` for a connectivity test. Normal runs save raw snapshots and
comparisons to `data/football_v2.sqlite`, which is excluded from Git.

Defaults can be overridden without changing code:

- `FOOTBALL_MIN_NET_EDGE` defaults to `0.05`
- `KALSHI_COST_BUFFER` defaults to `0.02`

The cost buffer is deliberately conservative for paper testing. It is not a
substitute for Kalshi's actual transaction-fee calculation and execution price.

## Tests

```bash
/home/vandal/bots/marchmadnessbot/.venv/bin/python -m unittest discover -s tests -v
```

## Legacy production system

The files at the repository root remain the original MLB/NCAA basketball bot.
They continue to run from `/home/vandal/bots/marchmadnessbot` on `main` while
football-v2 is developed and validated separately.
