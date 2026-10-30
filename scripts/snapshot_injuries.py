#!/usr/bin/env python3
"""
Save a snapshot of Fantasy Premier League injury and availability flags.

Past flags are not published anywhere, so they can only be tested as a model
input if they are collected before the matches happen. Each run appends every
flagged player, with their season stats as they stood at that moment.

A player missing from a later snapshot means their flag was cleared.

Usage:
    python scripts/snapshot_injuries.py

Author: Football Prediction System
Date: 2026-10-30
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import DATA_DIR

FPL_URL = 'https://fantasy.premierleague.com/api/bootstrap-static/'
SNAPSHOT_PATH = DATA_DIR / 'fpl_injury_flags.csv'

# FPL names that differ from the names in our match data
TEAM_NAMES = {
    'Man Utd': 'Man United',
    'Spurs': 'Tottenham',
    'Sheffield Utd': 'Sheffield United',
    'Coventry City': 'Coventry',
    'Hull City': 'Hull',
    'Ipswich Town': 'Ipswich'
}


def fetch_flags():
    """
    Fetch all players who have an availability flag or news item.

    Returns:
        pd.DataFrame: One row per flagged player
    """
    response = requests.get(FPL_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
    response.raise_for_status()
    data = response.json()

    teams = {team['id']: team['name'] for team in data['teams']}
    positions = {position['id']: position['singular_name_short'] for position in data['element_types']}
    snapshot_at = datetime.now(timezone.utc).isoformat(timespec='seconds')

    flagged = [
        {
            'snapshot_at': snapshot_at,
            'team': TEAM_NAMES.get(teams[player['team']], teams[player['team']]),
            'player_id': player['id'],
            'player': player['web_name'],
            'position': positions[player['element_type']],
            'status': player['status'],
            'chance_this_round': player['chance_of_playing_this_round'],
            'chance_next_round': player['chance_of_playing_next_round'],
            'news': player['news'],
            'news_added': player['news_added'],
            'minutes': player['minutes'],
            'starts': player['starts'],
            'expected_goals': player['expected_goals'],
            'expected_assists': player['expected_assists'],
            'now_cost': player['now_cost']
        }
        for player in data['elements']
        if player['status'] != 'a' or player['news']
    ]
    return pd.DataFrame(flagged)


def main():
    flags = fetch_flags()
    if flags.empty:
        print("⚠️  No flagged players returned, nothing saved")
        return 0

    flags.to_csv(SNAPSHOT_PATH, mode='a', header=not SNAPSHOT_PATH.exists(), index=False)
    print(f"✓ Saved {len(flags):,} flagged players to {SNAPSHOT_PATH.name}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
