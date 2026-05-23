#!/usr/bin/env python3
"""
Test The Odds API endpoint to verify implementation.

Tests:
1. Fetch upcoming fixtures
2. Verify we get odds for all our targets
3. Display parsed results
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from fetch_odds import fetch_upcoming_fixtures, parse_odds_for_targets
import json

def test_odds_api():
    """Test The Odds API endpoint."""
    print("\n" + "="*80)
    print("TESTING THE ODDS API")
    print("="*80)
    
    print("\n1️⃣  Fetching upcoming fixtures (next 7 days)...")
    print("-" * 80)
    
    try:
        fixtures = fetch_upcoming_fixtures(days_ahead=7)
        
        if not fixtures:
            print("\n❌ No fixtures returned from API")
            print("\nPossible reasons:")
            print("  • No upcoming Premier League matches in next 7 days")
            print("  • Invalid API key in .env")
            print("  • EPL season not in progress")
            print("  • API rate limit exceeded")
            return
        
        print(f"\n✅ Successfully fetched {len(fixtures)} fixtures")
        
        print("\n2️⃣  Testing odds parsing for each fixture...")
        print("-" * 80)
        
        for i, fixture in enumerate(fixtures, 1):
            print(f"\nFixture {i}/{len(fixtures)}:")
            
            parsed = parse_odds_for_targets(fixture)
            
            # Display match info
            print(f"  📅 Date: {parsed['match_date']} {parsed['match_time']}")
            print(f"  ⚽ Match: {parsed['home_team']} vs {parsed['away_team']}")
            print(f"  📊 Bookmaker: {parsed.get('bookmaker_title', 'N/A')} ({parsed.get('bookmaker', 'N/A')})")
            
            # Check if we have all required odds
            odds = parsed['odds']
            required_targets = {
                'over_25': 'Over 2.5 Goals',
                'under_25': 'Under 2.5 Goals',
                'btts_yes': 'Both Teams To Score (Yes)',
                'btts_no': 'Both Teams To Score (No)',
                'home_not_lose_1x': 'Home Not Lose (1X)',
                'away_not_lose_x2': 'Away Not Lose (X2)'
            }
            
            print(f"\n  🎯 Target Odds:")
            missing_targets = []
            
            for target_key, target_name in required_targets.items():
                if target_key in odds:
                    print(f"    ✅ {target_name}: {odds[target_key]:.2f}")
                else:
                    print(f"    ❌ {target_name}: MISSING")
                    missing_targets.append(target_name)
            
            # Display supporting odds (h2h)
            if 'home_win' in odds:
                print(f"\n  📈 Match Result Odds:")
                print(f"    Home Win: {odds['home_win']:.2f}")
                print(f"    Draw: {odds.get('draw', 'N/A'):.2f}")
                print(f"    Away Win: {odds['away_win']:.2f}")
            
            # Display metadata
            if 'metadata' in parsed and parsed['metadata']:
                print(f"\n  🕒 Market Updates:")
                meta = parsed['metadata']
                if meta.get('h2h_last_update'):
                    print(f"    H2H: {meta['h2h_last_update']}")
                if meta.get('totals_last_update'):
                    print(f"    Totals: {meta['totals_last_update']}")
                if meta.get('btts_last_update'):
                    print(f"    BTTS: {meta['btts_last_update']}")
            
            if missing_targets:
                print(f"\n  ⚠️  Missing {len(missing_targets)} target(s): {', '.join(missing_targets)}")
        
        print("\n" + "="*80)
        print("✅ API TEST COMPLETE")
        print("="*80)
        
        # Summary
        total_fixtures = len(fixtures)
        print(f"\n📊 Summary:")
        print(f"  • Total fixtures fetched: {total_fixtures}")
        print(f"  • All targets available: {'✅ YES' if all('over_25' in parse_odds_for_targets(f)['odds'] for f in fixtures) else '⚠️  SOME MISSING'}")
        
        # Test JSON output
        print("\n3️⃣  Testing JSON export...")
        print("-" * 80)
        parsed_fixtures = [parse_odds_for_targets(f) for f in fixtures]
        json_output = json.dumps(parsed_fixtures, indent=2)
        print(f"✅ JSON export successful ({len(json_output)} characters)")
        
        # Optionally save to file
        output_file = Path(__file__).parent.parent / 'logs' / 'test_odds_output.json'
        output_file.parent.mkdir(exist_ok=True)
        with open(output_file, 'w') as f:
            f.write(json_output)
        print(f"✅ Saved to: {output_file}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return

if __name__ == '__main__':
    test_odds_api()
