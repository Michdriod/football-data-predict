# Scripts Directory

This directory contains Python scripts for data loading, training, evaluating, and running predictions.

## 🚀 Quick Start (Recommended Workflow)

### **Weekly Update - Automated Pipeline** ⭐ **NEW**
```bash
# One command - does everything automatically
python scripts/auto_update.py --csv data/raw/E0_2025-26.csv
```

This single command:
- Loads CSV → Runs dbt → Checks threshold → Retrains (if needed) → Updates models (if improved)
- No human intervention required
- Prevents model degradation automatically

---

## Available Scripts

### 0. auto_update.py ⭐ **NEW - Automated Pipeline**

**Purpose**: Complete automation of weekly data updates and model retraining

**Usage**:
```bash
# Standard weekly update
python scripts/auto_update.py --csv data/raw/E0_2025-26.csv

# Force retrain (skip 20-match threshold)
python scripts/auto_update.py --csv data/raw/E0_2025-26.csv --force-retrain

# Skip dbt (testing only - not recommended)
python scripts/auto_update.py --csv data/raw/E0_2025-26.csv --skip-dbt
```

**What it does**:
1. Loads CSV into raw_football_matches (replaces existing season data)
2. Runs dbt pipeline (dbt run + dbt test)
3. Checks if 20+ new matches added since last training
4. If yes: Retrains all models on full dataset (~2 min)
5. Compares new vs old model validation AUC
6. Updates models only if ≥3 of 4 targets improved (98% tolerance)
7. No backups - always keeps best performing models in models/saved/

**Features**:
- ✅ Zero human intervention after CSV upload
- ✅ Smart quality control (prevents model degradation)
- ✅ Zero storage overhead (no backup directories)
- ✅ Full retraining on entire dataset (proper ML practice for RandomForest)
- ✅ Comprehensive logging and progress tracking

**Expected runtime**: 2-5 minutes (depending on whether retraining occurs)

**Example output**:
```
================================================================================
AUTOMATED FOOTBALL DATA UPDATE PIPELINE
================================================================================
Started: 2026-05-22 09:00:00

STEP 1: LOADING CSV DATA
  ✓ Loaded 385 matches

STEP 2: RUNNING DBT PIPELINE
  ✓ dbt run completed (10 models built)
  ✓ dbt test completed (17 tests passed)

STEP 3: CHECKING RETRAIN THRESHOLD
  New matches: 25 ≥ 20 (threshold)
  → Proceeding with retraining

STEP 4: TRAINING NEW MODELS
  ✓ Trained 4 targets × Random Forest

STEP 5: COMPARING MODEL PERFORMANCE
  Over 2.5:          0.9278 → 0.9301 ✓
  BTTS:              0.9465 → 0.9480 ✓
  Home Not Lose:     0.9084 → 0.9095 ✓
  Away Not Lose:     0.8935 → 0.8920 ✗

  ✅ Performance maintained (3/4 targets)
  → Models WILL be updated

UPDATE COMPLETE
  ✅ CSV loaded: 385 matches
  ✅ New matches: 25
  ✅ Models updated: Yes
```

---

### 1. load_raw_data.py (Manual Method)

**Purpose**: Load CSV files from football-data.co.uk into PostgreSQL

**Usage**:
```bash
# Load all CSV files from data/raw/ (append-only mode)
python scripts/load_raw_data.py --data-dir data/raw/ --no-backup

# Update specific season (delete old, reload fresh)
python scripts/load_raw_data.py --season 2025-26 --no-backup

# Update season with auto-download from web
python scripts/load_raw_data.py --season 2025-26 --auto-download --no-backup

# Full reload (truncate all, reload everything)
python scripts/load_raw_data.py --full-truncate --no-backup
```

**What it does**:
1. Validates CSV file format and columns
2. Detects and handles duplicates intelligently:
   - **Append mode**: Loads only new matches not in database
   - **Season mode**: Deletes old season data, loads fresh (no duplicates)
   - **Full-truncate mode**: Wipes everything, loads all seasons fresh
3. Creates backup of existing data (unless --no-backup)
4. Loads data to `raw_football_matches` table
5. Provides verification statistics

**Three modes**:
| Mode | Command | Use Case |
|------|---------|----------|
| Append (all seasons) | `--data-dir data/raw/ --no-backup` | Initial load, add historical seasons |
| Season update | `--season 2025-26 --no-backup` | Weekly updates during active season |
| Auto-download + update | `--season 2025-26 --auto-download --no-backup` | For cron jobs (downloads from web) |
| Full reload | `--full-truncate --no-backup` | One-time complete reset |

**Expected runtime**: 1-2 minutes (depending on file count and mode)

---

### 2. train_models.py

**Purpose**: Train baseline models for all 4 prediction targets

**Usage**:
```bash
# Train all models (default)
python scripts/train_models.py

# Train specific targets only
python scripts/train_models.py --targets target_over_25 target_btts_yes

# Train only logistic regression
python scripts/train_models.py --models logistic

# Train only random forest
python scripts/train_models.py --models random_forest
```

**What it does**:
1. Loads data from PostgreSQL `fct_model_training_dataset`
2. Creates 12 derived features (attack strength, form momentum, etc.)
3. Splits data by time: Train (pre-2023-07), Val (2023-24), Test (2024-2026)
4. Trains 8 models (4 targets × 2 model types)
5. Calibrates probabilities on validation set
6. Saves models to `models/saved/`
7. Prints validation metrics

