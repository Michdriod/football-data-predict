#!/usr/bin/env python3
"""Debug: Check raw API response to see what markets are returned."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import requests
from config import get_env_var
import json

ODDS_API_KEY = get_env_var('ODDS_API_KEY', required=True)
ODDS_API_BASE_URL = get_env_var('ODDS_API_BASE_URL', 'https://api.the-odds-api.com/v4', required=False)

url = f"{ODDS_API_BASE_URL}/sports/soccer_epl/odds"

params = {
    'apiKey': ODDS_API_KEY,
    'regions': 'uk',
    'markets': 'h2h,totals',
    'oddsFormat': 'decimal',
    'dateFormat': 'iso'
}

print("🔍 Fetching RAW API response...\n")
response = requests.get(url, params=params)

if response.status_code != 200:
    print(f"❌ Error: {response.status_code}")
    print(response.text)
else:
    data = response.json()
    print(f"✅ Got {len(data)} fixtures\n")
    
    if data:
        # Check first fixture
        first = data[0]
        print(f"First Fixture: {first['home_team']} vs {first['away_team']}")
        print(f"\nBookmakers available: {len(first.get('bookmakers', []))}")
        
        for bookmaker in first.get('bookmakers', []):
            print(f"\n📊 Bookmaker: {bookmaker['title']} ({bookmaker['key']})")
            print(f"   Markets available:")
            for market in bookmaker.get('markets', []):
                print(f"     - {market['key']}: {len(market['outcomes'])} outcomes")
                if market['key'] == 'totals':
                    print(f"       Totals outcomes:")
                    for outcome in market['outcomes']:
                        print(f"         {outcome['name']} {outcome.get('point', 'N/A')}: {outcome['price']}")
        
        # Save full response for inspection
        output_file = Path(__file__).parent.parent / 'logs' / 'raw_api_response.json'
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\n💾 Full response saved to: {output_file}")
