# Football Match Prediction System

A data-driven football match prediction engine focused on English Premier League matches. The system identifies high-confidence betting opportunities across multiple markets using machine learning.

## 📊 Features

- **7 Prediction Markets:**
  - Over/Under 2.5 Goals
  - Home Win, Draw, Away Win (3-way match result)
  - Home Win or Draw (1X)
  - Away Win or Draw (X2)
  - Both Teams To Score (BTTS)

- **Production-Quality ML Pipeline:**
  - 80+ features (rolling form, shot efficiency, defensive metrics, goal variance, home/away splits)
  - Random Forest models with temporal cross-validation
  - Rolling window training (2021-2026 data only)
  - Test AUC: 0.64 (Over 2.5), 0.61 (BTTS), 0.77 (Match Results)

- **Live Odds Integration:**
  - The Odds API integration (William Hill, LeoVegas)
  - Automatic value edge calculation
  - Betting recommendations with 70% probability + 5% edge thresholds

- **Automated Pipeline:**
  - Weekly CSV upload → dbt transformation → automatic retraining
  - One-command updates: `python scripts/auto_update.py --csv data/raw/E0_2025-26.csv`

---

## 🚀 Quick Start

### 1. Prerequisites

- **PostgreSQL 15+**: Database server running on localhost:5432
- **Python 3.10+**: With virtual environment
- **dbt-core + dbt-postgres**: Data transformation tool

### 2. Installation

```bash
# 1. Clone repository
cd /Users/mac/Desktop/football-data-predict

# 2. Create database
createdb football_prediction_db

# 3. Setup Python environment
python -m venv pred
source pred/bin/activate  # Mac/Linux
# OR: pred\Scripts\activate  # Windows
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env and set your DB_PASSWORD and ODDS_API_KEY

# 5. Initialize dbt
cd football_prediction
dbt debug  # Test connection
dbt run    # Build all models (takes ~5 seconds)
dbt test   # Run data quality tests
cd ..

# 6. Load historical data
python scripts/load_raw_data.py --data-dir data/raw/

# 7. Train models
python scripts/train_models.py
# Takes ~3 minutes, saves 14 models to models/saved/
```

---

## 📅 Weekly Workflow (Match Day Predictions)

### Option 1: Automated Pipeline (Recommended)

```bash
# One command does everything:
# - Loads new CSV data
# - Runs dbt transformations
# - Retrains models if 20+ new matches
# - Updates models only if performance improves
python scripts/auto_update.py --csv data/raw/E0_2025-26.csv
```

### Option 2: Manual Steps

```bash
# 1. Download latest CSV from football-data.co.uk
# Save to data/raw/E0_2025-26.csv

# 2. Load new data
python scripts/load_raw_data.py --csv data/raw/E0_2025-26.csv

# 3. Run dbt pipeline
cd football_prediction && dbt run && cd ..

# 4. Retrain if needed (after ~20 new matches)
python scripts/train_models.py

# 5. Generate predictions
python scripts/predict.py --fetch-odds --days 7
```

---

## 🔮 Prediction Modes

### Mode 1: Auto-Fetch Upcoming Fixtures (Live Odds)

```bash
# Fetch next 7 days of EPL fixtures with live odds
python scripts/predict.py --fetch-odds --days 7

# JSON output
python scripts/predict.py --fetch-odds --json
```

**Output Example:**
```
================================================================================
📅 2026-05-25 | Arsenal             vs Chelsea            
--------------------------------------------------------------------------------
  Over 2.5 Goals                   | Prob:  67.5% | HIGH   | Rec: BET    | Odds:  2.10 | Edge: +14.8%
  Home Win                          | Prob:  52.3% | MEDIUM | Rec: NO BET | Odds:  1.85 | Edge:  -1.7%
  Draw                              | Prob:  24.1% | LOW    | Rec: NO BET | Odds:  3.40 | Edge:  -5.3%
  Away Win                          | Prob:  23.6% | LOW    | Rec: NO BET | Odds:  4.20 | Edge:  -0.2%
  Home Win or Draw (1X)             | Prob:  76.4% | HIGH   | Rec: BET    | Odds:  1.36 | Edge:  +2.8%
  Away Win or Draw (X2)             | Prob:  47.7% | MEDIUM | Rec: NO BET
  Both Teams To Score               | Prob:  71.2% | HIGH   | (No market odds available)
================================================================================
```

### Mode 2: Manual Input (Historical/Testing)

```bash
# Specify teams and date manually
python scripts/predict.py --home Arsenal --away Chelsea --date 2026-05-25

# Get predictions without odds
python scripts/predict.py --home "Man City" --away Liverpool
```

