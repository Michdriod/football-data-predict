# Prediction Features Documentation

## Overview

This document explains what data/features are required to generate predictions for upcoming football matches.

---

## 🎯 Required Input for Predictions

To predict an upcoming match, you need **ONLY these basic inputs**:

### **Minimum Required (3 fields):**
1. **Home Team Name** (e.g., "Arsenal")
2. **Away Team Name** (e.g., "Chelsea")  
3. **Match Date** (e.g., "2026-05-25")

### **Optional but Recommended:**
4. **Current Betting Odds** (for value edge calculation):
   - Home Win Odds (e.g., 1.65)
   - Draw Odds (e.g., 3.80)
   - Away Win Odds (e.g., 4.50)
   - Over 2.5 Goals Odds (e.g., 1.85)
   - Under 2.5 Goals Odds (e.g., 2.00)

---

## 🔧 How the System Generates Features

The system **automatically calculates all 44+ features** from the database using the team names and date. You don't need to provide these manually.

### **Automatic Feature Generation Process:**

```
User Input → Team Names + Date
     ↓
System Queries Database → Get each team's last 5-10 matches
     ↓
System Calculates Features → Rolling averages, form metrics
     ↓
Model Predicts → Probabilities for 4 targets
     ↓
Output → Betting recommendations
```

---

## 📊 Complete Feature Set (44 Features)

The model uses these features (all calculated automatically from historical data):

### **Match Identifiers (4 features - not used for ML)**
- `match_key` - Unique identifier
- `match_date` - Date of match
- `home_team` - Home team name
- `away_team` - Away team name

### **Home Team Form Features (18 features)**

**Last 5 Matches:**
- `home_matches_played_before` - Number of matches played
- `home_avg_goals_for_last_5` - Average goals scored
- `home_avg_goals_against_last_5` - Average goals conceded
- `home_avg_shots_for_last_5` - Average shots
- `home_avg_shots_on_target_for_last_5` - Average shots on target
- `home_avg_corners_for_last_5` - Average corners
- `home_avg_points_last_5` - Average points (3 for win, 1 for draw, 0 for loss)
- `home_over_25_rate_last_5` - % of matches with 3+ goals
- `home_btts_rate_last_5` - % of matches where both teams scored
- `home_clean_sheet_rate_last_5` - % of matches without conceding
- `home_failed_to_score_rate_last_5` - % of matches without scoring

**Last 10 Matches:**
- `home_avg_goals_for_last_10` - Average goals scored
- `home_avg_goals_against_last_10` - Average goals conceded
- `home_over_25_rate_last_10` - % of matches with 3+ goals
- `home_btts_rate_last_10` - % of matches where both teams scored

### **Away Team Form Features (18 features)**

**Same as home team, but for away team:**
- `away_matches_played_before`
- `away_avg_goals_for_last_5`
- `away_avg_goals_against_last_5`
- `away_avg_shots_for_last_5`
- `away_avg_shots_on_target_for_last_5`
- `away_avg_corners_for_last_5`
- `away_avg_points_last_5`
- `away_over_25_rate_last_5`
- `away_btts_rate_last_5`
- `away_clean_sheet_rate_last_5`
- `away_failed_to_score_rate_last_5`
- `away_avg_goals_for_last_10`
- `away_avg_goals_against_last_10`
- `away_over_25_rate_last_10`
- `away_btts_rate_last_10`

### **Derived Features (14 features - calculated from above)**

These are calculated by the model from the base features:

- `home_attack_strength` = home_avg_goals_for / league_average
- `home_defense_strength` = home_avg_goals_against / league_average
- `away_attack_strength` = away_avg_goals_for / league_average
- `away_defense_strength` = away_avg_goals_against / league_average
- `home_form` = home_avg_points_last_5
- `away_form` = away_avg_points_last_5
- `expected_home_goals` = home_attack_strength × away_defense_strength × league_avg
- `expected_away_goals` = away_attack_strength × home_defense_strength × league_avg
- `expected_total_goals` = expected_home_goals + expected_away_goals
- `goal_difference_trend_home` = home_avg_goals_for - home_avg_goals_against
- `goal_difference_trend_away` = away_avg_goals_for - away_avg_goals_against
- `form_difference` = home_form - away_form
- `btts_likelihood` = (home_btts_rate + away_btts_rate) / 2
- `over_25_likelihood` = (home_over_25_rate + away_over_25_rate) / 2