**Output files**:
- `models/saved/target_*_logistic.pkl` (8 models)
- `models/saved/target_*_logistic_scaler.pkl` (4 scalers)
- `models/saved/training_metadata_*.pkl` (1 metadata file)

**Expected runtime**: 10-15 minutes

---

## Typical Workflows

### First-Time Setup

```bash
# 1. Download CSV files to data/raw/ (see data/raw/README.md)

# 2. Load data to PostgreSQL (all seasons)
python scripts/load_raw_data.py --data-dir data/raw/ --no-backup

# 3. Run dbt transformations
cd football_prediction
dbt run
dbt test

# 4. Train models
cd ..
python scripts/train_models.py
```

### Weekly Data Update (During Season)

```bash
# 1. Download updated CSV for current season to data/raw/

# 2. Update the season (delete old, reload fresh)
python scripts/load_raw_data.py --season 2025-26 --no-backup

# 3. Re-run dbt pipeline
cd football_prediction
dbt run
dbt test

# 4. Optional: Retrain models if significant new matches added
cd ..
python scripts/train_models.py
```

### Automated Weekly Update (via Cron)

```bash
# Install cron job
bash scripts/setup_cron.sh

# This runs every Monday, Wednesday, Friday at 3:00 AM:
# - Downloads 2025-26 CSV
# - Updates database (delete + reload)
# - Runs dbt pipeline
# - Re-trains models
```

### New Season

```bash
# 1. Download new season CSV (e.g., E0_2026-27.csv) to data/raw/

# 2. Update with auto-download
python scripts/load_raw_data.py --season 2026-27 --auto-download --no-backup

# 3. Re-run pipeline
cd football_prediction
dbt run
dbt test

# 4. Retrain models with expanded dataset
cd ..
python scripts/train_models.py
```

---

## Prerequisites

1. **Database**: PostgreSQL running with `football_prediction_db`
2. **dbt**: All transformations complete (fct_model_training_dataset exists)
3. **Python environment**: Virtual environment activated
4. **Dependencies**: `pip install -r requirements.txt`

## Configuration

### Database Connection

Edit database credentials in each script:

```python
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'football_prediction_db',
    'user': 'postgres',
    'password': 'your_password'  # TODO: Move to .env
}
```

**Security Note**: Store password in environment variable:

```bash
# Add to ~/.zshrc or ~/.bashrc
export PGPASSWORD="your_password"

# Or use .env file (requires python-dotenv)
echo "PGPASSWORD=your_password" > .env
```

### Model Configuration

Edit `train_models.py` to modify:

- `BETTING_THRESHOLDS`: Betting strategy parameters
- `SPLIT_DATES`: Train/validation/test cutoff dates
- `MODEL_CONFIGS`: Model hyperparameters

**Note**: Review CLAUDE.md before modifying these settings.

---

## Script Details

### load_raw_data.py

**Features**:
- ✅ CSV validation (required columns check)
- ✅ Duplicate detection (within files and vs database)
- ✅ Automatic backup creation
- ✅ Interactive duplicate handling
- ✅ Comprehensive logging
- ✅ Verification after load

**Safety Features**:
- Creates backup before any changes
- Detects and prevents duplicates
- Validates file format before loading
- Supports append or replace mode

### update_data.py

**Features**:
- ✅ Automated pipeline orchestration
- ✅ Prerequisites checking
- ✅ Dry-run mode for testing
- ✅ dbt integration
- ✅ Data quality validation

**Use Cases**:
- Weekly match results refresh
- New season data integration
- Scheduled data updates (cron job)

### train_models.py

**Features**:
- ✅ Time-based train/val/test splits
- ✅ Feature engineering (12 derived features)
- ✅ Model calibration (CalibratedClassifierCV)
- ✅ Overfitting detection
- ✅ Conservative betting strategy (70% threshold)
- ✅ Model persistence

**Models Trained**:
- Logistic Regression (with StandardScaler)
- Random Forest Classifier

**Targets**:
1. Over/Under 2.5 Goals
2. Both Teams To Score
3. Home Not Lose (1X)
4. Away Not Lose (X2)

---

## Making Scripts Executable

```bash
# Make all scripts executable
chmod +x scripts/*.py

# Run without 'python' prefix
./scripts/load_raw_data.py --help
./scripts/update_data.py --dry-run
./scripts/train_models.py
```

---

## Troubleshooting

### Database Connection Errors

```bash
# Test PostgreSQL connection
psql -h localhost -U postgres -d football_prediction_db -c "SELECT 1;"

# Check if database exists
psql -U postgres -l | grep football_prediction_db
```

### Import Errors

```bash
# Verify virtual environment activated
which python  # Should show path to pred/bin/python

# Reinstall dependencies
pip install -r requirements.txt
```

### dbt Errors

```bash
# Test dbt connection
cd football_prediction
dbt debug

# Check profiles.yml configuration
cat ~/.dbt/profiles.yml
```

---

## Next Steps

After training:
1. Review validation metrics in console output
2. Run evaluation script (to be created): `python scripts/evaluate_models.py`
3. Compare model performance on test set
4. Select best model for each target

---

*See IMPLEMENTATION_PLAN.md for detailed execution guide*  
*See data/raw/README.md for data download instructions*
