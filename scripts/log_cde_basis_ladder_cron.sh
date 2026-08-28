#!/usr/bin/env bash
# Cron-safe wrapper for scripts/log_cde_basis_ladder.py -- same pattern as
# log_cde_live_funding_rate_cron.sh, already running on this droplet.
#
# - flock prevents two overlapping runs from racing on the same CSV.
# - stdout/stderr always go to a log file, visible on inspection without depending on cron mail.
# - a failed fetch logs cleanly and lets the next hourly tick retry.
#
# Install:
#   chmod +x scripts/log_cde_basis_ladder_cron.sh
#   crontab -e
#   # ADD this line below whatever is already there -- do not replace the file's contents:
#   10 * * * * /root/ID_test/scripts/log_cde_basis_ladder_cron.sh
#   (offset 10 minutes past the hour, not :05 like the funding logger, so the two don't race
#   on the same minute)
#
# Verify:
#   ./scripts/log_cde_basis_ladder_cron.sh              # run once by hand
#   tail data/cde_basis_ladder_log.csv                  # confirm rows landed
#   tail data/cde_basis_ladder_cron.log                 # confirm the wrapper's own log

set -uo pipefail

REPO_DIR="/root/ID_test"
LOG_FILE="$REPO_DIR/data/cde_basis_ladder_cron.log"
LOCK_FILE="$REPO_DIR/data/.cde_basis_ladder.lock"

cd "$REPO_DIR" || { echo "$(date -u +%FT%TZ) FATAL: cannot cd to $REPO_DIR" >> "$LOG_FILE"; exit 1; }
mkdir -p "$(dirname "$LOG_FILE")"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "$(date -u +%FT%TZ) SKIP: previous run still holding the lock" >> "$LOG_FILE"
    exit 0
fi

{
    echo "$(date -u +%FT%TZ) START"
    # Pure stdlib script -- plain python3 is sufficient, no venv needed.
    if python3 scripts/log_cde_basis_ladder.py; then
        echo "$(date -u +%FT%TZ) OK"
    else
        echo "$(date -u +%FT%TZ) FAILED (exit $?) -- see output above; will retry next hour"
    fi
} >> "$LOG_FILE" 2>&1
