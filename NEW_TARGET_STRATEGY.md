# New Target Strategy - Complete Match Coverage

**Date:** May 23, 2026  
**Status:** ✅ Database Updated, Ready for Training

---

## 🎯 New Target Structure (7 Betting + 1 Prediction)

### **1. Over/Under Goals (1 target)**
| Target | Count | % | Odds Available? |
|---|---|---|---|
| Over 2.5 Goals | 1,638 | 54.7% | ✅ Yes (totals market) |

---

### **2. Match Result 3-Way (3 targets - NEW!)**
| Target | Count | % | Odds Available? |
|---|---|---|---|
| **Home Win** | 1,312 | **43.8%** | ✅ **Yes (h2h market)** |
| **Draw** | 686 | **22.9%** | ✅ **Yes (h2h market)** |
| **Away Win** | 994 | **33.2%** | ✅ **Yes (h2h market)** |

**Total:** 2,992 matches (100%)

---

### **3. Double Chance (2 targets)**
| Target | Count | % | Odds Available? |
|---|---|---|---|
| Home Not Lose (1X) | 1,998 | 66.8% | ✅ Yes (calculated) |
| Away Not Lose (X2) | 1,680 | 56.1% | ✅ Yes (calculated) |

---

### **4. BTTS (1 target - PREDICTION ONLY)**
| Target | Count | % | Odds Available? |
|---|---|---|---|
| BTTS Yes | 1,597 | 53.4% | ❌ No (not in API) |

---

## 📊 Target Distribution Analysis

### **Class Balance:**
```
Over 2.5:        55% / 45%  ✅ Well balanced
Home Win:        44% / 56%  ✅ Reasonable
Draw:            23% / 77%  ⚠️  Imbalanced (harder to predict)
Away Win:        33% / 67%  ✅ Reasonable
Home Not Lose:   67% / 33%  ✅ Reasonable
Away Not Lose:   56% / 44%  ✅ Well balanced
BTTS Yes:        53% / 47%  ✅ Well balanced
```

**Note:** Draw is naturally imbalanced (only 23% of matches), but we have **686 draws** which is enough for training.

---

## 🔄 What Changed

### **Database (dbt models):**
✅ Added 3 new columns to `int_prediction_targets`:
- `target_home_win` (1,312 matches)
- `target_draw` (686 matches)
- `target_away_win` (994 matches)

### **Configuration (config.py):**
✅ Updated `TARGETS` dict with 7 targets:
```python
TARGETS = {
    # Over/Under Goals
    'target_over_25': 'Over 2.5 Goals',
    
    # Match Result (3-way)
    'target_home_win': 'Home Win',
    'target_draw': 'Draw',
    'target_away_win': 'Away Win',
    
    # Double Chance (combined)
    'target_home_not_lose': 'Home Not Lose (1X)',
    'target_away_not_lose': 'Away Not Lose (X2)',
    
    # BTTS (prediction only)
    'target_btts_yes': 'Both Teams To Score (Prediction Only)'
}
```

---

## 📡 Odds API Coverage

### **What We Get from The Odds API:**

#### **h2h Market (Match Result):**
```json
{
  "home_win_odds": 3.90,
  "draw_odds": 3.80,
  "away_win_odds": 1.80
}
```
✅ Covers: target_home_win, target_draw, target_away_win  
✅ Covers: target_home_not_lose (home + draw), target_away_not_lose (away + draw)

#### **totals Market (Over/Under):**
```json
{
  "over_25_odds": 1.65,
  "under_25_odds": 2.20
}
```
✅ Covers: target_over_25

#### **BTTS Market:**
```
❌ NOT AVAILABLE from UK bookmakers
```
⚠️ target_btts_yes: Prediction only, no betting recommendations

---

## 🤖 Model Training Strategy

### **Models to Train (7 targets × 1 model type = 7 models):**

1. **target_over_25** - Random Forest
2. **target_home_win** - Random Forest (NEW!)
3. **target_draw** - Random Forest (NEW!)
4. **target_away_win** - Random Forest (NEW!)
5. **target_home_not_lose** - Random Forest
6. **target_away_not_lose** - Random Forest
7. **target_btts_yes** - Random Forest (prediction only)

