#!/usr/bin/env python3
"""
Match Model: scoreline model + Elo + recent form, stacked per market.

Pipeline:
1. A time-decayed Poisson goal model (Dixon-Coles low-score adjustment) gives
   every market from one scoreline grid, so the probabilities stay coherent.
2. Elo ratings and exponentially weighted form add what the goal model misses.
3. A regularised logistic regression stacks them per market. It is trained only
   on goal-model output produced before each match, so nothing leaks.

Upcoming fixtures are appended to the match history and go through the same
feature code as training, so training and live inputs cannot drift apart.

Odds are NOT features. They are used only to benchmark against the market.

Usage:
    python scripts/match_model.py --evaluate    # walk-forward test vs the market
    python scripts/match_model.py --train       # fit and save models/saved/match_model.joblib

Author: Football Prediction System
Date: 2026-10-30
"""

import sys
import argparse
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
import joblib
from scipy import sparse
from scipy.stats import poisson
from sklearn.linear_model import LogisticRegression, PoissonRegressor
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import create_engine

warnings.filterwarnings('ignore')

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import get_db_connection_string, LOGS_DIR, MODELS_DIR

MODEL_PATH = MODELS_DIR / 'match_model.joblib'

# Goal model settings, tuned on seasons before 2025-26 only
GOAL_MODEL_CONFIG = {
    'decay_per_day': 0.0025,   # half-life of about 9 months
    'alpha': 0.01,             # L2 penalty on team strengths
    'rho': -0.08,              # Dixon-Coles low-score adjustment
    'window_days': 1400        # about four seasons
}

ELO_CONFIG = {
    'k': 22,
    'home_advantage': 62,
    'season_carry': 0.72,      # share of a team's rating kept over the summer
    'promoted_offset': -15     # promoted teams start just below the relegated three
}

FORM_HALF_LIFE = 6             # matches
STACK_C = 0.03                 # strong regularisation: the signal is weak and easy to overfit
MIN_STACK_ROWS = 500

STACK_FEATURES = [
    'elo_diff', 'form_points_diff', 'shots_on_target_diff', 'shots_on_target_against_diff',
    'total_shots_on_target', 'total_goals_against', 'total_goals_for',
    'home_form_corners_for', 'away_form_corners_for', 'rest_days_diff',
    'home_is_promoted', 'away_is_promoted'
]

# Stacked targets. Double chance is derived from these so the markets always agree.
BASE_TARGETS = {
    'target_over_25': 'goal_over_25',
    'target_btts_yes': 'goal_btts',
    'target_home_win': 'goal_home',
    'target_draw': 'goal_draw',
    'target_away_win': 'goal_away'
}

EVAL_DEV_START = '2021-08-01'
EVAL_HOLDOUT_START = '2025-08-01'

# ============================================================================
# DATA
# ============================================================================

def load_matches():
    """
    Load played matches from the staging view.

    Returns:
        pd.DataFrame: One row per match in kick-off order
    """
    engine = create_engine(get_db_connection_string())
    query = """
    SELECT match_date, match_time, home_team, away_team,
           full_time_home_goals AS home_goals, full_time_away_goals AS away_goals,
           home_shots, away_shots, home_shots_on_target, away_shots_on_target,
           home_corners, away_corners,
           avg_home_win_odds, avg_draw_odds, avg_away_win_odds,
           avg_over_25_odds, avg_under_25_odds,
           avg_closing_home_win_odds, avg_closing_draw_odds, avg_closing_away_win_odds,
           avg_closing_over_25_odds, avg_closing_under_25_odds
    FROM stg_football_matches
    """
    df = pd.read_sql_query(query, engine)
    engine.dispose()

    df['match_date'] = pd.to_datetime(df['match_date'])
    return sort_matches(df)


