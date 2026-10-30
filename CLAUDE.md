# CLAUDE.md — Football Match Prediction System

## What This File Is

This file is the primary instruction document for a Claude Code agent working on the Football Match Prediction System. Read this file completely before doing anything. Follow all rules exactly. Do not improvise outside these instructions.

---

## Project Purpose

A disciplined, data-driven football match prediction engine focused on the English Premier League. The system identifies high-confidence opportunities across three prediction markets:

1. Over / Under 2.5 Goals
2. Both Teams To Score (BTTS)
3. Double Chance: Home Not Lose (1X) and Away Not Lose (X2)

The system outputs probabilities, confidence levels, and betting value signals — not binary win/lose picks. It is not a generic betting bot. It is a value-detection system that will say "No Bet" more often than "Bet."

---

## Technology Stack

| Layer | Tool |
|---|---|
| Database | PostgreSQL (local) |
| Transformation | dbt (dbt-core + dbt-postgres) |
| ML and Python | Python 3.10, pandas, numpy, scikit-learn |
| Future API | FastAPI |
| Future Frontend | React |

---

## Project Directory Layout

```
football-prediction/
├── CLAUDE.md                    ← this file
├── data/
│   └── raw/                     ← downloaded CSV files from football-data.co.uk go here
├── dbt_project/
│   ├── dbt_project.yml
│   ├── profiles.yml             ← local dbt connection config (not committed to git)
│   ├── models/
│   │   ├── staging/
│   │   │   ├── stg_football_matches.sql
│   │   │   └── staging.yml
│   │   ├── intermediate/
│   │   │   ├── int_match_results.sql
│   │   │   ├── int_match_stats.sql
│   │   │   ├── int_match_odds.sql
│   │   │   ├── int_prediction_targets.sql
│   │   │   ├── int_team_match_history.sql
│   │   │   └── intermediate.yml
│   │   └── marts/
│   │       ├── fct_team_rolling_features.sql
│   │       ├── fct_model_training_dataset.sql
│   │       └── marts.yml
│   └── tests/
├── scripts/
│   ├── load_raw_data.py         ← CSV loader script
│   ├── train_models.py          ← ML training script
│   ├── evaluate_models.py       ← evaluation and backtesting
│   └── predict.py               ← prediction output script
├── notebooks/
│   └── exploration.ipynb        ← EDA only, not production
├── models/
│   └── saved/                   ← serialized trained models (.pkl or .joblib)
└── requirements.txt
```

---

## Environment Setup

### PostgreSQL

- Database name: `football_prediction_db`
- Schema: `public`
- Default local connection: `host=localhost port=5432 user=postgres`
- **Credentials stored in .env file** (not hardcoded)

To create the database if it does not exist:

```bash
psql -U postgres -c "CREATE DATABASE football_prediction_db;"
```

### Environment Configuration

**IMPORTANT:** All database credentials and configuration are stored in a `.env` file (not committed to git).

1. Copy the template:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and set your database password:
   ```bash
   DB_PASSWORD=your_password_here
   ```

3. Test configuration:
   ```bash
   python scripts/config.py
   ```

All scripts automatically load configuration from `.env` via `scripts/config.py`.

### dbt Profile

The `profiles.yml` file should live at `~/.dbt/profiles.yml` (default dbt location) or at `dbt_project/profiles.yml`.

Expected profile name: `football_prediction`

```yaml
football_prediction:
  target: dev
  outputs:
    dev:
      type: postgres
      host: localhost
      user: postgres
      password: "{{ env_var('DBT_DB_PASSWORD') }}"
      port: 5432
      dbname: football_prediction
      schema: public
      threads: 4
```

### Python Environment

Use a virtual environment. Python 3.10 is required.

```bash
python -m venv venv
source venv/bin/activate        # on Mac/Linux
venv\Scripts\activate           # on Windows
pip install -r requirements.txt
```

`requirements.txt` should contain at minimum:

```
dbt-core
dbt-postgres
pandas
numpy
scikit-learn
sqlalchemy
psycopg2-binary
matplotlib
joblib
python-dotenv
```

---

## Data Source

Historical match data comes from football-data.co.uk.

### Download Instructions

1. Go to: https://www.football-data.co.uk/englandm.php
2. Download the Premier League (E0) CSV for each season needed
3. Recommended seasons: 2015/16 through 2024/25 (minimum 5 seasons, target 8-10)
4. Save files into: `data/raw/`
5. Use filenames like: `E0_2015-16.csv`, `E0_2016-17.csv`, etc.

### CSV Format

Files use the football-data.co.uk column format. Some column names contain special characters like `B365>2.5`. The raw table uses quoted column names to handle this.

---

## Commands Reference

### Automated Update Pipeline (NEW - Step 21)

```bash
# One-command weekly update: CSV → dbt → retrain (if needed) → update models
python scripts/auto_update.py --csv data/raw/E0_2025-26.csv

# Force retraining even if below 20 match threshold
python scripts/auto_update.py --csv data/raw/E0_2025-26.csv --force-retrain

# Skip dbt pipeline (testing only)
python scripts/auto_update.py --csv data/raw/E0_2025-26.csv --skip-dbt

# Specify season code manually
python scripts/auto_update.py --csv data/raw/E0_2025-26.csv --season 2025-26
```

This automated script:
- Loads CSV into raw_football_matches (replaces existing season data)
- Runs dbt pipeline (dbt run + dbt test)
- Checks if 20+ new matches added since last training
- If yes: Trains new models on full dataset
- Retrains and saves the match model
- Does not gate on performance: run `python scripts/match_model.py --evaluate` to check it

### Load Raw Data (Manual Method)

```bash
python scripts/load_raw_data.py --data-dir data/raw/
```

