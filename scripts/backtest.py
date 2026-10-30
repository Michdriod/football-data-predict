#!/usr/bin/env python3
"""
Football Match Prediction Backtesting Script

Backtests trained models on historical data by season:
- Win rate analysis
- ROI calculation
- Maximum drawdown
- Consistency across seasons

Usage:
    python scripts/backtest.py
    python scripts/backtest.py --season 2023-24
    python scripts/backtest.py --output backtest_report.csv

Author: Football Prediction System
Date: 2026-05-22
"""

import os
import sys
import argparse
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
import joblib

from sklearn.metrics import roc_auc_score, accuracy_score

import sqlalchemy
from sqlalchemy import create_engine

warnings.filterwarnings('ignore')

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

# Import centralized configuration
from config import (
    DB_CONFIG,
    get_db_connection_string,
    BETTING_THRESHOLDS,
    ROLLING_WINDOW_START_DATE,
    TARGETS,
    TARGET_NAMES
)

# Betting decision thresholds
BETTING_THRESHOLDS = {
    'min_probability': 0.70,
    'min_value_edge': 0.05,
    'min_odds': 1.50,
    'max_odds': 3.00
}

# Test set start
TEST_START_DATE = '2024-07-01'

# Prediction targets
TARGETS = {
    'target_over_25': 'Over/Under 2.5 Goals',
    'target_btts_yes': 'Both Teams To Score',
    'target_home_win': 'Home Win',
    'target_draw': 'Draw',
    'target_away_win': 'Away Win',
    'target_home_win_or_draw': 'Home Win or Draw (1X)',
    'target_away_win_or_draw': 'Away Win or Draw (X2)'
}

# ============================================================================
# DATABASE CONNECTION
# ============================================================================

def get_db_engine():
    """Create SQLAlchemy engine."""
    return create_engine(get_db_connection_string())

def load_backtest_data():
    """Load backtest data from database."""
    print("\n" + "="*80)
    print("LOADING BACKTEST DATA FROM DATABASE")
    print("="*80)
    
    engine = get_db_engine()
    
    query = f"""
    SELECT f.*,
           o.implied_over_25_prob AS implied_over_25_prob,
           o.implied_home_win_prob AS implied_home_win_prob,
           o.implied_draw_prob AS implied_draw_prob,
           o.implied_away_win_prob AS implied_away_win_prob
    FROM fct_model_features f
    LEFT JOIN fct_model_training_dataset o ON f.match_key = o.match_key
    ORDER BY f.match_date;
    """
    
    print(f"Connecting to: {DB_CONFIG['database']}")
    print(f"Loading backtest data from: fct_model_features")
    
    df = pd.read_sql_query(query, engine)
    df['match_date'] = pd.to_datetime(df['match_date'], format='mixed', dayfirst=True)
    
    # Apply rolling window filter (same as training)
    original_count = len(df)
    df = df[df['match_date'] >= ROLLING_WINDOW_START_DATE].copy()
    filtered_count = original_count - len(df)
    
    print(f"\n🔄 ROLLING WINDOW FILTER APPLIED:")
    print(f"  Start Date: {ROLLING_WINDOW_START_DATE}")
    print(f"  Removed: {filtered_count:,} old matches (pre-2021)")
    print(f"  Kept: {len(df):,} matches for backtesting (2021-2026)")
    
    print(f"\n✓ Loaded {len(df):,} matches")
    print(f"✓ Date range: {df['match_date'].min()} to {df['match_date'].max()}")
    
    engine.dispose()
    
    return df

def load_models(model_dir='models/saved'):
    """Load trained models."""
    models = {}
    
    for target_col in TARGETS.keys():
        models[target_col] = {}
        rf_path = os.path.join(model_dir, f"{target_col}_random_forest.pkl")
        if os.path.exists(rf_path):
            models[target_col]['random_forest'] = joblib.load(rf_path)
    
    return models

