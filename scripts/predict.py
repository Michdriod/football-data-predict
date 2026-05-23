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
import numpy as np
import joblib
from sqlalchemy import create_engine

warnings.filterwarnings('ignore')

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import centralized configuration
from config import (
    DB_CONFIG,
    get_db_connection_string,
    BETTING_THRESHOLDS,
    TARGETS,
    TARGET_NAMES,
    PROJECT_ROOT
)

# Import odds fetching functions
from fetch_odds import fetch_upcoming_fixtures, parse_odds_for_targets

# ============================================================================
# DATABASE CONNECTION
# ============================================================================

def get_db_engine():
    """Create SQLAlchemy engine."""
    return create_engine(get_db_connection_string())


def get_team_latest_form(team_name, as_home=True):
    """
    Get latest form features for a team from database.
    
    Args:
        team_name (str): Team name
        as_home (bool): Whether team is playing at home
        
    Returns:
        dict: Dictionary of feature values, or None if no data found
    """
    engine = get_db_engine()
    
    # Use parameterized query to avoid SQL injection (psycopg2 format)
    query = """
    SELECT *
    FROM fct_team_rolling_features
    WHERE team = %(team_name)s
      AND is_home = %(is_home)s
    ORDER BY match_date DESC, match_time DESC
    LIMIT 1;
    """
    
    try:
        df = pd.read_sql_query(query, engine, params={'team_name': team_name, 'is_home': as_home})
        engine.dispose()
        
        if len(df) == 0:
            return None
        
        return df.iloc[0].to_dict()
    except Exception as e:
        engine.dispose()
        print(f"⚠️  Error querying team form for {team_name}: {e}")
        return None


