#!/usr/bin/env python3
"""
Predict every market for every match in the coming week.

Updates results, retrains the model and saves injury news, then predicts all
fixtures at once. The app reads the same build_week() output.

Injury news is shown for context only. It does not change the probabilities,
because it cannot be tested until enough snapshots have been collected.

Usage:
    python scripts/predict_week.py              # update everything, then predict
    python scripts/predict_week.py --no-update  # predict from current data

Author: Football Prediction System
Date: 2026-10-30
"""

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import DBT_PROJECT_DIR, LOGS_DIR, PROJECT_ROOT
from fetch_odds import fetch_upcoming_fixtures, parse_odds_for_targets
from match_model import PICK_THRESHOLD, load_bundle, load_matches, predict_fixtures, select_picks, train
from snapshot_injuries import SNAPSHOT_PATH
from snapshot_injuries import main as save_injury_snapshot

logger = logging.getLogger(__name__)

FIXTURES_CACHE = LOGS_DIR / 'fixtures_cache.json'
ISSUED_PICKS = LOGS_DIR / 'issued_picks.csv'
WEEK_OUTPUT = LOGS_DIR / 'week_predictions.json'
UPDATE_LOG = LOGS_DIR / 'predict_week_update.log'

# Each odds call uses 2 of the free plan's 500 monthly credits
FIXTURES_MAX_AGE = timedelta(hours=6)
DAYS_AHEAD = 7
STALE_DATA_DAYS = 10

MIN_MINUTES_FOR_NEWS = 270     # three full matches; leaves out fringe players
PLAYERS_PER_TEAM = 3

# Caution label. Teams at these levels did about 2-4 points worse than predicted
# (Nov 2022 on), which is not proven, so it warns without changing probabilities.
CAUTION_REGULARS_OUT = 3
CAUTION_DEFENDERS_OUT = 2
REGULAR_START_SHARE = 0.5      # started at least half of this season's matches
MIN_MATCHES_FOR_CAUTION = 4

# Which price applies to each market. Double chance has no direct price.
ODDS_KEYS = {
    'target_home_win': 'home_win',
    'target_draw': 'draw',
    'target_away_win': 'away_win',
    'target_over_25': 'over_25',
    'target_home_win_or_draw': 'home_not_lose_1x',
    'target_away_win_or_draw': 'away_not_lose_x2'
}
CALCULATED_PRICES = {'target_home_win_or_draw', 'target_away_win_or_draw'}

# Display order for each match
MARKET_ORDER = [
    'target_home_win', 'target_draw', 'target_away_win',
    'target_home_win_or_draw', 'target_away_win_or_draw',
    'target_over_25', 'target_btts_yes', 'target_over_05_first_half'
]


def pick_label(target, home_team, away_team):
    """Describe a market in plain words."""
    return {
        'target_home_win': f'{home_team} to win',
        'target_draw': 'Draw',
        'target_away_win': f'{away_team} to win',
        'target_home_win_or_draw': f'{home_team} to win or draw',
        'target_away_win_or_draw': f'{away_team} to win or draw',
        'target_over_25': '3 or more goals',
        'target_btts_yes': 'Both teams to score',
        'target_over_05_first_half': 'Goal in the first half'
    }[target]

# ============================================================================
# DATA UPDATE
# ============================================================================

def current_season():
    """Season code for today, such as 2026-27. Seasons start in August."""
    today = datetime.now()
    start = today.year if today.month >= 8 else today.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def run_step(name, command, cwd):
    """Run one update step, logging output to a file so failures can be read later."""
    print(f"  {name}...", flush=True)
    with open(UPDATE_LOG, 'a') as log:
        result = subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        raise RuntimeError(f"{name} failed. See {UPDATE_LOG}")


def update_data():
    """Bring results, features, the model and injury news up to date."""
    print("\nUpdating data:")
    UPDATE_LOG.write_text('')
    python = sys.executable
    dbt = str(Path(python).parent / 'dbt')

    run_step('Loading latest results', [
        python, 'scripts/load_raw_data.py', '--data-dir', 'data/raw/',
        '--season', current_season(), '--auto-download', '--no-backup'
    ], PROJECT_ROOT)
    run_step('Rebuilding features', [dbt, 'run'], DBT_PROJECT_DIR)
    run_step('Checking data quality', [dbt, 'test'], DBT_PROJECT_DIR)

    print("  Retraining model...", flush=True)
    train()

    # Injury news is context, so a failure here should not stop the predictions
    try:
        save_injury_snapshot()
    except Exception:
        print("  ⚠️  Injury news could not be fetched")