def sort_matches(df):
    """Sort chronologically and label each row with its season start year."""
    df = df.copy()
    df['_kickoff'] = df['match_time'].astype(str)
    df = df.sort_values(['match_date', '_kickoff', 'home_team'], kind='stable').reset_index(drop=True)
    df = df.drop(columns='_kickoff')
    df['season'] = df['match_date'].dt.year.where(df['match_date'].dt.month >= 8, df['match_date'].dt.year - 1)
    return df


def add_targets(df):
    """Add market outcomes for played matches."""
    df = df.copy()
    home, away = df['home_goals'], df['away_goals']
    df['target_over_25'] = (home + away >= 3).astype(int)
    df['target_btts_yes'] = ((home > 0) & (away > 0)).astype(int)
    df['target_home_win'] = (home > away).astype(int)
    df['target_draw'] = (home == away).astype(int)
    df['target_away_win'] = (home < away).astype(int)
    df['target_home_win_or_draw'] = (home >= away).astype(int)
    df['target_away_win_or_draw'] = (away >= home).astype(int)
    return df

# ============================================================================
# FEATURES (everything is known before kick-off)
# ============================================================================

def add_promoted_flags(df):
    """Flag teams that were not in the league the season before."""
    df = df.copy()
    teams_by_season = {s: set(g['home_team']) | set(g['away_team']) for s, g in df.groupby('season')}
    seasons = sorted(teams_by_season)
    previous = dict(zip(seasons[1:], seasons[:-1]))

    def flag(season, team):
        return int(season in previous and team not in teams_by_season[previous[season]])

    df['home_is_promoted'] = [flag(s, t) for s, t in zip(df['season'], df['home_team'])]
    df['away_is_promoted'] = [flag(s, t) for s, t in zip(df['season'], df['away_team'])]
    return df


def add_elo(df):
    """Add pre-match Elo ratings. Rows without a score (fixtures) do not update ratings."""
    df = df.copy()
    k, home_adv = ELO_CONFIG['k'], ELO_CONFIG['home_advantage']
    ratings, home_ratings, away_ratings = {}, [], []
    current_season, previous_teams, season_teams, start_rating = None, set(), set(), 1500.0

    for row in df.itertuples():
        if row.season != current_season:
            previous_teams, season_teams = season_teams, set()
            if previous_teams:
                mean = np.mean([ratings[t] for t in previous_teams])
                for team in ratings:
                    ratings[team] = mean + ELO_CONFIG['season_carry'] * (ratings[team] - mean)
                weakest = sorted(ratings[t] for t in previous_teams)[:3]
                start_rating = float(np.mean(weakest)) + ELO_CONFIG['promoted_offset']
            current_season = row.season

        for team in (row.home_team, row.away_team):
            if team not in previous_teams and team not in season_teams:
                ratings[team] = start_rating
            season_teams.add(team)

        home, away = ratings[row.home_team], ratings[row.away_team]
        home_ratings.append(home)
        away_ratings.append(away)

        if pd.isna(row.home_goals):
            continue

        expected = 1 / (1 + 10 ** (-(home + home_adv - away) / 400))
        result = 1 if row.home_goals > row.away_goals else 0.5 if row.home_goals == row.away_goals else 0
        margin = abs(row.home_goals - row.away_goals)
        weight = 1 if margin <= 1 else 1.5 if margin == 2 else (11 + margin) / 8
        change = k * weight * (result - expected)
        ratings[row.home_team] = home + change
        ratings[row.away_team] = away - change

    df['elo_diff'] = np.array(home_ratings) - np.array(away_ratings) + home_adv
    return df