def build_match_features(home_team, away_team, odds_data=None):
    """
    Build feature vector for a match using latest team form.
    
    Args:
        home_team (str): Home team name
        away_team (str): Away team name
        odds_data (dict): Optional odds data from API
        
    Returns:
        pd.DataFrame: Single-row DataFrame with all features
    """
    # Get latest form for both teams
    home_features = get_team_latest_form(home_team, as_home=True)
    away_features = get_team_latest_form(away_team, as_home=False)
    
    if home_features is None or away_features is None:
        raise ValueError(f"No historical data found for {home_team} or {away_team}")
    
    # Build feature dictionary
    features = {
        'home_team': home_team,
        'away_team': away_team,
        'match_date': datetime.now().date(),
        
        # Home team features (from fct_team_rolling_features)
        'home_matches_played_before': home_features.get('matches_played_before', 0),
        'home_avg_goals_for_last_5': home_features.get('avg_goals_for_last_5', 0),
        'home_avg_goals_against_last_5': home_features.get('avg_goals_against_last_5', 0),
        'home_avg_shots_for_last_5': home_features.get('avg_shots_for_last_5', 0),
        'home_avg_shots_on_target_for_last_5': home_features.get('avg_shots_on_target_for_last_5', 0),
        'home_avg_corners_for_last_5': home_features.get('avg_corners_for_last_5', 0),
        'home_avg_points_last_5': home_features.get('avg_points_last_5', 0),
        'home_over_25_rate_last_5': home_features.get('over_25_rate_last_5', 0),
        'home_btts_rate_last_5': home_features.get('btts_rate_last_5', 0),
        'home_clean_sheet_rate_last_5': home_features.get('clean_sheet_rate_last_5', 0),
        'home_failed_to_score_rate_last_5': home_features.get('failed_to_score_rate_last_5', 0),
        'home_avg_goals_for_last_10': home_features.get('avg_goals_for_last_10', 0),
        'home_avg_goals_against_last_10': home_features.get('avg_goals_against_last_10', 0),
        'home_over_25_rate_last_10': home_features.get('over_25_rate_last_10', 0),
        'home_btts_rate_last_10': home_features.get('btts_rate_last_10', 0),
        
        # Goal-specific features for home team
        'home_shot_efficiency_last_5': home_features.get('shot_efficiency_last_5', 0),
        'home_shot_on_target_efficiency_last_5': home_features.get('shot_on_target_efficiency_last_5', 0),
        'home_defensive_solidity_last_5': home_features.get('defensive_solidity_last_5', 0),
        'home_avg_shots_against_last_5': home_features.get('avg_shots_against_last_5', 0),
        'home_avg_shots_on_target_against_last_5': home_features.get('avg_shots_on_target_against_last_5', 0),
        'home_goal_scoring_variance_last_5': home_features.get('goal_scoring_variance_last_5', 0),
        'home_goal_conceding_variance_last_5': home_features.get('goal_conceding_variance_last_5', 0),
        'home_avg_goals_for_home_last_5': home_features.get('avg_goals_for_home_last_5', 0),
        'home_avg_goals_for_away_last_5': home_features.get('avg_goals_for_away_last_5', 0),
        'home_avg_goals_against_home_last_5': home_features.get('avg_goals_against_home_last_5', 0),
        'home_avg_goals_against_away_last_5': home_features.get('avg_goals_against_away_last_5', 0),
        
        # Away team features
        'away_matches_played_before': away_features.get('matches_played_before', 0),
        'away_avg_goals_for_last_5': away_features.get('avg_goals_for_last_5', 0),
        'away_avg_goals_against_last_5': away_features.get('avg_goals_against_last_5', 0),
        'away_avg_shots_for_last_5': away_features.get('avg_shots_for_last_5', 0),
        'away_avg_shots_on_target_for_last_5': away_features.get('avg_shots_on_target_for_last_5', 0),
        'away_avg_corners_for_last_5': away_features.get('avg_corners_for_last_5', 0),
        'away_avg_points_last_5': away_features.get('avg_points_last_5', 0),
        'away_over_25_rate_last_5': away_features.get('over_25_rate_last_5', 0),
        'away_btts_rate_last_5': away_features.get('btts_rate_last_5', 0),
        'away_clean_sheet_rate_last_5': away_features.get('clean_sheet_rate_last_5', 0),
        'away_failed_to_score_rate_last_5': away_features.get('failed_to_score_rate_last_5', 0),
        'away_avg_goals_for_last_10': away_features.get('avg_goals_for_last_10', 0),
        'away_avg_goals_against_last_10': away_features.get('avg_goals_against_last_10', 0),
        'away_over_25_rate_last_10': away_features.get('over_25_rate_last_10', 0),
        'away_btts_rate_last_10': away_features.get('btts_rate_last_10', 0),
        
        # Goal-specific features for away team
        'away_shot_efficiency_last_5': away_features.get('shot_efficiency_last_5', 0),
        'away_shot_on_target_efficiency_last_5': away_features.get('shot_on_target_efficiency_last_5', 0),
        'away_defensive_solidity_last_5': away_features.get('defensive_solidity_last_5', 0),
        'away_avg_shots_against_last_5': away_features.get('avg_shots_against_last_5', 0),
        'away_avg_shots_on_target_against_last_5': away_features.get('avg_shots_on_target_against_last_5', 0),
        'away_goal_scoring_variance_last_5': away_features.get('goal_scoring_variance_last_5', 0),
        'away_goal_conceding_variance_last_5': away_features.get('goal_conceding_variance_last_5', 0),
        'away_avg_goals_for_home_last_5': away_features.get('avg_goals_for_home_last_5', 0),
        'away_avg_goals_for_away_last_5': away_features.get('avg_goals_for_away_last_5', 0),
        'away_avg_goals_against_home_last_5': away_features.get('avg_goals_against_home_last_5', 0),
        'away_avg_goals_against_away_last_5': away_features.get('avg_goals_against_away_last_5', 0),
        
        # ========================================================================
        # PHASE 1 FEATURES: Momentum and Home/Away Splits (Option C: NO position features)
        # ========================================================================
        
        # Home/Away win rates (venue-specific)
        'home_team_home_win_rate_last_5': home_features.get('home_win_rate_last_5', 0),
        'away_team_away_win_rate_last_5': away_features.get('away_win_rate_last_5', 0),
        'home_team_home_clean_sheet_rate_last_5': home_features.get('home_clean_sheet_rate_last_5', 0),
        'away_team_away_clean_sheet_rate_last_5': away_features.get('away_clean_sheet_rate_last_5', 0),
        'home_team_home_btts_rate_last_5': home_features.get('home_btts_rate_last_5', 0),
        'away_team_away_btts_rate_last_5': away_features.get('away_btts_rate_last_5', 0),
        
        # Momentum features
        'home_win_streak': home_features.get('win_streak', 0),
        'away_win_streak': away_features.get('win_streak', 0),
        'home_unbeaten_streak': home_features.get('unbeaten_streak', 0),
        'away_unbeaten_streak': away_features.get('unbeaten_streak', 0),
        'home_form_trend_points': home_features.get('form_trend_points', 0),
        'away_form_trend_points': away_features.get('form_trend_points', 0),
        'home_form_trend_goals': home_features.get('form_trend_goals', 0),
        'away_form_trend_goals': away_features.get('form_trend_goals', 0),
        'home_win_rate_last_5': home_features.get('win_rate_last_5', 0),
        'away_win_rate_last_5': away_features.get('win_rate_last_5', 0),
    }
    
    # Store odds separately for value edge calculation (not model features)
    odds_info = None
    if odds_data:
        odds_info = {
            'home_odds': odds_data.get('home_odds', 0),
            'draw_odds': odds_data.get('draw_odds', 0),
            'away_odds': odds_data.get('away_odds', 0),
            'over_25_odds': odds_data.get('over_25_odds', 0),
            'under_25_odds': odds_data.get('under_25_odds', 0),
            'implied_home_win_prob': 1 / odds_data['home_odds'] if odds_data.get('home_odds', 0) > 0 else 0,
            'implied_draw_prob': 1 / odds_data['draw_odds'] if odds_data.get('draw_odds', 0) > 0 else 0,
            'implied_away_win_prob': 1 / odds_data['away_odds'] if odds_data.get('away_odds', 0) > 0 else 0,
            'implied_over_25_prob': 1 / odds_data['over_25_odds'] if odds_data.get('over_25_odds', 0) > 0 else 0,
            'implied_under_25_prob': 1 / odds_data['under_25_odds'] if odds_data.get('under_25_odds', 0) > 0 else 0,
        }
    
    # Calculate derived features (like in fct_model_features.sql)
    features['home_attack_strength'] = features['home_avg_goals_for_last_5'] - features['away_avg_goals_against_last_5']
    features['away_attack_strength'] = features['away_avg_goals_for_last_5'] - features['home_avg_goals_against_last_5']
    features['home_defense_strength'] = features['away_avg_goals_for_last_5'] - features['home_avg_goals_against_last_5']
    features['away_defense_strength'] = features['home_avg_goals_for_last_5'] - features['away_avg_goals_against_last_5']
    features['home_form_strength'] = features['home_avg_points_last_5']
    features['away_form_strength'] = features['away_avg_points_last_5']
    features['total_attack_potential'] = (features['home_avg_goals_for_last_5'] + features['away_avg_goals_for_last_5']) / 2
    features['total_defense_weakness'] = (features['home_avg_goals_against_last_5'] + features['away_avg_goals_against_last_5']) / 2
    features['home_shot_efficiency'] = features['home_avg_goals_for_last_5'] / features['home_avg_shots_for_last_5'] if features['home_avg_shots_for_last_5'] > 0 else 0
    features['away_shot_efficiency'] = features['away_avg_goals_for_last_5'] / features['away_avg_shots_for_last_5'] if features['away_avg_shots_for_last_5'] > 0 else 0
    
    # OPTION C: Odds-based derived features REMOVED (data leakage)
    # [REMOVED] odds_home_favorite, odds_total_prob, odds_overround
    
    # ============================================================================
    # PHASE 1 DERIVED FEATURES (Option C: Form-based only, no position)
    # ============================================================================
    
    # Momentum difference (positive = home team has better momentum)
    features['momentum_differential'] = features['home_form_trend_points'] - features['away_form_trend_points']
    features['win_streak_differential'] = features['home_win_streak'] - features['away_win_streak']
    
    # Form strength differential
    features['win_rate_differential'] = features['home_win_rate_last_5'] - features['away_win_rate_last_5']
    
    # Home advantage factor (team's home performance vs away team's away performance)
    features['home_advantage_factor'] = features['home_team_home_win_rate_last_5'] - features['away_team_away_win_rate_last_5']
    
    # Return features DataFrame and odds_info separately
    # Odds are NOT model features, only used for value edge calculation
    return pd.DataFrame([features]), odds_info


