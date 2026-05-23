#!/bin/bash

###############################################################################
# Setup Cron Job for Automated Pipeline
# Runs: Monday 3:00 AM
# Pipeline: Load CSV → Run dbt → Tests → Email on failure
###############################################################################

PROJECT_DIR="/Users/mac/Desktop/football-data-predict"
SCRIPT_PATH="$PROJECT_DIR/scripts/run_pipeline.sh"
CRON_LOG="$PROJECT_DIR/logs/cron.log"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "run_pipeline.sh"; then
    echo "✓ Cron job already exists"
    crontab -l | grep run_pipeline.sh
    exit 0
fi

# Add cron job for Monday 3:00 AM
# Format: minute hour day month weekday
# 0 3 * * 1 = Every Monday at 3:00 AM
CRON_ENTRY="0 3 * * 1 $SCRIPT_PATH >> $CRON_LOG 2>&1"

# Create temporary crontab file
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo "✓ Cron job added successfully!"
echo "Schedule: Every Monday at 3:00 AM"
echo "Script: $SCRIPT_PATH"
echo "Log: $CRON_LOG"
echo ""
echo "Verify cron job:"
crontab -l | grep run_pipeline.sh
