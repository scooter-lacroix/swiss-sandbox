#!/bin/bash

LOG_FILE="$HOME/.swiss_sandbox/cleanup.log"

# Ensure log directory exists
mkdir -p "$HOME/.swiss_sandbox"

echo "$(date): Starting cleanup" >> "$LOG_FILE"

DIRS=("$HOME/.swiss_sandbox/artifacts/" "$HOME/.swiss_sandbox/workspaces/")

for DIR in "${DIRS[@]}"; do
    if [ -d "$DIR" ]; then
        echo "$(date): Processing directory $DIR" >> "$LOG_FILE"
        # Remove files older than 48 hours
        find "$DIR" -type f -mtime +1 -exec rm -f {} \; -print >> "$LOG_FILE" 2>&1
        # Remove empty directories older than 48 hours
        find "$DIR" -type d -empty -mtime +1 -exec rmdir {} \; -print >> "$LOG_FILE" 2>&1
    else
        echo "$(date): Directory $DIR does not exist" >> "$LOG_FILE"
    fi
done

echo "$(date): Cleanup completed" >> "$LOG_FILE"