def load_models(model_dir='models/saved', model_type='logistic'):
    """Load all trained models (Logistic Regression or Random Forest)."""
    print("\n" + "="*80)
    print(f"LOADING TRAINED MODELS ({model_type.upper()})")
    print("="*80)
    
    models = {}
    scalers = {}
    
    for target_col in TARGETS.keys():
        model_path = os.path.join(model_dir, f"{target_col}_{model_type}.pkl")
        scaler_path = os.path.join(model_dir, f"{target_col}_{model_type}_scaler.pkl")
        
        if os.path.exists(model_path):
            models[target_col] = joblib.load(model_path)
            print(f"✓ Loaded: {target_col}_{model_type}.pkl")
            
            # Load scaler if exists (Logistic Regression needs scaling)
            if os.path.exists(scaler_path):
                scalers[target_col] = joblib.load(scaler_path)
                print(f"✓ Loaded: {target_col}_{model_type}_scaler.pkl")
        else:
            print(f"⚠️  Missing: {target_col}_{model_type}.pkl")
    
    return models, scalers


def prepare_features(df, target_col):
    """Prepare features for prediction in the correct order."""
    # Get column order from database (fct_model_features table)
    engine = get_db_engine()
    
    try:
        # Query one row to get column names in correct order
        query = "SELECT * FROM fct_model_features LIMIT 1;"
        db_df = pd.read_sql_query(query, engine)
        engine.dispose()
        
        # Exclude non-feature columns
        exclude_cols = [
            'match_key', 'match_date', 'match_time', 'league_code',
            'home_team', 'away_team',
            'target_over_25', 'target_under_25',
            'target_btts_yes', 'target_btts_no',
            'target_home_win', 'target_draw', 'target_away_win',
            'target_home_win_or_draw', 'target_away_win_or_draw'
        ]
        
        # Get feature columns in database order
        feature_cols = [col for col in db_df.columns if col not in exclude_cols]
        
        # Ensure all feature columns exist in prediction DataFrame
        for col in feature_cols:
            if col not in df.columns:
                df[col] = 0
        
        # Return features in correct order
        return df[feature_cols].fillna(0)
        
    except Exception as e:
        engine.dispose()
        print(f"⚠️  Error getting feature column order: {e}")
        print(f"   Falling back to alphabetical order...")
        
        # Fallback: use alphabetical order
        exclude_cols = [
            'match_key', 'match_date', 'match_time', 'league_code',
            'home_team', 'away_team',
            'target_over_25', 'target_under_25',
            'target_btts_yes', 'target_btts_no',
            'target_home_win', 'target_draw', 'target_away_win',
            'target_home_win_or_draw', 'target_away_win_or_draw'
        ]
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        feature_cols = sorted([col for col in numeric_cols if col not in exclude_cols])
        
        return df[feature_cols].fillna(0)


