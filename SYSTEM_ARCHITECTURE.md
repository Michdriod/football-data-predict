# Football Match Prediction System - Architecture

**Version**: 1.0  
**Date**: 26 April 2026  
**Status**: In Development

---

## 🎯 SYSTEM OVERVIEW

A disciplined, data-driven football match prediction engine focused on the English Premier League. The system identifies high-confidence opportunities across three prediction markets using machine learning and value betting principles.

**Core Philosophy**: Say "No Bet" more often than "Bet" - focus on quality over quantity.

---

## 🏗️ HIGH-LEVEL ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────┐
│                     DATA SOURCES                             │
│  football-data.co.uk (Historical CSV files 2018-2026)       │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│              RAW DATA LAYER (PostgreSQL)                     │
│  • raw_football_matches (TEXT columns, ~3,000 rows)        │
│  • Manual CSV imports via Python script                     │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│           TRANSFORMATION LAYER (dbt)                         │
│  • 4 layers: Raw → Staging → Intermediate → Marts          │
│  • 10 models with data quality tests                        │
│  • Rolling features (excludes current match)                │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│            ML-READY DATASET (PostgreSQL)                     │
│  • fct_model_training_dataset (2,892 rows × 56 columns)    │
│  • Time-ordered, no data leakage                            │
│  • 4 binary targets, 42+ features                           │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│          MACHINE LEARNING LAYER (scikit-learn)               │
│  • 8 calibrated models (4 targets × 2 types)               │
│  • Conservative betting strategy (70% threshold)            │
│  • Trained on 2018-2023, tested on 2024-2026               │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│         PREDICTION ENGINE (Python Scripts)                   │
│  • Load saved models from disk                              │
│  • Apply betting decision rules                             │
│  • Generate predictions with confidence scores              │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│            OUTPUT / DELIVERY LAYER                           │
│  • JSON predictions with probabilities                      │
│  • Performance reports (ML + betting metrics)               │
│  • Future: REST API (FastAPI) + Dashboard (React)          │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 DETAILED COMPONENT ARCHITECTURE

### 1. DATA INGESTION LAYER

#### 1.1 Data Source
- **Provider**: football-data.co.uk
- **Format**: CSV files (one per season)
- **Coverage**: Premier League 2018/19 - 2024/25
- **Update Frequency**: Weekly during season
- **Columns**: 120+ (match results, stats, betting odds)

#### 1.2 Raw Storage
```
PostgreSQL Database: football_prediction_db
├── Schema: public
│   └── Table: raw_football_matches
│       ├── Columns: 120+ (all TEXT type)
│       ├── Rows: ~3,000 matches
│       ├── Primary Key: None (append-only)
│       └── Quality: 380 rows with NULL Time (fixed)
```

**Quality Checks**:
- ✓ Column shift detection and repair
- ✓ Date format validation
- ✓ Team name consistency
- ✓ Duplicate detection

#### 1.3 Ingestion Script
```python
scripts/load_raw_data.py (Future)
├── Read CSV files from data/raw/
├── Concatenate multiple seasons
├── Basic validation (date range, team names)
├── Upsert to raw_football_matches
└── Log import statistics
```

---

### 2. TRANSFORMATION LAYER (dbt)

#### 2.1 Architecture Pattern
```
Staging → Intermediate → Marts

Purpose:
- Staging: Type casting, cleaning, validation
- Intermediate: Business logic, feature creation
- Marts: Final datasets for consumption
```

#### 2.2 Model Lineage

```
raw_football_matches (PostgreSQL table)
    │
    ├─→ stg_football_matches (staging)
    │       │
    │       ├─→ int_match_results (intermediate)
    │       │       │
    │       │       ├─→ int_prediction_targets
    │       │       │
    │       │       └─→ int_team_match_history ─┐
    │       │                                     │
    │       ├─→ int_match_stats ─────────────────┤
    │       │                                     │
    │       └─→ int_match_odds                   │
    │                                             │
    └───────────────────────────────────────────┘
                                                  │
                                                  ▼
                                    fct_team_rolling_features
                                                  │
                                                  ▼
                                    fct_model_training_dataset
```

#### 2.3 Model Details

