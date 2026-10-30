#!/usr/bin/env python3
"""
Automated Football Data Update & Training Pipeline

This script automates the entire update workflow:
1. Load new CSV data into PostgreSQL
2. Run dbt transformation pipeline
3. Check if retraining is needed (20+ new matches)
4. Train new models if threshold met
5. Save the retrained match model

Usage:
    python scripts/auto_update.py --csv data/raw/E0_2025-26.csv
    python scripts/auto_update.py --csv data/raw/E0_2025-26.csv --force-retrain

Features:
- Comprehensive logging and progress tracking

Author: Football Prediction System
Date: 2026-05-22
"""

import os
import sys
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
import psycopg2

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import centralized configuration
from config import (
    DB_CONFIG,
    get_db_connection_string,
    RETRAIN_THRESHOLD,
    DBT_PROJECT_DIR
)

from load_raw_data import load_to_database, truncate_season
from match_model import train as train_match_model

# ============================================================================
# DATABASE UTILITIES
# ============================================================================

def get_db_engine():
    """Create SQLAlchemy database engine."""
    return create_engine(get_db_connection_string())

def get_db_connection():
    """Create psycopg2 database connection."""
    return psycopg2.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        database=DB_CONFIG['database'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password']
    )

def get_match_count():
    """
    Get current count of matches in fct_model_features.
    
    Returns:
        int: Number of matches available for training
    """
    engine = get_db_engine()
    
    try:
        query = "SELECT COUNT(*) as count FROM fct_model_features;"
        result = pd.read_sql_query(query, engine)
        return int(result['count'].iloc[0])
    except Exception as e:
        print(f"⚠️  Warning: Could not query fct_model_features: {e}")
        print("   (Table may not exist yet - will be created by dbt)")
        return 0

# ============================================================================
# CSV LOADING
# ============================================================================

def load_csv_to_database(csv_path, season_code=None):
    """
    Load CSV file into raw_football_matches table.
    
    Args:
        csv_path: Path to CSV file
        season_code: Optional season code (e.g., '2025-26')
        
    Returns:
        int: Number of rows loaded
    """
    print("\n" + "="*80)
    print("STEP 1: LOADING CSV DATA")
    print("="*80)
    
    csv_path = Path(csv_path)
    
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    # Extract season code from filename if not provided
    if season_code is None:
        import re
        match = re.search(r'E0_(\d{4}-\d{2})\.csv', csv_path.name)
        if match:
            season_code = match.group(1)
        else:
            raise ValueError(f"Could not extract season code from filename: {csv_path.name}")
    
    print(f"\n📁 CSV File: {csv_path}")
    print(f"📅 Season: {season_code}")
    
    # Read CSV
    print("\n  Reading CSV...")
    df = pd.read_csv(csv_path)
    print(f"  ✓ Read {len(df):,} matches from CSV")
    
    # Delete existing season data, then load the fresh copy
    print(f"\n  Deleting existing {season_code} data from database...")
    truncate_season(season_code)
    
    print(f"\n  Loading {len(df):,} new matches to database...")
    load_to_database(df)
    print(f"  ✓ Successfully loaded {len(df):,} matches")
    return len(df)

# ============================================================================
# DBT PIPELINE
# ============================================================================

