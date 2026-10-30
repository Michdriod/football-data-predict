#!/usr/bin/env python3
"""
Football Match Prediction Script - Generate predictions for upcoming matches

THREE MODES OF OPERATION:
1. Manual Mode: Specify teams and date manually
   python scripts/predict.py --home Arsenal --away Chelsea --date 2026-05-25

2. Auto-Fetch Mode: Automatically fetch upcoming fixtures with live odds
   python scripts/predict.py --fetch-odds --days 7

3. Hybrid Mode: Specify teams but fetch live odds
   python scripts/predict.py --home Arsenal --away Chelsea --fetch-odds

Outputs predictions with probabilities, value edge, and betting recommendations.

Author: Football Prediction System
Date: 2026-05-23
"""

import os
import sys
import argparse
import json
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

warnings.filterwarnings('ignore')

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import centralized configuration
from config import (
    BETTING_THRESHOLDS,
    TARGETS
)

# Import the trained match model
from match_model import load_bundle, predict_fixtures

# Import odds fetching functions
from fetch_odds import fetch_upcoming_fixtures, parse_odds_for_targets

# ============================================================================
# ODDS
# ============================================================================

def build_odds_info(odds_data):
    """
    Convert raw odds into implied probabilities.
    
    Odds are NOT model features, only used for value edge calculation.
    
    Args:
        odds_data (dict): Optional odds data from API
        
    Returns:
        dict: Odds and implied probabilities, or None without odds
    """
    if not odds_data:
        return None
    
    # parse_odds_for_targets() nests prices under 'odds'
    prices = odds_data.get('odds', {})
    
    def implied(price):
        return 1 / price if price > 0 else 0
    
    home_odds = prices.get('home_win', 0)
    draw_odds = prices.get('draw', 0)
    away_odds = prices.get('away_win', 0)
    over_25_odds = prices.get('over_25', 0)
    under_25_odds = prices.get('under_25', 0)
    
    return {
        'home_odds': home_odds,
        'draw_odds': draw_odds,
        'away_odds': away_odds,
        'over_25_odds': over_25_odds,
        'under_25_odds': under_25_odds,
        'implied_home_win_prob': implied(home_odds),
        'implied_draw_prob': implied(draw_odds),
        'implied_away_win_prob': implied(away_odds),
        'implied_over_25_prob': implied(over_25_odds),
        'implied_under_25_prob': implied(under_25_odds),
    }