| Layer | Model | Rows | Columns | Materialization | Purpose |
|-------|-------|------|---------|----------------|---------|
| Staging | stg_football_matches | 2,992 | 46 | View | Type-cast raw data |
| Intermediate | int_match_results | 2,992 | 11 | View | Match outcomes + key |
| Intermediate | int_prediction_targets | 2,992 | 11 | View | 4 binary targets |
| Intermediate | int_match_stats | 2,992 | 13 | View | Match statistics |
| Intermediate | int_match_odds | 2,992 | 33 | View | Betting odds + probs |
| Intermediate | int_team_match_history | 5,984 | 22 | View | Team perspective |
| Mart | fct_team_rolling_features | 5,984 | 22 | View | L5 & L10 form |
| Mart | fct_model_training_dataset | 2,892 | 56 | Table | Final ML dataset |

**Critical Rules**:
- Rolling windows: `rows between N preceding and 1 preceding`
- No `SELECT *` or `DISTINCT ON`
- All column names lowercase with underscores
- Consistent `match_key` formula across all models

#### 2.4 Data Quality Tests

```yaml
Tests: 9 total (all passing)

Staging:
✓ match_date NOT NULL
✓ home_team NOT NULL
✓ away_team NOT NULL
✓ full_time_result IN ('H', 'D', 'A')

Intermediate:
✓ match_key UNIQUE
✓ total_goals NOT NULL

Marts:
✓ match_key UNIQUE
✓ home_matches_played_before NOT NULL
✓ away_matches_played_before NOT NULL
```

---

### 3. FEATURE ENGINEERING LAYER

#### 3.1 Base Features (30 from dbt)

**Home Team Form (14 features)**:
- Last 5 matches: goals for/against, shots, corners, points, over_25_rate, btts_rate, clean_sheet_rate
- Last 10 matches: goals for/against, over_25_rate, btts_rate

**Away Team Form (14 features)**:
- Same structure as home team

**Betting Odds (12 features)**:
- Bet365 & Average: home/draw/away odds, over/under 2.5 odds
- Implied probabilities (derived from odds)

#### 3.2 Derived Features (12 from Python)

**Attack/Defense Strength (4 features)**:
```python
home_attack_strength = home_goals_for_L5 - away_goals_against_L5
away_attack_strength = away_goals_for_L5 - home_goals_against_L5
home_defense_strength = away_goals_for_L5 - home_goals_against_L5
away_defense_strength = home_goals_for_L5 - away_goals_against_L5
```

**Form Momentum (2 features)**:
```python
home_form_momentum = home_points_L5 - home_points_L10
away_form_momentum = away_points_L5 - away_points_L10
```

**Combined Metrics (2 features)**:
```python
total_attack_potential = (home_goals_for + away_goals_for) / 2
total_defense_weakness = (home_goals_against + away_goals_against) / 2
```

**Efficiency (2 features)**:
```python
home_shot_efficiency = home_goals_for / home_shots (if > 0, else 0)
away_shot_efficiency = away_goals_for / away_shots (if > 0, else 0)
```

**Odds-Based (2 features)**:
```python
odds_home_favorite = 1 if home_odds < away_odds else 0
odds_overround = total_implied_prob - 1.0  # Bookmaker margin
```

**Total Features**: 42

---

### 4. MACHINE LEARNING LAYER

#### 4.1 Prediction Targets

| Target | Market | Type | Expected Base Rate |
|--------|--------|------|-------------------|
| target_over_25 | Over 2.5 Goals | Binary | 45-55% |
| target_btts_yes | Both Teams To Score | Binary | 50-60% |
| target_home_not_lose | Double Chance 1X | Binary | 60-70% |
| target_away_not_lose | Double Chance X2 | Binary | 35-45% |

#### 4.2 Model Architecture

```
For each target:
    ├── Logistic Regression
    │   ├── StandardScaler (feature scaling)
    │   ├── LogisticRegression(class_weight='balanced', max_iter=1000)
    │   └── CalibratedClassifierCV(method='sigmoid', cv='prefit')
    │
    └── Random Forest
        ├── No scaling needed
        ├── RandomForestClassifier(n_estimators=100, max_depth=10, balanced)
        └── CalibratedClassifierCV(method='isotonic', cv='prefit')

Total: 8 calibrated models
```