# ============================================================================
# WEEK DATA
# ============================================================================

def get_fixtures(force_refresh=False):
    """
    Return upcoming fixtures, calling the odds API at most every 6 hours
    unless a refresh is forced.

    Returns:
        tuple: (cache dict or None, True if the latest refresh failed)
    """
    cache = json.loads(FIXTURES_CACHE.read_text()) if FIXTURES_CACHE.exists() else None
    if cache and not force_refresh:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(cache['fetched_at'])
        if age < FIXTURES_MAX_AGE:
            return cache, False

    try:
        fixtures = [parse_odds_for_targets(f) for f in fetch_upcoming_fixtures(days_ahead=DAYS_AHEAD)]
    except Exception:
        # The exception text can contain the request URL and API key, so it stays out of the response
        logger.error("Could not refresh fixtures from the odds API")
        return cache, True

    cache = {'fetched_at': datetime.now(timezone.utc).isoformat(), 'fixtures': fixtures}
    FIXTURES_CACHE.write_text(json.dumps(cache))
    return cache, False


def latest_likely_absentees():
    """
    Players in the newest snapshot who are likely to miss the next match.

    Returns:
        tuple: (DataFrame of players, snapshot time), both None without snapshots
    """
    if not SNAPSHOT_PATH.exists():
        return None, None

    flags = pd.read_csv(SNAPSHOT_PATH)
    latest = flags['snapshot_at'].max()
    flags = flags[flags['snapshot_at'] == latest]
    doubtful = (flags['status'] == 'd') & (flags['chance_next_round'].fillna(100) <= 50)
    return flags[flags['status'].isin(['i', 's']) | doubtful], latest


def team_cautions(absentees):
    """
    Warn about teams missing enough regulars to be worth a second look.

    Args:
        absentees (pd.DataFrame): Output of latest_likely_absentees()

    Returns:
        dict: Team name to caution text, only for teams that qualify
    """
    if absentees is None:
        return {}

    matches = load_matches()
    played_this_season = matches[matches['season'] == matches['season'].max()]
    games = pd.concat([played_this_season['home_team'], played_this_season['away_team']]).value_counts()

    cautions = {}
    for team, players in absentees.groupby('team'):
        played = games.get(team, 0)
        if played < MIN_MATCHES_FOR_CAUTION:
            continue
        regulars = players[players['starts'] >= played * REGULAR_START_SHARE]
        defenders = regulars[regulars['position'].isin(['DEF', 'GKP'])]

        reasons = []
        if len(regulars) >= CAUTION_REGULARS_OUT:
            reasons.append(f"{len(regulars)} regulars likely out")
        if len(defenders) >= CAUTION_DEFENDERS_OUT:
            reasons.append(f"{len(defenders)} defenders or keepers likely out")
        if reasons:
            cautions[team] = f"{team}: {' and '.join(reasons)}"
    return cautions


def get_injury_news(absentees):
    """
    Injury news for regular players, grouped by team.

    Args:
        absentees (pd.DataFrame): Output of latest_likely_absentees()

    Returns:
        dict: Team name to news list
    """
    if absentees is None:
        return {}

    regulars = absentees[absentees['minutes'] >= MIN_MINUTES_FOR_NEWS]

    return {
        team: [{'player': row.player, 'news': row.news if isinstance(row.news, str) else 'Unavailable'}
               for row in group.nlargest(PLAYERS_PER_TEAM, 'minutes').itertuples()]
        for team, group in regulars.groupby('team')
    }


def save_issued_picks(picks):
    """Record each pick the first time it is shown, so the live record cannot be rewritten."""
    if not picks:
        return

    new_picks = pd.DataFrame(picks)[['match_date', 'home_team', 'away_team', 'target', 'probability', 'price']]
    # Kept so flagged picks can be compared with unflagged ones later
    new_picks['had_caution'] = [bool(pick['cautions']) for pick in picks]
    new_picks.insert(0, 'issued_at', datetime.now(timezone.utc).isoformat(timespec='seconds'))
    match_columns = ['match_date', 'home_team', 'away_team']

    if ISSUED_PICKS.exists():
        issued = pd.read_csv(ISSUED_PICKS, dtype={'match_date': str})
        seen = new_picks.merge(issued[match_columns], on=match_columns, how='left', indicator=True)
        new_picks = new_picks[(seen['_merge'] == 'left_only').values]
        new_picks = pd.concat([issued, new_picks], ignore_index=True)

    new_picks.to_csv(ISSUED_PICKS, index=False)


