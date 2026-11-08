# Read-only Kalshi reporting

Commands added to the existing authorized Telegram poller:

| Command | Report |
| --- | --- |
| `/kalshi` | Cash, API positions valuation, total account value, open holdings |
| `/kalshiscores` | Holdings sorted live first, football scores and YES/NO comparisons |
| `/kalshihistory` | Saved Pacific daily observations and account value changes |

No orders or transfers are implemented. Existing paper scan/grading databases are unchanged. Supported comparisons are full-game NFL and college football winner, spread, and total contracts with recognized descriptions. Other contracts stay visible without a computed comparison. Matching requires both teams, sport and Pacific game date; ambiguous matches are withheld. Scores older than three minutes or without update times cannot establish a current comparison. Scores do not prove settlement. The score provider does not supply quarter/clock.

## Configuration and installation review

This is prepared source, not an active server installation. Obtain approval before deployment, service start/restart, or timer activation. Read the deployment's current ownership registry and local instructions first. Confirm service user, entry point, interpreter, central configuration, outputs, and impact on other systems. Back up source, configuration, registry, existing units, and databases before changes. Preserve current active/inactive states.

Keep server addresses, usernames, bot/chat identities, private-key locations and account data out of public changes. Record actual deployment values only in the protected server registry.

Check the server's clean git status, remote, branch and commit against the reviewed Football V2 base. Resolve any discrepancy before advancing the checkout; do not reset or overwrite local edits. This feature targets `codex/football-v2`, not the repository's older `main`. Record the exact reviewed and deployed commits.

Install the reviewed requirements with the existing bot interpreter, accounting for other services sharing that interpreter. Run `python -m pip check` and `python -m unittest discover -s tests -v` there. Preserve existing Telegram and Odds API configuration. Extend the existing poller; never start a second poller using its token.

The new client reads `KALSHI_API_KEY_ID` and `KALSHI_PRIVATE_KEY_PATH` after the application's established central env loader. An RSA PEM must remain outside the repository, owner-only on POSIX. Do not publish env files, private keys or account databases. To migrate an already saved API key ID without printing it, run:

```sh
python scripts/configure_kalshi.py --env "$CENTRAL_ENV" --id-file "$SAVED_ID_FILE" --key-file "$PRIVATE_KEY_FILE"
```

Supply those paths locally. The helper validates the UUID ID and key permissions, refuses differing existing settings, creates a mode 600 backup, and atomically adds only absent settings. It preserves unrelated text; the replacement env is mode 600 owned by the caller. Confirm all existing consumers have suitable access and review any other processes modifying the central env before running. Original saved credential files are not deleted.

Use the service interpreter to manually compare `build_account_report()` with the account website. Test `build_scores_report()` against actual holdings. Do not log credentials or raw HTTP exceptions. Unit tests use fixtures; account-specific authentication and feed matching require this server check. Successful scores are cached for 60 seconds; fetching NFL/NCAAF scores consumes existing Odds API credits.

## Midnight history activation

Create the deployment's `data` directory, owner-only. Render `deploy/kalshi-daily-snapshot.service.in` locally by substituting `@BOT_USER@`, `@BOT_DIR@`, and `@BOT_PYTHON@` with the approved service user, absolute repository path and absolute interpreter path. Properly quote paths if needed for systemd. Inspect the result before installing it as `kalshi-daily-snapshot.service` alongside the supplied timer. Keep rendered units private.

Verify both units using `systemd-analyze verify` and the schedule with `systemd-analyze calendar '*-*-* 00:00:00 America/Los_Angeles'`. After approval, reload systemd, activate the existing bot once and enable/start the new timer. Confirm all seven commands work in the approved Telegram chat and account information is inaccessible elsewhere. Inspect the next timer trigger in Pacific time and verify the first successful midnight run.

The timer observes midnight `America/Los_Angeles`, including DST. It allows five minutes of receipt latency, stores the preceding Pacific date plus cutoff and actual observation time, and never overwrites that date. `Persistent=false` prevents misleading late catch-up. Missing days are not filled using current balances; history before activation cannot be reconstructed by this recorder. Changes are raw account-value changes, not deposit-adjusted trading profit. Midnight observations approximate the prior day close.

History lives in `data/kalshi_account.sqlite`, separate from paper tracking. Add it to protected backup procedures. The snapshot process exits nonzero on failure; monitor the new unit's journal. No daily Telegram push is added. A manual daytime snapshot attempt is refused.

Update the protected server ownership registry with the three commands, same existing poller/chat, read-only account access, central-env setting names and private key path, separate history database, snapshot entry point, new unit names/schedule, Odds API usage, backups, deployed SHA/branch and actual activation state. Retain all paper scan/grading ownership entries.

## Rollback

After approval, disable/stop only the new timer and restore the previous reviewed code and units. Restore the bot's explicitly recorded prior active/inactive state. Preserve protected key/history files. Do not overwrite a shared central env from an old backup after other bots have edited it; review only the two added Kalshi settings. Update the registry to reflect the actual result. Do not alter paper databases.

References: [Kalshi authentication](https://docs.kalshi.com/getting_started/quick_start_authenticated_requests), [balance](https://docs.kalshi.com/api-reference/portfolio/get-balance), [positions](https://docs.kalshi.com/api-reference/portfolio/get-positions), [Odds API scores](https://the-odds-api.com/liveapi/guides/v4/#get-scores).
