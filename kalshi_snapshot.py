"""Run from the dedicated Pacific midnight systemd timer; never places trades."""
from datetime import datetime, timezone

from football_v2.kalshi_account import AccountClient
from football_v2.kalshi_history import HISTORY_PATH, cutoff_for, record_snapshot


def main() -> int:
    try:
        started = datetime.now(timezone.utc)
        cutoff = cutoff_for(started)
        if (started-cutoff).total_seconds()>240:
            print('Snapshot skipped: outside Pacific midnight observation window.')
            return 1
        balance = AccountClient.from_env().get_balance()
        observed = datetime.now(timezone.utc)
        saved = record_snapshot(HISTORY_PATH,balance,observed,cutoff)
        print('Pacific daily snapshot saved.' if saved else 'Daily snapshot already exists; preserved.')
        return 0
    except Exception:
        # Never print HTTP response bodies, request URLs, credentials, or exception text.
        print('Daily snapshot failed. Check credentials, dependencies, connectivity, and database permissions.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