### Mode 3: Manual Teams + Fetch Odds

```bash
# Specify teams, but fetch live odds from API
python scripts/predict.py --home Arsenal --away Chelsea --fetch-odds
```

---

## 📈 Model Evaluation

```bash
# Evaluate models on holdout test set (2024-2026)
python scripts/evaluate_models.py

# Run historical backtest by season
python scripts/backtest.py
```

**Current Performance (Test Set, 648 matches, 2021-2026):**
- Over 2.5 Goals: AUC 0.64 (improved from 0.53)
- BTTS: AUC 0.61 (improved from 0.54)
- Home Win: AUC 0.77
- Draw: AUC 0.68
- Away Win: AUC 0.76

---

## 🗂️ Project Structure

```
football-data-predict/
├── README.md                      ← This file
├── CLAUDE.md                      ← Detailed technical documentation
├── requirements.txt               ← Python dependencies
├── .env                           ← Environment config (not committed)
├── .env.example                   ← Template for .env
│
├── data/
│   ├── raw/                       ← CSV files from football-data.co.uk
│   └── team_name_mapping.json    ← API team name → DB team name mapping
│
├── dbt_project/                   ← Data transformation (dbt)
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── models/
│   │   ├── staging/               ← stg_football_matches
│   │   ├── intermediate/          ← 6 models (results, stats, odds, targets, history)
│   │   └── marts/                 ← 3 models (rolling features, training dataset, final features)
│   └── tests/
│
├── scripts/
│   ├── config.py                  ← Centralized configuration
│   ├── load_raw_data.py           ← CSV → PostgreSQL loader
│   ├── train_models.py            ← ML training with rolling window + temporal CV
│   ├── evaluate_models.py         ← Model evaluation on test set
│   ├── predict.py                 ← Generate predictions (3 modes)
│   ├── backtest.py                ← Historical performance analysis
│   ├── fetch_odds.py              ← The Odds API integration
│   └── auto_update.py             ← Automated weekly pipeline
│
├── models/
│   └── saved/                     ← Trained models (.pkl files)
│
├── logs/                          ← Prediction outputs and evaluation results
│
└── notebooks/                     ← Jupyter notebooks for EDA
```

---

## 🔧 Configuration

All configuration is centralized in `.env` file:

```bash
# Database
DB_PASSWORD=your_password_here
DB_HOST=localhost
DB_PORT=5432
DB_NAME=football_prediction_db
DB_USER=postgres

# The Odds API
ODDS_API_KEY=your_api_key_here
ODDS_SPORT_KEY=soccer_epl
ODDS_REGIONS=uk
ODDS_MARKETS=h2h,totals

# Model Settings
ROLLING_WINDOW_START_DATE=2021-07-01
RETRAIN_THRESHOLD=20
PERFORMANCE_TOLERANCE=0.98

# Betting Thresholds
MIN_PROBABILITY=0.70
MIN_VALUE_EDGE=0.05
MIN_ODDS=1.50
MAX_ODDS=3.00
```

---

## 📊 Data Pipeline

### 1. Raw Data → Database

**Source**: football-data.co.uk EPL CSV files

```bash
python scripts/load_raw_data.py --csv data/raw/E0_2024-25.csv
```

Creates: `raw_football_matches` table (2,889 matches, 94 columns)

### 2. dbt Transformations

```bash
cd football_prediction && dbt run
```

**Pipeline (10 models):**
1. **stg_football_matches**: Clean and cast raw data
2. **int_match_results**: Match outcomes and derived columns
3. **int_match_stats**: Shots, corners, cards statistics
4. **int_match_odds**: Betting odds + implied probabilities
5. **int_prediction_targets**: 9 binary target columns
6. **int_team_match_history**: Team-level match rows
7. **fct_team_rolling_features**: 22 rolling form features per team
8. **fct_model_training_dataset**: Join home + away features
9. **fct_model_features**: Add 12 derived features
10. **int_odds_canonical**: Real market odds (optional)

**Output**: `fct_model_features` table (2,889 matches × 94 features)

### 3. Model Training

```bash
python scripts/train_models.py
```

- Applies rolling window filter (2021+ only)
- Runs temporal cross-validation (4 folds)
- Trains 14 models (7 targets × 2 types)
- Saves to `models/saved/`

### 4. Prediction

```bash
python scripts/predict.py --fetch-odds --days 7
```

- Fetches upcoming fixtures from The Odds API
- Loads latest team form from database
- Generates predictions with value edge
- Outputs betting recommendations

---

## 🎯 Betting Strategy

**The system uses strict value-based criteria:**