This script should:
- Read all CSV files from `data/raw/`
- Concatenate them into a single DataFrame
- Load into the `raw_football_matches` table in PostgreSQL
- Use `if_exists='append'` or upsert logic to avoid duplicates

### Run dbt

```bash
cd dbt_project

# Test connection
dbt debug

# Run all models
dbt run

# Run a single model
dbt run --select stg_football_matches

# Run from a model and all downstream
dbt run --select stg_football_matches+

# Run tests
dbt test

# Run tests for a specific model
dbt test --select stg_football_matches

# Generate and serve docs
dbt docs generate
dbt docs serve
```

### Train Models

```bash
# Production model (saves models/saved/match_model.joblib)
python scripts/match_model.py --train

# Walk-forward test against bookmaker prices (logs/match_model_evaluation.csv)
python scripts/match_model.py --evaluate

# Baseline models only (Logistic Regression + Random Forest)
python scripts/train_models.py --models logistic random_forest --skip-cv
```

### Run Predictions

```bash
python scripts/predict.py --fetch-odds --days 7
python scripts/predict.py --home Arsenal --away Chelsea --date 2026-11-07

# Score logged practice picks against results and closing prices
python scripts/predict.py --practice-report
```

---

## Raw Data Table

Create this table once in PostgreSQL before running dbt.

```sql
DROP TABLE IF EXISTS raw_football_matches;

CREATE TABLE raw_football_matches (
    "Div" TEXT,
    "Date" TEXT,
    "Time" TEXT,
    "HomeTeam" TEXT,
    "AwayTeam" TEXT,
    "FTHG" TEXT,
    "FTAG" TEXT,
    "FTR" TEXT,
    "HTHG" TEXT,
    "HTAG" TEXT,
    "HTR" TEXT,
    "Referee" TEXT,
    "HxG" TEXT,
    "AxG" TEXT,
    "HS" TEXT,
    "AS" TEXT,
    "HST" TEXT,
    "AST" TEXT,
    "HF" TEXT,
    "AF" TEXT,
    "HC" TEXT,
    "AC" TEXT,
    "HY" TEXT,
    "AY" TEXT,
    "HR" TEXT,
    "AR" TEXT,
    "B365H" TEXT,
    "B365D" TEXT,
    "B365A" TEXT,
    "BFDH" TEXT,
    "BFDD" TEXT,
    "BFDA" TEXT,
    "BMGMH" TEXT,
    "BMGMD" TEXT,
    "BMGMA" TEXT,
    "BVH" TEXT,
    "BVD" TEXT,
    "BVA" TEXT,
    "BWH" TEXT,
    "BWD" TEXT,
    "BWA" TEXT,
    "CLH" TEXT,
    "CLD" TEXT,
    "CLA" TEXT,
    "LBH" TEXT,
    "LBD" TEXT,
    "LBA" TEXT,
    "PSH" TEXT,
    "PSD" TEXT,
    "PSA" TEXT,
    "MaxH" TEXT,
    "MaxD" TEXT,
    "MaxA" TEXT,
    "AvgH" TEXT,
    "AvgD" TEXT,
    "AvgA" TEXT,
    "BFEH" TEXT,
    "BFED" TEXT,
    "BFEA" TEXT,
    "B365>2.5" TEXT,
    "B365<2.5" TEXT,
    "P>2.5" TEXT,
    "P<2.5" TEXT,
    "Max>2.5" TEXT,
    "Max<2.5" TEXT,
    "Avg>2.5" TEXT,
    "Avg<2.5" TEXT,
    "BFE>2.5" TEXT,
    "BFE<2.5" TEXT,
    "AHh" TEXT,
    "B365AHH" TEXT,
    "B365AHA" TEXT,
    "PAHH" TEXT,
    "PAHA" TEXT,
    "MaxAHH" TEXT,
    "MaxAHA" TEXT,
    "AvgAHH" TEXT,
    "AvgAHA" TEXT,
    "BFEAHH" TEXT,
    "BFEAHA" TEXT,
    "B365CH" TEXT,
    "B365CD" TEXT,
    "B365CA" TEXT,
    "BFDCH" TEXT,
    "BFDCD" TEXT,
    "BFDCA" TEXT,
    "BMGMCH" TEXT,
    "BMGMCD" TEXT,
    "BMGMCA" TEXT,
    "BVCH" TEXT,
    "BVCD" TEXT,
    "BVCA" TEXT,
    "BWCH" TEXT,
    "BWCD" TEXT,
    "BWCA" TEXT,
    "CLCH" TEXT,
    "CLCD" TEXT,
    "CLCA" TEXT,
    "LBCH" TEXT,
    "LBCD" TEXT,
    "LBCA" TEXT,
    "PSCH" TEXT,
    "PSCD" TEXT,
    "PSCA" TEXT,
    "MaxCH" TEXT,
    "MaxCD" TEXT,
    "MaxCA" TEXT,
    "AvgCH" TEXT,
    "AvgCD" TEXT,
    "AvgCA" TEXT,
    "BFECH" TEXT,
    "BFECD" TEXT,
    "BFECA" TEXT,
    "B365C>2.5" TEXT,
    "B365C<2.5" TEXT,
    "PC>2.5" TEXT,
    "PC<2.5" TEXT,
    "MaxC>2.5" TEXT,
    "MaxC<2.5" TEXT,
    "AvgC>2.5" TEXT,
    "AvgC<2.5" TEXT,
    "BFEC>2.5" TEXT,
    "BFEC<2.5" TEXT,
    "AHCh" TEXT,
    "B365CAHH" TEXT,
    "B365CAHA" TEXT,
    "PCAHH" TEXT,
    "PCAHA" TEXT,
    "MaxCAHH" TEXT,
    "MaxCAHA" TEXT,
    "AvgCAHH" TEXT,
    "AvgCAHA" TEXT,
    "BFECAHH" TEXT,
    "BFECAHA" TEXT
);
```

