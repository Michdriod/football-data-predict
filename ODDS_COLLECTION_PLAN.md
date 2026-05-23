# Odds Collection for Match Predictions

**Date:** May 22, 2026  
**Status:** Planning Phase

---

## 🎯 Problem Statement

Currently, our prediction system can:
- ✅ Generate probabilities for 4 targets (Over 2.5, BTTS, 1X, X2)
- ✅ Calculate value edge IF odds are provided manually
- ❌ **Cannot automatically fetch current odds for upcoming matches**

**User Request:**
> "i think we should collect the odds too when trying to predict"

**Goal:** Integrate real-time odds fetching into the prediction workflow.

---

## 📊 Why We Need Odds

### **1. Value Edge Calculation**
```python
# Without odds: Can only show probability
prediction = {
    "target_over_25": 0.72  # 72% chance
}

# With odds: Can calculate betting value
prediction = {
    "target_over_25": {
        "probability": 0.72,      # Our model prediction
        "bookmaker_odds": 1.85,    # Market odds
        "implied_prob": 0.54,      # Bookmaker's implied probability
        "value_edge": 0.18,        # 72% - 54% = 18% edge!
        "recommendation": "BET"     # Value detected
    }
}
```

### **2. Betting Decision Logic**
Our system only recommends bets when:
- Model probability ≥ 70% **AND**
- Value edge ≥ 5% **AND**
- Odds between 1.50 - 3.00

**Without odds:** We can't make betting recommendations.

---

## 🔌 Odds API Options

### **Option 1: The Odds API** (Recommended)
- **Website:** https://the-odds-api.com
- **Coverage:** Premier League + 80+ sports
- **Data:** Pre-match odds from 40+ bookmakers
- **Pricing:** Free tier (500 requests/month)
- **Pros:** Easy integration, good documentation, free tier sufficient
- **Cons:** Rate limited on free tier

**Example Response:**
```json
{
  "id": "abc123",
  "sport_key": "soccer_epl",
  "commence_time": "2026-05-25T15:00:00Z",
  "home_team": "Arsenal",
  "away_team": "Chelsea",
  "bookmakers": [
    {
      "key": "bet365",
      "markets": [
        {
          "key": "h2h",
          "outcomes": [
            {"name": "Arsenal", "price": 1.65},
            {"name": "Draw", "price": 3.80},
            {"name": "Chelsea", "price": 4.50}
          ]
        },
        {
          "key": "totals",
          "outcomes": [
            {"name": "Over", "description": "Over 2.5", "price": 1.85},
            {"name": "Under", "description": "Under 2.5", "price": 2.00}
          ]
        }
      ]
    }
  ]
}
```

### **Option 2: API-Football (Football-Data.org API)**
- **Website:** https://www.api-football.com
- **Coverage:** Premier League + 1000+ leagues
- **Data:** Fixtures, odds, lineups, statistics
- **Pricing:** Free tier (100 requests/day)
- **Pros:** Comprehensive football data, includes lineups
- **Cons:** More complex API, lower free tier

### **Option 3: RapidAPI - Odds API**
- **Website:** https://rapidapi.com/hub
- **Coverage:** Multiple odds providers
- **Data:** Pre-match and live odds
- **Pricing:** Varies by provider
- **Pros:** Unified interface to multiple providers
- **Cons:** Requires RapidAPI account

---

## 🏗️ Implementation Plan

### **Phase 1: API Integration (Week 1)**

#### **Step 1: Choose API Provider**
- Research pricing and coverage
- Sign up for API key
- Test basic API calls

#### **Step 2: Create Odds Fetcher Module**

**File:** `scripts/fetch_odds.py`

