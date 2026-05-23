# The Odds API Integration - Implementation Guide

**Date:** May 22, 2026  
**API Provider:** The Odds API (https://the-odds-api.com)  
**Status:** ✅ **READY TO USE** (pending API key)

---

## 🎯 What We Built

### **Core Module: `scripts/fetch_odds.py`**

A production-ready Python module that:
- ✅ Fetches upcoming Premier League fixtures with live odds
- ✅ Extracts odds for all 4 prediction targets
- ✅ Maps team names between API and database
- ✅ Calculates Double Chance odds from h2h market
- ✅ Tracks API usage limits
- ✅ Handles errors gracefully

### **Supporting Files:**
- ✅ `data/team_name_mapping.json` - Team name translation
- ✅ `.env` - API configuration (updated)
- ✅ `.env.example` - Template with API settings

---

## 📡 The Odds API - How It Works

### **Endpoint Used:**
```
GET https://api.the-odds-api.com/v4/sports/soccer_epl/odds
```

### **Parameters We Use:**
| Parameter | Value | Purpose |
|---|---|---|
| `apiKey` | YOUR_API_KEY | Authentication |
| `regions` | `uk` | UK bookmakers (Bet365, etc.) |
| `markets` | `h2h,totals,btts` | Match result, Over/Under, BTTS |
| `oddsFormat` | `decimal` | Decimal odds (easier math) |
| `commenceTimeTo` | 7 days ahead | Filter upcoming fixtures |

### **What We Get Back:**
```json
[
  {
    "id": "abc123",
    "sport_key": "soccer_epl",
    "commence_time": "2026-05-25T15:00:00Z",
    "home_team": "Arsenal",
    "away_team": "Chelsea",
    "bookmakers": [
      {
        "key": "bet365",
        "title": "Bet365",
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
              {"name": "Over", "price": 1.85, "point": 2.5},
              {"name": "Under", "price": 2.00, "point": 2.5}
            ]
          },
          {
            "key": "btts",
            "outcomes": [
              {"name": "Yes", "price": 1.75},
              {"name": "No", "price": 2.10}
            ]
          }
        ]
      }
    ]
  }
]
```

---

## 💰 Cost Analysis

### **Free Tier:**
- **500 requests/month**
- **~16 requests/day**
- **Cost per request:** 3 credits (3 markets × 1 region)
- **Total matches:** 500 ÷ 3 = **~166 requests** (enough for 5+ months of weekly updates!)

### **Our Usage:**
- **Weekly update:** 1 request (fetch all upcoming matches)
- **Monthly usage:** 4 requests = 12 credits
- **Annual usage:** 48 requests = 144 credits

✅ **FREE TIER IS MORE THAN SUFFICIENT!**

### **Cost Breakdown:**
```
Cost = Markets × Regions
     = 3 markets × 1 region
     = 3 credits per request

Markets:
  h2h    = Match Result (Home/Draw/Away)
  totals = Over/Under 2.5 Goals
  btts   = Both Teams To Score
```

---

## 🗺️ Team Name Mapping

### **Why Needed:**
The API returns full names (e.g., "Manchester United"), but our database uses shortened names (e.g., "Man United") from football-data.co.uk.

### **Mapping File:** `data/team_name_mapping.json`

```json
{
  "api_to_database": {
    "Manchester United": "Man United",
    "Manchester City": "Man City",
    "Nottingham Forest": "Nott'm Forest",
    "Brighton & Hove Albion": "Brighton",
    "Wolverhampton Wanderers": "Wolves",
    "Tottenham Hotspur": "Tottenham",
    ...
  }
}
```

### **Auto-Mapping:**
`fetch_odds.py` automatically maps team names when parsing odds data.

---

## 🚀 How To Use

### **Step 1: Get API Key**
1. Go to: https://the-odds-api.com/#get-access
2. Enter your email
3. API key sent to your inbox
4. **Free tier:** 500 requests/month (sufficient!)

### **Step 2: Add API Key to .env**
```bash
nano .env  # or your preferred editor

# Add this line:
ODDS_API_KEY=your_actual_api_key_here
```

### **Step 3: Test Fetch Odds**
```bash
# Test with demo (will fail without API key)
python scripts/fetch_odds.py --days 7

# Expected output:
📡 Fetching upcoming soccer_epl fixtures from The Odds API...
   Markets: h2h,totals,btts
   Regions: uk
   Days ahead: 7
✅ Fetched 10 fixtures
   API Usage - Remaining: 497, Used: 3, Last Cost: 3

================================================================================
UPCOMING PREMIER LEAGUE FIXTURES WITH ODDS
================================================================================

2026-05-30 15:00:00: Arsenal vs Chelsea
  Bookmaker: bet365
  Match Result: Home 1.65 | Draw 3.80 | Away 4.50
  Over/Under 2.5: Over 1.85 | Under 2.00
  BTTS: Yes 1.75 | No 2.10
  Double Chance: 1X 1.21 | X2 1.85

2026-05-30 17:30:00: Man City vs Liverpool
  ...
```

### **Step 4: Use in predict.py (Future Enhancement)**
```python
from fetch_odds import fetch_upcoming_fixtures, parse_odds_for_targets

# Fetch fixtures with odds
fixtures = fetch_upcoming_fixtures(days_ahead=7)

for fixture in fixtures:
    odds = parse_odds_for_targets(fixture)
    
    # Now you have:
    # - Home team, away team, match date
    # - Live odds for all targets
    # - Ready to calculate value edge!
```

---

## 📊 Odds Data We Extract

For each match, we get these odds:

### **From h2h Market (Match Result):**
- `home_win` - Home win odds
- `draw` - Draw odds
- `away_win` - Away win odds

### **From totals Market (Over/Under 2.5):**
- `over_25` - Over 2.5 goals odds
- `under_25` - Under 2.5 goals odds

### **From btts Market (Both Teams To Score):**
- `btts_yes` - Both teams score odds
- `btts_no` - Clean sheet odds

### **Calculated (Double Chance):**
- `home_not_lose_1x` - Calculated from home_win + draw probabilities
- `away_not_lose_x2` - Calculated from away_win + draw probabilities

**Formula for Double Chance:**
```python
# Home Not Lose (1X) = Home Win OR Draw
home_prob = 1 / home_win_odds
draw_prob = 1 / draw_odds
home_not_lose_odds = 1 / (home_prob + draw_prob)

# Away Not Lose (X2) = Away Win OR Draw
away_prob = 1 / away_win_odds
draw_prob = 1 / draw_odds
away_not_lose_odds = 1 / (away_prob + draw_prob)
```

---

## 🔄 Workflow: From API to Predictions

### **Current Process:**
```
User → Upload CSV → load_raw_data.py → Database → dbt → Features → train_models.py
```

### **New Process (With Odds):**
```
Cron Job (Weekly)
    ↓
fetch_odds.py → Fetch upcoming fixtures with live odds
    ↓
predict.py (ENHANCED) → Load models + Get team features
    ↓
For each fixture:
    - Query database for team form (last 5-10 matches)
    - Calculate rolling features
    - Generate prediction probabilities
    - Compare to LIVE odds from API
    - Calculate value edge
    - Output BET or NO BET recommendation
    ↓
predictions.json → Save results
    ↓
(Optional) Dashboard / Email / Telegram Bot
```

---

## 📝 Environment Variables

### **Added to .env:**
```bash
# Odds API Configuration
ODDS_API_KEY=your_api_key_here
ODDS_API_BASE_URL=https://api.the-odds-api.com/v4
ODDS_SPORT_KEY=soccer_epl
ODDS_REGIONS=uk
ODDS_MARKETS=h2h,totals,btts
ODDS_FORMAT=decimal
```

### **Configuration Options:**

| Variable | Default | Options |
|---|---|---|
| `ODDS_SPORT_KEY` | `soccer_epl` | See /v4/sports endpoint |
| `ODDS_REGIONS` | `uk` | `us`, `us2`, `eu`, `au`, `uk` |
| `ODDS_MARKETS` | `h2h,totals,btts` | Add `spreads`, `outrights` |
| `ODDS_FORMAT` | `decimal` | `decimal` or `american` |

---

## ⚠️ Important Notes

### **API Rate Limits:**
- Free tier: 500 requests/month
- Rate limited to prevent bursts
- If 429 error → Wait a few seconds, retry

### **Team Name Mismatches:**
- Check `data/team_name_mapping.json` if matches don't appear
- Add new teams as needed (promoted/relegated)
- Script logs warnings for unmapped teams

### **Odds Availability:**
- Fixtures appear 1-2 weeks before match
- Odds update every 5-10 minutes
- Some markets may not be available for all matches

### **Double Chance Calculation:**
- Calculated from h2h market (not fetched directly)
- May have slight rounding differences vs bookmaker

---

## 🎯 Next Steps

### **Phase 1: DONE ✅**
- [x] Created `fetch_odds.py` module
- [x] Team name mapping file
- [x] Environment configuration
- [x] Documentation

### **Phase 2: Update predict.py (Coming Next)**
- [ ] Add `--fetch-odds` flag to predict.py
- [ ] Integrate fetch_odds.py into prediction workflow
- [ ] Calculate value edge with live odds
- [ ] Output betting recommendations

### **Phase 3: Automation (Optional)**
- [ ] Daily cron job for predictions
- [ ] JSON output for dashboards
- [ ] Email/Telegram notifications

---

## 🧪 Testing Without API Key

Until you get your API key, you can test the structure:

```python
# Mock fixture data for testing
mock_fixture = {
    'home_team': 'Arsenal',
    'away_team': 'Chelsea',
    'commence_time': '2026-05-30T15:00:00Z',
    'bookmakers': [
        {
            'key': 'bet365',
            'markets': [
                {
                    'key': 'h2h',
                    'outcomes': [
                        {'name': 'Arsenal', 'price': 1.65},
                        {'name': 'Draw', 'price': 3.80},
                        {'name': 'Chelsea', 'price': 4.50}
                    ]
                }
            ]
        }
    ]
}

from fetch_odds import parse_odds_for_targets
odds = parse_odds_for_targets(mock_fixture)
print(odds)
```

---

## 📚 API Documentation

**Full documentation:** https://the-odds-api.com/liveapi/guides/v4/

**Key endpoints:**
- `GET /v4/sports` - List all sports
- `GET /v4/sports/{sport}/odds` - Get odds (we use this)
- `GET /v4/sports/{sport}/events` - Get fixtures without odds (free)

---

## ✅ Summary

**What you need to do:**
1. Sign up at https://the-odds-api.com/#get-access (2 minutes)
2. Add API key to `.env` file (1 line)
3. Test: `python scripts/fetch_odds.py --days 7`

**What you get:**
- ✅ Live odds for all upcoming EPL matches
- ✅ All 4 prediction targets covered
- ✅ Automatic team name mapping
- ✅ API usage tracking
- ✅ FREE tier sufficient for our needs (500 requests/month)

**Cost:**
- $0/month (free tier)
- 3 credits per fetch
- ~166 fetches available monthly
- Only need 4-8 fetches per month

**Ready to integrate into predict.py when you approve!** 🚀
