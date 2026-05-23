# System Audit: Phase 1 Feature Awareness

**Date:** May 23, 2026  
**Purpose:** Verify all system components are using Phase 1 features correctly

---

## ✅ Component Status

### 1. Database (dbt models)

**Status: ✅ COMPLETE**

- `fct_team_rolling_features.sql` - Calculates 15 Phase 1 features
- `int_league_standings.sql` - NEW model for position tracking
- `fct_model_training_dataset.sql` - Includes all Phase 1 features
- `fct_model_features.sql` - 121 total columns (15 Phase 1 + derived features)

**Phase 1 Features in Database:**
```
1. home_cumulative_points
2. away_cumulative_points
3. home_cumulative_goal_difference
4. away_cumulative_goal_difference
5. home_win_streak
6. away_win_streak
7. home_unbeaten_streak
8. away_unbeaten_streak
9. home_form_trend_points
10. away_form_trend_points
11. home_form_trend_goals
12. away_form_trend_goals
13. points_gap (derived)
14. goal_difference_gap (derived)
15. win_streak_differential (derived)
```

**Additional derived features:**
- momentum_differential
- team_quality_disparity
- win_rate_differential
- home_advantage_factor

---

### 2. Training Script (scripts/train_models.py)

**Status: ✅ AUTOMATIC (uses database features)**

- Reads from `fct_model_features` table
- Automatically includes all 121 columns
- No manual feature list required
- **Verified:** Trained models have 107 input features

---

### 3. Prediction Script (scripts/predict.py)

**Status: ✅ UPDATED**

**Function `get_team_latest_form()`:**
- ✅ Pulls from `fct_team_rolling_features` table
- ✅ Gets all Phase 1 features automatically

**Function `build_match_features()`:**
- ✅ Extracts Phase 1 features from database results:
  ```python
  'home_cumulative_points': home_features.get('cumulative_points', 0)
  'home_win_streak': home_features.get('win_streak', 0)
  'home_form_trend_points': home_features.get('form_trend_points', 0)
  # ... etc
  ```

**Function `build_match_features()` derived features:**
- ✅ Calculates `points_gap`, `goal_difference_gap`
- ✅ Calculates `team_quality_disparity`
- ✅ Calculates `momentum_differential`, `win_streak_differential`
- ✅ Calculates `win_rate_differential`, `home_advantage_factor`

---

### 4. Evaluation Script (scripts/evaluate_models.py)

**Status: ✅ AUTOMATIC (uses database features)**

- Reads test data from `fct_model_features` table
- Uses same feature columns as training
- No manual updates required

---

## 🔍 Data Leakage Analysis

### Problem Identified

**Symptoms:**
- Validation AUC = 1.0000 for Home Win, Draw, Away Win
- Test predictions showing extreme values (100%, 0%)
- Perfect Brier Score = 0.0000

**Root Cause:**
`cumulative_points` provides near-perfect information about outcomes **within a season**.

**Example of Leakage:**
```
Match: Arsenal (65 pts) vs Burnley (18 pts) on Dec 31, 2023
Model learns: "65 pts vs 18 pts = 95% home win"

But in next season:
Match: Arsenal (65 pts) vs Burnley (18 pts) on Dec 31, 2024
Different context! Last season's Arsenal ≠ this season's Arsenal
```

### Why This Happens

1. **Within-season prediction:** Model memorizes point totals
2. **Across-season failure:** Points reset, teams change
3. **Random Forest overfitting:** Memorizes exact point values
4. **Temporal data:** Position at match 30 predicts match 31-38 perfectly

---

## 🔧 Option B Implementation Plan

### What Will Change

**REMOVE (causes leakage):**
- `home_cumulative_points`
- `away_cumulative_points`
- `home_cumulative_goal_difference`
- `away_cumulative_goal_difference`
- `points_gap` (derived from cumulative_points)
- `goal_difference_gap` (derived from cumulative_GD)

**ADD (safer alternative):**
- `home_position_tier` (categorical: Top 4, Top 6, Mid Table, etc.)
- `away_position_tier`
- `position_tier_gap` (numerical: 1=home better, -1=away better, 0=equal)

**KEEP (no leakage):**
- All momentum features (win_streak, unbeaten_streak, form_trend)
- All venue-specific features (home_win_rate_last_5, etc.)
- All rolling averages (already excluded current match)

### Implementation Steps

1. **Update `fct_model_features.sql`:**
   - Join with `int_league_standings` to get position_tier
   - Replace cumulative features with tier features
   - Calculate position_tier_gap

2. **Update `scripts/predict.py`:**
   - Query `int_league_standings` for current position
   - Replace cumulative features with position_tier
   - Calculate position_tier_gap

3. **Rebuild dbt pipeline:**
   ```bash
   cd football_prediction && dbt run
   ```

4. **Retrain models:**
   ```bash
   python scripts/train_models.py
   ```

5. **Re-test predictions:**
   ```bash
   python scripts/predict.py --fetch-odds --days 7
   ```

### Expected Results

**Validation AUC:**
- Over 2.5: 0.75-0.80 (down from 0.98, but more realistic)
- Home Win: 0.78-0.82 (down from 1.00)
- BTTS: 0.72-0.76 (down from 0.99)

**Predictions:**
- No more 100% / 0% extremes
- Man City: 70-80% home win (not 92%)
- Arsenal away: 60-70% win (not 100%)
- Mid-table matches: 40-55% ranges

**Generalization:**
- Model will work across seasons
- Position tiers are stable (Top 4 teams behave similarly across years)
- Less overfitting, better real-world performance

---

## 📝 Summary

**Current State:**
- ✅ All components aware of Phase 1 features
- ✅ Database has 121 columns with Phase 1 enhancements
- ✅ predict.py correctly extracts Phase 1 features
- ✅ train_models.py uses all features automatically
- ⚠️  Data leakage from cumulative_points causing overfitting

**Recommended Action:**
**Implement Option B** - Replace cumulative points with position tiers

This will:
- ✅ Keep team quality differentiation
- ✅ Eliminate data leakage
- ✅ Improve generalization to new seasons
- ✅ Maintain momentum and venue features
- ✅ Produce realistic probabilities (no 100%/0%)

---

**Ready to proceed with Option B implementation?**