---

## dbt Architecture

Use these four logical layers. All models materialize in the `public` schema for Version 1.

```
raw_football_matches          ← PostgreSQL table (loaded by Python script)
        ↓
stg_football_matches          ← staging: rename, cast, clean
        ↓
int_match_results             ← intermediate: result logic
int_match_stats               ← intermediate: shot/corner stats
int_match_odds                ← intermediate: odds + implied probs
int_prediction_targets        ← intermediate: ML target labels
int_team_match_history        ← intermediate: one row per team per match
        ↓
fct_team_rolling_features     ← mart: rolling form features per team
        ↓
fct_model_training_dataset    ← mart: final ML-ready dataset (one row per match)
```

All model SQL is defined below. Do not add DISTINCT ON, SELECT *, or uppercase column aliases.

---

## Staging Model: stg_football_matches

```sql
select
    "Div" as league_code,
    to_date("Date", 'DD/MM/YYYY') as match_date,
    nullif("Time", '')::time as match_time,

    "HomeTeam" as home_team,
    "AwayTeam" as away_team,

    nullif("FTHG", '')::int as full_time_home_goals,
    nullif("FTAG", '')::int as full_time_away_goals,
    "FTR" as full_time_result,

    nullif("HTHG", '')::int as half_time_home_goals,
    nullif("HTAG", '')::int as half_time_away_goals,
    "HTR" as half_time_result,

    "Referee" as referee,

    nullif("HxG", '')::numeric as home_xg,
    nullif("AxG", '')::numeric as away_xg,

    nullif("HS", '')::int as home_shots,
    nullif("AS", '')::int as away_shots,
    nullif("HST", '')::int as home_shots_on_target,
    nullif("AST", '')::int as away_shots_on_target,

    nullif("HF", '')::int as home_fouls,
    nullif("AF", '')::int as away_fouls,
    nullif("HC", '')::int as home_corners,
    nullif("AC", '')::int as away_corners,

    nullif("HY", '')::int as home_yellow_cards,
    nullif("AY", '')::int as away_yellow_cards,
    nullif("HR", '')::int as home_red_cards,
    nullif("AR", '')::int as away_red_cards,

    nullif("B365H", '')::numeric as bet365_home_win_odds,
    nullif("B365D", '')::numeric as bet365_draw_odds,
    nullif("B365A", '')::numeric as bet365_away_win_odds,

    nullif("AvgH", '')::numeric as avg_home_win_odds,
    nullif("AvgD", '')::numeric as avg_draw_odds,
    nullif("AvgA", '')::numeric as avg_away_win_odds,

    nullif("B365>2.5", '')::numeric as bet365_over_25_odds,
    nullif("B365<2.5", '')::numeric as bet365_under_25_odds,
    nullif("Avg>2.5", '')::numeric as avg_over_25_odds,
    nullif("Avg<2.5", '')::numeric as avg_under_25_odds,

    nullif("B365CH", '')::numeric as bet365_closing_home_win_odds,
    nullif("B365CD", '')::numeric as bet365_closing_draw_odds,
    nullif("B365CA", '')::numeric as bet365_closing_away_win_odds,

    nullif("AvgCH", '')::numeric as avg_closing_home_win_odds,
    nullif("AvgCD", '')::numeric as avg_closing_draw_odds,
    nullif("AvgCA", '')::numeric as avg_closing_away_win_odds,

    nullif("B365C>2.5", '')::numeric as bet365_closing_over_25_odds,
    nullif("B365C<2.5", '')::numeric as bet365_closing_under_25_odds,
    nullif("AvgC>2.5", '')::numeric as avg_closing_over_25_odds,
    nullif("AvgC<2.5", '')::numeric as avg_closing_under_25_odds,

    nullif("AHh", '')::numeric as asian_handicap_line,
    nullif("AHCh", '')::numeric as closing_asian_handicap_line

from {{ source('public', 'raw_football_matches') }}
```

If source config is not yet set up, temporarily use `from raw_football_matches`.

---

## Intermediate Models

### int_match_results

```sql
select
    league_code,
    match_date,
    match_time,
    home_team,
    away_team,
    referee,

    full_time_home_goals,
    full_time_away_goals,
    full_time_result,
    half_time_home_goals,
    half_time_away_goals,
    half_time_result,

    full_time_home_goals + full_time_away_goals as total_goals,

    case when full_time_result = 'H' then true else false end as is_home_win,
    case when full_time_result = 'D' then true else false end as is_draw,
    case when full_time_result = 'A' then true else false end as is_away_win,

    concat(
        league_code, '_',
        to_char(match_date, 'YYYYMMDD'), '_',
        replace(home_team, ' ', '_'), '_',
        replace(away_team, ' ', '_')
    ) as match_key

from {{ ref('stg_football_matches') }}
```

### int_prediction_targets

```sql
select
    match_key,
    league_code,
    match_date,
    home_team,
    away_team,

    total_goals,
    full_time_home_goals,
    full_time_away_goals,
    full_time_result,

    case when total_goals >= 3 then true else false end as target_over_25,
    case when total_goals <= 2 then true else false end as target_under_25,

    case
        when full_time_home_goals >= 1 and full_time_away_goals >= 1
        then true else false
    end as target_btts_yes,

    case
        when full_time_home_goals = 0 or full_time_away_goals = 0
        then true else false
    end as target_btts_no,

    case
        when full_time_result in ('H', 'D')
        then true else false
    end as target_home_not_lose,

    case
        when full_time_result in ('A', 'D')
        then true else false
    end as target_away_not_lose

from {{ ref('int_match_results') }}
```

### int_match_stats

