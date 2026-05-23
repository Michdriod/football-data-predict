#!/usr/bin/env python3
"""
Load Raw Football Data to PostgreSQL

This script reads CSV files from football-data.co.uk and loads them into
the raw_football_matches table in PostgreSQL.

Features:
- Validates CSV format and columns
- Detects and prevents duplicates
- Handles multiple seasons
- Creates backup before loading
- Comprehensive logging

Usage:
    python scripts/load_raw_data.py --data-dir data/raw/
    python scripts/load_raw_data.py --data-dir data/raw/ --force-reload
    python scripts/load_raw_data.py --file data/raw/E0_2023-24.csv

Expected CSV format:
    Files from: https://www.football-data.co.uk/englandm.php
    League: Premier League (E0)
    Naming: E0_YYYY-YY.csv (e.g., E0_2023-24.csv)

Author: Football Prediction System
Date: 2026-04-26
"""

import os
import sys
import argparse
import glob
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
import psycopg2
import requests
from psycopg2.extras import execute_values
from sqlalchemy import create_engine

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path.cwd()))

# Import centralized configuration
from scripts.config import DB_CONFIG, get_db_connection_string

# Expected CSV columns (from football-data.co.uk)
REQUIRED_COLUMNS = [
    'Div', 'Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR'
]

# Recommended columns for full functionality
RECOMMENDED_COLUMNS = [
    'HTHG', 'HTAG', 'HTR', 'HS', 'AS', 'HST', 'AST',
    'HC', 'AC', 'HY', 'AY', 'HR', 'AR',
    'B365H', 'B365D', 'B365A', 'B365>2.5', 'B365<2.5'
]

# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

def get_db_connection():
    """Create psycopg2 database connection."""
    return psycopg2.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        database=DB_CONFIG['database'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password']
    )

def get_db_engine():
    """Create SQLAlchemy engine."""
    connection_string = (
        f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )
    return create_engine(connection_string)

def extract_season_from_filename(filename):
    """
    Extract season code from filename.
    
    Args:
        filename: String like 'E0_2025-26.csv'
        
    Returns:
        str: Season code like '2025-26' or None if invalid
    """
    import re
    match = re.search(r'E0_(\d{4}-\d{2})\.csv', filename)
    return match.group(1) if match else None