---

## 💡 Example: Predicting Arsenal vs Chelsea

### **What You Provide:**
```json
{
  "home_team": "Arsenal",
  "away_team": "Chelsea", 
  "match_date": "2026-05-25",
  "odds": {
    "home_win": 1.65,
    "draw": 3.80,
    "away_win": 4.50,
    "over_25": 1.85,
    "under_25": 2.00
  }
}
```

### **What the System Does Automatically:**

1. **Query Database** for Arsenal's last 5 matches:
   ```sql
   SELECT * FROM int_team_match_history 
   WHERE team = 'Arsenal' 
   ORDER BY match_date DESC 
   LIMIT 5
   ```
   
2. **Calculate Arsenal's Features:**
   - Last 5 matches: 3 wins, 1 draw, 1 loss
   - Avg goals for: 2.2
   - Avg goals against: 1.0
   - Over 2.5 rate: 60%
   - BTTS rate: 40%
   - etc...

3. **Query Database** for Chelsea's last 5 matches (same process)

4. **Calculate Derived Features** (14 additional features from above)

5. **Create Feature Vector** (44 total features)

6. **Load Trained Models** from `models/saved/`

7. **Generate Predictions:**
   ```json
   {
     "match": "Arsenal vs Chelsea",
     "predictions": {
       "over_25": {
         "probability": 0.68,
         "odds": 1.85,
         "implied_prob": 0.54,
         "value_edge": 0.14,
         "recommendation": "NO BET"  // Below 70% threshold
       },
       "btts_yes": {
         "probability": 0.72,
         "odds": 1.75,
         "implied_prob": 0.57,
         "value_edge": 0.15,
         "recommendation": "BET"  // Above 70% + 5% edge
       }
     }
   }
   ```

---

## 🚀 How to Use (Future Workflow)

### **Option 1: Manual Input (Current)**
```python
# Create fixture CSV
fixtures = pd.DataFrame({
    'home_team': ['Arsenal'],
    'away_team': ['Chelsea'],
    'match_date': ['2026-05-25']
})

# Run prediction (will be built in Phase 2)
python scripts/predict_upcoming.py --fixtures fixtures.csv
```

### **Option 2: API Input (Future)**
```bash
# System fetches fixtures from API automatically
python scripts/predict_today.py

# API returns fixtures → System queries DB → Calculates features → Predicts
```

---

## 🔒 Security & Scalability Features

### **1. Environment Variables (.env)**
✅ All credentials in `.env` file (not hardcoded)
✅ `.env.example` provided as template
✅ `.gitignore` prevents committing credentials

### **2. Centralized Configuration**
✅ Single `config.py` module for all settings
✅ Easy to change database without editing multiple files
✅ Validation on startup to catch configuration errors

### **3. Error Handling**
✅ Clear error messages when config missing
✅ Validation of all thresholds and parameters
✅ Graceful failures with helpful debugging info

### **4. Scalability**
✅ Database queries optimized (indexed columns)
✅ Feature calculation happens once per match
✅ Model loading cached in memory
✅ Can easily add new features without code changes

### **5. Debugging**
✅ Comprehensive logging at each step
✅ Progress tracking during long operations
✅ Test mode available (`python scripts/config.py`)
✅ Each module self-contained and testable

---

## 📋 Minimum Data Requirements

**To make predictions, the database MUST contain:**

1. **At least 5 prior matches for each team**
   - Needed to calculate rolling averages
   - System will skip predictions if insufficient data

2. **Match history in `int_team_match_history` table**
   - Automatically created by dbt from raw data
   - Contains: goals, shots, corners, results

3. **Team names must match exactly**
   - Database: "Man United"
   - Input: "Man United" ✅
   - Input: "Manchester United" ❌ (won't match)
   - Solution: Team name mapping (built in Phase 2)

---

## 🎯 Summary

**What you provide:**
- Home team name
- Away team name
- Match date
- (Optional) Current odds

**What system calculates automatically:**
- All 44 features from historical match data
- No manual feature engineering required

**What you get:**
- Probabilities for 4 prediction targets
- Betting recommendations (BET or NO BET)
- Value edge calculation
- Confidence levels

**Next step:** Build `predict_upcoming.py` in Phase 2 to automate this process.