def add_form(df):
    """Add exponentially weighted form. shift(1) keeps the current match out of its own window."""
    df = df.copy()
    shared = {'match_index': df.index, 'match_date': df['match_date']}
    home = pd.DataFrame({
        **shared, 'team': df['home_team'], 'is_home': 1,
        'goals_for': df['home_goals'], 'goals_against': df['away_goals'],
        'shots_on_target_for': df['home_shots_on_target'],
        'shots_on_target_against': df['away_shots_on_target'],
        'corners_for': df['home_corners']
    })
    away = pd.DataFrame({
        **shared, 'team': df['away_team'], 'is_home': 0,
        'goals_for': df['away_goals'], 'goals_against': df['home_goals'],
        'shots_on_target_for': df['away_shots_on_target'],
        'shots_on_target_against': df['home_shots_on_target'],
        'corners_for': df['away_corners']
    })
    teams = pd.concat([home, away]).sort_values(['match_date', 'match_index'], kind='stable')
    teams['points'] = np.where(
        teams['goals_for'].isna(), np.nan,
        np.select([teams['goals_for'] > teams['goals_against'],
                   teams['goals_for'] == teams['goals_against']], [3, 1], 0)
    )

    stats = ['goals_for', 'goals_against', 'shots_on_target_for', 'shots_on_target_against',
             'corners_for', 'points']
    grouped = teams.groupby('team', sort=False)
    for stat in stats:
        teams[f'form_{stat}'] = grouped[stat].transform(
            lambda s: s.shift(1).ewm(halflife=FORM_HALF_LIFE, min_periods=3).mean()
        )
    teams['rest_days'] = grouped['match_date'].diff().dt.days.clip(upper=14)

    columns = [f'form_{stat}' for stat in stats] + ['rest_days']
    home_form = teams[teams['is_home'] == 1].set_index('match_index')[columns].add_prefix('home_')
    away_form = teams[teams['is_home'] == 0].set_index('match_index')[columns].add_prefix('away_')
    df = df.join(home_form).join(away_form)

    df['form_points_diff'] = df['home_form_points'] - df['away_form_points']
    df['shots_on_target_diff'] = df['home_form_shots_on_target_for'] - df['away_form_shots_on_target_for']
    df['shots_on_target_against_diff'] = df['home_form_shots_on_target_against'] - df['away_form_shots_on_target_against']
    df['total_shots_on_target'] = df['home_form_shots_on_target_for'] + df['away_form_shots_on_target_for']
    df['total_goals_against'] = df['home_form_goals_against'] + df['away_form_goals_against']
    df['total_goals_for'] = df['home_form_goals_for'] + df['away_form_goals_for']
    df['rest_days_diff'] = df['home_rest_days'] - df['away_rest_days']
    return df


def build_features(df):
    """Run all feature steps. Used unchanged for training and for live fixtures."""
    return add_form(add_elo(add_promoted_flags(df)))

# ============================================================================
# GOAL MODEL
# ============================================================================

def goal_design_matrix(attack_ids, defence_ids, is_home, attack_promoted, defence_promoted, n_teams):
    """Build the attack/defence matrix. An id of -1 (unseen team) gets no strength term."""
    rows, cols = [], []
    for row, (attack, defence) in enumerate(zip(attack_ids, defence_ids)):
        if attack >= 0:
            rows.append(row)
            cols.append(attack)
        if defence >= 0:
            rows.append(row)
            cols.append(n_teams + defence)
    strengths = sparse.csr_matrix(
        (np.ones(len(rows)), (rows, cols)), shape=(len(attack_ids), 2 * n_teams)
    )
    extras = sparse.csr_matrix(np.column_stack([is_home, attack_promoted, defence_promoted]))
    return sparse.hstack([strengths, extras]).tocsr()


def fit_goal_model(history, as_of):
    """
    Fit time-decayed Poisson goal rates on matches before as_of.

    Args:
        history (pd.DataFrame): Played matches with promoted flags
        as_of (pd.Timestamp): Date the fit is made on

    Returns:
        dict: Fitted model and the team index it uses
    """
    config = GOAL_MODEL_CONFIG
    train = history[history['match_date'] > as_of - pd.Timedelta(days=config['window_days'])]
    teams = sorted(set(train['home_team']) | set(train['away_team']))
    team_index = {team: i for i, team in enumerate(teams)}
    home_ids = train['home_team'].map(team_index).values
    away_ids = train['away_team'].map(team_index).values
    weights = np.exp(-config['decay_per_day'] * (as_of - train['match_date']).dt.days.values)

    X = sparse.vstack([
        goal_design_matrix(home_ids, away_ids, np.ones(len(train)),
                           train['home_is_promoted'].values, train['away_is_promoted'].values, len(teams)),
        goal_design_matrix(away_ids, home_ids, np.zeros(len(train)),
                           train['away_is_promoted'].values, train['home_is_promoted'].values, len(teams))
    ])
    y = np.r_[train['home_goals'].values, train['away_goals'].values]
    model = PoissonRegressor(alpha=config['alpha'], max_iter=300, solver='newton-cholesky')
    model.fit(X, y, sample_weight=np.r_[weights, weights])
    return {'model': model, 'team_index': team_index}