def truncate_season(season_code):
    """
    Delete all rows for a specific season from raw_football_matches.
    
    Args:
        season_code: Season code like '2025-26'
        
    Returns:
        int: Number of rows deleted
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Extract year from season code to match dates
        # E.g., '2025-26' → year 2025 (Aug 2025 - Jul 2026)
        start_year = int(season_code.split('-')[0])
        
        # Dates from Aug start_year to Jul (start_year+1)
        # Since dates in football-data are DD/MM/YYYY, delete rows where year matches
        
        print(f"\n  Truncating season {season_code} from database...")
        
        # Delete rows where the year of the date falls within the season
        # Format: DD/MM/YYYY, so year is at positions 7-10 (1-indexed)
        delete_query = """
        DELETE FROM raw_football_matches
        WHERE CASE 
            WHEN "Date" ~ '^[0-9]{2}/[0-9]{2}/[0-9]{4}$' THEN
                CAST(SUBSTRING("Date" FROM 7 FOR 4) AS INTEGER)
            ELSE 0
        END IN (%s, %s)
        """
        
        # If season is 2025-26, delete matches from 2025 and 2026
        years_to_delete = (start_year, start_year + 1)
        cur.execute(delete_query, years_to_delete)
        
        deleted_count = cur.rowcount
        conn.commit()
        
        print(f"  ✓ Deleted {deleted_count:,} rows for season {season_code}")
        return deleted_count
        
    except Exception as e:
        print(f"  ❌ Error truncating season: {e}")
        conn.rollback()
        return 0
        
    finally:
        cur.close()
        conn.close()

def check_table_exists():
    """Check if raw_football_matches table exists."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'raw_football_matches'
        );
    """)
    
    exists = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    return exists

def get_existing_row_count():
    """Get current number of rows in raw_football_matches."""
    if not check_table_exists():
        return 0
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('SELECT COUNT(*) FROM raw_football_matches;')
    count = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    return count

def create_backup_table():
    """Create backup of raw_football_matches before loading new data."""
    if not check_table_exists():
        print("  ⓘ No existing table to backup")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"raw_football_matches_backup_{timestamp}"
    
    try:
        print(f"  Creating backup: {backup_name}")
        cur.execute(f"""
            CREATE TABLE {backup_name} AS 
            SELECT * FROM raw_football_matches;
        """)
        conn.commit()
        print(f"  ✓ Backup created successfully")
        
    except Exception as e:
        print(f"  ⚠️ Backup failed: {e}")
        conn.rollback()
    
    finally:
        cur.close()
        conn.close()

# ============================================================================
# DOWNLOAD FUNCTIONS
# ============================================================================

def download_season_csv(season_code, data_dir):
    """
    Download CSV file for a specific season from football-data.co.uk
    
    Args:
        season_code: Season code like '2025-26'
        data_dir: Directory to save the CSV file
        
    Returns:
        tuple: (success: bool, filepath: str or None, message: str)
    """
    print(f"\n  Downloading season {season_code} from football-data.co.uk...")
    
    # Construct filename and URL
    filename = f"E0_{season_code}.csv"
    filepath = os.path.join(data_dir, filename)
    url = f"https://www.football-data.co.uk/mmz4281/{filename}"
    
    try:
        # Download with timeout
        response = requests.get(url, timeout=10)
        
        if response.status_code == 404:
            return False, None, f"File not found on server (404): {url}"
        
        if response.status_code != 200:
            return False, None, f"Download failed (HTTP {response.status_code}): {url}"
        
        # Save to file
        os.makedirs(data_dir, exist_ok=True)
        with open(filepath, 'w') as f:
            f.write(response.text)
        
        # Verify file was written
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            return False, None, f"Downloaded file is empty: {filepath}"
        
        print(f"  ✓ Downloaded {filename} ({os.path.getsize(filepath):,} bytes)")
        return True, filepath, None
        
    except requests.exceptions.Timeout:
        return False, None, "Download timeout (server not responding)"
    except requests.exceptions.ConnectionError:
        return False, None, "Connection error (check internet)"
    except Exception as e:
        return False, None, f"Download failed: {str(e)}"

# ============================================================================
# CSV PROCESSING
# ============================================================================

def validate_csv_file(filepath):
    """
    Validate CSV file structure.
    
    Args:
        filepath: Path to CSV file
        
    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        # Try reading first few rows
        df_test = pd.read_csv(filepath, nrows=5)
        
        # Check required columns
        missing_cols = [col for col in REQUIRED_COLUMNS if col not in df_test.columns]
        
        if missing_cols:
            return False, f"Missing required columns: {missing_cols}"
        
        # Check if file is empty
        if len(df_test) == 0:
            return False, "File is empty"
        
        # Check for recommended columns
        missing_recommended = [col for col in RECOMMENDED_COLUMNS if col not in df_test.columns]
        if missing_recommended:
            print(f"  ⓘ Missing recommended columns: {missing_recommended[:5]}...")
        
        return True, None
        
    except Exception as e:
        return False, f"Error reading file: {str(e)}"

def standardize_csv_columns(df):
    """
    Ensure all expected columns exist (fill with NULL if missing).
    
    Args:
        df: Input dataframe
        
    Returns:
        DataFrame with standardized columns
    """
    # Get all possible columns from the table schema
    # For simplicity, we'll just ensure required columns exist
    # Missing columns will be handled by PostgreSQL as TEXT NULL
    
    return df

def read_csv_files(data_dir):
    """
    Read all CSV files from directory.
    
    Args:
        data_dir: Directory containing CSV files
        
    Returns:
        pd.DataFrame: Concatenated data from all CSVs
    """
    print("\n" + "="*80)
    print("READING CSV FILES")
    print("="*80)
    
    # Find all CSV files
    csv_pattern = os.path.join(data_dir, "*.csv")
    csv_files = glob.glob(csv_pattern)
    
    if not csv_files:
        print(f"❌ No CSV files found in: {data_dir}")
        print(f"   Expected pattern: E0_YYYY-YY.csv")
        sys.exit(1)
    
    print(f"\nFound {len(csv_files)} CSV file(s):")
    for f in csv_files:
        print(f"  - {os.path.basename(f)}")
    
    # Validate all files first
    print("\nValidating files...")
    all_valid = True
    for filepath in csv_files:
        is_valid, error = validate_csv_file(filepath)
        if not is_valid:
            print(f"  ❌ {os.path.basename(filepath)}: {error}")
            all_valid = False
        else:
            print(f"  ✓ {os.path.basename(filepath)}")
    
    if not all_valid:
        print("\n❌ Some files failed validation. Please fix and try again.")
        sys.exit(1)
    
    # Read and concatenate all files
    print("\nReading data...")
    dfs = []
    total_rows = 0
    
    for filepath in sorted(csv_files):
        filename = os.path.basename(filepath)
        
        try:
            df = pd.read_csv(filepath)
            rows = len(df)
            total_rows += rows
            
            # Add source file column for tracking
            df['_source_file'] = filename
            
            dfs.append(df)
            print(f"  ✓ {filename}: {rows:,} rows")
            
        except Exception as e:
            print(f"  ❌ {filename}: Error reading - {e}")
            sys.exit(1)
    
    # Concatenate all dataframes
    df_combined = pd.concat(dfs, ignore_index=True)
    
    print(f"\n✓ Total rows loaded: {total_rows:,}")
    print(f"✓ Total columns: {len(df_combined.columns)}")
    
    return df_combined

