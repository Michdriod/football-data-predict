#!/bin/bash

###############################################################################
# Football Prediction Pipeline Orchestration
# Automates: Data Load → dbt Transform → Data Tests
# Schedule: Weekly Monday 3:00 AM (auto, no manual intervention)
# Alerts: Email on failure
###############################################################################

set -e  # Exit on any error
set -o pipefail  # A failing command piped into tee must still count as a failure

PROJECT_DIR="/Users/mac/Desktop/football-data-predict"
LOG_FILE="$PROJECT_DIR/logs/pipeline_$(date +%Y%m%d_%H%M%S).log"
PYTHON_ENV="$PROJECT_DIR/pred"
DBT_DIR="$PROJECT_DIR/football_prediction"
EMAIL_ON_ERROR="michwaleh@gmail.com"  # Alerts on failure

# Activate Python virtual environment
source "$PYTHON_ENV/bin/activate"

PYTHON_BIN="python"
DBT_BIN="dbt"

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_DIR/logs"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error_exit() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    # Email alert on error
    if command -v mail &> /dev/null && [ -n "$EMAIL_ON_ERROR" ]; then
        echo "Pipeline failed at $(date)" | mail -s "[ALERT] Football Pipeline Failed" "$EMAIL_ON_ERROR"
    fi
    exit 1
}

success() {
    echo -e "${GREEN}[✓]${NC} $1" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log "════════════════════════════════════════════════════════════════"
log "FOOTBALL PREDICTION PIPELINE STARTED"
log "════════════════════════════════════════════════════════════════"

cd "$PROJECT_DIR" || error_exit "Cannot cd to $PROJECT_DIR"

# Step 2: Verify Python environment
log ""
log "Step 2: Verifying Python environment..."
if ! command -v $PYTHON_BIN &> /dev/null; then
    error_exit "Python not found"
fi
success "Python environment verified"

# Step 3: Load/append raw data
log ""
log "Step 3: Loading data from CSV files..."

# Detect current season based on date
# Premier League season runs Aug-Jul, so April 2026 = 2025-26 season
CURRENT_MONTH=$(date +%m)
CURRENT_YEAR=$(date +%Y)

# If month is Jan-Jul, current season is (YEAR-1)-(YEAR%100)
# If month is Aug-Dec, current season is YEAR-(YEAR+1%100)
if [ "$CURRENT_MONTH" -ge "08" ]; then
    SEASON_START=$CURRENT_YEAR
    SEASON_END=$((CURRENT_YEAR + 1))
else
    SEASON_START=$((CURRENT_YEAR - 1))
    SEASON_END=$CURRENT_YEAR
fi

# Format season as YYYY-YY
SEASON_END_SHORT=$(printf "%02d" $((SEASON_END % 100)))
CURRENT_SEASON="$SEASON_START-$SEASON_END_SHORT"

info "Current season detected: $CURRENT_SEASON"
info "Loading data with SEASON REFRESH mode for $CURRENT_SEASON"
info "  - Historical seasons: append-only (not affected)"
info "  - Current season ($CURRENT_SEASON): truncate and reload fresh"

$PYTHON_BIN scripts/load_raw_data.py --data-dir data/raw/ --season "$CURRENT_SEASON" --auto-download --no-backup 2>&1 | tee -a "$LOG_FILE" || error_exit "Data load failed"
success "Data loaded successfully (season $CURRENT_SEASON refreshed)"

# Step 4: Run dbt transformations
log ""
log "Step 4: Running dbt transformations..."
cd "$DBT_DIR" || error_exit "Cannot cd to $DBT_DIR"
$DBT_BIN run 2>&1 | tee -a "$LOG_FILE" || error_exit "dbt run failed"
success "dbt transformations completed"

# Step 5: Run data tests
log ""
log "Step 5: Running data quality tests..."
$DBT_BIN test 2>&1 | tee -a "$LOG_FILE" || error_exit "dbt tests failed"
success "All data tests passed"

# Step 5b: Retrain the match model on the refreshed data
log ""
log "Step 5b: Retraining match model..."
cd "$PROJECT_DIR" || error_exit "Cannot return to project directory"
$PYTHON_BIN scripts/match_model.py --train 2>&1 | tee -a "$LOG_FILE" || error_exit "Model training failed"
success "Match model retrained"

# Step 5c: Log practice picks at current prices. A failed odds call must not fail the run.
log ""
log "Step 5c: Logging practice picks..."
$PYTHON_BIN scripts/predict.py --fetch-odds --days 7 2>&1 | tee -a "$LOG_FILE" || info "Practice picks skipped (odds unavailable)"

# Step 6: Validation query
log ""
log "Step 6: Final validation..."
cd "$PROJECT_DIR" || error_exit "Cannot return to project directory"
TRAINING_ROWS=$($PYTHON_BIN -c "
import psycopg2
import sys
sys.path.insert(0, 'scripts')
from config import DB_CONFIG
conn = psycopg2.connect(**{('dbname' if k == 'database' else k): v for k, v in DB_CONFIG.items()})
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM fct_model_training_dataset;')
result = cur.fetchone()[0]
cur.close()
conn.close()
print(result)
" 2>&1)

if [ -z "$TRAINING_ROWS" ]; then
    error_exit "Failed to validate training dataset"
fi

success "Training dataset ready: $TRAINING_ROWS rows"

log ""
log "════════════════════════════════════════════════════════════════"
log "PIPELINE COMPLETED SUCCESSFULLY"
log "════════════════════════════════════════════════════════════════"
log "ML dataset rows: $TRAINING_ROWS"
log "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
log "Log file: $LOG_FILE"
log "════════════════════════════════════════════════════════════════"

exit 0