def market_probabilities(home_rate, away_rate, rho):
    """Turn two goal rates into market probabilities via the scoreline grid."""
    goals = np.arange(11)
    grid = np.outer(poisson.pmf(goals, home_rate), poisson.pmf(goals, away_rate))
    grid[0, 0] *= 1 - home_rate * away_rate * rho
    grid[0, 1] *= 1 + home_rate * rho
    grid[1, 0] *= 1 + away_rate * rho
    grid[1, 1] *= 1 - rho
    grid = np.clip(grid, 1e-12, None)
    grid /= grid.sum()

    home, away = np.indices(grid.shape)
    return {
        'goal_over_25': grid[home + away >= 3].sum(),
        'goal_btts': grid[(home > 0) & (away > 0)].sum(),
        'goal_home': grid[home > away].sum(),
        'goal_draw': grid[home == away].sum(),
        'goal_away': grid[home < away].sum()
    }


def apply_goal_model(goal_model, frame):
    """Score matches with a fitted goal model."""
    team_index = goal_model['team_index']
    n_teams = len(team_index)
    home_ids = frame['home_team'].map(team_index).fillna(-1).astype(int).values
    away_ids = frame['away_team'].map(team_index).fillna(-1).astype(int).values

    home_rates = goal_model['model'].predict(goal_design_matrix(
        home_ids, away_ids, np.ones(len(frame)),
        frame['home_is_promoted'].values, frame['away_is_promoted'].values, n_teams))
    away_rates = goal_model['model'].predict(goal_design_matrix(
        away_ids, home_ids, np.zeros(len(frame)),
        frame['away_is_promoted'].values, frame['home_is_promoted'].values, n_teams))

    probabilities = [market_probabilities(h, a, GOAL_MODEL_CONFIG['rho'])
                     for h, a in zip(home_rates, away_rates)]
    return pd.DataFrame(probabilities, index=frame.index)


def out_of_sample_goal_probabilities(df, start_season):
    """Refit the goal model weekly and score each week using earlier matches only."""
    scored = []
    upcoming = df[df['season'] >= start_season]
    for _, week in upcoming.groupby(pd.Grouper(key='match_date', freq='W-TUE')):
        if week.empty:
            continue
        as_of = week['match_date'].min()
        goal_model = fit_goal_model(df[df['match_date'] < as_of], as_of)
        scored.append(apply_goal_model(goal_model, week))
    return pd.concat(scored)

# ============================================================================
# STACKING
# ============================================================================

def logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def stack_inputs(frame, goal_column):
    """Stacker inputs for one market."""
    inputs = frame[STACK_FEATURES].copy()
    inputs['goal_model_logit'] = logit(frame[goal_column].values)
    return inputs


def fit_stacker(train, target, goal_column):
    """Fit one market's stacker. Medians fill form gaps for teams with too few matches."""
    inputs = stack_inputs(train, goal_column)
    medians = inputs.median()
    model = make_pipeline(StandardScaler(), LogisticRegression(C=STACK_C, max_iter=500))
    model.fit(inputs.fillna(medians), train[target].values)
    return {'model': model, 'medians': medians}


def apply_stacker(stacker, frame, goal_column):
    inputs = stack_inputs(frame, goal_column).fillna(stacker['medians'])
    return stacker['model'].predict_proba(inputs)[:, 1]


