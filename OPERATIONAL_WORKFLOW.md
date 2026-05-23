# Football Prediction System - Operational Workflow

**Date:** May 22, 2026  
**Status:** Production-Ready (V1.0)  
**Purpose:** Complete guide for keeping the system updated and generating live predictions

---

## 📊 Understanding the Two Data Flows

Your system needs **two separate data flows** that serve different purposes:

### **Flow 1: TRAINING DATA (Historical Results)**
**Purpose:** Keep the model trained on latest completed matches  
**Source:** football-data.co.uk CSV files  
**Frequency:** Weekly during season (every Monday)  
**Updates:** Database → dbt features → retrain models (monthly)

### **Flow 2: PREDICTION DATA (Upcoming Fixtures)**  
**Purpose:** Generate predictions for matches that haven't been played yet  
**Source:** Premier League fixtures + current odds  
**Frequency:** Weekly (every Friday before gameweek)  
**Requires:** Fixture list → team stats → predictions

---

## 🔄 Weekly Update Cycle (During Active Season)

### **Every Monday Morning: Update with Weekend Results**

#### **NEW: One-Command Automated Update** ⭐ **RECOMMENDED**

```bash
cd /Users/mac/Desktop/football-data-predict

# Activate virtual environment
source pred/bin/activate

# ONE COMMAND - does everything automatically:
# 1. Loads CSV into database
# 2. Runs dbt pipeline
# 3. Checks if 20+ new matches
# 4. Retrains models if threshold met
# 5. Compares performance vs old models
# 6. Updates only if improved
python scripts/auto_update.py --csv data/raw/E0_2025-26.csv

# Force retrain even if below 20 matches
python scripts/auto_update.py --csv data/raw/E0_2025-26.csv --force-retrain
```

**What happens automatically:**
- ✅ Deletes old 2025-26 season data
- ✅ Loads new CSV matches
- ✅ Runs dbt pipeline (all 10 models + 17 tests)
- ✅ Checks: new match count vs last training
- ✅ If ≥20 new: Retrains all models on full dataset (~2 min)
- ✅ Compares new vs old validation AUC
- ✅ Replaces models only if ≥3 of 4 targets improved
- ✅ No backups needed (keeps best models always)

**Expected output:**
```
================================================================================
AUTOMATED FOOTBALL DATA UPDATE PIPELINE
================================================================================

Started: 2026-05-22 09:00:00
CSV File: data/raw/E0_2025-26.csv

📊 Initial match count (features): 2,889

================================================================================
STEP 1: LOADING CSV DATA
================================================================================

📁 CSV File: data/raw/E0_2025-26.csv
📅 Season: 2025-26

  Reading CSV...
  ✓ Read 385 matches from CSV

  Deleting existing 2025-26 data from database...
  ✓ Deleted 375 existing rows for season 2025-26

  Loading 385 new matches to database...
  ✓ Successfully loaded 385 matches

================================================================================
STEP 2: RUNNING DBT PIPELINE
================================================================================

📂 dbt Project: football_prediction

  Running: dbt run
  ✓ dbt run completed (10 models built)

  Running: dbt test
  ✓ dbt test completed (17 tests passed)

================================================================================
STEP 3: CHECKING RETRAIN THRESHOLD
================================================================================

  Initial matches: 2,889
  Updated matches: 2,899
  New matches:     10
  Threshold:       20

  ⏭️  Threshold not met (10 < 20)
     → Skipping retraining

================================================================================
UPDATE COMPLETE (No retraining needed)
================================================================================
```

---

#### **Alternative: Manual Step-by-Step** (Old Method)

#### **Step 1: Download Latest Results**
```bash
# Go to: https://www.football-data.co.uk/englandm.php
# Download: E0 (Premier League) - Current season
# Example: E0_2025-26.csv
# Save to: data/raw/E0_2025-26.csv
```

**Important:** football-data.co.uk updates **2-3 days after matches**, usually by Tuesday/Wednesday.

#### **Step 2: Update Database**
```bash
cd /Users/mac/Desktop/football-data-predict

# Activate virtual environment
source pred/bin/activate

# Load new data (replaces old 2025-26 season data)
python scripts/load_raw_data.py --season 2025-26 --no-backup

# Verify load succeeded
psql -U postgres -d football_prediction_db -c "\
  SELECT COUNT(*) as total_matches, MAX(match_date) as latest_match \
  FROM raw_football_matches \
  WHERE \"Div\" = 'E0';"
```