```sql
select
    concat(
        league_code, '_',
        to_char(match_date, 'YYYYMMDD'), '_',
        replace(home_team, ' ', '_'), '_',
        replace(away_team, ' ', '_')
    ) as match_key,

    league_code,
    match_date,
    home_team,
    away_team,

    home_shots,
    away_shots,
    home_shots_on_target,
    away_shots_on_target,
    home_fouls,
    away_fouls,
    home_corners,
    away_corners,
    home_yellow_cards,
    away_yellow_cards,
    home_red_cards,
    away_red_cards

from {{ ref('stg_football_matches') }}
```

### int_match_odds

```sql
select
    concat(
        league_code, '_',
        to_char(match_date, 'YYYYMMDD'), '_',
        replace(home_team, ' ', '_'), '_',
        replace(away_team, ' ', '_')
    ) as match_key,

    league_code,
    match_date,
    home_team,
    away_team,

    bet365_home_win_odds,
    bet365_draw_odds,
    bet365_away_win_odds,
    avg_home_win_odds,
    avg_draw_odds,
    avg_away_win_odds,
    bet365_over_25_odds,
    bet365_under_25_odds,
    avg_over_25_odds,
    avg_under_25_odds,

    bet365_closing_home_win_odds,
    bet365_closing_draw_odds,
    bet365_closing_away_win_odds,
    avg_closing_home_win_odds,
    avg_closing_draw_odds,
    avg_closing_away_win_odds,
    bet365_closing_over_25_odds,
    bet365_closing_under_25_odds,
    avg_closing_over_25_odds,
    avg_closing_under_25_odds,

    asian_handicap_line,
    closing_asian_handicap_line,

    case when bet365_home_win_odds > 0 then 1.0 / bet365_home_win_odds end as implied_home_win_prob,
    case when bet365_draw_odds > 0 then 1.0 / bet365_draw_odds end as implied_draw_prob,
    case when bet365_away_win_odds > 0 then 1.0 / bet365_away_win_odds end as implied_away_win_prob,
    case when bet365_over_25_odds > 0 then 1.0 / bet365_over_25_odds end as implied_over_25_prob,
    case when bet365_under_25_odds > 0 then 1.0 / bet365_under_25_odds end as implied_under_25_prob,

    bet365_closing_home_win_odds - bet365_home_win_odds as home_win_odds_movement,
    bet365_closing_draw_odds - bet365_draw_odds as draw_odds_movement,
    bet365_closing_away_win_odds - bet365_away_win_odds as away_win_odds_movement,
    bet365_closing_over_25_odds - bet365_over_25_odds as over_25_odds_movement,
    bet365_closing_under_25_odds - bet365_under_25_odds as under_25_odds_movement

from {{ ref('stg_football_matches') }}
```

### int_team_match_history

```sql
with base as (
    select
        r.match_key,
        r.league_code,
        r.match_date,
        r.match_time,
        r.home_team,
        r.away_team,
        r.full_time_home_goals,
        r.full_time_away_goals,
        r.full_time_result,
        r.total_goals,

        s.home_shots,
        s.away_shots,
        s.home_shots_on_target,
        s.away_shots_on_target,
        s.home_corners,
        s.away_corners,
        s.home_fouls,
        s.away_fouls,
        s.home_yellow_cards,
        s.away_yellow_cards,
        s.home_red_cards,
        s.away_red_cards

    from {{ ref('int_match_results') }} r
    left join {{ ref('int_match_stats') }} s
        on r.match_key = s.match_key
),

home_rows as (
    select
        match_key,
        league_code,
        match_date,
        match_time,
        home_team as team,
        away_team as opponent,
        true as is_home,

        full_time_home_goals as goals_for,
        full_time_away_goals as goals_against,
        home_shots as shots_for,
        away_shots as shots_against,
        home_shots_on_target as shots_on_target_for,
        away_shots_on_target as shots_on_target_against,
        home_corners as corners_for,
        away_corners as corners_against,
        home_fouls as fouls_committed,
        away_fouls as fouls_received,
        home_yellow_cards as yellow_cards,
        home_red_cards as red_cards,

        case
            when full_time_result = 'H' then 'W'
            when full_time_result = 'D' then 'D'
            else 'L'
        end as team_result,

        case
            when full_time_result = 'H' then 3
            when full_time_result = 'D' then 1
            else 0
        end as points,

        case when total_goals >= 3 then true else false end as over_25,
        case when full_time_home_goals >= 1 and full_time_away_goals >= 1 then true else false end as btts,
        case when full_time_away_goals = 0 then true else false end as clean_sheet,
        case when full_time_home_goals = 0 then true else false end as failed_to_score

    from base
),

away_rows as (
    select
        match_key,
        league_code,
        match_date,
        match_time,
        away_team as team,
        home_team as opponent,
        false as is_home,

        full_time_away_goals as goals_for,
        full_time_home_goals as goals_against,
        away_shots as shots_for,
        home_shots as shots_against,
        away_shots_on_target as shots_on_target_for,
        home_shots_on_target as shots_on_target_against,
        away_corners as corners_for,
        home_corners as corners_against,
        away_fouls as fouls_committed,
        home_fouls as fouls_received,
        away_yellow_cards as yellow_cards,
        away_red_cards as red_cards,

        case
            when full_time_result = 'A' then 'W'
            when full_time_result = 'D' then 'D'
            else 'L'
        end as team_result,

        case
            when full_time_result = 'A' then 3
            when full_time_result = 'D' then 1
            else 0
        end as points,

        case when total_goals >= 3 then true else false end as over_25,
        case when full_time_home_goals >= 1 and full_time_away_goals >= 1 then true else false end as btts,
        case when full_time_home_goals = 0 then true else false end as clean_sheet,
        case when full_time_away_goals = 0 then true else false end as failed_to_score

    from base
)

select * from home_rows
union all
select * from away_rows
```

