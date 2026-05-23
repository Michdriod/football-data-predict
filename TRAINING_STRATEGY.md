# Football Prediction Training Strategy & Roadmap

## Current Status

✅ **Data Pipeline Complete**
- 2,889 football matches loaded
- 100% odds coverage (real market odds only)
- Canonical odds with intelligent fallback
- Clear separation: prediction features vs. betting odds

✅ **Infrastructure Ready**
- dbt pipeline building all models (10 models, 17 tests)
- PostgreSQL database with clean data
- End-to-end Jupyter notebook created

---

## What We're Doing Now

### Phase 1: Validation in Jupyter Notebook (THIS WEEK)

**Location**: `/notebooks/end_to_end_pipeline.ipynb`

**Purpose**: Prove the pipeline works before production training

**Workflow**:
1. Load 2,889 matches with canonical odds
2. Train Logistic Regression for **Home Not Lose (1X)** target
3. Evaluate on test set (calibrated probabilities)
4. Simulate betting with real market odds only
5. Calculate ROI based on actual market performance
6. Document guardrails and data sources

**Outputs**:
- ✓ Model performance metrics (AUC, Brier, Accuracy)
- ✓ Betting simulation results (win rate, ROI, profit)
- ✓ Data integrity checks (odds coverage, no imputation)
- ✓ Sample predictions with confidence levels

**Validation Criteria**:
- [ ] Model AUC ≥ 0.60 on test set
- [ ] Betting win rate ≥ 55% with positive ROI
- [ ] All odds verified as real (no imputation)
- [ ] Clear logging of what was used where

---

## Forward Plan: Production Training Pipeline

### Phase 2: Full Model Training (AFTER Notebook Validation)

**Script Location**: `scripts/train_models.py` (to be enhanced)

**What Gets Trained**:
- **4 models** (one per target market)
- **2 model types** each (LR + Random Forest)
- **Total: 8 models** to compare

#### Models:

| # | Target | Market | Description |
|---|--------|--------|-------------|
| 1 | `target_home_not_lose` | 1X | Home win or draw |
| 2 | `target_away_not_lose` | X2 | Away win or draw |
| 3 | `target_over_25` | Over 2.5 Goals | 3+ goals total |
| 4 | `target_btts_yes` | BTTS | Both teams score |

Each target gets:
- **Logistic Regression** (baseline, fast, interpretable)
- **Random Forest** (advanced, captures non-linearity)

#### Training Data:

| Set | Proportion | Dates | Purpose |
|-----|-----------|-------|---------|
| Train | 70% | 2018-08-10 to 2023-07-01 | Model learning |
| Val | 15% | 2023-07-01 to 2024-07-01 | Hyperparameter tuning + calibration |
| Test | 15% | 2024-07-01 to 2026-04-22 | Final evaluation |

**All 2,889 matches used** (odds not required for prediction)

#### Hyperparameter Tuning:

```
Logistic Regression:
  - C: [0.1, 1, 10]
  - max_iter: 1000
  - class_weight: balanced

Random Forest:
  - n_estimators: [50, 100, 200]
  - max_depth: [5, 10, 15]
  - min_samples_split: [10, 20]
  - class_weight: balanced
```

#### Model Calibration:

All probabilities calibrated on validation set using **Isotonic Regression**

#### Model Comparison:

| Metric | LR | RF | Winner |
|--------|----|----|--------|
| AUC | X | X | Higher |
| Calibration | X | X | Better |
| Interpretability | X | X | LR |
| Speed | X | X | LR |
| Non-linearity | X | X | RF |

**Selection Criterion**: Best AUC on validation set

---

### Phase 3: Betting Value Evaluation

**What We Do**:
1. Use test set predictions
2. Only evaluate on matches with real odds (all 2,889)
3. Calculate implied probabilities from market odds
4. Compute expected value for each match

**Betting Decision Logic**:
```
Place bet if ALL of:
  - Model probability ≥ 60% (or 70% for high confidence)
  - Value edge ≥ 5% (model_prob - implied_prob)
  - Odds within reasonable range (1.50 - 3.00)
  - Odds are REAL (has_real_odds = True)
```

**ROI Calculation**:
```
ROI = (Total Profit / Total Staked) × 100
    = ((Wins × Avg_Odds) - Losses) / Num_Bets × 100
```

**Success Criteria**:
- Win rate ≥ 55%
- ROI ≥ 5%
- AUC ≥ 0.60
- No data leakage (time-based split)

---

### Phase 4: Live/Future Predictions

**Input**: 
- Upcoming match (features from rolling stats)
- Current market odds (from user or API)

**Output**:
```json
{
  "match": "Arsenal vs Chelsea",
  "market": "Over 2.5 Goals",
  "model_probability": 0.68,
  "market_odds": 1.90,
  "implied_probability": 0.526,
  "value_edge": 0.154,
  "confidence": "High",
  "recommendation": "Bet"
}
```