**Expected output:** Should show increased match count and latest date = last weekend.

#### **Step 3: Rebuild Rolling Features**
```bash
# Run dbt to recalculate all rolling features
cd football_prediction
dbt run

# Run tests to verify data quality
dbt test

# Return to project root
cd ..
```

**What this does:**
- Recalculates each team's last 5 matches stats
- Updates form metrics (goals for/against, clean sheets, etc.)
- Rebuilds the final feature table for predictions

#### **Step 4: Verify Update Success**
```bash
# Check feature table has latest data
psql -U postgres -d football_prediction_db -c "\
  SELECT COUNT(*) as total_features, MAX(match_date) as latest \
  FROM fct_model_features;"

# Quick evaluation check
python scripts/evaluate_models.py
```

---

## 🎯 Generating Predictions for Upcoming Matches

### **Current Status: Manual Fixture Input Required**

The system has trained models but needs a way to:
1. Get upcoming fixture list
2. Calculate team features for those fixtures
3. Generate predictions

### **Every Friday: Predict Next Weekend's Matches**

#### **Option A: Manual Prediction (Current Capability)**

**Step 1: Get Upcoming Fixtures**
- Visit: https://www.premierleague.com/fixtures
- Or: https://www.bbc.com/sport/football/premier-league/scores-fixtures
- Note down next gameweek fixtures

**Step 2: Create Fixture CSV**
Create file: `data/upcoming/fixtures_YYYY-MM-DD.csv`

```csv
Date,HomeTeam,AwayTeam
25/05/2026,Arsenal,Everton
25/05/2026,Brentford,Newcastle
25/05/2026,Brighton,Man United
25/05/2026,Chelsea,Bournemouth
25/05/2026,Crystal Palace,Aston Villa
25/05/2026,Fulham,Man City
25/05/2026,Leicester,West Ham
25/05/2026,Liverpool,Wolves
25/05/2026,Southampton,Nottingham Forest
25/05/2026,Tottenham,Leeds
```

**Step 3: Get Current Odds (Optional but Recommended)**
Visit: https://www.oddschecker.com/football/english/premier-league

Add odds to CSV:
```csv
Date,HomeTeam,AwayTeam,B365H,B365D,B365A,B365>2.5,B365<2.5
25/05/2026,Arsenal,Everton,1.40,4.50,8.00,1.85,2.00
25/05/2026,Brentford,Newcastle,2.20,3.40,3.30,1.90,1.95
```

**Step 4: Generate Predictions**
```bash
# Currently: Manual lookup required
# MISSING: Automated prediction script

# Temporary workaround: Use evaluation results as reference
python scripts/evaluate_models.py
```

---

## ⚠️ Missing Component: `predict_upcoming.py`

**What's Needed:** A script that takes upcoming fixtures and generates predictions.

**Required Functionality:**
```python
# Input: Fixture CSV or manual team names
python scripts/predict_upcoming.py \
  --home-team "Arsenal" \
  --away-team "Chelsea" \
  --date "2026-05-25"

# OR batch mode:
python scripts/predict_upcoming.py --fixtures data/upcoming/fixtures_2026-05-25.csv

# Output: JSON with predictions + betting recommendations
{
  "match": "Arsenal vs Chelsea",
  "date": "2026-05-25",
  "predictions": {
    "Over 2.5 Goals": {
      "probability": 0.68,
      "confidence": "HIGH",
      "recommendation": "BET",
      "value_edge": 0.12
    },
    "BTTS": {
      "probability": 0.72,
      "confidence": "HIGH",
      "recommendation": "BET"
    },
    "Home Not Lose (1X)": {
      "probability": 0.85,
      "confidence": "HIGH",
      "recommendation": "NO BET"
    }
  }
}
```

**How It Should Work:**
1. Query database for team's latest stats (last 5 matches)
2. Calculate same features dbt creates
3. Load trained models from `models/saved/`
4. Generate predictions with calibrated probabilities
5. Compare against current odds (if provided)
6. Output betting recommendations

---

## 🗓️ Recommended Weekly Schedule

### **During Active Season (August - May)**