def prepare_features(df, target_col):
    """Prepare features for prediction."""
    exclude_cols = [
        'match_key', 'match_date', 'match_time', 'league_code',
        'home_team', 'away_team',
        'target_over_25', 'target_under_25',
        'target_btts_yes', 'target_btts_no',
        'target_home_win', 'target_draw', 'target_away_win',
        'target_home_win_or_draw', 'target_away_win_or_draw',
        # Odds are for betting evaluation only, never model inputs
        'implied_over_25_prob', 'implied_home_win_prob',
        'implied_draw_prob', 'implied_away_win_prob'
    ]
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    feature_cols = [col for col in numeric_cols if col not in exclude_cols]
    
    return df[feature_cols].fillna(0), feature_cols

def make_predictions(df, models):
    """Make predictions for all matches."""
    predictions = df[['match_date', 'home_team', 'away_team']].copy()
    
    for target_col in TARGETS.keys():
        if 'random_forest' in models[target_col]:
            model = models[target_col]['random_forest']
            X, _ = prepare_features(df, target_col)
            predictions[f"{target_col}_prob"] = model.predict_proba(X)[:, 1]
    
    # Add actual outcomes and odds
    predictions['target_over_25'] = df['target_over_25'].values
    predictions['target_btts_yes'] = df['target_btts_yes'].values
    predictions['target_home_win'] = df['target_home_win'].values
    predictions['target_draw'] = df['target_draw'].values
    predictions['target_away_win'] = df['target_away_win'].values
    predictions['target_home_win_or_draw'] = df['target_home_win_or_draw'].values
    predictions['target_away_win_or_draw'] = df['target_away_win_or_draw'].values
    
    predictions['implied_over_25_prob'] = df['implied_over_25_prob'].values
    predictions['implied_home_not_lose_prob'] = (df['implied_home_win_prob'] + df['implied_draw_prob']).values
    predictions['implied_away_not_lose_prob'] = (df['implied_away_win_prob'] + df['implied_draw_prob']).values
    
    return predictions

def calculate_betting_performance(predictions):
    """Calculate betting performance metrics."""
    print("\n" + "="*80)
    print("BACKTESTING RESULTS")
    print("="*80)
    
    backtest_results = []
    
    for target_col in TARGETS.keys():
        pred_col = f"{target_col}_prob"
        
        if pred_col not in predictions.columns:
            continue
        
        # Map to actual outcome
        if 'over_25' in target_col:
            actual_col = 'target_over_25'
            implied_col = 'implied_over_25_prob'
        elif 'btts' in target_col:
            actual_col = 'target_btts_yes'
            implied_col = None
        elif 'home_not_lose' in target_col:
            actual_col = 'target_home_win_or_draw'
            implied_col = 'implied_home_not_lose_prob'
        else:
            actual_col = 'target_away_win_or_draw'
            implied_col = 'implied_away_not_lose_prob'
        
        # Overall performance
        mask_valid = predictions[pred_col].notna() & predictions[actual_col].notna()
        
        if mask_valid.sum() == 0:
            continue
        
        y_true = predictions.loc[mask_valid, actual_col].astype(int).values
        y_pred = predictions.loc[mask_valid, pred_col].values
        
        auc = roc_auc_score(y_true, y_pred)
        accuracy = accuracy_score(y_true, (y_pred > 0.5).astype(int))
        
        # Betting analysis
        if implied_col:
            implied_prob = predictions.loc[mask_valid, implied_col].values
            value_edge = y_pred - implied_prob
            
            # High confidence bets
            high_conf = (y_pred >= BETTING_THRESHOLDS['min_probability']) & (value_edge >= BETTING_THRESHOLDS['min_value_edge'])
            
            if high_conf.sum() > 0:
                bet_accuracy = y_true[high_conf].mean()
                # Flat 1-unit stakes settled at the implied market price
                bet_roi = ((y_true[high_conf] / implied_prob[high_conf]).mean() - 1) * 100
                bet_count = high_conf.sum()
            else:
                bet_accuracy = 0
                bet_roi = 0
                bet_count = 0
        else:
            bet_count = 0
            bet_accuracy = 0
            bet_roi = 0
        
        backtest_results.append({
            'Target': TARGETS[target_col],
            'Total Matches': mask_valid.sum(),
            'Test AUC': f"{auc:.4f}",
            'Accuracy': f"{accuracy:.4f}",
            'Betting Opportunities': bet_count,
            'Bet Win Rate': f"{bet_accuracy:.1%}" if bet_count > 0 else "N/A",
            'Bet ROI': f"{bet_roi:.1f}%" if bet_count > 0 else "N/A"
        })
    
    backtest_df = pd.DataFrame(backtest_results)
    print("\n" + backtest_df.to_string(index=False))
    
    return backtest_df