```python
"""
Fetch current odds from The Odds API for upcoming matches.

Usage:
    python scripts/fetch_odds.py --date 2026-05-25
    python scripts/fetch_odds.py --days 7
"""

import os
import requests
from datetime import datetime, timedelta
from config import get_env_var

API_KEY = get_env_var('ODDS_API_KEY', required=True)
API_BASE_URL = 'https://api.the-odds-api.com/v4'

def fetch_epl_fixtures(days_ahead=7):
    """Fetch upcoming Premier League fixtures with odds."""
    
    url = f"{API_BASE_URL}/sports/soccer_epl/odds"
    
    params = {
        'apiKey': API_KEY,
        'regions': 'uk',  # UK bookmakers
        'markets': 'h2h,totals,btts',  # Match result, Over/Under, BTTS
        'oddsFormat': 'decimal',
        'dateFormat': 'iso'
    }
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    
    fixtures = response.json()
    
    # Filter to next N days
    cutoff_date = datetime.now() + timedelta(days=days_ahead)
    
    upcoming = [
        f for f in fixtures 
        if datetime.fromisoformat(f['commence_time'].replace('Z', '+00:00')) <= cutoff_date
    ]
    
    return upcoming

def parse_odds_for_model(fixture):
    """Extract relevant odds from API response."""
    
    # Get Bet365 odds (or average if Bet365 not available)
    bet365 = next(
        (b for b in fixture['bookmakers'] if b['key'] == 'bet365'),
        fixture['bookmakers'][0]  # Fallback to first bookmaker
    )
    
    odds = {}
    
    # Match result (H2H)
    h2h_market = next((m for m in bet365['markets'] if m['key'] == 'h2h'), None)
    if h2h_market:
        outcomes = {o['name']: o['price'] for o in h2h_market['outcomes']}
        odds['home_win'] = outcomes.get(fixture['home_team'])
        odds['draw'] = outcomes.get('Draw')
        odds['away_win'] = outcomes.get(fixture['away_team'])
    
    # Over/Under 2.5
    totals_market = next((m for m in bet365['markets'] if m['key'] == 'totals'), None)
    if totals_market:
        over_25 = next((o for o in totals_market['outcomes'] if 'Over' in o['name']), None)
        under_25 = next((o for o in totals_market['outcomes'] if 'Under' in o['name']), None)
        
        if over_25:
            odds['over_25'] = over_25['price']
        if under_25:
            odds['under_25'] = under_25['price']
    
    # BTTS
    btts_market = next((m for m in bet365['markets'] if m['key'] == 'btts'), None)
    if btts_market:
        outcomes = {o['name']: o['price'] for o in btts_market['outcomes']}
        odds['btts_yes'] = outcomes.get('Yes')
        odds['btts_no'] = outcomes.get('No')
    
    return {
        'match_date': fixture['commence_time'][:10],
        'home_team': fixture['home_team'],
        'away_team': fixture['away_team'],
        'odds': odds
    }
```

#### **Step 3: Update .env with API Key**

Add to `.env`:
```bash
# Odds API Configuration
ODDS_API_KEY=your_api_key_here
ODDS_API_PROVIDER=the-odds-api  # or api-football, rapidapi
```

Add to `.env.example`:
```bash
# Odds API Configuration (for fetching current betting odds)
ODDS_API_KEY=your_api_key_here  # Sign up at https://the-odds-api.com
ODDS_API_PROVIDER=the-odds-api
```

#### **Step 4: Team Name Mapping**

**Problem:** API returns "Manchester United", database has "Man United"

**Solution:** Create mapping file

**File:** `data/team_name_mapping.json`

```json
{
  "api_to_database": {
    "Manchester United": "Man United",
    "Manchester City": "Man City",
    "Nottingham Forest": "Nott'm Forest",
    "Newcastle United": "Newcastle",
    "West Ham United": "West Ham",
    "Brighton & Hove Albion": "Brighton",
    "Wolverhampton Wanderers": "Wolves",
    "Tottenham Hotspur": "Tottenham",
    "Leicester City": "Leicester"
  }
}
```

### **Phase 2: Update predict.py (ONE Unified File)**

**Strategy: Enhance existing `scripts/predict.py` to handle both workflows**

#### **Unified predict.py Modes:**

**Mode 1: Manual Input (Current - Keep)**
```bash
# User provides match details manually
python scripts/predict.py --home Arsenal --away Chelsea --date 2026-05-25
```

**Mode 2: Auto-Fetch with Odds (NEW)**
```bash
# Automatically fetch upcoming fixtures with odds from API
python scripts/predict.py --fetch-odds
python scripts/predict.py --fetch-odds --days 7
python scripts/predict.py --fetch-odds --json > predictions.json
```

**Mode 3: Hybrid (NEW)**
```bash
# Manual match + fetch odds from API
python scripts/predict.py --home Arsenal --away Chelsea --date 2026-05-25 --fetch-odds
```

#### **Implementation: Single File Architecture**