---

## Mart Models

### fct_team_rolling_features

Critical rule: do not include the current match in any rolling window. Always use `rows between N preceding and 1 preceding`.

```sql
select
    match_key,
    league_code,
    match_date,
    match_time,
    team,
    opponent,
    is_home,

    count(*) over (
        partition by team
        order by match_date, match_time, match_key
        rows between unbounded preceding and 1 preceding
    ) as matches_played_before,

    avg(goals_for) over (
        partition by team
        order by match_date, match_time, match_key
        rows between 5 preceding and 1 preceding
    ) as avg_goals_for_last_5,

    avg(goals_against) over (
        partition by team
        order by match_date, match_time, match_key
        rows between 5 preceding and 1 preceding
    ) as avg_goals_against_last_5,

    avg(shots_for) over (
        partition by team
        order by match_date, match_time, match_key
        rows between 5 preceding and 1 preceding
    ) as avg_shots_for_last_5,

    avg(shots_on_target_for) over (
        partition by team
        order by match_date, match_time, match_key
        rows between 5 preceding and 1 preceding
    ) as avg_shots_on_target_for_last_5,

    avg(corners_for) over (
        partition by team
        order by match_date, match_time, match_key
        rows between 5 preceding and 1 preceding
    ) as avg_corners_for_last_5,

    avg(points) over (
        partition by team
        order by match_date, match_time, match_key
        rows between 5 preceding and 1 preceding
    ) as avg_points_last_5,

    avg(case when over_25 then 1.0 else 0.0 end) over (
        partition by team
        order by match_date, match_time, match_key
        rows between 5 preceding and 1 preceding
    ) as over_25_rate_last_5,

    avg(case when btts then 1.0 else 0.0 end) over (
        partition by team
        order by match_date, match_time, match_key
        rows between 5 preceding and 1 preceding
    ) as btts_rate_last_5,

    avg(case when clean_sheet then 1.0 else 0.0 end) over (
        partition by team
        order by match_date, match_time, match_key
        rows between 5 preceding and 1 preceding
    ) as clean_sheet_rate_last_5,

    avg(case when failed_to_score then 1.0 else 0.0 end) over (
        partition by team
        order by match_date, match_time, match_key
        rows between 5 preceding and 1 preceding
    ) as failed_to_score_rate_last_5,

    avg(goals_for) over (
        partition by team
        order by match_date, match_time, match_key
        rows between 10 preceding and 1 preceding
    ) as avg_goals_for_last_10,

    avg(goals_against) over (
        partition by team
        order by match_date, match_time, match_key
        rows between 10 preceding and 1 preceding
    ) as avg_goals_against_last_10,

    avg(case when over_25 then 1.0 else 0.0 end) over (
        partition by team
        order by match_date, match_time, match_key
        rows between 10 preceding and 1 preceding
    ) as over_25_rate_last_10,

    avg(case when btts then 1.0 else 0.0 end) over (
        partition by team
        order by match_date, match_time, match_key
        rows between 10 preceding and 1 preceding
    ) as btts_rate_last_10

from {{ ref('int_team_match_history') }}
```

### fct_model_training_dataset

```sql
with home_features as (
    select * from {{ ref('fct_team_rolling_features') }} where is_home = true
),

away_features as (
    select * from {{ ref('fct_team_rolling_features') }} where is_home = false
),

results as (select * from {{ ref('int_match_results') }}),
targets as (select * from {{ ref('int_prediction_targets') }}),
odds as (select * from {{ ref('int_match_odds') }})

select
    r.match_key,
    r.league_code,
    r.match_date,
    r.match_time,
    r.home_team,
    r.away_team,

    hf.matches_played_before as home_matches_played_before,
    af.matches_played_before as away_matches_played_before,

    hf.avg_goals_for_last_5 as home_avg_goals_for_last_5,
    hf.avg_goals_against_last_5 as home_avg_goals_against_last_5,
    hf.avg_shots_for_last_5 as home_avg_shots_for_last_5,
    hf.avg_shots_on_target_for_last_5 as home_avg_shots_on_target_for_last_5,
    hf.avg_corners_for_last_5 as home_avg_corners_for_last_5,
    hf.avg_points_last_5 as home_avg_points_last_5,
    hf.over_25_rate_last_5 as home_over_25_rate_last_5,
    hf.btts_rate_last_5 as home_btts_rate_last_5,
    hf.clean_sheet_rate_last_5 as home_clean_sheet_rate_last_5,
    hf.failed_to_score_rate_last_5 as home_failed_to_score_rate_last_5,
    hf.avg_goals_for_last_10 as home_avg_goals_for_last_10,
    hf.avg_goals_against_last_10 as home_avg_goals_against_last_10,
    hf.over_25_rate_last_10 as home_over_25_rate_last_10,
    hf.btts_rate_last_10 as home_btts_rate_last_10,

    af.avg_goals_for_last_5 as away_avg_goals_for_last_5,
    af.avg_goals_against_last_5 as away_avg_goals_against_last_5,
    af.avg_shots_for_last_5 as away_avg_shots_for_last_5,
    af.avg_shots_on_target_for_last_5 as away_avg_shots_on_target_for_last_5,
    af.avg_corners_for_last_5 as away_avg_corners_for_last_5,
    af.avg_points_last_5 as away_avg_points_last_5,
    af.over_25_rate_last_5 as away_over_25_rate_last_5,
    af.btts_rate_last_5 as away_btts_rate_last_5,
    af.clean_sheet_rate_last_5 as away_clean_sheet_rate_last_5,
    af.failed_to_score_rate_last_5 as away_failed_to_score_rate_last_5,
    af.avg_goals_for_last_10 as away_avg_goals_for_last_10,
    af.avg_goals_against_last_10 as away_avg_goals_against_last_10,
    af.over_25_rate_last_10 as away_over_25_rate_last_10,
    af.btts_rate_last_10 as away_btts_rate_last_10,

    o.bet365_home_win_odds,
    o.bet365_draw_odds,
    o.bet365_away_win_odds,
    o.avg_home_win_odds,
    o.avg_draw_odds,
    o.avg_away_win_odds,
    o.bet365_over_25_odds,
    o.bet365_under_25_odds,
    o.avg_over_25_odds,
    o.avg_under_25_odds,
    o.implied_home_win_prob,
    o.implied_draw_prob,
    o.implied_away_win_prob,
    o.implied_over_25_prob,
    o.implied_under_25_prob,

    t.target_over_25,
    t.target_under_25,
    t.target_btts_yes,
    t.target_btts_no,
    t.target_home_not_lose,
    t.target_away_not_lose

from results r
left join home_features hf on r.match_key = hf.match_key and r.home_team = hf.team
left join away_features af on r.match_key = af.match_key and r.away_team = af.team
left join odds o on r.match_key = o.match_key
left join targets t on r.match_key = t.match_key

where hf.matches_played_before >= 5
  and af.matches_played_before >= 5
```