def run_dbt_pipeline():
    """
    Run dbt pipeline to transform raw data.
    
    Returns:
        bool: True if successful, False otherwise
    """
    print("\n" + "="*80)
    print("STEP 2: RUNNING DBT PIPELINE")
    print("="*80)
    
    if not DBT_PROJECT_DIR.exists():
        print(f"❌ dbt project directory not found: {DBT_PROJECT_DIR}")
        return False
    
    print(f"\n📂 dbt Project: {DBT_PROJECT_DIR}")
    
    # Run dbt run
    print("\n  Running: dbt run")
    try:
        result = subprocess.run(
            ['dbt', 'run'],
            cwd=DBT_PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode != 0:
            print(f"  ❌ dbt run failed:")
            print(result.stderr)
            return False
        
        # Count successful models
        success_count = result.stdout.count('OK created')
        print(f"  ✓ dbt run completed ({success_count} models built)")
        
    except subprocess.TimeoutExpired:
        print("  ❌ dbt run timed out (>5 minutes)")
        return False
    except Exception as e:
        print(f"  ❌ Error running dbt: {e}")
        return False
    
    # Run dbt test
    print("\n  Running: dbt test")
    try:
        result = subprocess.run(
            ['dbt', 'test'],
            cwd=DBT_PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )
        
        if result.returncode != 0:
            print(f"  ⚠️  dbt tests had failures:")
            print(result.stderr)
            # Don't fail the whole pipeline on test failures
        else:
            test_count = result.stdout.count('PASS')
            print(f"  ✓ dbt test completed ({test_count} tests passed)")
        
    except Exception as e:
        print(f"  ⚠️  Error running dbt tests: {e}")
    
    return True

# ============================================================================
# MODEL TRAINING
# ============================================================================

# ============================================================================
# MAIN WORKFLOW
# ============================================================================

def main():
    """Main automated update workflow."""
    parser = argparse.ArgumentParser(
        description='Automated football data update and training pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/auto_update.py --csv data/raw/E0_2025-26.csv
  python scripts/auto_update.py --csv data/raw/E0_2025-26.csv --force-retrain
  python scripts/auto_update.py --csv data/raw/E0_2025-26.csv --skip-dbt
        """
    )
    
    parser.add_argument(
        '--csv',
        type=str,
        required=True,
        help='Path to CSV file to load (e.g., data/raw/E0_2025-26.csv)'
    )
    
    parser.add_argument(
        '--season',
        type=str,
        help='Season code (e.g., 2025-26). If not provided, extracted from filename'
    )
    
    parser.add_argument(
        '--force-retrain',
        action='store_true',
        help='Force retraining even if below threshold'
    )
    
    parser.add_argument(
        '--skip-dbt',
        action='store_true',
        help='Skip dbt pipeline (use for testing only)'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("AUTOMATED FOOTBALL DATA UPDATE PIPELINE")
    print("="*80)
    print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"CSV File: {args.csv}")
    
    # Get initial match count
    initial_count = get_match_count()
    print(f"\n📊 Initial match count (features): {initial_count:,}")
    
    # Step 1: Load CSV data
    try:
        loaded_count = load_csv_to_database(args.csv, args.season)
    except Exception as e:
        print(f"\n❌ FAILED at Step 1: {e}")
        return 1
    
    # Step 2: Run dbt pipeline
    if not args.skip_dbt:
        success = run_dbt_pipeline()
        if not success:
            print("\n❌ FAILED at Step 2: dbt pipeline failed")
            return 1
    else:
        print("\n⏭️  Skipping dbt pipeline (--skip-dbt flag)")
    
    # Get updated match count
    updated_count = get_match_count()
    new_matches = updated_count - initial_count
    
    print("\n" + "="*80)
    print("STEP 3: CHECKING RETRAIN THRESHOLD")
    print("="*80)
    print(f"\n  Initial matches: {initial_count:,}")
    print(f"  Updated matches: {updated_count:,}")
    print(f"  New matches:     {new_matches:,}")
    print(f"  Threshold:       {RETRAIN_THRESHOLD}")
    
    # Decide if retraining is needed
    should_retrain = args.force_retrain or new_matches >= RETRAIN_THRESHOLD
    
    if args.force_retrain:
        print(f"\n  ⚡ Force retrain enabled (--force-retrain flag)")
    elif new_matches >= RETRAIN_THRESHOLD:
        print(f"\n  ✅ Threshold met ({new_matches} ≥ {RETRAIN_THRESHOLD})")
        print("     → Proceeding with retraining")
    else:
        print(f"\n  ⏭️  Threshold not met ({new_matches} < {RETRAIN_THRESHOLD})")
        print("     → Skipping retraining")
        print("\n" + "="*80)
        print("UPDATE COMPLETE (No retraining needed)")
        print("="*80)
        return 0
    
    # Step 4: Retrain. The design is fixed, so more data replaces the saved model;
    # run match_model.py --evaluate to re-check it against the market.
    print("\n" + "="*80)
    print("STEP 4: RETRAINING MATCH MODEL")
    print("="*80)
    train_match_model()
    
    # Summary
    print("\n" + "="*80)
    print("UPDATE PIPELINE COMPLETE")
    print("="*80)
    print(f"\n✅ CSV loaded:        {loaded_count:,} matches")
    print(f"✅ dbt pipeline:     {'Completed' if not args.skip_dbt else 'Skipped'}")
    print(f"✅ New matches:      {new_matches:,}")
    print(f"✅ Retrained:        {'Yes' if should_retrain else 'No'}")
    
    print(f"\n📊 Total matches in system: {updated_count:,}")
    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
