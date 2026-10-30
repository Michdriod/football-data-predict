#!/usr/bin/env python3
"""
Football Match Prediction Model Training Script

Trains baseline models (Logistic Regression + Random Forest) for 4 prediction targets:
1. Over/Under 2.5 Goals
2. Both Teams To Score (BTTS)
3. Home Not Lose (1X)
4. Away Not Lose (X2)

Usage:
    python scripts/train_models.py
    python scripts/train_models.py --targets over_25 btts_yes
    python scripts/train_models.py --models logistic

Author: Football Prediction System
Date: 2026-04-26
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

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
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
    SPLIT_DATES,
    ROLLING_WINDOW_START_DATE,
    TEMPORAL_CV_CONFIG,
    MODEL_CONFIGS,
    TARGETS,
    TARGET_NAMES
)

# Feature columns to use for training
FEATURE_COLUMNS = [
    # Match identifiers (for reference, not features)
    'match_key', 'match_date', 'home_team', 'away_team',
    
    # Home team form features (last 5 matches)
    'home_matches_played_before',
    'home_avg_goals_for_last_5',
    'home_avg_goals_against_last_5',
    'home_avg_shots_for_last_5',
    'home_avg_shots_on_target_for_last_5',
    'home_avg_corners_for_last_5',
    'home_avg_points_last_5',
    'home_over_25_rate_last_5',
    'home_btts_rate_last_5',
    'home_clean_sheet_rate_last_5',
    'home_failed_to_score_rate_last_5',
    
    # Home team form features (last 10 matches)
    'home_avg_goals_for_last_10',
    'home_avg_goals_against_last_10',
    'home_over_25_rate_last_10',
    'home_btts_rate_last_10',
    
    # Away team form features (last 5 matches)
    'away_matches_played_before',
    'away_avg_goals_for_last_5',
    'away_avg_goals_against_last_5',
    'away_avg_shots_for_last_5',
    'away_avg_shots_on_target_for_last_5',
    'away_avg_corners_for_last_5',
    'away_avg_points_last_5',
    'away_over_25_rate_last_5',
    'away_btts_rate_last_5',
    'away_clean_sheet_rate_last_5',
    'away_failed_to_score_rate_last_5',
    
    # Away team form features (last 10 matches)
    'away_avg_goals_for_last_10',
    'away_avg_goals_against_last_10',
    'away_over_25_rate_last_10',
    'away_btts_rate_last_10',
    
    # Betting odds features
    'bet365_home_win_odds',
    'bet365_draw_odds',
    'bet365_away_win_odds',
    'avg_home_win_odds',
    'avg_draw_odds',
    'avg_away_win_odds',
    'bet365_over_25_odds',
    'bet365_under_25_odds',
    'avg_over_25_odds',
    'avg_under_25_odds',
    'implied_home_win_prob',
    'implied_draw_prob',
    'implied_away_win_prob',
    'implied_over_25_prob',
    'implied_under_25_prob'
]

# ============================================================================
# DATABASE CONNECTION
# ============================================================================

def get_db_engine():
    """Create SQLAlchemy engine for PostgreSQL connection."""
    connection_string = (
        f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )
    return create_engine(connection_string)

def load_training_data():
    """
    Load training dataset from PostgreSQL.
    
    Returns:
        pd.DataFrame: Complete training dataset
    """
    print("\n" + "="*80)
    print("LOADING DATA FROM DATABASE")
    print("="*80)
    
    engine = get_db_engine()
    
    query = """
    SELECT *
    FROM fct_model_features
    ORDER BY match_date;
    """
    
    print(f"Connecting to: {DB_CONFIG['database']}")
    print(f"Loading data from: fct_model_features")
    
    df = pd.read_sql_query(query, engine)
    
    print(f"\n✓ Loaded {len(df):,} matches")
    print(f"✓ Date range: {df['match_date'].min()} to {df['match_date'].max()}")
    print(f"✓ Columns: {len(df.columns)}")
    print(f"✓ Teams: {df['home_team'].nunique()}")
    
    engine.dispose()
    
    return df

# ============================================================================
# FEATURE ENGINEERING (moved to dbt model: fct_model_features)
# ============================================================================

def prepare_data_for_training(df):
    """
    Final data preparation before training.
    All feature engineering now happens in dbt (fct_model_features.sql).
    This function only handles basic preprocessing.
    
    Args:
        df (pd.DataFrame): Input dataframe from fct_model_features
        
    Returns:
        pd.DataFrame: Cleaned data ready for training
    """
    print("\n" + "="*80)
    print("DATA PREPARATION")
    print("="*80)
    
    df = df.copy()
    
    # Ensure datetime column (handle mixed date formats)
    df['match_date'] = pd.to_datetime(df['match_date'], format='mixed', dayfirst=True)
    
    # Apply rolling window filter (use only recent data)
    original_count = len(df)
    df = df[df['match_date'] >= ROLLING_WINDOW_START_DATE].copy()
    filtered_count = original_count - len(df)
    
    print(f"\n🔄 ROLLING WINDOW FILTER APPLIED:")
    print(f"  Start Date: {ROLLING_WINDOW_START_DATE}")
    print(f"  Removed: {filtered_count:,} old matches (pre-2021)")
    print(f"  Kept: {len(df):,} recent matches (2021-2026)")
    print(f"  Rationale: Football tactics evolve - 2018 data is outdated for 2026")
    
    # Handle any missing values
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].fillna(0)
    
    print(f"\n✓ Data prepared for training")
    print(f"  Total rows: {len(df):,}")
    print(f"  Total features: {len(df.columns)}")
    print(f"  Note: All 12 derived features created in dbt (fct_model_features)")
    
    return df

def get_feature_columns(df, target):
    """
    Get list of feature columns for modeling.
    
    Args:
        df (pd.DataFrame): Input dataframe
        target (str): Target column name
        
    Returns:
        list: List of feature column names
    """
    # Exclude non-feature columns
    exclude_cols = [
        'match_key', 'match_date', 'match_time', 'league_code',
        'home_team', 'away_team',
        # Exclude all target columns
        'target_over_25', 'target_under_25',
        'target_btts_yes', 'target_btts_no',
        'target_home_win', 'target_draw', 'target_away_win',
        'target_home_win_or_draw', 'target_away_win_or_draw'
    ]
    
    # Get numeric columns only
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    # Remove excluded columns
    feature_cols = [col for col in numeric_cols if col not in exclude_cols]
    
    return feature_cols

# ============================================================================
# DATA SPLITTING
# ============================================================================

def split_data(df):
    """
    Split data into train/validation/test sets based on time.
    
    Args:
        df (pd.DataFrame): Input dataframe with match_date column
        
    Returns:
        tuple: (train_df, val_df, test_df)
    """
    print("\n" + "="*80)
    print("TIME-BASED DATA SPLIT")
    print("="*80)
    
    # Ensure match_date is datetime
    df['match_date'] = pd.to_datetime(df['match_date'])
    
    # Split based on dates
    train_df = df[df['match_date'] < SPLIT_DATES['train_end']].copy()
    val_df = df[
        (df['match_date'] >= SPLIT_DATES['train_end']) & 
        (df['match_date'] < SPLIT_DATES['val_end'])
    ].copy()
    test_df = df[df['match_date'] >= SPLIT_DATES['val_end']].copy()
    
    print(f"\nTrain Set:")
    print(f"  Dates: {train_df['match_date'].min()} to {train_df['match_date'].max()}")
    print(f"  Matches: {len(train_df):,}")
    print(f"  Percentage: {len(train_df)/len(df)*100:.1f}%")
    
    print(f"\nValidation Set:")
    print(f"  Dates: {val_df['match_date'].min()} to {val_df['match_date'].max()}")
    print(f"  Matches: {len(val_df):,}")
    print(f"  Percentage: {len(val_df)/len(df)*100:.1f}%")
    
    print(f"\nTest Set:")
    print(f"  Dates: {test_df['match_date'].min()} to {test_df['match_date'].max()}")
    print(f"  Matches: {len(test_df):,}")
    print(f"  Percentage: {len(test_df)/len(df)*100:.1f}%")
    
    print(f"\n✓ No data leakage: Train < Val < Test (time-ordered)")
    
    return train_df, val_df, test_df

def temporal_cross_validate(df, target_col, model_type='random_forest'):
    """
    Perform walk-forward temporal cross-validation.
    
    This validates that models generalize across different time periods,
    not just the most recent validation set.
    
    Args:
        df (pd.DataFrame): Full dataset (already filtered by rolling window)
        target_col (str): Target column name
        model_type (str): Model type to validate
        
    Returns:
        dict: CV results with AUC scores per fold
    """
    from sklearn.metrics import roc_auc_score
    
    if not TEMPORAL_CV_CONFIG['enable']:
        return None
    
    print(f"\n{'='*80}")
    print(f"TEMPORAL CROSS-VALIDATION: {TARGETS[target_col]}")
    print(f"{'='*80}")
    
    df = df.sort_values('match_date').reset_index(drop=True)
    min_date = df['match_date'].min()
    max_date = df['match_date'].max()
    
    # Create temporal folds (expanding window)
    n_splits = TEMPORAL_CV_CONFIG['n_splits']
    fold_results = []
    
    print(f"\nWalk-Forward Validation Strategy:")
    print(f"  Total Data Range: {min_date.date()} to {max_date.date()}")
    print(f"  Number of Folds: {n_splits}")
    print(f"  Method: Expanding window (train on past, validate on future)\n")
    
    # Calculate date ranges for each fold
    date_range = (max_date - min_date).days
    fold_size_days = date_range // (n_splits + 1)  # +1 to leave room for test
    
    for fold in range(n_splits):
        # Train on all data up to fold boundary
        train_end_days = (fold + 1) * fold_size_days
        val_end_days = (fold + 2) * fold_size_days
        
        train_end = min_date + pd.Timedelta(days=train_end_days)
        val_end = min_date + pd.Timedelta(days=val_end_days)
        
        fold_train = df[df['match_date'] < train_end].copy()
        fold_val = df[(df['match_date'] >= train_end) & (df['match_date'] < val_end)].copy()
        
        if len(fold_train) < 100 or len(fold_val) < 20:
            continue  # Skip folds with insufficient data
        
        # Prepare features
        feature_cols = get_feature_columns(fold_train, target_col)
        X_train = fold_train[feature_cols].fillna(0)
        y_train = fold_train[target_col].values
        X_val = fold_val[feature_cols].fillna(0)
        y_val = fold_val[target_col].values
        
        # Train model
        model, scaler, _ = train_single_model(
            X_train, y_train, X_val, y_val, 
            model_type=model_type, target_col=target_col
        )
        
        # Make predictions
        if model_type == 'logistic' and scaler is not None:
            X_val_scaled = scaler.transform(X_val)
            y_pred_proba = model.predict_proba(X_val_scaled)[:, 1]
        else:
            y_pred_proba = model.predict_proba(X_val)[:, 1]
        
        # Calculate AUC
        auc = roc_auc_score(y_val, y_pred_proba)
        
        fold_results.append({
            'fold': fold + 1,
            'train_dates': f"{fold_train['match_date'].min().date()} to {fold_train['match_date'].max().date()}",
            'val_dates': f"{fold_val['match_date'].min().date()} to {fold_val['match_date'].max().date()}",
            'train_size': len(fold_train),
            'val_size': len(fold_val),
            'auc': auc
        })
        
        print(f"Fold {fold + 1}:")
        print(f"  Train: {fold_results[-1]['train_dates']} ({len(fold_train):,} matches)")
        print(f"  Val:   {fold_results[-1]['val_dates']} ({len(fold_val):,} matches)")
        print(f"  AUC:   {auc:.4f}")
    
    # Summary
    aucs = []  # Initialize before if statement to avoid "possibly unbound" error
    if fold_results:
        aucs = [r['auc'] for r in fold_results]
        print(f"\n{'='*80}")
        print(f"Temporal CV Summary:")
        print(f"  Mean AUC: {np.mean(aucs):.4f} ± {np.std(aucs):.4f}")
        print(f"  Min AUC:  {np.min(aucs):.4f}")
        print(f"  Max AUC:  {np.max(aucs):.4f}")
        print(f"  Consistency: {'GOOD' if np.std(aucs) < 0.10 else 'POOR (high variance)'}")
        print(f"{'='*80}")
    
    return {
        'target': target_col,
        'model_type': model_type,
        'n_folds': len(fold_results),
        'fold_results': fold_results,
        'mean_auc': np.mean(aucs) if aucs else None,
        'std_auc': np.std(aucs) if aucs else None
    }

# ============================================================================
# MODEL TRAINING
# ============================================================================

def train_single_model(X_train, y_train, X_val, y_val, model_type='logistic', target_col=None):
    """
    Train and calibrate a single model.
    
    Args:
        X_train: Training features
        y_train: Training labels
        X_val: Validation features
        y_val: Validation labels
        model_type: 'logistic' or 'random_forest'
        target_col: Target column name (for special handling)
        
    Returns:
        tuple: (calibrated_model, scaler or None, training_metrics)
    """
    scaler = None
    
    # Initialize model
    if model_type == 'logistic':
        # Logistic regression needs scaling
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_val_scaled = scaler.transform(X_val)
        
        model = LogisticRegression(**MODEL_CONFIGS['logistic'])
        model.fit(X_train_scaled, y_train)
        
        # Calibrate on validation set. FrozenEstimator keeps the model fitted on
        # the training set; without it sklearn refits a clone on validation data only.
        calibrated_model = CalibratedClassifierCV(
            FrozenEstimator(model),
            method='sigmoid'
        )
        calibrated_model.fit(X_val_scaled, y_val)
        
        # Get training metrics
        train_proba = model.predict_proba(X_train_scaled)[:, 1]
        val_proba = calibrated_model.predict_proba(X_val_scaled)[:, 1]
        
    else:  # random_forest
        # Use class_weight='balanced' for imbalanced targets (Draw)
        rf_config = MODEL_CONFIGS['random_forest'].copy()
        if target_col == 'target_draw':
            rf_config['class_weight'] = 'balanced'
            print("    ℹ️  Using class_weight='balanced' for imbalanced Draw target")
        
        model = RandomForestClassifier(**rf_config)
        model.fit(X_train, y_train)
        
        # Calibrate on validation set (see the logistic note above)
        calibrated_model = CalibratedClassifierCV(
            FrozenEstimator(model),
            method='isotonic'
        )
        calibrated_model.fit(X_val, y_val)
        
        # Get training metrics
        train_proba = model.predict_proba(X_train)[:, 1]
        val_proba = calibrated_model.predict_proba(X_val)[:, 1]
    
    # Calculate training metrics
    metrics = {
        'train_auc': roc_auc_score(y_train, train_proba),
        'val_auc': roc_auc_score(y_val, val_proba),
        'train_brier': brier_score_loss(y_train, train_proba),
        'val_brier': brier_score_loss(y_val, val_proba),
        'overfitting_gap': roc_auc_score(y_train, train_proba) - roc_auc_score(y_val, val_proba)
    }
    
    return calibrated_model, scaler, metrics

def train_all_models(train_df, val_df, model_types=['logistic', 'random_forest']):
    """
    Train all models for all targets.
    
    Args:
        train_df: Training dataframe
        val_df: Validation dataframe
        model_types: List of model types to train
        
    Returns:
        dict: Trained models and metadata
    """
    print("\n" + "="*80)
    print("MODEL TRAINING")
    print("="*80)
    
    results = {}
    
    for target_col, target_name in TARGETS.items():
        print(f"\n{'='*80}")
        print(f"Target: {target_name} ({target_col})")
        print(f"{'='*80}")
        
        # Check target distribution
        train_dist = train_df[target_col].value_counts()
        val_dist = val_df[target_col].value_counts()
        
        print(f"\nTarget Distribution:")
        print(f"  Train: {dict(train_dist)}")
        print(f"  Train %: Positive={train_df[target_col].mean()*100:.1f}%")
        print(f"  Val: {dict(val_dist)}")
        print(f"  Val %: Positive={val_df[target_col].mean()*100:.1f}%")
        
        # Get features
        feature_cols = get_feature_columns(train_df, target_col)
        
        print(f"\nFeatures: {len(feature_cols)} columns")
        
        # Prepare data
        X_train = train_df[feature_cols].fillna(0)
        y_train = train_df[target_col].astype(int)
        X_val = val_df[feature_cols].fillna(0)
        y_val = val_df[target_col].astype(int)
        
        results[target_col] = {
            'target_name': target_name,
            'feature_columns': feature_cols,
            'models': {}
        }
        
        # Train each model type
        for model_type in model_types:
            print(f"\n  Training: {model_type.replace('_', ' ').title()}")
            
            model, scaler, metrics = train_single_model(
                X_train, y_train, X_val, y_val, model_type, target_col
            )
            
            print(f"    Train AUC: {metrics['train_auc']:.4f}")
            print(f"    Val AUC:   {metrics['val_auc']:.4f}")
            print(f"    Train Brier: {metrics['train_brier']:.4f}")
            print(f"    Val Brier:   {metrics['val_brier']:.4f}")
            print(f"    Overfitting Gap: {metrics['overfitting_gap']:.4f}")
            
            if metrics['overfitting_gap'] > 0.10:
                print(f"    ⚠️  WARNING: Large overfitting gap detected!")
            
            results[target_col]['models'][model_type] = {
                'model': model,
                'scaler': scaler,
                'metrics': metrics
            }
    
    return results

# ============================================================================
# MODEL PERSISTENCE
# ============================================================================

def save_models(results, output_dir='models/saved'):
    """
    Save trained models to disk.
    
    Args:
        results: Dictionary of trained models
        output_dir: Directory to save models
    """
    print("\n" + "="*80)
    print("SAVING MODELS")
    print("="*80)
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for target_col, target_data in results.items():
        for model_type, model_data in target_data['models'].items():
            # Save model
            model_filename = f"{target_col}_{model_type}.pkl"
            model_path = os.path.join(output_dir, model_filename)
            joblib.dump(model_data['model'], model_path)
            print(f"✓ Saved: {model_filename}")
            
            # Save scaler if exists
            if model_data['scaler'] is not None:
                scaler_filename = f"{target_col}_{model_type}_scaler.pkl"
                scaler_path = os.path.join(output_dir, scaler_filename)
                joblib.dump(model_data['scaler'], scaler_path)
                print(f"✓ Saved: {scaler_filename}")
    
    # Save metadata
    metadata = {
        'timestamp': timestamp,
        'split_dates': SPLIT_DATES,
        'betting_thresholds': BETTING_THRESHOLDS,
        'targets': TARGETS,
        'model_configs': MODEL_CONFIGS
    }
    metadata_path = os.path.join(output_dir, f'training_metadata_{timestamp}.pkl')
    joblib.dump(metadata, metadata_path)
    print(f"✓ Saved: training_metadata_{timestamp}.pkl")
    
    print(f"\n✓ All models saved to: {output_dir}")

# ============================================================================
# TRAINING SUMMARY
# ============================================================================

def print_training_summary(results):
    """
    Print summary of training results.
    
    Args:
        results: Dictionary of training results
    """
    print("\n" + "="*80)
    print("TRAINING SUMMARY")
    print("="*80)
    
    summary_data = []
    
    for target_col, target_data in results.items():
        for model_type, model_data in target_data['models'].items():
            metrics = model_data['metrics']
            summary_data.append({
                'Target': target_data['target_name'],
                'Model': model_type.replace('_', ' ').title(),
                'Val AUC': f"{metrics['val_auc']:.4f}",
                'Val Brier': f"{metrics['val_brier']:.4f}",
                'Overfit Gap': f"{metrics['overfitting_gap']:.4f}"
            })
    
    summary_df = pd.DataFrame(summary_data)
    print("\n" + summary_df.to_string(index=False))
    
    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print("\n1. Review validation metrics above")
    print("2. Run evaluation script: python scripts/evaluate_models.py")
    print("3. Check test set performance and betting metrics")
    print("4. Select best model for each target")
    print("\nSuccess Criteria:")
    print("  ✓ Val AUC ≥ 0.62 (good), ≥ 0.68 (excellent)")
    print("  ✓ Val Brier < 0.24 (good calibration)")
    print("  ✓ Overfitting Gap < 0.10 (good generalization)")
    print("="*80)

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Train football prediction models')
    parser.add_argument(
        '--targets',
        nargs='+',
        default=list(TARGETS.keys()),
        choices=list(TARGETS.keys()),
        help='Which targets to train (default: all)'
    )
    parser.add_argument(
        '--models',
        nargs='+',
        default=['logistic'],
        choices=['logistic', 'random_forest'],
        help='Which models to train (default: logistic only)'
    )
    parser.add_argument(
        '--skip-cv',
        action='store_true',
        help='Skip temporal cross-validation (faster training)'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("FOOTBALL MATCH PREDICTION - MODEL TRAINING")
    print("="*80)
    print(f"\nStart Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Targets: {', '.join([TARGETS[t] for t in args.targets])}")
    print(f"Models: {', '.join(args.models)}")
    print(f"Betting Threshold: {BETTING_THRESHOLDS['min_probability']*100:.0f}% probability")
    print(f"Value Edge Required: {BETTING_THRESHOLDS['min_value_edge']*100:.0f}%")
    
    try:
        # Load data (with all features already created in dbt)
        df = load_training_data()
        
        # Final data preparation
        df = prepare_data_for_training(df)
        
        # Split data
        train_df, val_df, test_df = split_data(df)
        
        # Run temporal cross-validation (if enabled and not skipped)
        cv_results = []
        if TEMPORAL_CV_CONFIG['enable'] and not args.skip_cv:
            print(f"\n{'='*80}")
            print("RUNNING TEMPORAL CROSS-VALIDATION")
            print(f"{'='*80}")
            print("This validates model performance across different time periods...")
            print("(Use --skip-cv flag to skip this step for faster training)\n")
            
            # Run CV for Over 2.5 and BTTS (the problematic targets)
            for target in ['target_over_25', 'target_btts_yes']:
                if target in args.targets:
                    cv_result = temporal_cross_validate(df, target, model_type='logistic')
                    if cv_result:
                        cv_results.append(cv_result)
            
            # Print CV summary
            if cv_results:
                print(f"\n{'='*80}")
                print("TEMPORAL CV SUMMARY - OVERFITTING CHECK")
                print(f"{'='*80}")
                for cv_res in cv_results:
                    target_name = TARGETS[cv_res['target']]
                    print(f"\n{target_name}:")
                    print(f"  Temporal CV AUC: {cv_res['mean_auc']:.4f} ± {cv_res['std_auc']:.4f}")
                    print(f"  Generalization: {'✓ GOOD' if cv_res['std_auc'] < 0.10 else '⚠ POOR (high variance)'}")
                print(f"{'='*80}\n")
        
        # Train models
        results = train_all_models(train_df, val_df, model_types=args.models)
        
        # Save models
        save_models(results)
        
        # Print summary
        print_training_summary(results)
        
        print(f"\n{'='*80}")
        print(f"✓ Training completed successfully!")
        print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")
        
        return 0
        
    except Exception as e:
        print(f"\n{'='*80}")
        print(f"❌ ERROR: Training failed!")
        print(f"{'='*80}")
        print(f"\n{str(e)}\n")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