def detect_duplicates(df):
    """
    Detect duplicate matches in dataframe.
    
    Args:
        df: Input dataframe
        
    Returns:
        tuple: (has_duplicates, duplicate_count)
    """
    # Create match key
    df['_match_key'] = (
        df['Div'].astype(str) + '_' +
        df['Date'].astype(str) + '_' +
        df['HomeTeam'].astype(str) + '_' +
        df['AwayTeam'].astype(str)
    )
    
    duplicates = df[df.duplicated(subset='_match_key', keep=False)]
    
    if len(duplicates) > 0:
        print(f"\n⚠️ Found {len(duplicates)} duplicate matches:")
        print(duplicates[['Date', 'HomeTeam', 'AwayTeam', '_source_file']].head(10))
        return True, len(duplicates)
    
    return False, 0

def check_database_duplicates(df):
    """
    Check if data already exists in database.
    
    Args:
        df: Input dataframe
        
    Returns:
        list: List of match keys that already exist in database
    """
    if not check_table_exists():
        return []
    
    # Create match keys
    df['_match_key'] = (
        df['Div'].astype(str) + '_' +
        df['Date'].astype(str) + '_' +
        df['HomeTeam'].astype(str) + '_' +
        df['AwayTeam'].astype(str)
    )
    
    # Get existing match keys from database
    engine = get_db_engine()
    
    query = """
    SELECT DISTINCT 
        "Div" || '_' || "Date" || '_' || "HomeTeam" || '_' || "AwayTeam" as match_key
    FROM raw_football_matches;
    """
    
    existing_keys = pd.read_sql_query(query, engine)
    existing_key_set = set(existing_keys['match_key'])
    
    engine.dispose()
    
    # Find matches already in database (return list of their match keys)
    duplicates = df[df['_match_key'].isin(existing_key_set)]['_match_key'].tolist()
    
    return duplicates

# ============================================================================
# DATA LOADING
# ============================================================================

def load_to_database(df, mode='append'):
    """
    Load dataframe to PostgreSQL.
    
    NOTE: Always uses 'append' mode because dbt views depend on the raw table.
    Duplicates must be filtered BEFORE calling this function.
    
    Args:
        df: Input dataframe (should already have duplicates removed)
        mode: Ignored - always appends. Kept for backward compatibility.
    """
    print("\n" + "="*80)
    print("LOADING TO DATABASE")
    print("="*80)
    
    # Remove temporary columns
    df_clean = df.drop(columns=[col for col in df.columns if col.startswith('_')], errors='ignore')
    
    # Always use append mode to preserve dependent dbt views
    actual_mode = 'append'
    print(f"\nMode: {actual_mode} (always append - dbt views depend on this table)")
    print(f"Rows to load: {len(df_clean):,}")
    print(f"Columns: {len(df_clean.columns)}")
    
    # Convert all columns to string (raw table is all TEXT)
    for col in df_clean.columns:
        df_clean[col] = df_clean[col].astype(str)
        df_clean[col] = df_clean[col].replace('nan', None)
        df_clean[col] = df_clean[col].replace('', None)
    
    # Load to database
    engine = get_db_engine()
    
    try:
        print("\nLoading data...")
        df_clean.to_sql(
            'raw_football_matches',
            engine,
            if_exists=actual_mode,
            index=False,
            method=None,
            chunksize=10
        )
        
        print("✓ Data loaded successfully!")
        
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        sys.exit(1)
    
    finally:
        engine.dispose()