def generate_prediction(home_team, away_team, match_date, bundle, odds_data=None):
    """
    Generate predictions for a single match.
    
    Args:
        home_team (str): Home team name
        away_team (str): Away team name
        match_date (str): Match date
        bundle (dict): Trained match model
        odds_data (dict): Optional odds data
        
    Returns:
        dict: Prediction results
    """
    try:
        # Probabilities come from form up to the latest played match (odds NOT used)
        fixture = pd.DataFrame([{'home_team': home_team, 'away_team': away_team, 'match_date': match_date}])
        probabilities = predict_fixtures(bundle, fixture).iloc[0]
        odds_info = build_odds_info(odds_data)
        
        # Generate predictions
        prediction = {
            'match_date': str(match_date),
            'home_team': home_team,
            'away_team': away_team,
            'predictions': {}
        }
        
        for target_col in TARGETS:
            proba = probabilities[target_col]
            
            target_name = TARGETS[target_col]
            
            pred_detail = {
                'probability': float(round(proba, 4)),
                'confidence': 'HIGH' if proba >= 0.70 else 'MEDIUM' if proba >= 0.60 else 'LOW'
            }
            
            # Add odds and value edge if available (for betting evaluation only)
            if odds_info:
                # Map target to odds field
                odds_mapping = {
                    'target_over_25': ('over_25_odds', 'implied_over_25_prob'),
                    'target_home_win': ('home_odds', 'implied_home_win_prob'),
                    'target_draw': ('draw_odds', 'implied_draw_prob'),
                    'target_away_win': ('away_odds', 'implied_away_win_prob'),
                    'target_home_win_or_draw': (None, 'implied_home_not_lose_prob'),
                    'target_away_win_or_draw': (None, 'implied_away_not_lose_prob'),
                }
                
                if target_col in odds_mapping:
                    odds_key, implied_key = odds_mapping[target_col]
                    
                    if odds_key and odds_key in odds_info:
                        decimal_odds = odds_info[odds_key]
                        implied_prob = 1 / decimal_odds if decimal_odds > 0 else 0
                    elif implied_key == 'implied_home_not_lose_prob':
                        implied_prob = odds_info['implied_home_win_prob'] + odds_info['implied_draw_prob']
                        decimal_odds = 1 / implied_prob if implied_prob > 0 else 0
                    elif implied_key == 'implied_away_not_lose_prob':
                        implied_prob = odds_info['implied_away_win_prob'] + odds_info['implied_draw_prob']
                        decimal_odds = 1 / implied_prob if implied_prob > 0 else 0
                    else:
                        implied_prob = None
                        decimal_odds = None
                    
                    if implied_prob is not None and implied_prob > 0:
                        value_edge = proba - implied_prob
                        pred_detail['market_odds'] = float(round(decimal_odds, 2))
                        pred_detail['implied_probability'] = float(round(implied_prob, 4))
                        pred_detail['value_edge'] = float(round(value_edge, 4))
                        
                        # Betting recommendation
                        if (proba >= BETTING_THRESHOLDS['min_probability'] and 
                            value_edge >= BETTING_THRESHOLDS['min_value_edge'] and
                            BETTING_THRESHOLDS['min_odds'] <= decimal_odds <= BETTING_THRESHOLDS['max_odds']):
                            pred_detail['recommendation'] = 'BET'
                            pred_detail['bet_size'] = 'STANDARD'
                        else:
                            pred_detail['recommendation'] = 'NO BET'
                            
                            # Explain why
                            reasons = []
                            if proba < BETTING_THRESHOLDS['min_probability']:
                                reasons.append(f"Probability too low ({proba:.1%} < {BETTING_THRESHOLDS['min_probability']:.0%})")
                            if value_edge < BETTING_THRESHOLDS['min_value_edge']:
                                reasons.append(f"Value edge too low ({value_edge:+.2%} < {BETTING_THRESHOLDS['min_value_edge']:+.0%})")
                            if decimal_odds < BETTING_THRESHOLDS['min_odds'] or decimal_odds > BETTING_THRESHOLDS['max_odds']:
                                reasons.append(f"Odds outside range ({decimal_odds:.2f})")
                            pred_detail['reason'] = ', '.join(reasons)
            
            prediction['predictions'][target_name] = pred_detail
        
        return prediction
        
    except Exception as e:
        print(f"❌ Error generating prediction for {home_team} vs {away_team}: {e}")
        import traceback
        traceback.print_exc()
        return None


