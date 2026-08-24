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
# Install:
#   chmod +x scripts/log_cde_live_funding_rate_cron.sh
#   crontab -e
#   # ADD this line below whatever is already there -- don't replace the file's existing
#   # contents (this box already runs at least one other cron job under root):
#   5 * * * * /root/ID_test/scripts/log_cde_live_funding_rate_cron.sh
#
# Verify:
#   ./scripts/log_cde_live_funding_rate_cron.sh          # run once by hand
#   tail data/cde_live_funding_rate_log.csv              # confirm a row landed
#   tail data/cde_live_funding_rate_cron.log             # confirm the wrapper's own log
#   grep CRON /var/log/syslog | tail                     # confirm cron actually fired (Debian/Ubuntu)

set -uo pipefail

REPO_DIR="/root/ID_test"
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
    # Pure stdlib script (argparse/csv/json/urllib only) -- plain python3 is sufficient, no
    # venv needed. This box's /opt/itera/venv is for Core v1's own runtime, unrelated to this.
    if python3 scripts/log_cde_live_funding_rate.py; then
        echo "$(date -u +%FT%TZ) OK"
    else
        echo "$(date -u +%FT%TZ) FAILED (exit $?) -- see output above; will retry next hour"
    fi
} >> "$LOG_FILE" 2>&1