### **Training Command:**
```bash
source pred/bin/activate
python scripts/train_models.py
```

This will:
- Load 2,889 matches from `fct_model_training_dataset`
- Split by time: Train (<2023-07-01), Val (2023-2024), Test (>2024-07-01)
- Train 7 Random Forest models + calibrate probabilities
- Save models to `models/saved/`

---

## 🎯 Prediction Output Example

### **Arsenal vs Chelsea (2026-05-25 15:00)**

```
📊 BETTING OPPORTUNITIES (with odds):
═══════════════════════════════════════════════

Match Result (Pick ONE):
  ✅ Home Win:  52% prob vs 2.10 odds → VALUE: 4.4% → BET
  ❌ Draw:      28% prob vs 3.40 odds → NO VALUE
  ❌ Away Win:  20% prob vs 4.20 odds → NO VALUE

Double Chance (combined):
  ✅ Home Not Lose (1X): 80% prob vs 1.25 odds → NO BET (low value)
  ❌ Away Not Lose (X2): 48% prob vs 2.15 odds → NO VALUE

Over/Under Goals:
  ✅ Over 2.5: 68% prob vs 1.70 odds → VALUE: 9.2% → BET

═══════════════════════════════════════════════
ℹ️  PREDICTION ONLY (no odds):
  
  Both Teams To Score: 65% probability
  (No betting recommendation - odds not available)

═══════════════════════════════════════════════
💡 RECOMMENDED BETS:
  
  1. Home Win @ 2.10 (Value: 4.4%)
  2. Over 2.5 Goals @ 1.70 (Value: 9.2%)
```

---

## ⚠️ Important Notes

### **1. Draw Predictions are Harder:**
- Only 23% of matches end in draws
- Model may struggle to identify draws
- Expect lower accuracy for `target_draw` vs other targets

### **2. Match Result Mutual Exclusivity:**
- Home Win, Draw, and Away Win are mutually exclusive
- Probabilities should sum to ~100% (we can enforce this with softmax)
- Currently trained independently - consider ensemble in future

### **3. BTTS Limitation:**
- We train the model and show predictions
- BUT we cannot calculate betting value (no odds)
- User must manually decide whether to bet on BTTS

---

## 🚀 Next Steps

### **Step 1: Train New Models**
```bash
source pred/bin/activate
python scripts/train_models.py
```

### **Step 2: Evaluate Performance**
```bash
python scripts/evaluate_models.py
```

### **Step 3: Update predict.py**
Add new targets to prediction workflow:
- Extract home/draw/away odds from h2h market
- Calculate value edge for each
- Output BET/NO BET recommendations

### **Step 4: Test with Live Data**
```bash
python scripts/predict.py --fetch-odds --days 7
```

---

## 📈 Expected Performance

### **Easier Targets (60-75% AUC):**
- ✅ Over 2.5 Goals (well balanced)
- ✅ BTTS (well balanced)
- ✅ Away Not Lose (well balanced)

### **Moderate Targets (55-65% AUC):**
- ⚠️ Home Win (43% prevalence)
- ⚠️ Away Win (33% prevalence)
- ⚠️ Home Not Lose (67% prevalence)

### **Harder Targets (50-60% AUC):**
- ⚠️ Draw (only 23% prevalence, imbalanced)

**Note:** Even 55-60% AUC can be profitable with proper bankroll management!

---

## ✅ Summary

**What We Added:**
- ✅ 3 new prediction targets (Home Win, Draw, Away Win)
- ✅ All have odds available from API
- ✅ Database updated (2,992 matches with new targets)
- ✅ Config updated (7 targets defined)
- ✅ Ready for model training

**What We Kept:**
- ✅ Over 2.5 Goals (betting)
- ✅ Home/Away Not Lose (betting)
- ✅ BTTS (prediction only, no odds)

**Total Betting Targets:** 7 (all with odds)  
**Total Prediction Targets:** 1 (BTTS only)  
**Total Models to Train:** 8

---

**Ready to train models? Run:**
```bash
source pred/bin/activate
python scripts/train_models.py
```