### Recommendation: **BET**
- Model probability ≥ 70%
- Value edge ≥ 5% (model prob - implied prob)
- Odds between 1.50 and 3.00

### Recommendation: **NO BET**
- Any of the above criteria not met
- System explains reason (e.g., "Probability too low", "Value edge negative")

**Note**: System says "NO BET" more often than "BET" - this is correct behavior!

---

## 🔄 Automated Updates

### Weekly Update Pipeline

```bash
python scripts/auto_update.py --csv data/raw/E0_2025-26.csv
```

**Workflow:**
1. Loads CSV (replaces existing season data)
2. Runs dbt pipeline (dbt run + dbt test)
3. Checks if 20+ new matches since last training
4. If yes: Retrains all models on full dataset
5. Compares new vs old model performance (validation AUC)
6. Only updates models if ≥3 of 4 core targets improved (98% tolerance)
7. Keeps best models always in `models/saved/`

**Flags:**
- `--force-retrain`: Skip 20-match threshold
- `--skip-dbt`: Skip dbt pipeline (testing only)
- `--season 2025-26`: Manually specify season code

---

## 🧪 Testing & Validation

### Run All Tests

```bash
# dbt data quality tests
cd football_prediction && dbt test

# Python unit tests (if available)
pytest tests/

# End-to-end pipeline test
./scripts/run_pipeline.sh
```

### Manual Verification

```bash
# Check database
psql -d football_prediction_db -c "SELECT COUNT(*) FROM fct_model_features;"

# Check models
ls -lh models/saved/

# Verify predictions
python scripts/predict.py --home Arsenal --away Chelsea
```

---

## 🐛 Troubleshooting

### Database Connection Failed

```bash
# Check PostgreSQL is running
psql -U postgres -c "SELECT version();"

# Test connection
python scripts/config.py

# Recreate database if needed
dropdb football_prediction_db
createdb football_prediction_db
cd football_prediction && dbt run
```

### No Predictions Generated

```bash
# Check if models exist
ls models/saved/*.pkl

# Retrain if missing
python scripts/train_models.py

# Check team names match database
python -c "from fetch_odds import load_team_mapping; print(load_team_mapping())"
```

### Odds API Rate Limit

- Free tier: 500 requests/month
- Each fixture fetch counts as 1 request
- If over limit: Wait for next month or upgrade

### dbt Model Failures

```bash
# Check logs
cat football_prediction/logs/dbt.log

# Run specific model
cd football_prediction
dbt run --select stg_football_matches
dbt test --select stg_football_matches
```

---

## 📚 Advanced Usage

### Custom Model Configuration

Edit `scripts/config.py`:

```python
MODEL_CONFIGS = {
    'random_forest': {
        'n_estimators': 50,      # Number of trees
        'max_depth': 10,         # Max tree depth
        'min_samples_split': 20, # Min samples to split
        'min_samples_leaf': 10,  # Min samples per leaf
        'class_weight': 'balanced',
        'random_state': 42,
        'n_jobs': -1
    }
}
```

### Change Betting Thresholds

Edit `.env`:

```bash
MIN_PROBABILITY=0.75  # Increase for more conservative bets
MIN_VALUE_EDGE=0.10   # Increase for higher edge requirement
MAX_ODDS=2.50         # Lower for safer bets
```

### Add New Features

1. Update `fct_team_rolling_features.sql` (dbt model)
2. Add column to `fct_model_training_dataset.sql`
3. Add column to `fct_model_features.sql`
4. Run: `cd football_prediction && dbt run`
5. Retrain: `python scripts/train_models.py`

---

## 🚧 Roadmap (Future v2)

### Not Yet Implemented

- [ ] **predict.py 3-mode integration** (in progress)
- [ ] **backtest.py rolling window filter** (needs update)
- [ ] **FastAPI backend** (future)
- [ ] **React frontend** (future)
- [ ] Real-time odds streaming
- [ ] Multi-league support (La Liga, Bundesliga, etc.)
- [ ] Advanced features (xG, player injuries, manager changes)
- [ ] Ensemble stacking models
- [ ] Bayesian probability calibration

---

## 📄 License

This project is for educational and research purposes only. Use at your own risk. Gambling can be addictive. Please bet responsibly.

---

## 👤 Author

**Football Prediction System**  
Date: May 23, 2026  
Version: 1.0.0

---

## 🙏 Acknowledgments

- Data source: [football-data.co.uk](https://www.football-data.co.uk/)
- Odds API: [The Odds API](https://the-odds-api.com/)
- ML framework: scikit-learn
- Data transformation: dbt (Data Build Tool)