def stacked_market_probabilities(stackers, frame):
    """Score all markets. 1X2 is normalised and double chance derived from it."""
    out = pd.DataFrame(index=frame.index)
    for target, goal_column in BASE_TARGETS.items():
        out[target] = apply_stacker(stackers[target], frame, goal_column)

    result = out[['target_home_win', 'target_draw', 'target_away_win']]
    out[result.columns] = result.div(result.sum(axis=1), axis=0)
    out['target_home_win_or_draw'] = 1 - out['target_away_win']
    out['target_away_win_or_draw'] = 1 - out['target_home_win']
    return out

# ============================================================================
# EVALUATION
# ============================================================================

def score(y, p):
    return {
        'matches': len(y),
        'log_loss': log_loss(y, np.clip(p, 1e-6, 1 - 1e-6)),
        'brier': brier_score_loss(y, p),
        'auc': roc_auc_score(y, p),
        'accuracy': accuracy_score(y, p >= 0.5)
    }


def market_benchmarks(df):
    """Bookmaker probabilities with the margin removed."""
    out = pd.DataFrame(index=df.index)
    for label, columns in (('opening', ('avg_home_win_odds', 'avg_draw_odds', 'avg_away_win_odds',
                                        'avg_over_25_odds', 'avg_under_25_odds')),
                           ('closing', ('avg_closing_home_win_odds', 'avg_closing_draw_odds',
                                        'avg_closing_away_win_odds', 'avg_closing_over_25_odds',
                                        'avg_closing_under_25_odds'))):
        home, draw, away, over, under = (1 / df[column].astype(float) for column in columns)
        book = home + draw + away
        out[f'{label}|target_home_win'] = home / book
        out[f'{label}|target_draw'] = draw / book
        out[f'{label}|target_away_win'] = away / book
        out[f'{label}|target_home_win_or_draw'] = (home + draw) / book
        out[f'{label}|target_away_win_or_draw'] = (away + draw) / book
        out[f'{label}|target_over_25'] = over / (over + under)
    return out


def walk_forward(df):
    """Predict every match from 2021-22 on, refitting stackers every 28 days."""
    predictions = []
    upcoming = df[df['match_date'] >= EVAL_DEV_START]
    for _, block in upcoming.groupby(pd.Grouper(key='match_date', freq='28D')):
        if block.empty:
            continue
        train = df[df['match_date'] < block['match_date'].min()].dropna(subset=['goal_home'])
        if len(train) < MIN_STACK_ROWS:
            continue
        stackers = {target: fit_stacker(train, target, goal_column)
                    for target, goal_column in BASE_TARGETS.items()}
        predictions.append(stacked_market_probabilities(stackers, block))
    return pd.concat(predictions)


def evaluate():
    """Compare the model with the market on the development and holdout periods."""
    print("\nLoading matches and building features...")
    df = add_targets(build_features(load_matches()))
    print(f"✓ {len(df):,} matches to {df['match_date'].max().date()}")

    print("Scoring the goal model week by week (earlier matches only)...")
    goal_probabilities = out_of_sample_goal_probabilities(df, df['season'].min() + 1)
    df = df.join(goal_probabilities)

    print("Walking the stacker forward...")
    model_probabilities = walk_forward(df)
    benchmarks = market_benchmarks(df)
    goal_columns = {**BASE_TARGETS,
                    'target_home_win_or_draw': None, 'target_away_win_or_draw': None}

    rows = []
    for period, mask in (('development', df['match_date'] < EVAL_HOLDOUT_START),
                         ('holdout', df['match_date'] >= EVAL_HOLDOUT_START)):
        index = model_probabilities.index.intersection(df.index[mask])
        for target, goal_column in goal_columns.items():
            y = df.loc[index, target]
            rows.append({'period': period, 'target': target, 'model': 'match_model',
                         **score(y, model_probabilities.loc[index, target])})
            if goal_column:
                rows.append({'period': period, 'target': target, 'model': 'goal_model_only',
                             **score(y, df.loc[index, goal_column])})
            for label in ('opening', 'closing'):
                column = f'{label}|{target}'
                if column in benchmarks:
                    priced = benchmarks.loc[index, column].dropna()
                    rows.append({'period': period, 'target': target, 'model': f'market_{label}',
                                 **score(y.loc[priced.index], priced)})

    results = pd.DataFrame(rows)
    output_path = LOGS_DIR / 'match_model_evaluation.csv'
    results.to_csv(output_path, index=False)

    pd.set_option('display.width', 160)
    for period, group in results.groupby('period', sort=False):
        print(f"\n{period.upper()}")
        print(group.drop(columns='period').round(4).to_string(index=False))
    print(f"\n✓ Saved: {output_path}")
    return results