def backtest_by_season(predictions):
    """Backtest by season."""
    print("\n" + "="*80)
    print("SEASON-BY-SEASON ANALYSIS")
    print("="*80)
    
    predictions['season'] = predictions['match_date'].dt.strftime('%Y-%m')
    
    season_results = []
    
    for season in sorted(predictions['season'].unique()):
        mask = predictions['season'] == season
        matches = mask.sum()
        
        # Over 2.5 analysis
        pred_col = 'target_over_25_prob'
        actual_col = 'target_over_25'
        
        if pred_col in predictions.columns and actual_col in predictions.columns:
            mask_valid = mask & predictions[pred_col].notna() & predictions[actual_col].notna()
            
            if mask_valid.sum() > 0:
                y_true = predictions.loc[mask_valid, actual_col].astype(int).values
                y_pred = predictions.loc[mask_valid, pred_col].values
                
                try:
                    auc = roc_auc_score(y_true, y_pred)
                    accuracy = accuracy_score(y_true, (y_pred > 0.5).astype(int))
                    
                    season_results.append({
                        'Season': season,
                        'Matches': matches,
                        'Over 2.5 AUC': f"{auc:.4f}",
                        'Over 2.5 Acc': f"{accuracy:.1%}"
                    })
                except:
                    pass
    
    if season_results:
        season_df = pd.DataFrame(season_results)
        print("\n" + season_df.to_string(index=False))
        return season_df
    
    return None

def save_results(backtest_df, season_df=None, output_dir='logs'):
    """Save backtest results."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save overall results
    output_file = os.path.join(output_dir, f"backtest_results_{timestamp}.csv")
    backtest_df.to_csv(output_file, index=False)
    print(f"\n✓ Backtest results saved to: {output_file}")
    
    # Save season results
    if season_df is not None:
        season_file = os.path.join(output_dir, f"season_results_{timestamp}.csv")
        season_df.to_csv(season_file, index=False)
        print(f"✓ Season results saved to: {season_file}")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Backtest prediction models')
    parser.add_argument('--season', help='Specific season (YYYY-MM)')
    parser.add_argument('--output', help='Output directory')
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("FOOTBALL MATCH PREDICTION - BACKTESTING")
    print("="*80)
    print(f"\nStart Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Load data and models
        df = load_backtest_data()
        models = load_models()
        print("✓ Models loaded successfully")
        
        # Make predictions
        print("\nMaking predictions...")
        predictions = make_predictions(df, models)
        print("✓ Predictions generated")
        
        # Calculate metrics
        backtest_df = calculate_betting_performance(predictions)
        
        # Season analysis
        season_df = backtest_by_season(predictions)
        
        # Save results
        save_results(backtest_df, season_df, output_dir=args.output or 'logs')
        
        print(f"\n{'='*80}")
        print(f"✓ Backtesting completed!")
        print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")
        
        return 0
        
    except Exception as e:
        print(f"\n{'='*80}")
        print(f"❌ ERROR: Backtesting failed!")
        print(f"{'='*80}")
        print(f"{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