| Day | Time | Task | Script | Duration |
|-----|------|------|--------|----------|
| **Tuesday** | 9:00 AM | Download latest CSV | Manual | 2 min |
| **Tuesday** | 9:05 AM | Update database | `load_raw_data.py --season 2025-26` | 1 min |
| **Tuesday** | 9:06 AM | Rebuild features | `cd football_prediction && dbt run` | 2 min |
| **Tuesday** | 9:08 AM | Verify update | `psql` or `evaluate_models.py` | 2 min |
| **Friday** | 5:00 PM | Get next fixtures | Manual (premierleague.com) | 5 min |
| **Friday** | 5:05 PM | Get current odds | Manual (oddschecker.com) | 5 min |
| **Friday** | 5:10 PM | Generate predictions | `predict_upcoming.py` (TO BUILD) | 1 min |
| **Friday** | 5:11 PM | Review & decide | Manual analysis | 10 min |

**Monthly Tasks:**
- **1st of Month:** Retrain models (`train_models.py`) - 5 min
- **1st of Month:** Run backtest to verify performance - 2 min

**Total Weekly Time:** ~30 minutes

---

## 🔧 Monthly Retraining (First Tuesday of Each Month)

**When to Retrain:**
- After 20+ new matches added
- Monthly during active season
- At season start with new season data
- If model performance degrades

**Retraining Process:**
```bash
# 1. Ensure latest data loaded
python scripts/load_raw_data.py --season 2025-26 --no-backup
cd football_prediction && dbt run && cd ..

# 2. Retrain all models
python scripts/train_models.py

# 3. Evaluate performance
python scripts/evaluate_models.py

# 4. Compare to previous models
# Check: Val AUC should be ≥ 0.70 for double chance markets

# 5. Run backtest
python scripts/backtest.py

# 6. If performance improved, keep new models
# If worse, investigate data quality issues
```

---

## 🚀 Automation Options

### **Level 1: Semi-Automated (Recommended for Now)**
**What:** Manual fixture input, automated predictions  
**Requirements:**
- Create `predict_upcoming.py` script ✅ Can be built now
- Weekly CSV download (2 min manual task)
- Weekly fixture list (5 min manual task)

**Workflow:**
```bash
# One command for weekly update
bash scripts/weekly_update.sh

# One command for predictions
python scripts/predict_upcoming.py --fixtures fixtures.csv
```

### **Level 2: API Integration (Future Enhancement)**
**What:** Automated fixture fetching + odds monitoring  
**Requirements:**
- API-Football account (free tier: 100 calls/day)
- The Odds API account (free tier: 500 calls/month)
- Create `fetch_upcoming_matches.py`
- Create `fetch_current_odds.py`

**Workflow:**
```bash
# Fully automated - run daily
python scripts/daily_update_and_predict.py
```

### **Level 3: Full Production System (Future)**
**What:** Web dashboard + REST API + automated alerts  
**Requirements:**
- FastAPI backend
- React frontend
- Scheduled tasks (cron)
- Email/SMS notifications
- Cloud deployment

---

## 📋 Typical Weekly Workflow Example

### **Example: Predict Gameweek 38 (May 25, 2026)**

**Tuesday, May 20:**
```bash
# 1. Download E0_2025-26.csv (includes matches up to May 18)
# 2. Update system
python scripts/load_raw_data.py --season 2025-26 --no-backup
cd football_prediction && dbt run && cd ..

# 3. Verify
python scripts/evaluate_models.py
# ✅ Models still performing well (AUC 0.74+ on double chance)
```

**Friday, May 23:**
```bash
# 4. Get upcoming fixtures manually:
# - Arsenal vs Everton (Sat 3pm)
# - Chelsea vs Bournemouth (Sat 3pm)
# - Man City vs Liverpool (Sat 5:30pm)
# (... 7 more matches)

# 5. Get current odds from oddschecker.com
# - Arsenal: 1.40 (H), 4.50 (D), 8.00 (A)
# - Over 2.5: 1.85, Under 2.5: 2.00

# 6. Create data/upcoming/fixtures_2026-05-25.csv

# 7. Generate predictions
python scripts/predict_upcoming.py --fixtures data/upcoming/fixtures_2026-05-25.csv

# Output shows:
# Arsenal vs Everton:
#   - Home Not Lose (1X): 85% prob, Odds 1.11 → NO BET (no value)
#   - Over 2.5: 68% prob, Odds 1.85 → NO BET (below 70% threshold)
#   - BTTS: 72% prob, Value edge 12% → BET ✅
```