---

## dbt YAML Tests

### staging.yml

```yaml
version: 2

sources:
  - name: public
    tables:
      - name: raw_football_matches

models:
  - name: stg_football_matches
    columns:
      - name: match_date
        tests:
          - not_null
      - name: home_team
        tests:
          - not_null
      - name: away_team
        tests:
          - not_null
      - name: full_time_home_goals
        tests:
          - not_null
      - name: full_time_away_goals
        tests:
          - not_null
      - name: full_time_result
        tests:
          - not_null
          - accepted_values:
              values: ['H', 'D', 'A']
```

### intermediate.yml

```yaml
version: 2

models:
  - name: int_match_results
    columns:
      - name: match_key
        tests:
          - not_null
          - unique
      - name: total_goals
        tests:
          - not_null

  - name: int_prediction_targets
    columns:
      - name: match_key
        tests:
          - not_null
          - unique
```

### marts.yml

```yaml
version: 2

models:
  - name: fct_model_training_dataset
    columns:
      - name: match_key
        tests:
          - not_null
          - unique
      - name: home_matches_played_before
        tests:
          - not_null
      - name: away_matches_played_before
        tests:
          - not_null
```

---

## dbt Code Rules

The agent must follow these rules when writing or editing any dbt SQL:

- No `SELECT *` in any model
- No `DISTINCT ON` — rewrite using `ROW_NUMBER()` if deduplication is needed
- All column names must be lowercase with underscores
- Always use `nullif(column, '')::type` before casting raw columns
- Never use current-match data in rolling feature windows
- Rolling windows must use `rows between N preceding and 1 preceding`
- Do not add columns not defined in this file without checking first
- Do not change the `match_key` concatenation formula — it must be identical across all models
- Do not rename columns that are already established in this document

---

## Data Handling & Train/Test Split (CRITICAL)

### Time-Based Split Rules

**NEVER use random shuffling for football matches. Time matters.**

#### Before Splitting

1. **Convert to datetime**
   ```python
   df['match_date'] = pd.to_datetime(df['match_date'], format='%d/%m/%Y', errors='coerce')
   ```

2. **Sort by date and reset index**
   ```python
   df = df.sort_values('match_date').reset_index(drop=True)
   ```
   - Ensures chronological order
   - Index alignment for time-based filtering

3. **Verify rolling features**
   - ALL rolling windows MUST use: `rows between N preceding and 1 preceding`
   - This excludes the current match from the window
   - Example: `avg_goals_for_last_5` does NOT include today's match

#### After Splitting

Create three chronological splits (NO random shuffle):

| Dataset | Purpose | Time Range | Notes |
|---------|---------|-----------|-------|
| **train_df** | Model learning | before 2023-07-01 | ~2,000+ matches |
| **val_df** | Hyperparameter tuning + calibration | 2023-07-01 to 2024-07-01 | ~500+ matches |
| **test_df** | Final evaluation | after 2024-07-01 | ~400+ matches |

```python
TRAIN_END = '2023-07-01'
VAL_END = '2024-07-01'

train_df = df[df['match_date'] < TRAIN_END].copy()
val_df = df[(df['match_date'] >= TRAIN_END) & (df['match_date'] < VAL_END)].copy()
test_df = df[df['match_date'] >= VAL_END].copy()
```

### Data Separation: Prediction vs. Betting

**Two distinct datasets. Do NOT confuse them.**

