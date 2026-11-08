# Kalshi reporting in the existing football bot

Extend the existing authorized
Telegram bot with /kalshi, /kalshiscores and /kalshihistory. Record balances at
midnight America/Los_Angeles, with DST-aware dates. Keep account history separate
from paper recommendations. Never place trades. Keep credentials on the server.

Approach: extend the existing bot with separate account,
score interpretation and history modules. Do not introduce a second Telegram
poller. Existing recommendation and final-only grading code stays unchanged.

Use signed GET requests to Kalshi and existing Odds API score credentials. Match
both teams, sport and Pacific game date conservatively; unmatched or ambiguous
games have no asserted score. Support positive YES and negative NO fractional
positions, moneyline, full-game spread and total; unsupported contracts keep their
original market description. Game scores are indications, not settlement proof.
Show source timestamps and label stale data. The Odds API does not document a
quarter/clock in its score schema, so do not invent them.

Record API cash and position valuation, observed time, and the intended daily
cutoff separately. Never backfill a missed midnight with the current balance.
Report raw account-value changes, not deposit-adjusted trading profit. Historical
balances begin when recording is activated; prior intraday observations in chat
are not end-of-day balances. No outgoing daily Telegram push is included: the
approved history command retrieves recorded values in the existing chat.

Configuration: the application's existing central env, KALSHI_API_KEY_ID and
KALSHI_PRIVATE_KEY_PATH. A migration helper can read the already-saved ID file
without printing it and back up central env before adding absent settings.
Private key file remains protected and is never committed. History SQLite lives
under the active Football V2 data directory. Midnight runs through a dedicated
systemd oneshot/timer. Preserve the service state until explicit activation.

Update server BOT_SYSTEM.md through a reviewed additive registry fragment at
activation; note the actual branch and service state. Server installation,
dependency installation in its shared interpreter and restart require final
approval. Tests and prepared GitHub branch are authorized now.
