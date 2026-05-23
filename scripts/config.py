#!/usr/bin/env python3
"""
Centralized Configuration Management

Loads all configuration from environment variables (.env file).
This provides:
- Security: No hardcoded credentials in code
- Scalability: Easy to change config without editing code
- Debugging: Clear error messages when config is missing

Usage:
    from config import DB_CONFIG, RETRAIN_THRESHOLD, BETTING_THRESHOLDS
    
    engine = create_engine(get_db_connection_string())
    
Author: Football Prediction System
Date: 2026-05-22
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
# Search for .env in project root
env_path = Path(__file__).parent.parent / '.env'

if env_path.exists():
    load_dotenv(env_path)
else:
    print(f"⚠️  Warning: .env file not found at {env_path}")
    print(f"   Create .env from .env.example and fill in your credentials")
    print(f"   Continuing with environment variables if available...")

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

def get_env_var(key, default=None, required=True):
    """
    Get environment variable with validation.
    
    Args:
        key: Environment variable name
        default: Default value if not found
        required: If True, raise error if missing
        
    Returns:
        str: Environment variable value
        
    Raises:
        ValueError: If required variable is missing
    """
    value = os.getenv(key, default)
    
    if required and value is None:
        raise ValueError(
            f"Missing required environment variable: {key}\n"
            f"Create a .env file from .env.example and set {key}"
        )
    
    return value

# Database configuration
DB_CONFIG = {
    'host': get_env_var('DB_HOST', 'localhost', required=False),
    'port': int(get_env_var('DB_PORT', '5432', required=False)),
    'database': get_env_var('DB_NAME', 'football_prediction_db', required=False),
    'user': get_env_var('DB_USER', 'postgres', required=False),
    'password': get_env_var('DB_PASSWORD', required=True)  # Always required
}

def get_db_connection_string():
    """
    Get PostgreSQL connection string for SQLAlchemy.
    
    Returns:
        str: Database connection string
    """
    return (
        f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
        f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )

# ============================================================================
# MODEL CONFIGURATION
# ============================================================================

# Retraining threshold (minimum new matches before retraining)
RETRAIN_THRESHOLD = int(get_env_var('RETRAIN_THRESHOLD', '20', required=False))

# Model performance tolerance (0.98 = allow 2% degradation)
PERFORMANCE_TOLERANCE = float(get_env_var('PERFORMANCE_TOLERANCE', '0.98', required=False))

# Time-based data splits
SPLIT_DATES = {
    'train_end': '2023-07-01',
    'val_end': '2024-07-01'
}

# Rolling window training (use only recent data to handle concept drift)
# Football tactics evolve: training on 2018-2020 data is outdated for 2026
ROLLING_WINDOW_START_DATE = '2021-07-01'  # Only use last ~3 seasons

# Time-based cross-validation configuration
TEMPORAL_CV_CONFIG = {
    'enable': True,  # Set to True to use walk-forward validation
    'n_splits': 4,   # Number of temporal folds (e.g., 2021, 2022, 2023, 2024)
    'min_train_months': 12  # Minimum 12 months of training data per fold
}

# Model configurations
MODEL_CONFIGS = {
    'logistic': {
        'penalty': 'l2',
        'C': 1.0,
        'class_weight': 'balanced',
        'max_iter': 1000,
        'random_state': 42
    },
    'random_forest': {
        'n_estimators': 100,
        'max_depth': 10,
        'min_samples_split': 20,
        'min_samples_leaf': 10,
        'class_weight': 'balanced',
        'random_state': 42,
        'n_jobs': -1
    }
}

# ============================================================================
# BETTING CONFIGURATION
# ============================================================================

BETTING_THRESHOLDS = {
    'min_probability': float(get_env_var('MIN_PROBABILITY', '0.70', required=False)),
    'min_value_edge': float(get_env_var('MIN_VALUE_EDGE', '0.05', required=False)),
    'min_odds': float(get_env_var('MIN_ODDS', '1.50', required=False)),
    'max_odds': float(get_env_var('MAX_ODDS', '3.00', required=False))
}

# ============================================================================
# PREDICTION TARGETS
# ============================================================================

# Targets WITH odds (can generate betting recommendations)
TARGETS = {
    # Over/Under Goals
    'target_over_25': 'Over 2.5 Goals',
    
    # Match Result (3-way)
    'target_home_win': 'Home Win',
    'target_draw': 'Draw',
    'target_away_win': 'Away Win',
    
    # Double Chance (combined)
    'target_home_win_or_draw': 'Home Win or Draw (1X)',
    'target_away_win_or_draw': 'Away Win or Draw (X2)',
    
    # BTTS (prediction only - NO odds available from API)
    'target_btts_yes': 'Both Teams To Score (Prediction Only)'
}

TARGET_NAMES = TARGETS  # Alias for compatibility

# ============================================================================
# PATHS
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
RAW_DATA_DIR = DATA_DIR / 'raw'
MODELS_DIR = PROJECT_ROOT / 'models' / 'saved'
LOGS_DIR = PROJECT_ROOT / 'logs'
DBT_PROJECT_DIR = PROJECT_ROOT / 'football_prediction'

# Create directories if they don't exist
LOGS_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# VALIDATION
# ============================================================================

def validate_config():
    """
    Validate all configuration is properly loaded.
    
    Raises:
        ValueError: If any required configuration is invalid
    """
    # Check database password is set
    if not DB_CONFIG['password']:
        raise ValueError("Database password not set. Check .env file.")
    
    # Check thresholds are valid
    if RETRAIN_THRESHOLD < 1:
        raise ValueError(f"RETRAIN_THRESHOLD must be >= 1, got {RETRAIN_THRESHOLD}")
    
    if not 0 < PERFORMANCE_TOLERANCE <= 1:
        raise ValueError(f"PERFORMANCE_TOLERANCE must be 0-1, got {PERFORMANCE_TOLERANCE}")
    
    if not 0 < BETTING_THRESHOLDS['min_probability'] <= 1:
        raise ValueError(f"MIN_PROBABILITY must be 0-1, got {BETTING_THRESHOLDS['min_probability']}")
    
    print("✓ Configuration validated successfully")

# Run validation on import (optional - comment out if too verbose)
# validate_config()

if __name__ == '__main__':
    """Test configuration loading."""
    print("="*80)
    print("CONFIGURATION TEST")
    print("="*80)
    
    print(f"\nDatabase: {DB_CONFIG['database']}")
    print(f"Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"User: {DB_CONFIG['user']}")
    print(f"Password: {'*' * len(DB_CONFIG['password'])}")
    
    print(f"\nRetrain Threshold: {RETRAIN_THRESHOLD} matches")
    print(f"Performance Tolerance: {PERFORMANCE_TOLERANCE}")
    
    print(f"\nBetting Thresholds:")
    for key, value in BETTING_THRESHOLDS.items():
        print(f"  {key}: {value}")
    
    print(f"\nPaths:")
    print(f"  Project Root: {PROJECT_ROOT}")
    print(f"  Models: {MODELS_DIR}")
    print(f"  Logs: {LOGS_DIR}")
    
    print("\n" + "="*80)
    validate_config()
    print("="*80)