#### 4.3 Training Pipeline

```
1. Load Data
   └── PostgreSQL: fct_model_training_dataset (2,892 rows)

2. Feature Engineering
   └── Create 12 derived features → 42 total features

3. Time-Based Split
   ├── Train: 2018-09-22 to 2023-06-30 (~2,000 matches)
   ├── Validation: 2023-07-01 to 2024-06-30 (~400 matches)
   └── Test: 2024-07-01 to 2026-04-22 (~500 matches)

4. For each target:
   └── For each model type:
       ├── Train on train set
       ├── Calibrate on validation set
       ├── Evaluate on validation set
       └── Save model + scaler (if applicable)

5. Outputs
   ├── models/saved/*.pkl (12 files total)
   └── Training metrics (console + logs)
```

#### 4.4 Data Leakage Prevention

**Mechanisms**:
- ✓ Time-based splits only (no random shuffling)
- ✓ Rolling features use `rows between N preceding and 1 preceding`
- ✓ Calibration uses separate validation set
- ✓ Test set never used until final evaluation
- ✓ No future information in features
- ✓ Match-level filtering (min 5 matches played)

---

### 5. BETTING DECISION ENGINE

#### 5.1 Value Calculation

```python
# For each prediction:
model_probability = calibrated_model.predict_proba(features)[0, 1]
bookmaker_odds = get_current_odds(match, market)
implied_probability = 1 / bookmaker_odds
value_edge = model_probability - implied_probability
```

#### 5.2 Decision Rules

```python
def should_bet(probability, odds, value_edge):
    """
    Conservative betting strategy.
    
    Returns True only if ALL conditions met:
    - High confidence: probability ≥ 0.70
    - Positive value: value_edge ≥ 0.05
    - Reasonable odds: 1.50 ≤ odds ≤ 3.00
    """
    return (
        probability >= 0.70 and
        value_edge >= 0.05 and
        1.50 <= odds <= 3.00
    )
```

**Expected Behavior**:
- Recommend bet: 10-20% of matches (selective)
- Average confidence when betting: 72-80%
- Average odds taken: 1.70-2.20

#### 5.3 Confidence Levels

```python
if probability >= 0.70:
    confidence = "High"
elif probability >= 0.60:
    confidence = "Medium"
else:
    confidence = "Low"
```

---

### 6. PREDICTION OUTPUT LAYER

#### 6.1 Output Schema

```json
{
  "match": {
    "home_team": "Arsenal",
    "away_team": "Chelsea",
    "match_date": "2026-05-03",
    "league": "Premier League"
  },
  "market": "Over 2.5 Goals",
  "prediction": {
    "outcome": "Over 2.5",
    "model_probability": 0.72,
    "confidence": "High"
  },
  "betting_analysis": {
    "bookmaker_odds": 1.85,
    "implied_probability": 0.541,
    "value_edge": 0.179,
    "decision": "BET",
    "recommended_stake": "1 unit"
  },
  "model_info": {
    "model_type": "Random Forest",
    "target": "target_over_25",
    "version": "1.0",
    "trained_on": "2018-2023"
  }
}
```

#### 6.2 Prediction Script

```python
scripts/predict.py (Future)
├── Load saved models from models/saved/
├── Accept upcoming match details (CLI or API)
├── Fetch current team form from database
├── Calculate derived features
├── Generate predictions for all 4 targets
├── Apply betting decision rules
├── Output JSON with recommendations
└── Optional: Send to API or save to database
```

---

### 7. EVALUATION & MONITORING LAYER

#### 7.1 ML Performance Metrics

**Classification Metrics**:
- ROC-AUC: Discrimination ability (target ≥ 0.62)
- Brier Score: Calibration quality (target ≤ 0.24)
- Log Loss: Probability accuracy (target ≤ 0.65)
- Accuracy: Overall correctness (target ≥ 0.58)
- Precision/Recall: Per-class performance

**Overfitting Detection**:
```python
overfitting_gap = train_auc - validation_auc
# Good: gap < 0.05
# Acceptable: gap < 0.10
# Bad: gap > 0.10 (retrain with more regularization)
```

#### 7.2 Betting Performance Metrics