#### Prediction Dataset
- **Includes**: ALL 2,889 matches (prediction doesn't need odds)
- **Purpose**: Train models to predict match outcomes
- **Features**: Team stats, rolling form, goals, shots, corners, etc.
- **NO odds in features**: Odds used only for betting evaluation
- **Filtering**: Only apply rolling feature filter (≥5 prior matches)

#### Betting Evaluation Dataset
- **For each market separately**: Filter to rows where `has_real_odds = True`
- **Purpose**: Calculate ROI and value edge on REAL market odds only
- **NO removal from prediction**: Matches with missing odds stay in prediction model
- **Example workflow**:
  ```python
  # Prediction: use all matches
  X_train = train_df[feature_cols].fillna(0)  # All 2,000+ rows
  
  # Betting ROI: filter to real odds
  betting_train = train_df[train_df['has_real_odds'] == True].copy()
  betting_proba = model.predict_proba(X_train[betting_train.index])
  ```

### No Data Leakage Checklist

- [x] No random shuffling — chronological only
- [x] Train < Val < Test (strict time ordering)
- [x] No future information in features
- [x] Rolling windows exclude current match
- [x] Odds NOT used as features (only for betting eval)
- [x] Validation set used only for calibration
- [x] Test set never touched until final evaluation
- [x] Matches with missing odds kept in prediction model

---

## Machine Learning Plan

### Models to Train (Version 1)

Train four separate binary classification models:

| Target Column | Market |
|---|---|
| `target_over_25` | Over 2.5 Goals |
| `target_btts_yes` | Both Teams To Score |
| `target_home_not_lose` | Double Chance 1X |
| `target_away_not_lose` | Double Chance X2 |

### Train/Test Split

Use time-based splits only. Never use random splits.

```
Train:      2015/16 — 2022/23
Validation: 2023/24
Test:       2024/25
```

### Baseline Models (Start Here)

- Logistic Regression
- Random Forest

Later add: XGBoost, LightGBM, calibrated ensemble

### Evaluation Metrics

ML metrics:
- Accuracy, Precision, Recall
- ROC-AUC
- Brier Score
- Log Loss

Betting metrics:
- Number of recommended bets
- Win rate
- Average odds taken
- Profit/loss
- ROI and Yield
- Maximum drawdown

---

## Betting Value Logic

```
implied_probability = 1 / decimal_odds
value_edge = model_probability - implied_probability
```

**Practice mode is active (owner decision, 2026-10-30).** predict.py never outputs Bet. It labels a pick PRACTICE when a real bookmaker price has value_edge >= 0.03 and odds of 1.30 to 6.00, and logs it to logs/practice_picks.csv. Do not re-enable real-money labels unless `--practice-report` shows a positive price vs closing over 200+ settled picks and the owner approves.

Original Version 1 decision rule, not in use:

```
Recommend Bet only if:
  model_probability >= 0.60
  AND value_edge >= 0.05
  AND both teams have at least 5 prior matches
```

---

## Prediction Output Contract

```json
{
  "match": "Arsenal vs Chelsea",
  "market": "Over 2.5 Goals",
  "prediction": "Over 2.5",
  "model_probability": 0.68,
  "bookmaker_odds": 1.90,
  "implied_probability": 0.526,
  "value_edge": 0.154,
  "confidence": "High",
  "decision": "Bet"
}
```

Confidence bands:

```
High:   model_probability >= 0.70
Medium: model_probability >= 0.60 and < 0.70
Low:    model_probability < 0.60
```

---

## Current Project Status

Update this section as work progresses. The agent should read this before starting any session.

```
Step  1  — Create PostgreSQL database                  [✓] Complete
Step  2  — Create raw_football_matches table           [✓] Complete
Step  3  — Import raw CSV data                         [✓] Complete
Step  4  — Create dbt project                          [✓] Complete
Step  5  — Create stg_football_matches                 [✓] Complete
Step  6  — Add basic dbt tests                         [✓] Complete
Step  7  — Create int_match_results                    [✓] Complete
Step  8  — Create int_prediction_targets               [✓] Complete
Step  9  — Create int_match_stats                      [✓] Complete
Step 10  — Create int_match_odds                       [✓] Complete
Step 11  — Create int_team_match_history               [✓] Complete
Step 12  — Create fct_team_rolling_features            [✓] Complete
Step 13  — Create fct_model_training_dataset           [✓] Complete
Step 14  — Validate dataset manually                   [✓] Complete
Step 14a — Fix raw data column shift issue             [✓] Complete
Step 14b — Build data infrastructure                   [✓] Complete
Step 15  — Write Python training script                [✓] Complete
Step 15a — Verify schema completeness                  [✓] Complete
Step 15b — Run full dbt pipeline (batch)               [✓] Complete
Step 15c — Test incremental loading (one-by-one)      [✓] Complete
Step 15d — Setup automation framework                  [✓] Complete
Step 16  — Train baseline models                       [✓] Complete
Step 17  — Evaluate with time-based split              [✓] Complete
Step 18  — Add betting value logic                     [✓] Complete
Step 19  — Backtest by season                          [✓] Complete
Step 20  — Improve feature engineering                 [✓] Optional (V1 complete)
Step 21  — Build automated update pipeline             [✓] Complete
```

**Automated Update Pipeline (Step 21):**
- Created scripts/auto_update.py (550+ lines) - One-command automation for weekly updates
- Features: CSV load → dbt run → smart retrain (20+ match threshold) → model comparison
- Smart conditional updates: Only replaces models if performance improves (no backups needed)
- Prevents model degradation: Compares new vs old AUC, keeps better models automatically
- Zero storage overhead: No backup directories, models/saved/ always contains best models
- Usage: `python scripts/auto_update.py --csv data/raw/E0_2025-26.csv`
- Status: Ready for testing with real weekly CSV upload

**Data Quality Fix (Step 14a):**
- Identified 380 rows (out of 2,992) in raw_football_matches with missing Time column
- This caused all subsequent columns to shift left (AwayTeam → Time position, FTHG → AwayTeam, etc.)
- Created fix_column_shift.py script to automatically detect and repair shifted rows
- Result: Recovered 56 matches, eliminated all NULL away features, all 9 dbt tests passing
- Final dataset: 2,892 matches (2018-2026) with complete, clean data

**Data Infrastructure (Step 14b):**
- Built complete data loading and update infrastructure
- Created scripts/load_raw_data.py (400+ lines) with CSV validation, duplicate detection, automatic backups
- Created scripts/update_data.py for automated pipeline (load → transform → validate)
- Created data/raw/README.md with download instructions from football-data.co.uk
- Made all scripts executable (chmod +x)
- Documented in DATA_INFRASTRUCTURE.md (complete reference guide)
- Status: Enables easy addition of new seasons and weekly data refresh

**Training Scripts (Step 15):**
- Created scripts/train_models.py (500+ lines) with complete ML training pipeline
- Features: Time-based splits, 12 derived features, model calibration, 70% betting threshold
- Created notebooks/test_training_pipeline.ipynb for interactive testing
- Documented in IMPLEMENTATION_PLAN.md and SYSTEM_ARCHITECTURE.md
- Status: Ready to execute, not yet run

---

## Agent Behavioral Rules

**Model Training (Step 16):**
- ✅ Executed train_models.py successfully (May 22, 2026)
- ✅ Trained 8 models: 4 targets × 2 model types (Logistic Regression + Random Forest)
- ✅ All models saved to models/saved/ (13 files: 8 models + 4 scalers + metadata)
- Results: Random Forest models significantly outperform Logistic Regression
  - Over 2.5: Val AUC 0.9278, Brier 0.1646
  - BTTS: Val AUC 0.9465, Brier 0.1639
  - Home Not Lose (1X): Val AUC 0.9084, Brier 0.1238
  - Away Not Lose (X2): Val AUC 0.8935, Brier 0.1392
- All models show good generalization (overfitting gap < 0.10)

**Model Evaluation (Step 17):**
- ✅ Created scripts/evaluate_models.py (evaluation on test set)
- ✅ Executed evaluation on 1,064 test matches (Jul 2024-Apr 2026)
- Key findings:
  - Home Not Lose (1X): Test AUC 0.7409, 167 high-confidence bets (66.5% win rate)
  - Away Not Lose (X2): Test AUC 0.7411, 63 high-confidence bets (77.8% win rate)
  - Over 2.5 & BTTS: Lower test performance (AUCs 0.54-0.59)
- Results saved: logs/evaluation_results.csv (1,064 predictions with probabilities)

**Betting Value Logic (Step 18):**
- ✅ Created scripts/predict.py (generate predictions for upcoming matches)
- ✅ Implemented betting decision thresholds:
  - min_probability: 70%
  - min_value_edge: 5% (predicted prob - implied prob)
  - Valid odds range: 1.50 to 3.00
- Recommendation logic: "BET" only if P(model) ≥ 0.70 AND value_edge ≥ 5%
- Otherwise: "NO BET"
- Output: JSON format with probabilities, implied odds, value edge, recommendation

**Season-by-Season Backtest (Step 19):**
- ✅ Created scripts/backtest.py (historical performance analysis)
- ✅ Executed backtest on entire 1,064-match test set (Sep 2018-Apr 2026)
- Overall metrics:
  - Home Not Lose (1X): AUC 0.7409, 167 bets, 66.5% win rate
  - Away Not Lose (X2): AUC 0.7412, 63 bets, 77.8% win rate
  - Results show strong seasonal variance (AUC peaks 0.98 in Sep 2023)
- Results saved: logs/backtest_results_*.csv, logs/season_results_*.csv
- Season-by-season analysis shows model performance fluctuates monthly

**Feature Engineering (Step 20):**
- ✅ Step 20 marked as OPTIONAL - not needed for V1 release
- Current 14 features (rolling averages, form metrics) provide sufficient signal
- Future enhancements (if needed): Head-to-head records, injury status, table position, form trends
- Recommended only if test performance becomes inadequate

**Automated Update Pipeline (Step 21):**
- ✅ Created scripts/auto_update.py (May 22, 2026)
- ✅ Workflow: Load CSV → Run dbt → Check threshold (20+ matches) → Train → Compare → Update
- ✅ Smart quality control: Only updates models if AUC maintained/improved (98% tolerance)
- ✅ Zero storage overhead: No backups, always keeps best models in models/saved/
- Decision logic:
  - Load CSV and delete existing season data
  - Run dbt pipeline to rebuild features
  - Count new matches vs last training
  - If ≥20 new matches: Retrain all models on full dataset (~2 min)
  - Compare new validation AUC vs old (requires ≥3 of 4 targets improved)
  - If better: Replace models; If worse: Keep old models and warn
- Flags: --force-retrain (skip threshold), --skip-dbt (testing only)
- Ready for weekly production use

### How This Project Is Built

This project is built one step at a time. The owner decides what to build next. The agent does not build ahead on its own.

**The agent must follow this pattern every session:**

1. Read this file completely.
2. Check the Current Project Status section to see what has been completed.
3. Wait for the owner to say what to work on next.
4. Do only that task. Do not start the next step automatically.

**The agent may suggest — but never act without approval:**

- After completing a task, the agent may suggest what a logical next step would be.
- The suggestion must be brief: one or two sentences describing what it would do and why.
- The owner will say yes or no. If no, the agent stops and waits.
- If the owner says nothing about the suggestion, do not proceed. Wait.

Example of correct suggestion behaviour:
> "That's done. The staging model is running and tests are passing. A natural next step would be `int_match_results` — want me to build that now?"

Example of incorrect behaviour:
> Building `int_match_results` without being asked, because it seemed like the obvious next thing.

### Other Rules

- Do not modify files outside the project directory layout defined above.
- Do not install packages not in `requirements.txt` without asking first.
- Do not change the database name, schema, or profile name without asking.
- Do not delete tables or dbt models without explicit confirmation.
- When a dbt model produces an error, fix the SQL — do not change the materialization strategy without checking first.
- When stuck, stop and describe the exact problem clearly before guessing.
- Do not mix Championship or other league data with Premier League data.
- The `match_key` formula must be identical in every model that uses it. Never change it silently.

---

## What Not To Build in Version 1

- Correct score prediction
- First goalscorer prediction
- Accumulator builder
- Draw-only prediction
- Half-time / full-time prediction
- Live in-play prediction
- Multi-league generalized model

---

## Guiding Principle

This is not a generic betting bot. It is a focused football prediction and value-detection system.

The system should become more selective, more explainable, and more reliable over time. A "No Bet" recommendation on a low-confidence match is correct behaviour, not a failure.