**No Odds Available**:
```json
{
  "match": "Arsenal vs Chelsea",
  "model_probability": 0.68,
  "confidence": "High",
  "recommendation": "Prediction only (no odds provided)"
}
```

---

## Data Separation (Critical)

### Prediction Model

**Uses**: All 2,889 matches

**Features**:
- Home team rolling stats (goals, shots, corners, etc.)
- Away team rolling stats
- Form momentum, attack/defense strength
- Historical head-to-head if available

**Does NOT use**:
- Market odds
- Bookmaker odds
- Any betting-related data

**Target**: Win/Draw/Loss probability

### Betting Evaluation

**Uses**: All 2,889 matches WITH real odds (100% coverage)

**Features**:
- Model predictions
- Real market odds (Bet365, Avg Pre-Match, Max Market)
- Implied probabilities (calculated from odds)
- Expected value edge

**Does NOT use**:
- Fake/imputed odds
- Forward-filled odds
- Mean-filled odds

**Output**: ROI, win rate, bet recommendations

---

## Guardrails

### Data Integrity

- ✅ `has_real_odds` flag on every match
- ✅ `odds_source` tracks data provenance
- ✅ NO forward-fill of missing odds
- ✅ NO mean imputation for ROI
- ✅ NO artificial odds treated as real
- ✅ All odds real market odds

### Model Integrity

- ✅ Time-based split (train < val < test)
- ✅ NO random shuffle (prevents leakage)
- ✅ Calibration on validation set only
- ✅ Feature scaling applied consistently
- ✅ No target data in features

### Betting Integrity

- ✅ ROI calculated only on real odds
- ✅ Expected value only on validated markets
- ✅ Clear logging of bet count/win rate
- ✅ No silently filled missing odds
- ✅ Explicit inclusion/exclusion of matches

---

## Timeline

| Week | Phase | Deliverable |
|------|-------|-------------|
| **THIS** | Validation | ✅ End-to-end notebook working |
| Next | Training | ✅ 8 models trained |
| Next | Evaluation | ✅ ROI simulation completed |
| Next | Production | ✅ API ready |
| Future | Monitoring | ✅ Live predictions active |

---

## Files & Locations

```
football-data-predict/
├── notebooks/
│   ├── end_to_end_pipeline.ipynb      ← START HERE
│   └── test_training_pipeline.ipynb   ← Old, keep for reference
├── scripts/
│   ├── train_models.py                ← Production training (to enhance)
│   ├── evaluate_models.py             ← ROI simulation
│   └── predict.py                     ← Live predictions
├── models/
│   └── saved/                         ← Trained model files (.pkl/.joblib)
├── football_prediction/
│   ├── models/
│   │   ├── staging/stg_football_matches.sql
│   │   ├── intermediate/int_odds_canonical.sql    ← NEW
│   │   └── mart/fct_model_training_dataset.sql    ← UPDATED
│   └── tests/
└── CLAUDE.md                          ← Master instructions (this file)
```

---

## Commands Reference

### Validate in Notebook
```bash
cd /Users/mac/Desktop/football-data-predict
source pred/bin/activate
jupyter notebook notebooks/end_to_end_pipeline.ipynb
```

### Production Training (Coming)
```bash
cd /Users/mac/Desktop/football-data-predict
source pred/bin/activate
python scripts/train_models.py --target all --model-type both
```

### Generate dbt Models
```bash
cd /Users/mac/Desktop/football-data-predict/football_prediction
source ../pred/bin/activate
dbt run && dbt test
```

---

## Success Criteria (Full Pipeline)

✅ **Data Phase** (DONE)
- [x] 100% odds coverage
- [x] No imputation
- [x] Canonical odds created

⏳ **Model Phase** (IN PROGRESS)
- [ ] Notebook validation passes
- [ ] 8 models trained
- [ ] Best model selected per target

⏳ **Betting Phase** (PENDING)
- [ ] ROI ≥ 5% on test set
- [ ] Win rate ≥ 55%
- [ ] AUC ≥ 0.60 per model

⏳ **Production Phase** (PENDING)
- [ ] API deployed
- [ ] Live predictions working
- [ ] Monitoring active

---

## Next Immediate Action

**OPEN & RUN THE NOTEBOOK**:

```bash
jupyter notebook notebooks/end_to_end_pipeline.ipynb
```

**Execute each cell** to:
1. Validate data loads correctly
2. Confirm odds coverage is 100%
3. Train example model (Logistic Regression for 1X)
4. Simulate betting on test set
5. Confirm ROI calculation works

**After validation passes, we proceed to production training.**

---

*Last updated: 2026-04-27*
*Status: Ready for notebook validation*