```python
# Backtest on test set (2024-2026)
total_bets = count(predictions where decision="BET")
wins = count(predictions where outcome_correct=True)
losses = total_bets - wins

win_rate = wins / total_bets  # Target: ≥ 55%

total_staked = total_bets * stake_per_bet
total_returned = sum(odds * stake for wins)
profit = total_returned - total_staked

roi = (profit / total_staked) * 100  # Target: ≥ 5%
yield_per_bet = roi / total_bets      # Target: ≥ 5%
```

#### 7.3 Evaluation Script

```python
scripts/evaluate_models.py (Step 16 - To Be Created)
├── Load test set (2024-2026, ~500 matches)
├── Load all 8 trained models
├── Generate predictions with probabilities
├── Apply betting decision rules
├── Calculate ML metrics (per model)
├── Calculate betting metrics (per model)
├── Compare Logistic vs Random Forest
├── Identify best model per target
├── Generate performance report (CSV/JSON)
└── Recommend model for production
```

---

### 8. PERSISTENCE & STORAGE

#### 8.1 Database Schema

```sql
-- Current (Version 1)
football_prediction_db
├── Schema: public
│   └── raw_football_matches (raw CSV data)
│
└── Schema: public_public
    ├── stg_football_matches (view)
    ├── int_match_results (view)
    ├── int_prediction_targets (view)
    ├── int_match_stats (view)
    ├── int_match_odds (view)
    ├── int_team_match_history (view)
    ├── fct_team_rolling_features (view)
    └── fct_model_training_dataset (table)

-- Future (Version 2)
└── Schema: public
    ├── predictions (table)
    │   ├── prediction_id (PK)
    │   ├── match_key (FK)
    │   ├── target
    │   ├── model_type
    │   ├── probability
    │   ├── decision
    │   ├── created_at
    │   └── actual_outcome (updated post-match)
    │
    └── betting_performance (table)
        ├── season
        ├── target
        ├── model_type
        ├── total_bets
        ├── wins
        ├── roi
        └── updated_at
```

#### 8.2 Model Storage

```
models/saved/
├── target_over_25_logistic.pkl              (calibrated model)
├── target_over_25_logistic_scaler.pkl       (feature scaler)
├── target_over_25_random_forest.pkl
├── target_btts_yes_logistic.pkl
├── target_btts_yes_logistic_scaler.pkl
├── target_btts_yes_random_forest.pkl
├── target_home_not_lose_logistic.pkl
├── target_home_not_lose_logistic_scaler.pkl
├── target_home_not_lose_random_forest.pkl
├── target_away_not_lose_logistic.pkl
├── target_away_not_lose_logistic_scaler.pkl
├── target_away_not_lose_random_forest.pkl
└── training_metadata_YYYYMMDD_HHMMSS.pkl    (config + stats)
```

---

### 9. FUTURE EXTENSIONS (Version 2+)

#### 9.1 REST API (FastAPI)

```python
api/
├── main.py
│   ├── GET  /health
│   ├── GET  /models
│   ├── POST /predict
│   │   Body: {"home_team": "Arsenal", "away_team": "Chelsea"}
│   │   Returns: predictions for all 4 targets
│   │
│   └── GET  /performance
│       Returns: historical performance metrics
│
├── models.py (Pydantic schemas)
├── database.py (SQLAlchemy connection)
└── predictor.py (load models, generate predictions)
```

#### 9.2 Frontend Dashboard (React)

```
frontend/
├── src/
│   ├── components/
│   │   ├── PredictionCard.tsx
│   │   ├── PerformanceChart.tsx
│   │   └── UpcomingMatches.tsx
│   │
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── Predictions.tsx
│   │   └── History.tsx
│   │
│   └── services/
│       └── api.ts (fetch from FastAPI)
```

#### 9.3 Advanced ML (Phase 2)

**Triggered if ROI < 5% on test set**:

```python
Phase 2 Models:
├── XGBoost
│   └── Better at capturing complex interactions
├── LightGBM
│   └── Faster training, handles large datasets
└── Neural Network (MLP)
    └── Deep learning for non-linear patterns

Ensemble Strategy:
├── Train all models
├── Calibrate each individually
├── Weighted voting based on validation AUC
└── Select top 2-3 per target
```

