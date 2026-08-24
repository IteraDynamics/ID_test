#!/usr/bin/env bash
# Cron-safe wrapper for scripts/log_cde_live_funding_rate.py.
#
# - flock prevents two overlapping runs (e.g. a slow network call still in flight when the
#   next hourly tick fires) from racing on the same CSV.
# - stdout/stderr always go to a log file, so a failure is visible on inspection without
#   depending on cron's mail delivery being configured on this box.
# - exits non-zero on real failure (so `echo $?` / log inspection reflects reality), but never
#   throws an unhandled exception that could look like a crash in the log -- log_cde_live_
#   funding_rate.py already exits cleanly with a RuntimeError message on an HTTP failure; this
#   wrapper just makes sure that message lands somewhere durable.
#
# Install (edit REPO_DIR below to match this droplet's actual checkout path first):
#   chmod +x scripts/log_cde_live_funding_rate_cron.sh
#   crontab -e
#   # add this line (fires 5 minutes past every hour, matching CDE's own hourly funding cadence):
#   5 * * * * /path/to/ID_test/scripts/log_cde_live_funding_rate_cron.sh
#
# Verify:
#   ./scripts/log_cde_live_funding_rate_cron.sh          # run once by hand
#   tail data/cde_live_funding_rate_log.csv              # confirm a row landed
#   tail data/cde_live_funding_rate_cron.log             # confirm the wrapper's own log
#   grep CRON /var/log/syslog | tail                     # confirm cron actually fired (Debian/Ubuntu)

set -uo pipefail

REPO_DIR="/opt/itera/ID_test"   # <-- EDIT to this droplet's actual checkout path
LOG_FILE="$REPO_DIR/data/cde_live_funding_rate_cron.log"
LOCK_FILE="$REPO_DIR/data/.cde_live_funding_rate.lock"

cd "$REPO_DIR" || { echo "$(date -u +%FT%TZ) FATAL: cannot cd to $REPO_DIR" >> "$LOG_FILE"; exit 1; }
mkdir -p "$(dirname "$LOG_FILE")"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "$(date -u +%FT%TZ) SKIP: previous run still holding the lock" >> "$LOG_FILE"
    exit 0
fi

{
    echo "$(date -u +%FT%TZ) START"
    if uv run python scripts/log_cde_live_funding_rate.py; then
        echo "$(date -u +%FT%TZ) OK"
    else
        echo "$(date -u +%FT%TZ) FAILED (exit $?) -- see output above; will retry next hour"
    fi
} >> "$LOG_FILE" 2>&1
