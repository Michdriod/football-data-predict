#!/usr/bin/env python3
"""
Fetch live odds from The Odds API for upcoming Premier League matches.

This module provides functions to:
1. Fetch upcoming EPL fixtures with odds from The Odds API
2. Parse odds data for our prediction targets
3. Map team names from API format to database format

API Documentation: https://the-odds-api.com/liveapi/guides/v4/

Usage:
    from fetch_odds import fetch_upcoming_fixtures, parse_odds_for_targets
    
    fixtures = fetch_upcoming_fixtures(days_ahead=7)
    for fixture in fixtures:
        odds = parse_odds_for_targets(fixture)

Author: Football Prediction System
Date: 2026-05-22
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
import logging
from datetime import timezone

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import get_env_var, PROJECT_ROOT

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

ODDS_API_KEY = get_env_var('ODDS_API_KEY', required=True)
ODDS_API_BASE_URL = get_env_var('ODDS_API_BASE_URL', 'https://api.the-odds-api.com/v4', required=False)
ODDS_SPORT_KEY = get_env_var('ODDS_SPORT_KEY', 'soccer_epl', required=False)
ODDS_REGIONS = get_env_var('ODDS_REGIONS', 'uk', required=False)
ODDS_MARKETS = get_env_var('ODDS_MARKETS', 'h2h,totals,btts', required=False)
ODDS_FORMAT = get_env_var('ODDS_FORMAT', 'decimal', required=False)
ODDS_BOOKMAKER_PREFERENCE = get_env_var('ODDS_BOOKMAKER_PREFERENCE', 'bet365', required=False)
ODDS_BOOKMAKER_FALLBACK = get_env_var('ODDS_BOOKMAKER_FALLBACK', 'livescorebet', required=False)

TEAM_MAPPING_FILE = PROJECT_ROOT / 'data' / 'team_name_mapping.json'

# ============================================================================
# TEAM NAME MAPPING
# ============================================================================

def load_team_mapping():
    """
    Load team name mapping from JSON file.
    
    Maps API team names (full names) to database team names (shortened).
    Example: "Manchester United" → "Man United"
    
    Returns:
        dict: API name → Database name mapping
    """
    if not TEAM_MAPPING_FILE.exists():
        logger.warning(f"Team mapping file not found: {TEAM_MAPPING_FILE}")
        logger.warning("Using team names as-is from API. Create mapping file if names don't match.")
        return {}
    
    try:
        with open(TEAM_MAPPING_FILE, 'r') as f:
            mapping_data = json.load(f)
            return mapping_data.get('api_to_database', {})
    except Exception as e:
        logger.error(f"Error loading team mapping: {e}")
        return {}

def map_team_name(api_name, mapping):
    """
    Map API team name to database team name.
    
    Args:
        api_name: Team name from API
        mapping: Team name mapping dict
        
    Returns:
        str: Database team name (or original if no mapping found)
    """
    db_name = mapping.get(api_name, api_name)
    if db_name != api_name:
        logger.debug(f"Mapped team: '{api_name}' → '{db_name}'")
    return db_name

# ============================================================================
# API CALLS
# ============================================================================

def fetch_upcoming_fixtures(days_ahead=7):
    """
    Fetch upcoming Premier League fixtures with odds from The Odds API.
    
    API Endpoint: GET /v4/sports/{sport}/odds
    Documentation: https://the-odds-api.com/liveapi/guides/v4/#get-odds
    
    Args:
        days_ahead: Number of days ahead to fetch (default: 7)
        
    Returns:
        list: List of fixture dicts with odds data
        
    Raises:
        requests.exceptions.RequestException: If API call fails
    """
    url = f"{ODDS_API_BASE_URL}/sports/{ODDS_SPORT_KEY}/odds"
    
    params = {
        'apiKey': ODDS_API_KEY,
        'regions': ODDS_REGIONS,
        'markets': ODDS_MARKETS,
        'oddsFormat': ODDS_FORMAT,
        'dateFormat': 'iso'
    }
    
    logger.info(f"📡 Fetching upcoming {ODDS_SPORT_KEY} fixtures from The Odds API...")
    logger.info(f"   Markets: {ODDS_MARKETS}")
    logger.info(f"   Regions: {ODDS_REGIONS}")
    logger.info(f"   Days ahead: {days_ahead}")
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        fixtures = response.json()
        
        # Filter to only upcoming matches within days_ahead
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days_ahead)
        
        filtered_fixtures = []
        for fixture in fixtures:
            commence_time = datetime.fromisoformat(fixture['commence_time'].replace('Z', '+00:00'))
            if now <= commence_time <= cutoff:
                filtered_fixtures.append(fixture)
        
        # Log API usage from response headers
        remaining = response.headers.get('x-requests-remaining', 'N/A')
        used = response.headers.get('x-requests-used', 'N/A')
        last_cost = response.headers.get('x-requests-last', 'N/A')
        
        logger.info(f"✅ Fetched {len(fixtures)} fixtures (filtered to {len(filtered_fixtures)} within {days_ahead} days)")
        logger.info(f"   API Usage - Remaining: {remaining}, Used: {used}, Last Cost: {last_cost}")
        
        return filtered_fixtures
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ API request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            if e.response.status_code == 401:
                logger.error("   Invalid API key. Check ODDS_API_KEY in .env file")
            elif e.response.status_code == 429:
                logger.error("   Rate limit exceeded. Try again later or upgrade plan")
            elif e.response.status_code == 422:
                logger.error("   Invalid parameters. Check sport key, regions, markets")
        else:
            # Network error (no response received)
            logger.error("   Network error - check your internet connection")
        raise

# ============================================================================
# ODDS PARSING
# ============================================================================

def parse_odds_for_targets(fixture, bookmaker_preference=None):
    """
    Extract odds for our prediction targets from API fixture.
    
    Extracts odds for:
    - Over 2.5 Goals (totals market)
    - Both Teams To Score (btts market)  
    - Home Not Lose / Away Not Lose (derived from h2h market)
    
    Args:
        fixture: Fixture dict from API
        bookmaker_preference: Preferred bookmaker (default: from .env)
        
    Returns:
        dict: Parsed odds with match info
    """
    # Use config value if not explicitly provided
    if bookmaker_preference is None:
        bookmaker_preference = ODDS_BOOKMAKER_PREFERENCE
    team_mapping = load_team_mapping()
    
    # Map team names to database format
    home_team = map_team_name(fixture['home_team'], team_mapping)
    away_team = map_team_name(fixture['away_team'], team_mapping)
    
    # Extract match info
    match_date = fixture['commence_time'][:10]  # YYYY-MM-DD
    match_time = fixture['commence_time'][11:19]  # HH:MM:SS
    
    odds_data = {
        'match_date': match_date,
        'match_time': match_time,
        'commence_time': fixture['commence_time'],  # Full ISO timestamp
        'home_team': home_team,
        'away_team': away_team,
        'api_home_team': fixture['home_team'],  # Original for debugging
        'api_away_team': fixture['away_team'],
        'event_id': fixture.get('id', ''),  # API event ID
        'odds': {},
        'metadata': {}  # For market-specific timestamps
    }
    
    # Find bookmaker with all required markets
    bookmakers = fixture.get('bookmakers', [])
    if not bookmakers:
        logger.warning(f"No bookmakers found for {home_team} vs {away_team}")
        return odds_data
    
    # Required markets for our predictions
    required_markets = {'h2h', 'totals'}
    
    # Filter bookmakers that have all required markets
    bookmakers_with_all_markets = []
    for b in bookmakers:
        market_keys = {m['key'] for m in b.get('markets', [])}
        if required_markets.issubset(market_keys):
            bookmakers_with_all_markets.append(b)
    
    # Try preferred bookmaker first (if it has all markets)
    bookmaker = None
    if bookmakers_with_all_markets:
        bookmaker = next(
            (b for b in bookmakers_with_all_markets if b['key'] == bookmaker_preference),
            None
        )
        
        # If preferred not found, try fallback
        if bookmaker is None:
            bookmaker = next(
                (b for b in bookmakers_with_all_markets if b['key'] == ODDS_BOOKMAKER_FALLBACK),
                bookmakers_with_all_markets[0]  # Use first bookmaker with all markets
            )
    else:
        # No bookmaker has all markets - use any bookmaker (partial data)
        logger.warning(f"No bookmaker has all required markets for {home_team} vs {away_team}")
        bookmaker = next(
            (b for b in bookmakers if b['key'] == bookmaker_preference),
            bookmakers[0]
        )
    
    used_bookmaker = bookmaker['key']
    bookmaker_title = bookmaker.get('title', used_bookmaker)
    bookmaker_link = bookmaker.get('link', '')
    bookmaker_last_update = bookmaker.get('last_update', '')
    
    if used_bookmaker != bookmaker_preference:
        logger.debug(f"Using {bookmaker_title} ({used_bookmaker}) odds (preferred {bookmaker_preference} not available with all markets)")
    
    # Parse markets
    markets = bookmaker.get('markets', [])
    
    for market in markets:
        market_key = market['key']
        outcomes = market['outcomes']
        market_last_update = market.get('last_update', '')
        
        # Match Result (h2h) - for Home Not Lose / Away Not Lose
        if market_key == 'h2h':
            odds_data['metadata']['h2h_last_update'] = market_last_update
            for outcome in outcomes:
                if outcome['name'] == fixture['home_team']:
                    odds_data['odds']['home_win'] = outcome['price']
                elif outcome['name'] == fixture['away_team']:
                    odds_data['odds']['away_win'] = outcome['price']
                elif outcome['name'] == 'Draw':
                    odds_data['odds']['draw'] = outcome['price']
        
        # Over/Under 2.5 Goals (totals)
        elif market_key == 'totals':
            odds_data['metadata']['totals_last_update'] = market_last_update
            for outcome in outcomes:
                # Check if it's 2.5 goals market
                point = outcome.get('point', 0)
                if point == 2.5:
                    if outcome['name'] == 'Over':
                        odds_data['odds']['over_25'] = outcome['price']
                    elif outcome['name'] == 'Under':
                        odds_data['odds']['under_25'] = outcome['price']
        
        # Both Teams To Score (btts) - NOT available from UK bookmakers via API
        # We'll need to calculate this from individual match predictions
        elif market_key == 'btts':
            odds_data['metadata']['btts_last_update'] = market_last_update
            for outcome in outcomes:
                if outcome['name'] == 'Yes':
                    odds_data['odds']['btts_yes'] = outcome['price']
                elif outcome['name'] == 'No':
                    odds_data['odds']['btts_no'] = outcome['price']
    
    # Calculate Double Chance odds (if we have h2h odds)
    if all(k in odds_data['odds'] for k in ['home_win', 'draw', 'away_win']):
        home_prob = 1.0 / odds_data['odds']['home_win']
        draw_prob = 1.0 / odds_data['odds']['draw']
        away_prob = 1.0 / odds_data['odds']['away_win']
        
        home_not_lose_prob = home_prob + draw_prob
        away_not_lose_prob = away_prob + draw_prob
        
        odds_data['odds']['home_not_lose_1x'] = round(1.0 / home_not_lose_prob, 2)
        odds_data['odds']['away_not_lose_x2'] = round(1.0 / away_not_lose_prob, 2)
    
    # Add bookmaker metadata (matching API schema)
    odds_data['bookmaker'] = used_bookmaker
    odds_data['bookmaker_title'] = bookmaker_title
    odds_data['bookmaker_link'] = bookmaker_link
    odds_data['bookmaker_last_update'] = bookmaker_last_update
    
    return odds_data