def generate_prediction(home_team, away_team, match_date, models, scalers, odds_data=None):
    """
    Generate predictions for a single match.
    
    Args:
        home_team (str): Home team name
        away_team (str): Away team name
        match_date (str): Match date
        models (dict): Loaded models
        scalers (dict): Loaded scalers (for Logistic Regression)
        odds_data (dict): Optional odds data
        
    Returns:
        dict: Prediction results
    """
    try:
        # Build feature vector (odds NOT included as features)
        df, odds_info = build_match_features(home_team, away_team, odds_data)
        
        # Generate predictions
        prediction = {
            'match_date': str(match_date),
            'home_team': home_team,
            'away_team': away_team,
            'predictions': {}
        }
        
        # Get predictions from each model
        for target_col, model in models.items():
            X = prepare_features(df, target_col)
            
            # Apply scaling if scaler exists (Logistic Regression)
            if target_col in scalers:
                X_scaled = scalers[target_col].transform(X)
                proba = model.predict_proba(X_scaled)[0, 1]
            else:
                # No scaling (Random Forest)
                proba = model.predict_proba(X)[0, 1]
            
            target_name = TARGETS[target_col]
            
            pred_detail = {
                'probability': float(round(proba, 4)),
                'confidence': 'HIGH' if proba >= 0.70 else 'MEDIUM' if proba >= 0.55 else 'LOW'
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
        # Load models (Logistic Regression by default)
        models, scalers = load_models(model_type='logistic')
        
        if len(models) == 0:
            print("\n❌ No models found! Please train models first:")
            print("   python scripts/train_models.py")
            return 1
        
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
            pred = generate_prediction(args.home, args.away, match_date, models, scalers, odds_data)
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
                        models,
                        scalers,
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
    sys.exit(main())