#### 9.4 Automated Retraining Pipeline

```python
Scheduled Job (Weekly):
1. Download latest CSV from football-data.co.uk
2. Run scripts/load_raw_data.py
3. Run dbt run (refresh transformations)
4. Check if season ended:
   └── If yes: Retrain models with new season
5. Run evaluation on last 30 days
6. Compare to previous model performance
7. Alert if performance degraded
```

---

## 🔒 DATA SECURITY & COMPLIANCE

### 10.1 Sensitive Data

**No personal data collected** - all data is publicly available match statistics.

**Database credentials**:
- ❌ Currently hardcoded in scripts (bad practice)
- ✅ Move to `.env` file (not committed to git)
- ✅ Use environment variables in production

### 10.2 API Security (Future)

```python
# Add to FastAPI endpoints
- Rate limiting (prevent abuse)
- API key authentication
- HTTPS only
- CORS restrictions
```

---

## 📈 SCALABILITY CONSIDERATIONS

### 11.1 Current Limitations

| Component | Current | Bottleneck |
|-----------|---------|-----------|
| Database | Local PostgreSQL | Single machine |
| Training | Sequential (1 model at a time) | CPU-bound |
| Predictions | Script-based | No API |
| Storage | Local disk | No backups |

### 11.2 Production Scaling Plan

**Database**: Migrate to cloud PostgreSQL (AWS RDS, Azure PostgreSQL)  
**Training**: Parallelize model training (joblib, multiprocessing)  
**Predictions**: Deploy FastAPI on cloud (AWS Lambda, Azure Functions)  
**Storage**: S3/Blob storage for models, automated backups

---

## 🧪 TESTING STRATEGY

### 12.1 Data Quality Tests (dbt)

```bash
dbt test  # 9 tests, all must pass
```

### 12.2 Unit Tests (Python - Future)

```python
tests/
├── test_feature_engineering.py
│   └── Test derived feature calculations
├── test_betting_logic.py
│   └── Test decision rules
└── test_predictions.py
    └── Test model loading and inference
```

### 12.3 Integration Tests

```python
# End-to-end test
1. Load sample match data
2. Generate predictions
3. Verify output schema
4. Check betting decisions
```

---

## 🚀 DEPLOYMENT WORKFLOW

### Current (Version 1 - Local Development)

```bash
1. Download CSV data → data/raw/
2. Load to PostgreSQL → raw_football_matches
3. Run dbt → fct_model_training_dataset
4. Train models → python scripts/train_models.py
5. Evaluate → python scripts/evaluate_models.py
6. Predict → python scripts/predict.py --match "Arsenal vs Chelsea"
```

### Future (Version 2 - Production)

```bash
1. CI/CD Pipeline (GitHub Actions):
   ├── Run dbt tests
   ├── Run Python unit tests
   └── Build Docker image

2. Deploy to Cloud:
   ├── Database: Managed PostgreSQL
   ├── API: FastAPI on container service
   ├── Models: Blob storage
   └── Frontend: Static hosting (Vercel, Netlify)

3. Monitoring:
   ├── Model performance tracking
   ├── Prediction logs
   └── Betting ROI dashboard
```

---

## 📋 PROJECT STATUS (26 April 2026)

```
✓ Step 1-14a: Data pipeline complete (2,892 clean matches)
✓ Step 15: Training script created (ready to test)
⏳ Step 16: Evaluation script (next)
⏳ Step 17: Model selection
⏳ Step 18: Production prediction script
⏳ Step 19: API development (Version 2)
⏳ Step 20: Dashboard (Version 2)
```

---

## 🎯 SUCCESS METRICS

### Phase 1 (Current - Baseline Models)

- ✓ All dbt tests passing
- ✓ Training completes without errors
- ✅ Validation AUC ≥ 0.60 for at least 3 targets
- ✅ Test set ROI ≥ 3%
- ✅ Win rate ≥ 52%

### Phase 2 (Future - Production)

- ⏳ API uptime ≥ 99%
- ⏳ Prediction latency < 200ms
- ⏳ Live betting ROI ≥ 5% over 1 season
- ⏳ Model retraining automated
- ⏳ Dashboard deployed and accessible

---

*End of System Architecture Document*
