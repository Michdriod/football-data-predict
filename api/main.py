#!/usr/bin/env python3
"""
Prediction App API

Serves the 85%+ picks for upcoming Premier League matches and their track
record, plus the built frontend. Picks are information, not betting advice.

Usage:
    uvicorn api.main:app --host 127.0.0.1 --port 8000

Author: Football Prediction System
Date: 2026-10-30
"""

import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from config import LOGS_DIR, PROJECT_ROOT
from fetch_odds import fetch_upcoming_fixtures, parse_odds_for_targets
from match_model import (
    MODEL_PATH, PICK_HISTORY_PATH, PICK_THRESHOLD, add_targets,
    load_bundle, load_matches, predict_fixtures, select_picks
)

logger = logging.getLogger(__name__)

FIXTURES_CACHE = LOGS_DIR / 'fixtures_cache.json'
ISSUED_PICKS = LOGS_DIR / 'issued_picks.csv'
FRONTEND_BUILD = PROJECT_ROOT / 'frontend' / 'dist'

# Each odds call uses 2 of the free plan's 500 monthly credits
FIXTURES_MAX_AGE = timedelta(hours=6)
DAYS_AHEAD = 7
STALE_DATA_DAYS = 10

# Which price applies to each market. Double chance has no direct price.
ODDS_KEYS = {
    'target_home_win': 'home_win',
    'target_away_win': 'away_win',
    'target_over_25': 'over_25',
    'target_home_win_or_draw': 'home_not_lose_1x',
    'target_away_win_or_draw': 'away_not_lose_x2'
}
CALCULATED_PRICES = {'target_home_win_or_draw', 'target_away_win_or_draw'}

app = FastAPI(title='Football Prediction App')


def pick_label(target, home_team, away_team):
    """Describe a pick in plain words."""
    return {
        'target_home_win': f'{home_team} to win',
        'target_away_win': f'{away_team} to win',
        'target_home_win_or_draw': f'{home_team} to win or draw',
        'target_away_win_or_draw': f'{away_team} to win or draw',
        'target_over_25': '3 or more goals',
        'target_btts_yes': 'Both teams to score'
    }[target]


def read_fixture_cache():
    if not FIXTURES_CACHE.exists():
        return None
    return json.loads(FIXTURES_CACHE.read_text())


def get_fixtures():
    """
    Return upcoming fixtures, calling the odds API at most every 6 hours.

    Returns:
        tuple: (cache dict or None, True if the latest refresh failed)
    """
    cache = read_fixture_cache()
    if cache:
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


def save_issued_picks(picks):
    """Record each pick the first time it is shown, so the live record cannot be rewritten."""
    if not picks:
        return

    new_picks = pd.DataFrame(picks)[['match_date', 'home_team', 'away_team', 'target', 'probability', 'price']]
    new_picks.insert(0, 'issued_at', datetime.now(timezone.utc).isoformat(timespec='seconds'))
    match_columns = ['match_date', 'home_team', 'away_team']

    if ISSUED_PICKS.exists():
        issued = pd.read_csv(ISSUED_PICKS, dtype={'match_date': str})
        seen = new_picks.merge(issued[match_columns], on=match_columns, how='left', indicator=True)
        new_picks = new_picks[(seen['_merge'] == 'left_only').values]
        new_picks = pd.concat([issued, new_picks], ignore_index=True)

    new_picks.to_csv(ISSUED_PICKS, index=False)


def live_record():
    """Score picks the app has actually shown against real results."""
    if not ISSUED_PICKS.exists():
        return {'issued': 0, 'settled': 0, 'correct': 0, 'recent': []}

    issued = pd.read_csv(ISSUED_PICKS, parse_dates=['match_date'])
    results = add_targets(load_matches())
    settled = issued.merge(results, on=['match_date', 'home_team', 'away_team'])
    rows = settled.to_dict('records')
    recent = [
        {
            'match_date': str(row['match_date'].date()),
            'match': f"{row['home_team']} vs {row['away_team']}",
            'pick': pick_label(row['target'], row['home_team'], row['away_team']),
            'probability': row['probability'],
            'score': f"{int(row['home_goals'])}-{int(row['away_goals'])}",
            'won': bool(row[row['target']])
        }
        for row in rows
    ]
    return {
        'issued': len(issued),
        'settled': len(recent),
        'correct': sum(pick['won'] for pick in recent),
        'recent': recent[::-1][:20]
    }


@app.get('/api/picks')
def get_picks():
    """Picks for the next 7 days. An empty list is a normal, honest answer."""
    if not MODEL_PATH.exists():
        raise HTTPException(status_code=503, detail='Model not trained. Run: python scripts/match_model.py --train')

    bundle = load_bundle()
    cache, refresh_failed = get_fixtures()
    fixtures = (cache or {}).get('fixtures', [])
    now = datetime.now(timezone.utc)
    fixtures = [f for f in fixtures
                if datetime.fromisoformat(f['commence_time'].replace('Z', '+00:00')) > now]

    picks = []
    if fixtures:
        frame = pd.DataFrame(fixtures)
        probabilities = predict_fixtures(bundle, frame)
        for index, pick in select_picks(probabilities).iterrows():
            fixture = fixtures[index]
            price = fixture['odds'].get(ODDS_KEYS.get(pick['target']))
            picks.append({
                'match_date': fixture['match_date'],
                'kickoff': fixture['commence_time'],
                'home_team': fixture['home_team'],
                'away_team': fixture['away_team'],
                'target': pick['target'],
                'pick': pick_label(pick['target'], fixture['home_team'], fixture['away_team']),
                'probability': round(float(pick['probability']), 4),
                'price': price,
                'price_is_calculated': pick['target'] in CALCULATED_PRICES
            })
        picks.sort(key=lambda p: p['kickoff'])
        save_issued_picks(picks)

    data_through = load_matches()['match_date'].max().date()
    return {
        'threshold': PICK_THRESHOLD,
        'matches_checked': len(fixtures),
        'picks': picks,
        'data_through': str(data_through),
        'data_is_stale': (now.date() - data_through).days > STALE_DATA_DAYS,
        'odds_checked_at': (cache or {}).get('fetched_at'),
        'odds_refresh_failed': refresh_failed
    }


@app.get('/api/track-record')
def get_track_record():
    """Past performance of the pick rule, and the record of picks actually shown."""
    live = live_record()
    if not PICK_HISTORY_PATH.exists():
        return {'tested': None, 'live': live}

    history = pd.read_csv(PICK_HISTORY_PATH)
    seasons = [
        {
            'season': f"{season}-{str(season + 1)[-2:]}",
            'picks': len(group),
            'correct': int(group['won'].sum()),
            'hit_rate': round(group['won'].mean(), 4)
        }
        for season, group in history.groupby('season')
    ]
    priced = history.dropna(subset=['fair_closing_odds'])
    return {
        'tested': {
            'picks': len(history),
            'correct': int(history['won'].sum()),
            'hit_rate': round(history['won'].mean(), 4),
            'first_date': history['match_date'].min(),
            'last_date': history['match_date'].max(),
            'typical_price': round(priced['fair_closing_odds'].median(), 2),
            'seasons': seasons
        },
        'live': live
    }


# Registered last so the /api routes above take priority
if FRONTEND_BUILD.exists():
    app.mount('/', StaticFiles(directory=FRONTEND_BUILD, html=True), name='frontend')