```python
#!/usr/bin/env python3
"""
Football Match Prediction Script - ONE unified prediction file

Supports THREE modes:
1. Manual match input (for specific predictions)
2. Auto-fetch upcoming matches with odds (daily workflow)
3. Hybrid: Manual match + auto-fetch odds

Usage:
    # Mode 1: Manual (current functionality)
    python scripts/predict.py --home Arsenal --away Chelsea
    
    # Mode 2: Auto-fetch (NEW)
    python scripts/predict.py --fetch-odds --days 7
    
    # Mode 3: Hybrid (NEW)
    python scripts/predict.py --home Arsenal --away Chelsea --fetch-odds
"""

def main():
    parser = argparse.ArgumentParser()
    
    # Manual input mode
    parser.add_argument('--home', help='Home team name')
    parser.add_argument('--away', help='Away team name')
    parser.add_argument('--date', help='Match date (YYYY-MM-DD)')
    
    # Auto-fetch mode
    parser.add_argument('--fetch-odds', action='store_true', 
                       help='Fetch upcoming matches with odds from API')
    parser.add_argument('--days', type=int, default=7,
                       help='Days ahead to fetch (default: 7)')
    
    # Output options
    parser.add_argument('--json', action='store_true', help='JSON output')
    
    args = parser.parse_args()
    
    # Determine mode
    if args.fetch_odds and not args.home:
        # Mode 2: Auto-fetch all upcoming matches
        predictions = predict_upcoming_with_odds(days_ahead=args.days)
    
    elif args.home and args.away:
        # Mode 1 or 3: Manual match input
        if args.fetch_odds:
            # Mode 3: Manual + fetch odds from API
            predictions = predict_manual_with_odds(
                args.home, args.away, args.date
            )
        else:
            # Mode 1: Manual without odds (current)
            predictions = predict_manual(args.home, args.away, args.date)
    
    else:
        print("Error: Either use --fetch-odds OR provide --home and --away")
        return
    
    # Output
    if args.json:
        print(json.dumps(predictions, indent=2))
    else:
        print_predictions_table(predictions)

if __name__ == '__main__':
    main()
```

**Benefits of ONE file:**
- ✅ Simpler for users (one command to remember)
- ✅ Shared code (no duplication)
- ✅ Easy to maintain
- ✅ Flexible modes for different use cases
- ✅ No confusion about which script to use

### **Phase 3: Scheduling & Automation (Week 3)**

#### **Daily Odds Update Cron Job**

```bash
# Update odds daily at 9 AM
0 9 * * * cd /path/to/project && source pred/bin/activate && python scripts/predict_today.py --json > predictions/$(date +\%Y-\%m-\%d).json
```

---

## 📝 Data Flow with Odds Collection

### **Current Workflow (Manual):**
```
User → Manual CSV → load_raw_data.py → Database → dbt → Features → train_models.py → Models
```

### **New Prediction Workflow (Automated):**
```
Cron Job → fetch_odds.py → Upcoming Fixtures with Odds
                                    ↓
                          Team Name Mapping
                                    ↓
                          Database Query (team form)
                                    ↓
                          Feature Calculation
                                    ↓
                          Trained Models
                                    ↓
                          Predictions + Value Edge
                                    ↓
                          Betting Recommendations
                                    ↓
                          JSON Output / Email / Dashboard
```

---

## 💰 Cost Analysis

### **The Odds API (Recommended)**

**Free Tier:**
- 500 requests/month
- ~16 requests/day
- EPL has ~10 matches/week (2 requests/week needed)
- **Sufficient for our use case**

**Paid Tier ($60/month):**
- 10,000 requests/month
- Only needed if scaling to multiple leagues

---

## ✅ Next Steps

### **Immediate (User Decision Needed):**
1. ❓ Choose odds API provider (The Odds API recommended)
2. ❓ Sign up and get API key
3. ✅ Add API key to `.env`

### **Implementation (After User Approval):**
1. Create `scripts/fetch_odds.py` (odds API wrapper)
2. Create `data/team_name_mapping.json` (API ↔ DB team names)
3. **Update `scripts/predict.py`** to support all 3 modes (ONE unified file)
4. Test end-to-end workflow
5. Set up daily cron job (optional)

---

## 🎯 Summary

**What user gets:**
- ✅ Automatic odds fetching for upcoming matches
- ✅ Real-time value edge calculation
- ✅ Automated betting recommendations
- ✅ Daily prediction updates (via cron)
- ✅ JSON output for integration with dashboards/bots

**What user needs to do:**
1. Choose odds API provider
2. Sign up and get API key
3. Approve implementation plan

**Estimated timeline:**
- Week 1: API integration + team mapping
- Week 2: Prediction workf(`fetch_odds.py` + team mapping)
- Week 2: Update existing `predict.py` with 3 modes (no new files)
- Week 3: Automation + testing

**ONE prediction file, THREE modes - simple and powerful!**
**Ready to proceed when user provides API key.**