def format_output(predictions, as_json=False):
    """Format predictions for output."""
    if as_json:
        return json.dumps(predictions, indent=2)
    
    # Text format
    output = "\n" + "="*120 + "\n"
    output += "FOOTBALL MATCH PREDICTIONS\n"
    output += "="*120 + "\n"
    
    for pred in predictions:
        output += f"\n📅 {pred['match_date']} | {pred['home_team']:20} vs {pred['away_team']:20}\n"
        output += "-" * 120 + "\n"
        
        for market, details in pred['predictions'].items():
            prob = details['probability']
            conf = details['confidence']
            
            line = f"  {market:35} | Prob: {prob:6.1%} | {conf:6}"
            
            if 'recommendation' in details:
                rec = details['recommendation']
                line += f" | Rec: {rec:6}"
                
                if 'market_odds' in details:
                    odds = details['market_odds']
                    edge = details['value_edge']
                    line += f" | Odds: {odds:5.2f} | Edge: {edge:+6.1%}"
            
            output += line + "\n"
        
    output += "\n" + "="*120 + "\n"
    
    return output


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Generate football predictions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
  # Mode 1: Manual input
  python scripts/predict.py --home Arsenal --away Chelsea --date 2026-05-25
  
  # Mode 2: Auto-fetch upcoming fixtures
  python scripts/predict.py --fetch-odds --days 7
  
  # Mode 3: Manual teams with live odds
  python scripts/predict.py --home Arsenal --away Chelsea --fetch-odds
  
  # JSON output
  python scripts/predict.py --fetch-odds --json
        """
    )
    
    parser.add_argument('--home', type=str, help='Home team name')
    parser.add_argument('--away', type=str, help='Away team name')
    parser.add_argument('--date', type=str, help='Match date (YYYY-MM-DD)')
    parser.add_argument('--fetch-odds', action='store_true', help='Fetch live odds from API')
    parser.add_argument('--days', type=int, default=7, help='Days ahead to fetch fixtures (default: 7)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("FOOTBALL MATCH PREDICTION SYSTEM")
    print("="*80)
    print(f"\nStart Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Load the trained match model
        bundle = load_bundle()
        print(f"\n✓ Match model trained through {bundle['trained_through']} ({bundle['matches']:,} matches)")
        
        predictions = []
        
        # ====================================================================
        # MODE 1: Manual input (--home and --away specified)
        # ====================================================================
        if args.home and args.away:
            print(f"\n📋 Mode: Manual Input")
            print(f"   Home: {args.home}")
            print(f"   Away: {args.away}")
            
            match_date = args.date if args.date else datetime.now().strftime('%Y-%m-%d')
            
            # Fetch odds if requested
            odds_data = None
            if args.fetch_odds:
                print(f"\n🔄 Fetching live odds from The Odds API...")
                try:
                    fixtures = fetch_upcoming_fixtures(days_ahead=args.days)
                    
                    # Find matching fixture
                    for fixture in fixtures:
                        fixture_odds = parse_odds_for_targets(fixture)
                        if (fixture_odds['home_team'] == args.home and 
                            fixture_odds['away_team'] == args.away):
                            odds_data = fixture_odds
                            print(f"✓ Found odds for {args.home} vs {args.away}")
                            break
                    
                    if odds_data is None:
                        print(f"⚠️  No odds found for {args.home} vs {args.away}")
                        print(f"   Generating predictions without odds...")
                except Exception as e:
                    print(f"⚠️  Error fetching odds: {e}")
                    print(f"   Generating predictions without odds...")
            
            # Generate prediction
            pred = generate_prediction(args.home, args.away, match_date, bundle, odds_data)
            if pred:
                predictions.append(pred)
        
        # ====================================================================
        # MODE 2: Auto-fetch upcoming fixtures (--fetch-odds without manual teams)
        # ====================================================================
        elif args.fetch_odds:
            print(f"\n📋 Mode: Auto-Fetch Upcoming Fixtures")
            print(f"   Days ahead: {args.days}")
            
            print(f"\n🔄 Fetching upcoming fixtures from The Odds API...")
            
            try:
                fixtures = fetch_upcoming_fixtures(days_ahead=args.days)
                
                if len(fixtures) == 0:
                    print("\n⚠️  No upcoming fixtures found in next {} days".format(args.days))
                    return 0
                
                print(f"✓ Found {len(fixtures)} upcoming fixture(s)\n")
                
                # Generate predictions for each fixture
                for i, fixture in enumerate(fixtures, 1):
                    odds_data = parse_odds_for_targets(fixture)
                    
                    print(f"[{i}/{len(fixtures)}] {odds_data['home_team']} vs {odds_data['away_team']} ({odds_data['match_date']})")
                    
                    pred = generate_prediction(
                        odds_data['home_team'],
                        odds_data['away_team'],
                        odds_data['match_date'],
                        bundle,
                        odds_data
                    )
                    
                    if pred:
                        predictions.append(pred)
                
            except Exception as e:
                print(f"\n❌ Error fetching fixtures: {e}")
                import traceback
                traceback.print_exc()
                return 1
        
        # ====================================================================
        # MODE 3: Show help if no mode specified
        # ====================================================================
        else:
            print("\n⚠️  Please specify a prediction mode:\n")
            print("  Mode 1 (Manual): --home Arsenal --away Chelsea --date 2026-05-25")
            print("  Mode 2 (Auto-fetch): --fetch-odds --days 7")
            print("  Mode 3 (Hybrid): --home Arsenal --away Chelsea --fetch-odds\n")
            parser.print_help()
            return 0
        
        # ====================================================================
        # OUTPUT PREDICTIONS
        # ====================================================================
        if len(predictions) > 0:
            print("\n" + "="*80)
            print("GENERATING PREDICTIONS")
            print("="*80)
            
            output = format_output(predictions, as_json=args.json)
            print(output)
            
            # Save to file
            os.makedirs('logs', exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if args.json:
                output_file = f"logs/predictions_{timestamp}.json"
                with open(output_file, 'w') as f:
                    f.write(output)
            else:
                output_file = f"logs/predictions_{timestamp}.txt"
                with open(output_file, 'w') as f:
                    f.write(output)
            
            print(f"\n✓ Predictions saved to: {output_file}")
        else:
            print("\n⚠️  No predictions generated")
        
        print(f"\n{'='*80}")
        print(f"✓ Prediction completed!")
        print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")
        
        return 0
        
    except Exception as e:
        print(f"\n{'='*80}")
        print(f"❌ ERROR: Prediction failed!")
        print(f"{'='*80}")
        print(f"\n{type(e).__name__}: {e}\n")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
