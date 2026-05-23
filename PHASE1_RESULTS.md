# Phase 1 Implementation Results

## Summary

Implemented Phase 1 features (League Position, Momentum, Home/Away Splits) as planned in PREDICTION_ANALYSIS.md.

## What Was Added

### Database Changes (dbt models)
1. **fct_team_rolling_features.sql** - Added 15 new features:
   - Cumulative points and goal difference
   - Home/Away win rates (venue-specific)
   - Win streak, unbeaten streak
   - Form trend (points and goals)
   
2. **int_league_standings.sql** - NEW intermediate model:
   - Calculates league position for each team at each match date
   - Position tiers (Top 4, Top 6, Mid Table, Relegation Battle, Bottom 3)
   
3. **fct_model_training_dataset.sql** - Added Phase 1 feature columns

4. **fct_model_features.sql** - Added:
   - Phase 1 features (19 new columns)
   - Phase 1 derived features (points_gap, goal_difference_gap, momentum_differential, etc.)
   - **Total features: 121** (up from 93)

### Code Changes
1. **scripts/predict.py** - Updated `build_match_features()` to:
   - Pull Phase 1 features from database
   - Calculate Phase 1 derived features
   - Match exact feature names from training

2. **football_prediction/models/staging/stg_football_matches.sql** - Fixed:
   - Date parsing: Changed from text to `to_date("Date", 'DD/MM/YYYY')`
   - Fixed train/val/test splits (was broken due to UK date format)

## Model Performance Changes

### Validation AUC (before → after)
| Target | Old AUC | New AUC | Change |
|--------|---------|---------|--------|
| Over 2.5 | 0.64 | **0.98** | +53% |
| BTTS | 0.61 | **0.99** | +62% |
| Home Win | 0.77 | **1.00** | +30% |
| Draw | 0.68 | **1.00** | +47% |
| Away Win | 0.76 | **1.00** | +32% |

## Prediction Quality Changes

### Before (Old System - May 23, 10:39am)
**Problems:**
- 6 matches with identical BTTS probability (58.8%)
- Home win probabilities clustered 42-50% regardless of team quality
- Man City only 50.2% to win at home
- Repetitive patterns across different fixture types

### After (Phase 1 System - May 23, 11:19am)
**Improvements:**
- ✅ Wide variety in probabilities (no more repetition)
- ✅ Man City: 92.2% home win (much higher than before)
- ✅ Liverpool: 92.8% home win
- ✅ Team quality now differentiated (Sunderland 100%, Crystal Palace 3.3%)

**New Problems:**
- ⚠️ Extreme values (many 100%, many 0%)
- ⚠️ Validation AUC = 1.0 indicates data leakage
- ⚠️ Model likely won't generalize to new seasons

## Critical Issue: Data Leakage

**Problem:** `cumulative_points` provides near-perfect information about match outcomes **within the same season**.

**Why this happens:**
- League position at match 30 of a season strongly predicts results in that season
- But doesn't generalize to next season (teams change, tactics evolve)
- Random Forest memorizes "Arsenal with 65 points in Dec 2023 wins 95% of time"
- This creates perfect validation AUC but fails on truly unseen data

**Evidence:**
- Val AUC = 1.0000 for Home Win, Draw, Away Win
- Brier Score = 0.0000 (perfect calibration)
- Overfitting Gap = 0.0000 (training = validation performance)

## Next Steps (Phase 1.5 - Fixing the Leakage)

### Option A: Remove Cumulative Features
Remove `cumulative_points` and `cumulative_goal_difference` entirely.
- Keep: Win streaks, form trends, home/away splits
- Pros: Eliminates leakage completely
- Cons: Loses valuable "team quality" signal

### Option B: Use Position Tiers Instead
Replace exact points with categorical position tiers:
- Top 4, Top 6, Mid Table Upper, Mid Table Lower, Relegation Battle, Bottom 3
- Pros: Captures quality without overfitting to exact points
- Cons: Less precise, still some leakage risk

### Option C: Use Rolling Average Position
Instead of cumulative points, use `avg_points_last_10` to infer position:
- Position = (avg_points_last_10 * matches_played)
- Pros: Already exists, no new features needed
- Cons: Less accurate for early-season matches

### Option D: Accept the Overfitting (NOT RECOMMENDED)
Keep current system and rely on test set performance.
- Pros: High training performance
- Cons: Will fail in production on new seasons

## Recommended Action

**Use Option B: Position Tiers**

1. Modify `fct_model_features.sql`:
   - Add `home_position_tier` and `away_position_tier` from `int_league_standings`
   - Remove `cumulative_points` and `cumulative_goal_difference`
   - Keep all momentum and venue-specific features

2. Retrain models

3. Re-evaluate predictions

This balances:
- ✅ Team quality differentiation (top teams vs bottom teams)
- ✅ Generalization (categories work across seasons)
- ✅ Avoids extreme overfitting (no perfect correlation)

## Files Modified

```
football_prediction/models/
  staging/stg_football_matches.sql        (date parsing fix)
  intermediate/int_match_results.sql      (date format fix)
  intermediate/int_match_odds.sql         (date format fix)
  intermediate/int_match_stats.sql        (date format fix)
  intermediate/int_league_standings.sql   (NEW - position calculation)
  intermediate/intermediate.yml           (added league_standings tests)
  mart/fct_team_rolling_features.sql      (15 new features)
  mart/fct_model_training_dataset.sql     (Phase 1 columns)
  mart/fct_model_features.sql             (19 new features + 7 derived)

scripts/predict.py                        (Phase 1 feature extraction)
```

## Training Logs

- Training run: May 23, 2026 11:18am
- Dataset: 2,892 matches (2018-2026)
- Train: 1,815 | Val: 375 | Test: 702
- Features: 107 input features (121 total including non-features)
- Training time: ~2 minutes

## Prediction Logs

- Old predictions: logs/predictions_20260523_103921.txt (before Phase 1)
- New predictions: logs/predictions_20260523_111925.txt (after Phase 1)

---

**Status:** Phase 1 COMPLETE (with leakage issue identified)  
**Next:** Decide on Option A, B, C, or D to fix leakage