def build_week(force_refresh=False):
    """
    Predict every market for every upcoming match.

    Returns:
        dict: Top picks, all matches and data freshness
    """
    bundle = load_bundle()
    cache, refresh_failed = get_fixtures(force_refresh)
    now = datetime.now(timezone.utc)
    fixtures = [f for f in (cache or {}).get('fixtures', [])
                if datetime.fromisoformat(f['commence_time'].replace('Z', '+00:00')) > now]
    fixtures.sort(key=lambda f: f['commence_time'])

    absentees, injuries_checked_at = latest_likely_absentees()
    injury_news = get_injury_news(absentees)
    cautions = team_cautions(absentees)
    matches, picks = [], []

    if fixtures:
        probabilities = predict_fixtures(bundle, pd.DataFrame(fixtures))
        selected = select_picks(probabilities)

        for index, fixture in enumerate(fixtures):
            home, away = fixture['home_team'], fixture['away_team']
            top_target = selected['target'].get(index)
            markets = [
                {
                    'target': target,
                    'label': pick_label(target, home, away),
                    'probability': round(float(probabilities.loc[index, target]), 4),
                    'price': fixture['odds'].get(ODDS_KEYS.get(target)),
                    'price_is_calculated': target in CALCULATED_PRICES,
                    'is_top_pick': target == top_target
                }
                for target in MARKET_ORDER
            ]
            match = {
                'match_date': fixture['match_date'],
                'kickoff': fixture['commence_time'],
                'home_team': home,
                'away_team': away,
                'markets': markets,
                'injuries': {'home': injury_news.get(home, []), 'away': injury_news.get(away, [])},
                'cautions': [cautions[team] for team in (home, away) if team in cautions]
            }
            matches.append(match)

            for market in markets:
                if market['is_top_pick']:
                    picks.append({
                        **market,
                        'pick': market['label'],
                        'match_date': match['match_date'],
                        'kickoff': match['kickoff'],
                        'home_team': home,
                        'away_team': away,
                        'cautions': match['cautions']
                    })

        save_issued_picks(picks)

    data_through = load_matches()['match_date'].max().date()
    return {
        'threshold': PICK_THRESHOLD,
        'matches_checked': len(fixtures),
        'picks': picks,
        'matches': matches,
        'data_through': str(data_through),
        'data_is_stale': (now.date() - data_through).days > STALE_DATA_DAYS,
        'odds_checked_at': (cache or {}).get('fetched_at'),
        'odds_refresh_failed': refresh_failed,
        'injuries_checked_at': injuries_checked_at
    }

# ============================================================================
# OUTPUT
# ============================================================================

def print_week(week):
    """Print the week's predictions."""
    print("\n" + "="*80)
    print(f"PREDICTIONS: {week['matches_checked']} matches, results up to {week['data_through']}")
    print("="*80)

    if week['data_is_stale']:
        print("\n⚠️  Results are out of date, so these chances may be too.")
    if week['odds_refresh_failed']:
        print("\n⚠️  Fixtures could not be refreshed. Using the last saved list.")

    print(f"\nTOP PICKS ({week['threshold']:.0%}+): {len(week['picks'])}")
    for pick in week['picks']:
        print(f"  {pick['home_team']} vs {pick['away_team']}: {pick['pick']} {pick['probability']:.0%}")
        for caution in pick['cautions']:
            print(f"    ⚠️  Caution: {caution}")

    for match in week['matches']:
        print(f"\n{match['match_date']}  {match['home_team']} vs {match['away_team']}")
        for caution in match['cautions']:
            print(f"  ⚠️  Caution: {caution}")
        for market in match['markets']:
            flag = '  <- top pick' if market['is_top_pick'] else ''
            print(f"  {market['label']:<40} {market['probability']:>4.0%}{flag}")
        for side in ('home', 'away'):
            for item in match['injuries'][side]:
                print(f"  Injury news: {item['player']}: {item['news']}")


def main():
    parser = argparse.ArgumentParser(description="Predict this week's matches")
    parser.add_argument('--no-update', action='store_true', help='Skip the data update and retrain')
    args = parser.parse_args()

    if not args.no_update:
        update_data()

    week = build_week(force_refresh=not args.no_update)
    WEEK_OUTPUT.write_text(json.dumps(week, indent=2))
    print_week(week)
    print(f"\n✓ Saved: {WEEK_OUTPUT}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
