#!/usr/bin/env python3
"""
Prediction App API

Serves the week's predictions and the track record, plus the built frontend.
Predictions are information, not betting advice.

Usage:
    uvicorn api.main:app --host 127.0.0.1 --port 8000

Author: Football Prediction System
Date: 2026-10-30
"""

import sys
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from config import PROJECT_ROOT
from match_model import MODEL_PATH, PICK_HISTORY_PATH, add_targets, load_matches
from predict_week import ISSUED_PICKS, build_week, pick_label

FRONTEND_BUILD = PROJECT_ROOT / 'frontend' / 'dist'

app = FastAPI(title='Football Prediction App')


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


@app.get('/api/week')
def get_week():
    """Every market for every match in the next 7 days, plus any 85%+ picks."""
    if not MODEL_PATH.exists():
        raise HTTPException(status_code=503, detail='Model not trained. Run: python scripts/match_model.py --train')
    return build_week()


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
