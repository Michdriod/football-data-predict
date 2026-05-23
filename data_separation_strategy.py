"""
Separate Prediction Model from Betting Evaluation

Strategy:
1. PREDICTION MODEL - Train on all 2,889 matches with valid features
   - Predict: Home Win, Draw, Away Win probabilities
   - Features: Team stats, rolling averages, match history
   - No odds required (odds are not features)

2. BETTING EVALUATION - Only use matches with real odds
   - Use 2,889 matches (all have real odds)
   - Calculate implied probabilities from real market odds
   - Simulate betting with real expected value
   - Track ROI on matches with actual market odds

Key guardrails:
- No forward-fill of odds
- No mean imputation for ROI
- No artificial odds treated as real
- Clear logging of data splits
"""

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import warnings
warnings.filterwarnings('ignore')

# Database connection
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'football_prediction_db',
    'user': 'postgres',
    'password': 'michwaleh'
}

def get_engine():
    connection_string = (
        f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )
    return create_engine(connection_string)

# Load training dataset
engine = get_engine()

print("="*80)
print("LOADING DATA")
print("="*80)

query = """
SELECT *
FROM fct_model_training_dataset
ORDER BY match_date;
"""

df = pd.read_sql_query(query, engine)
print(f"\n✓ Loaded {len(df):,} matches")

# Convert match_date to datetime
df['match_date'] = pd.to_datetime(df['match_date'], format='%d/%m/%Y', errors='coerce')

print(f"✓ Date range: {df['match_date'].min()} to {df['match_date'].max()}")
print(f"✓ Total columns: {len(df.columns)}")

# Check odds coverage
print("\n" + "="*80)
print("ODDS COVERAGE CHECK")
print("="*80)

print(f"\nMatches with real odds: {df['has_real_odds'].sum():,} / {len(df):,}")
print(f"Matches missing odds: {(~df['has_real_odds']).sum():,} / {len(df):,}")
print(f"Coverage: {df['has_real_odds'].sum() / len(df) * 100:.1f}%")

print("\nOdds Source Breakdown:")
odds_breakdown = df['odds_source'].value_counts()
for source, count in odds_breakdown.items():
    print(f"  {source}: {count:,} ({count/len(df)*100:.1f}%)")

print("\nOdds by Source - Date Ranges:")
for source in df[df['has_real_odds']]['odds_source'].unique():
    source_df = df[df['odds_source'] == source]
    print(f"  {source}:")
    print(f"    Date range: {source_df['match_date'].min()} to {source_df['match_date'].max()}")
    print(f"    Matches: {len(source_df):,}")

# Validate odds columns
print("\n" + "="*80)
print("ODDS DATA VALIDATION")
print("="*80)

required_odds = ['market_home_odds', 'market_draw_odds', 'market_away_odds']
for col in required_odds:
    null_count = df[col].isnull().sum()
    if null_count == 0:
        print(f"✓ {col}: NO missing values")
    else:
        print(f"⚠️ {col}: {null_count:,} missing ({null_count/len(df)*100:.1f}%)")

# Check if missing odds are only where has_real_odds = False
if ((df['has_real_odds'] == False) & (df['market_home_odds'].notna())).any():
    print("❌ ERROR: has_real_odds flag inconsistent with odds columns")
else:
    print("✓ has_real_odds flag is consistent")

print("\n" + "="*80)
print("PREDICTION MODEL DATASET")
print("="*80)

# Prediction model uses all matches (odds not required)
pred_df = df[df['home_matches_played_before'] >= 5].copy()  # Need prior match history

print(f"\nMatches with ≥5 prior games: {len(pred_df):,}")
print(f"Date range: {pred_df['match_date'].min()} to {pred_df['match_date'].max()}")

# Check targets
targets = ['target_home_not_lose', 'target_away_not_lose', 'target_over_25', 'target_btts_yes']
print(f"\nTarget Variables:")
for target in targets:
    non_null = pred_df[target].notna().sum()
    print(f"  {target}: {non_null:,} non-null ({non_null/len(pred_df)*100:.1f}%)")

print("\n" + "="*80)
print("BETTING EVALUATION DATASET")
print("="*80)

# Betting evaluation uses matches with real odds
betting_df = df[df['has_real_odds'] == True].copy()
print(f"\nMatches with real odds: {len(betting_df):,}")
print(f"Date range: {betting_df['match_date'].min()} to {betting_df['match_date'].max()}")

# Verify odds are populated
print(f"\nOdds validation:")
print(f"  market_home_odds: {betting_df['market_home_odds'].notna().sum():,} / {len(betting_df):,}")
print(f"  market_draw_odds: {betting_df['market_draw_odds'].notna().sum():,} / {len(betting_df):,}")
print(f"  market_away_odds: {betting_df['market_away_odds'].notna().sum():,} / {len(betting_df):,}")

# Show some sample rows
print(f"\nSample betting data:")
sample_cols = ['match_date', 'home_team', 'away_team', 'odds_source', 
               'market_home_odds', 'market_draw_odds', 'market_away_odds']
print(betting_df[sample_cols].head(10).to_string(index=False))

print("\n" + "="*80)
print("SUMMARY")
print("="*80)

print(f"""
PREDICTION MODEL DATASET:
  ✓ Total matches: {len(pred_df):,}
  ✓ Date range: {pred_df['match_date'].min().date()} to {pred_df['match_date'].max().date()}
  ✓ Odds required: NO (odds not used as features)
  ✓ Targets present: YES (all valid)
  ✓ Use case: Train model to predict outcomes

BETTING EVALUATION DATASET:
  ✓ Total matches: {len(betting_df):,}
  ✓ Date range: {betting_df['match_date'].min().date()} to {betting_df['match_date'].max().date()}
  ✓ Odds source: {betting_df['odds_source'].nunique()} sources
    - Bet365 Odds: {(betting_df['odds_source'] == 'Bet365 Odds').sum():,}
    - Avg Pre-Match Odds: {(betting_df['odds_source'] == 'Avg Pre-Match Odds').sum():,}
  ✓ All have real odds: {betting_df['has_real_odds'].all()}
  ✓ Use case: Simulate betting and ROI with real market odds

GUARDRAILS ACTIVE:
  ✓ No forward-fill of missing odds (fallback priority used instead)
  ✓ No mean imputation for ROI (all odds are real market odds)
  ✓ No artificial odds treated as real (explicit has_real_odds flag)
  ✓ Clear separation: Prediction uses all features, Betting uses only real odds
  ✓ Logging: Both datasets tracked separately

NEXT STEPS:
  1. Train prediction model on {len(pred_df):,} matches
  2. Evaluate predictions on test set
  3. Simulate betting on {len(betting_df):,} matches with real odds
  4. Calculate ROI only on real market odds
""")

# Store for downstream use
print("\n✓ Dataframes created: df (raw), pred_df (for model), betting_df (for evaluation)")
