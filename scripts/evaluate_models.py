#!/usr/bin/env python3
"""
Football Match Prediction Model Evaluation Script

Evaluates trained models on test set and calculates betting metrics:
- ROC-AUC, Brier Score, Log Loss
- Betting value edge analysis
- ROI and win rate with real market odds
- Performance by season

Usage:
    python scripts/evaluate_models.py
    python scripts/evaluate_models.py --models random_forest
    python scripts/evaluate_models.py --targets target_over_25 target_btts_yes

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
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.metrics import (
    roc_auc_score, brier_score_loss, log_loss,
    accuracy_score, precision_score, recall_score, f1_score,
    roc_curve, confusion_matrix, classification_report
)

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

# Test set dates
TEST_START_DATE = '2024-07-01'

# Prediction targets
TARGETS = {
    'target_over_25': 'Over/Under 2.5 Goals',
    'target_btts_yes': 'Both Teams To Score',
    'target_home_win': 'Home Win',
    'target_draw': 'Draw',
    'target_away_win': 'Away Win',
    'target_home_win_or_draw': 'Home Win or Draw (1X)',
    'target_away_win_or_draw': 'Away Win or Draw (X2)',
}

# Model mapping for betting outcomes
TARGET_TO_ODDS_COL = {
    'target_over_25': 'implied_over_25_prob',
    'target_btts_yes': None,  # No direct odds column, use derived
    'target_home_win': 'implied_home_win_prob',
    'target_draw': 'implied_draw_prob',
    'target_away_win': 'implied_away_win_prob',
    'target_home_win_or_draw': 'implied_home_not_lose_prob',
    'target_away_win_or_draw': 'implied_away_not_lose_prob'
}

# ============================================================================
# DATABASE CONNECTION
# ============================================================================

def get_db_engine():
    """Create SQLAlchemy engine."""
    return create_engine(get_db_connection_string())

def load_test_data():
    """Load test set data from database."""
    print("\n" + "="*80)
    print("LOADING TEST DATA FROM DATABASE")
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
    print(f"Loading test data from: fct_model_features")
    print(f"Start date: {TEST_START_DATE}")
    
    df = pd.read_sql_query(query, engine)
    
    # Parse dates
    df['match_date'] = pd.to_datetime(df['match_date'], format='mixed', dayfirst=True)
    
    # Apply rolling window filter (same as training)
    original_count = len(df)
    df = df[df['match_date'] >= ROLLING_WINDOW_START_DATE].copy()
    filtered_count = original_count - len(df)
    
    print(f"\n🔄 ROLLING WINDOW FILTER APPLIED:")
    print(f"  Start Date: {ROLLING_WINDOW_START_DATE}")
    print(f"  Removed: {filtered_count:,} old test matches (pre-2021)")
    print(f"  Kept: {len(df):,} matches for evaluation (2021-2026)")
    
    print(f"\n✓ Final test set")
    print(f"  Matches: {len(df):,}")
    print(f"  Date range: {df['match_date'].min()} to {df['match_date'].max()}")
    print(f"  Columns: {len(df.columns)}")
    
    engine.dispose()
    
    return df

def load_models(model_dir='models/saved'):
    """Load all trained models and metadata."""
    print("\n" + "="*80)
    print("LOADING TRAINED MODELS")
    print("="*80)
    
    models = {}
    
    for target_col in TARGETS.keys():
        models[target_col] = {}
        
        # Load logistic regression
        logistic_path = os.path.join(model_dir, f"{target_col}_logistic.pkl")
        if os.path.exists(logistic_path):
            models[target_col]['logistic'] = joblib.load(logistic_path)
            print(f"✓ Loaded: {target_col}_logistic.pkl")
            
            # Load scaler
            scaler_path = os.path.join(model_dir, f"{target_col}_logistic_scaler.pkl")
            if os.path.exists(scaler_path):
                models[target_col]['logistic_scaler'] = joblib.load(scaler_path)
        
        # Load random forest
        rf_path = os.path.join(model_dir, f"{target_col}_random_forest.pkl")
        if os.path.exists(rf_path):
            models[target_col]['random_forest'] = joblib.load(rf_path)
            print(f"✓ Loaded: {target_col}_random_forest.pkl")
    
    # Load metadata
    metadata_files = [f for f in os.listdir(model_dir) if f.startswith('training_metadata')]
    if metadata_files:
        latest_metadata = sorted(metadata_files)[-1]
        metadata_path = os.path.join(model_dir, latest_metadata)
        metadata = joblib.load(metadata_path)
        print(f"✓ Loaded: {latest_metadata}")
    else:
        metadata = None
    
    return models, metadata

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
    """Make predictions using all models."""
    print("\n" + "="*80)
    print("MAKING PREDICTIONS ON TEST SET")
    print("="*80)
    
    predictions = pd.DataFrame({
        'match_key': df['match_key'],
        'match_date': df['match_date'],
        'home_team': df['home_team'],
        'away_team': df['away_team']
    })
    
    for target_col in TARGETS.keys():
        X, feature_cols = prepare_features(df, target_col)
        
        # Make predictions for each model
        for model_type in ['logistic', 'random_forest']:
            if model_type in models[target_col]:
                model = models[target_col][model_type]
                
                if model_type == 'logistic' and 'logistic_scaler' in models[target_col]:
                    scaler = models[target_col]['logistic_scaler']
                    X_scaled = scaler.transform(X)
                    proba = model.predict_proba(X_scaled)[:, 1]
                else:
                    proba = model.predict_proba(X)[:, 1]
                
                col_name = f"{target_col}_{model_type}_prob"
                predictions[col_name] = proba
        
        print(f"✓ Predictions for {TARGETS[target_col]}")
    
    return predictions

def calculate_betting_metrics(predictions, df):
    """Calculate betting value and ROI metrics."""
    print("\n" + "="*80)
    print("CALCULATING BETTING METRICS")
    print("="*80)
    
    # Add actual outcomes
    predictions['actual_over_25'] = df['target_over_25'].values
    predictions['actual_btts'] = df['target_btts_yes'].values
    predictions['actual_home_win'] = df['target_home_win'].values
    predictions['actual_draw'] = df['target_draw'].values
    predictions['actual_away_win'] = df['target_away_win'].values
    predictions['actual_home_not_lose'] = df['target_home_win_or_draw'].values
    predictions['actual_away_not_lose'] = df['target_away_win_or_draw'].values
    
    # Add odds
    predictions['implied_over_25_prob'] = df['implied_over_25_prob'].values
    predictions['implied_home_not_lose_prob'] = (df['implied_home_win_prob'] + df['implied_draw_prob']).values
    predictions['implied_away_not_lose_prob'] = (df['implied_away_win_prob'] + df['implied_draw_prob']).values
    
    betting_results = []
    
    # Evaluate each target with best model (Random Forest)
    for target_col in TARGETS.keys():
        if f"{target_col}_random_forest_prob" not in predictions.columns:
            continue
        
        pred_col = f"{target_col}_random_forest_prob"
        actual_col = f"actual_{target_col.replace('target_', '')}"
        
        if actual_col not in predictions.columns:
            # Map target to actual column
            if 'over_25' in target_col:
                actual_col = 'actual_over_25'
            elif 'btts' in target_col:
                actual_col = 'actual_btts'
            elif 'home_not_lose' in target_col:
                actual_col = 'actual_home_not_lose'
            else:
                actual_col = 'actual_away_not_lose'
        
        # Get implied probabilities based on target
        if 'over_25' in target_col:
            implied_col = 'implied_over_25_prob'
        elif 'home_not_lose' in target_col:
            implied_col = 'implied_home_not_lose_prob'
        elif 'away_not_lose' in target_col:
            implied_col = 'implied_away_not_lose_prob'
        else:
            # For BTTS, estimate from goal probabilities
            implied_col = None
        
        # Calculate metrics for this target
        df_target = predictions[[pred_col, actual_col, implied_col]].copy() if implied_col else predictions[[pred_col, actual_col]].copy()
        df_target = df_target.dropna()
        
        if len(df_target) == 0:
            continue
        
        y_true = df_target[actual_col].astype(int)
        y_pred = df_target[pred_col]
        
        # Base metrics
        auc = roc_auc_score(y_true, y_pred)
        brier = brier_score_loss(y_true, y_pred)
        accuracy = accuracy_score(y_true, (y_pred > 0.5).astype(int))
        
        # Betting metrics
        if implied_col:
            implied_prob = df_target[implied_col].values
            value_edge = y_pred - implied_prob
            
            # Find high-confidence bets
            high_conf = (y_pred >= BETTING_THRESHOLDS['min_probability']) & (value_edge >= BETTING_THRESHOLDS['min_value_edge'])
            
            if high_conf.sum() > 0:
                bet_accuracy = y_true[high_conf].mean()
                bet_count = high_conf.sum()
            else:
                bet_accuracy = 0
                bet_count = 0
        else:
            bet_count = 0
            bet_accuracy = 0
        
        betting_results.append({
            'Target': TARGETS[target_col],
            'Test Matches': len(df_target),
            'Test AUC': f"{auc:.4f}",
            'Test Brier': f"{brier:.4f}",
            'Accuracy': f"{accuracy:.4f}",
            'High-Conf Bets': bet_count,
            'Bet Accuracy': f"{bet_accuracy:.4f}" if bet_count > 0 else "N/A"
        })
    
    betting_df = pd.DataFrame(betting_results)
    print("\n" + betting_df.to_string(index=False))
    
    return predictions

def evaluate_by_season(predictions, df):
    """Evaluate models by season."""
    print("\n" + "="*80)
    print("EVALUATION BY SEASON")
    print("="*80)
    
    predictions['season'] = predictions['match_date'].dt.strftime('%Y-%m')
    
    season_results = []
    
    for season in sorted(predictions['season'].unique()):
        mask = predictions['season'] == season
        season_matches = mask.sum()
        
        # Get sample accuracy for Over 2.5
        if 'target_over_25_random_forest_prob' in predictions.columns:
            y_true = df.loc[mask, 'target_over_25'].values
            y_pred = predictions.loc[mask, 'target_over_25_random_forest_prob'].values
            
            try:
                auc = roc_auc_score(y_true, y_pred)
                season_results.append({
                    'Season': season,
                    'Matches': season_matches,
                    'Over 2.5 AUC': f"{auc:.4f}"
                })
            except:
                pass
    
    if season_results:
        season_df = pd.DataFrame(season_results)
        print("\n" + season_df.to_string(index=False))

def save_results(predictions, output_path='logs/evaluation_results.csv'):
    """Save predictions to file."""
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    predictions.to_csv(output_path, index=False)
    print(f"\n✓ Predictions saved to: {output_path}")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Evaluate trained models')
    parser.add_argument(
        '--models',
        nargs='+',
        default=['logistic', 'random_forest'],
        choices=['logistic', 'random_forest']
    )
    parser.add_argument(
        '--targets',
        nargs='+',
        default=list(TARGETS.keys())
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("FOOTBALL MATCH PREDICTION - MODEL EVALUATION")
    print("="*80)
    print(f"\nStart Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Load data and models
        test_df = load_test_data()
        models, metadata = load_models()
        
        # Make predictions
        predictions = make_predictions(test_df, models)
        
        # Calculate metrics
        calculate_betting_metrics(predictions, test_df)
        
        # Evaluate by season
        evaluate_by_season(predictions, test_df)
        
        # Save results
        save_results(predictions)
        
        print(f"\n{'='*80}")
        print(f"✓ Evaluation completed successfully!")
        print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")
        
        return 0
        
    except Exception as e:
        print(f"\n{'='*80}")
        print(f"❌ ERROR: Evaluation failed!")
        print(f"{'='*80}")
        print(f"{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