**Saturday, May 24:**
```bash
# Place selected bets based on recommendations
# Track actual results for future validation
```

---

## 📊 Data Quality Checks

### **After Each Update, Verify:**

```bash
# 1. Check match count increased
psql -U postgres -d football_prediction_db -c "\
  SELECT 
    COUNT(*) as total_matches,
    MIN(match_date) as first_match,
    MAX(match_date) as latest_match
  FROM raw_football_matches
  WHERE \"Div\" = 'E0';"

# 2. Check no NULL values in key columns
psql -U postgres -d football_prediction_db -c "\
  SELECT 
    COUNT(*) FILTER (WHERE home_avg_goals_for_last_5 IS NULL) as null_home_features,
    COUNT(*) FILTER (WHERE away_avg_goals_for_last_5 IS NULL) as null_away_features
  FROM fct_model_features;"
# Should return: null_home_features = 0, null_away_features = 0

# 3. Check dbt tests pass
cd football_prediction && dbt test
# Should show: all tests passed
```

---

## 🎯 Current System Capabilities

### **✅ What Works Now:**
- ✅ Load historical CSV data
- ✅ Clean and transform with dbt
- ✅ Train calibrated ML models
- ✅ Evaluate on test set
- ✅ Backtest historical performance
- ✅ Generate example predictions

### **❌ What's Missing:**
- ❌ Automated fixture fetching
- ❌ Live prediction generation for upcoming matches
- ❌ Odds monitoring integration
- ❌ Web dashboard for viewing predictions
- ❌ Automated betting recommendations

### **🔨 What Needs to Be Built:**
1. **Priority 1:** `predict_upcoming.py` - Generate predictions for fixture list
2. **Priority 2:** `weekly_update.sh` - One-click update script
3. **Priority 3:** Fixture template CSV + documentation
4. **Priority 4:** API integration scripts (future)
5. **Priority 5:** Web dashboard (future)

---

## 💡 Quick Reference Commands

### **Weekly Update:**
```bash
# Full update sequence (every Tuesday)
python scripts/load_raw_data.py --season 2025-26 --no-backup
cd football_prediction && dbt run && dbt test && cd ..
python scripts/evaluate_models.py
```

### **Monthly Retrain:**
```bash
# First Tuesday of month (after ~20 new matches)
python scripts/train_models.py
python scripts/evaluate_models.py
python scripts/backtest.py
```

### **Generate Predictions:**
```bash
# CURRENT: Manual lookup required
# FUTURE: Will be automated
python scripts/predict_upcoming.py --fixtures data/upcoming/fixtures_DATE.csv
```

---

## 📞 Troubleshooting

### **Issue: "No new matches after update"**
**Cause:** football-data.co.uk not yet updated  
**Solution:** Wait 1-2 days after matches, check website first

### **Issue: "NULL values in features"**
**Cause:** Team hasn't played 5+ matches yet  
**Solution:** Normal at season start, features valid after gameweek 5

### **Issue: "Models performing worse"**
**Cause:** Odds changed significantly, or seasonal variance  
**Solution:** Check backtest, retrain if needed, may need new features

### **Issue: "Cannot predict upcoming fixtures"**
**Cause:** `predict_upcoming.py` not yet created  
**Solution:** Script needs to be built (next priority)

---

## 🎯 Next Steps

### **Immediate (This Week):**
1. Create `predict_upcoming.py` script
2. Test with manual fixture input
3. Document prediction workflow
4. Create fixture CSV template

### **Short Term (This Month):**
1. Automate weekly update (shell script)
2. Set up prediction tracking spreadsheet
3. Compare predictions to actual results
4. Refine betting thresholds based on real performance

### **Long Term (Next Quarter):**
1. API integration for fixtures
2. Automated odds fetching
3. Web dashboard for predictions
4. Backtesting automation
5. Model performance monitoring

---

**Last Updated:** May 22, 2026  
**System Version:** 1.0 Production  
**Contact:** See CLAUDE.md for system architecture
y or after that has been added should we r