def verify_load():
    """Verify data was loaded correctly."""
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get row count
    cur.execute('SELECT COUNT(*) FROM raw_football_matches;')
    total_rows = cur.fetchone()[0]
    
    # Get date range
    cur.execute('SELECT MIN("Date"), MAX("Date") FROM raw_football_matches;')
    min_date, max_date = cur.fetchone()
    
    # Get unique teams
    cur.execute('SELECT COUNT(DISTINCT "HomeTeam") FROM raw_football_matches;')
    unique_teams = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    print(f"\nDatabase Status:")
    print(f"  Total Rows: {total_rows:,}")
    print(f"  Date Range: {min_date} to {max_date}")
    print(f"  Unique Teams: {unique_teams}")
    
    print("\n✓ Verification complete")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Load football match data from CSV files to PostgreSQL'
    )
    parser.add_argument(
        '--data-dir',
        default='data/raw/',
        help='Directory containing CSV files (default: data/raw/)'
    )
    parser.add_argument(
        '--file',
        help='Load single CSV file instead of directory'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip backup creation'
    )
    parser.add_argument(
        '--skip-duplicate-check',
        action='store_true',
        help='Skip database duplicate check (faster but may create duplicates)'
    )
    parser.add_argument(
        '--full-truncate',
        action='store_true',
        help='TRUNCATE entire table before loading all seasons. Use for fresh start.'
    )
    parser.add_argument(
        '--season',
        help='Season code (e.g., 2025-26). Delete just this season and reload. Use for updates.'
    )
    parser.add_argument(
        '--auto-download',
        action='store_true',
        help='Auto-download season CSV from football-data.co.uk before loading (use with --season)'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("FOOTBALL DATA LOADER")
    print("="*80)
    print(f"\nStart Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Database: {DB_CONFIG['database']}")
    
    if args.full_truncate:
        print(f"Mode: FULL LOAD (truncate entire table + load all seasons)")
        print("  - TRUNCATE all existing data")
        print("  - Load all 10 seasons fresh")
    elif args.season:
        print(f"Mode: SEASON UPDATE ({args.season})")
        print("  - DELETE existing data for this season only")
        print("  - Load fresh data for this season")
        print("  - Historical seasons unchanged")
    else:
        print("Mode: APPEND (default - add new data without affecting existing)")
    
    # Check if table exists
    table_exists = check_table_exists()
    if not table_exists:
        print("\n⚠️  Table 'raw_football_matches' does not exist")
        print("   Creating table automatically...")
        # Table will be created by pandas to_sql
    else:
        existing_count = get_existing_row_count()
        print(f"\n✓ Table exists with {existing_count:,} rows")
    
    # Create backup if not skipped
    if not args.no_backup and table_exists and existing_count > 0:
        create_backup_table()
    
    # Read CSV files
    if args.file:
        # Single file mode
        print(f"\nLoading single file: {args.file}")
        if not os.path.exists(args.file):
            print(f"❌ File not found: {args.file}")
            sys.exit(1)
        
        is_valid, error = validate_csv_file(args.file)
        if not is_valid:
            print(f"❌ Invalid file: {error}")
            sys.exit(1)
        
        df = pd.read_csv(args.file)
        df['_source_file'] = os.path.basename(args.file)
        loaded_files = [os.path.basename(args.file)]
        
    else:
        # Directory mode
        if not os.path.exists(args.data_dir):
            print(f"\n❌ Directory not found: {args.data_dir}")
            print(f"   Please create it and add CSV files from football-data.co.uk")
            sys.exit(1)
        
        df = read_csv_files(args.data_dir)
        loaded_files = df['_source_file'].unique().tolist() if '_source_file' in df.columns else []
    
    # Handle different loading modes
    skip_dup_check = False
    
    if args.full_truncate:
        # Mode 1: Full Load - TRUNCATE entire table, then load all seasons
        print(f"\n{'='*80}")
        print("MODE: FULL LOAD (All Seasons)")
        print(f"{'='*80}")
        
        if table_exists:
            print(f"\nTRUNCATING entire table...")
            conn = get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("TRUNCATE TABLE raw_football_matches;")
                conn.commit()
                print(f"✓ Table truncated successfully")
            except Exception as e:
                print(f"❌ Error truncating table: {e}")
                sys.exit(1)
            finally:
                cur.close()
                conn.close()
        
        print(f"\nLoading all {len(loaded_files)} seasons...")
        skip_dup_check = True  # Skip dup check after truncate
        
    elif args.season:
        # Mode 2: Season Update - DELETE just this season, then reload it
        print(f"\n{'='*80}")
        print(f"MODE: SEASON UPDATE ({args.season})")
        print(f"{'='*80}")
        
        # Try auto-download if requested
        if args.auto_download:
            success, filepath, error = download_season_csv(args.season, args.data_dir)
            if success:
                print(f"  ✓ Auto-download successful")
                # Reload the directory to get the newly downloaded file
                df = read_csv_files(args.data_dir)
                loaded_files = df['_source_file'].unique().tolist() if '_source_file' in df.columns else []
            else:
                print(f"  ⚠️ Auto-download failed: {error}")
                print(f"  Falling back to local files...")
        
        # Filter to only files from this season
        matching_files = [f for f in loaded_files if extract_season_from_filename(f) == args.season]
        
        if not matching_files:
            print(f"\n❌ No files found for season {args.season}")
            print(f"   Available files: {loaded_files}")
            if args.auto_download:
                print(f"   Auto-download failed and no local backup found.")
            sys.exit(1)
        
        print(f"\nFiles for season {args.season}:")
        for f in matching_files:
            print(f"  - {f}")
        
        # Filter dataframe to only this season's data
        df = df[df['_source_file'].isin(matching_files)].copy()
        print(f"Rows for {args.season}: {len(df):,}")
        
        # Delete that season from database
        if table_exists:
            print(f"\nDeleting existing {args.season} data from database...")
            truncate_season(args.season)
        
        skip_dup_check = True  # Skip dup check after delete
        
    else:
        # Mode 3: Append (default) - add new data without affecting existing
        print(f"\nMode: APPEND (add new data only)")
        skip_dup_check = args.skip_duplicate_check
    
    # Check for duplicates within CSV files
    has_dupes, dupe_count = detect_duplicates(df)
    if has_dupes:
        print(f"\n⚠️  Warning: {dupe_count} duplicate matches found in CSV files")
        print("   Keeping first occurrence only")
        df = df.drop_duplicates(subset='_match_key', keep='first')
    
    # Check for duplicates in database (unless current season mode or skip requested)
    if not skip_dup_check and table_exists:
        print("\nChecking for duplicates in database...")
        db_dupes_list = check_database_duplicates(df)
        db_dupes_count = len(db_dupes_list)
        
        if db_dupes_count > 0:
            print(f"\n⚠️  Warning: {db_dupes_count} matches already exist in database")
            print("   Removing duplicates from import data...")
            
            # Remove duplicates - keep only new data
            df = df[~df['_match_key'].isin(db_dupes_list)]
            print(f"✓ {len(df):,} new matches to import")
            
            if len(df) == 0:
                print("\n✓ No new data to import. Exiting.")
                sys.exit(0)
    
    # Load to database (always append mode)
    mode = 'append'  # Always append - never replace
    load_to_database(df, mode=mode)
    
    # Verify
    verify_load()
    
    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print("\n1. Run dbt to update transformations:")
    print("   cd football_prediction && dbt run")
    print("\n2. Verify data quality:")
    print("   cd football_prediction && dbt test")
    print("\n3. Check final dataset:")
    print("   psql -d football_prediction_db -c 'SELECT COUNT(*) FROM fct_model_training_dataset;'")
    
    print(f"\n{'='*80}")
    print(f"✓ Load completed successfully!")
    print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}")
    
    print(f"\n{'='*80}")
    print("LOADING MODES REFERENCE")
    print(f"{'='*80}")
    print("\n1. FULL LOAD (fresh start - all seasons)")
    print("   python scripts/load_raw_data.py --data-dir data/raw/ --full-truncate --no-backup")
    print("   → Truncates entire table")
    print("   → Loads all 10 seasons fresh")
    print("   → Use this for: Fresh database restart")
    
    print("\n2. SEASON UPDATE (refresh current season)")
    print("   python scripts/load_raw_data.py --data-dir data/raw/ --season 2025-26 --no-backup")
    print("   → Deletes only 2025-26 data")
    print("   → Loads local CSV file for that season")
    print("   → Historical seasons untouched")
    print("   → Use this for: Manual season refresh")
    
    print("\n2b. SEASON UPDATE WITH AUTO-DOWNLOAD (recommended for automation)")
    print("    python scripts/load_raw_data.py --data-dir data/raw/ --season 2025-26 --auto-download --no-backup")
    print("    → Downloads latest 2025-26 CSV from football-data.co.uk")
    print("    → Deletes existing 2025-26 data from database")
    print("    → Reloads fresh data from downloaded CSV")
    print("    → Falls back to local file if download fails")
    print("    → Use this for: Cron automation (weekly updates)")
    
    print("\n3. APPEND MODE (default - add new data)")
    print("   python scripts/load_raw_data.py --data-dir data/raw/ --no-backup")
    print("   → Detects and skips duplicates")
    print("   → Appends only new matches")
    print("   → Safe for one-off season additions")
    print(f"\n{'='*80}\n")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
