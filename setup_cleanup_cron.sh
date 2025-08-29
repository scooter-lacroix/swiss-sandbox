#!/bin/bash

SCRIPT_PATH="$HOME/swiss-sandbox/cleanup_workspace.sh"

CRON_JOB="0 0 * * * $SCRIPT_PATH"

(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "Cron job added to run cleanup daily at midnight."