# ============================================================================
# TRAINING AND PREDICTION
# ============================================================================

def train():
    """Fit on all played matches and save the bundle predict.py loads."""
    print("\nLoading matches and building features...")
    df = add_targets(build_features(load_matches()))
    print(f"✓ {len(df):,} matches to {df['match_date'].max().date()}")

    print("Building leak-free stacker training data...")
    df = df.join(out_of_sample_goal_probabilities(df, df['season'].min() + 1))
    stack_data = df.dropna(subset=['goal_home'])
    stackers = {target: fit_stacker(stack_data, target, goal_column)
                for target, goal_column in BASE_TARGETS.items()}

    as_of = df['match_date'].max() + pd.Timedelta(days=1)
    bundle = {
        'goal_model': fit_goal_model(df, as_of),
        'stackers': stackers,
        'trained_at': datetime.now().isoformat(timespec='seconds'),
        'trained_through': str(df['match_date'].max().date()),
        'matches': len(df),
        'stack_rows': len(stack_data)
    }
    joblib.dump(bundle, MODEL_PATH)
    print(f"✓ Saved: {MODEL_PATH} (stacker rows: {len(stack_data):,})")
    return bundle


def load_bundle():
    """Load the saved model, or raise with the command that creates it."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"{MODEL_PATH} not found. Run: python scripts/match_model.py --train")
    return joblib.load(MODEL_PATH)


def predict_fixtures(bundle, fixtures):
    """
    Predict upcoming matches using all results in the database.

    Args:
        bundle (dict): Output of load_bundle()
        fixtures (pd.DataFrame): Columns home_team, away_team, match_date

    Returns:
        pd.DataFrame: One probability column per target, aligned to fixtures
    """
    matches = load_matches()
    known_teams = set(matches['home_team']) | set(matches['away_team'])
    unknown = (set(fixtures['home_team']) | set(fixtures['away_team'])) - known_teams
    if unknown:
        raise ValueError(f"Unknown team names (check data/team_name_mapping.json): {sorted(unknown)}")

    upcoming = fixtures[['home_team', 'away_team', 'match_date']].copy()
    upcoming['match_date'] = pd.to_datetime(upcoming['match_date'])
    upcoming['fixture_id'] = fixtures.index

    combined = sort_matches(pd.concat([matches, upcoming], ignore_index=True))
    featured = build_features(combined)
    frame = featured[featured['fixture_id'].notna()].copy()
    frame = frame.join(apply_goal_model(bundle['goal_model'], frame))

    probabilities = stacked_market_probabilities(bundle['stackers'], frame)
    probabilities.index = frame['fixture_id'].astype(fixtures.index.dtype).values
    return probabilities.loc[fixtures.index]


def main():
    parser = argparse.ArgumentParser(description='Train or evaluate the match model')
    parser.add_argument('--train', action='store_true', help='Fit on all data and save the model')
    parser.add_argument('--evaluate', action='store_true', help='Walk-forward test against the market')
    args = parser.parse_args()

    if not args.train and not args.evaluate:
        parser.print_help()
        return 0
    if args.evaluate:
        evaluate()
    if args.train:
        train()
    return 0


if __name__ == '__main__':
    sys.exit(main())
