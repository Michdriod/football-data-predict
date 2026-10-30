{{
    config(
        materialized='table',
        indexes=[
            {'columns': ['match_key'], 'unique': True},
        ]
    )
}}

select
    -- Match identifiers
    base.match_key,
    base.league_code,
    base.match_date,
    base.home_team,
    base.away_team,

    -- Base home team features (last 5 matches)
    base.home_matches_played_before,
    base.home_avg_goals_for_last_5,
    base.home_avg_goals_against_last_5,
    base.home_avg_shots_for_last_5,
    base.home_avg_shots_on_target_for_last_5,
    base.home_avg_corners_for_last_5,
    base.home_avg_points_last_5,
    base.home_over_25_rate_last_5,
    base.home_btts_rate_last_5,
    base.home_clean_sheet_rate_last_5,
    base.home_failed_to_score_rate_last_5,

    -- Base home team features (last 10 matches)
    base.home_avg_goals_for_last_10,
    base.home_avg_goals_against_last_10,
    base.home_over_25_rate_last_10,
    base.home_btts_rate_last_10,

    -- Goal-specific features for home team
    base.home_shot_efficiency_last_5,
    base.home_shot_on_target_efficiency_last_5,
    base.home_defensive_solidity_last_5,
    base.home_avg_shots_against_last_5,
    base.home_avg_shots_on_target_against_last_5,
    base.home_goal_scoring_variance_last_5,
    base.home_goal_conceding_variance_last_5,
    base.home_avg_goals_for_home_last_5,
    base.home_avg_goals_for_away_last_5,
    base.home_avg_goals_against_home_last_5,
    base.home_avg_goals_against_away_last_5,

    -- Base away team features (last 5 matches)
    base.away_matches_played_before,
    base.away_avg_goals_for_last_5,
    base.away_avg_goals_against_last_5,
    base.away_avg_shots_for_last_5,
    base.away_avg_shots_on_target_for_last_5,
    base.away_avg_corners_for_last_5,
    base.away_avg_points_last_5,
    base.away_over_25_rate_last_5,
    base.away_btts_rate_last_5,
    base.away_clean_sheet_rate_last_5,
    base.away_failed_to_score_rate_last_5,

    -- Base away team features (last 10 matches)
    base.away_avg_goals_for_last_10,
    base.away_avg_goals_against_last_10,
    base.away_over_25_rate_last_10,
    base.away_btts_rate_last_10,

    -- Goal-specific features for away team
    base.away_shot_efficiency_last_5,
    base.away_shot_on_target_efficiency_last_5,
    base.away_defensive_solidity_last_5,
    base.away_avg_shots_against_last_5,
    base.away_avg_shots_on_target_against_last_5,
    base.away_goal_scoring_variance_last_5,
    base.away_goal_conceding_variance_last_5,
    base.away_avg_goals_for_home_last_5,
    base.away_avg_goals_for_away_last_5,
    base.away_avg_goals_against_home_last_5,
    base.away_avg_goals_against_away_last_5,

    -- Phase 1 enhancements: Momentum and home/away splits
    -- OPTION C: Position features REMOVED to prevent data leakage (league_position leaks outcome)
    -- Only using rolling form features from recent matches
    base.home_team_home_win_rate_last_5,
    base.away_team_away_win_rate_last_5,
    base.home_team_home_clean_sheet_rate_last_5,
    base.away_team_away_clean_sheet_rate_last_5,
    base.home_team_home_btts_rate_last_5,
    base.away_team_away_btts_rate_last_5,
    base.home_win_streak,
    base.away_win_streak,
    base.home_unbeaten_streak,
    base.away_unbeaten_streak,
    base.home_form_trend_points,
    base.away_form_trend_points,
    base.home_form_trend_goals,
    base.away_form_trend_goals,
    base.home_win_rate_last_5,
    base.away_win_rate_last_5,

    -- OPTION C: Odds features REMOVED from training (data leakage - bookmakers know the outcome)
    -- Odds are kept in fct_model_training_dataset for betting evaluation only
    -- DO NOT use implied_home_win_prob, bet365_home_win_odds, etc. as model features

    -- ============================================================================
    -- DERIVED FEATURES (created in SQL, not pandas)
    -- ============================================================================

    -- 1. Attack strength differentials
    (base.home_avg_goals_for_last_5 - base.away_avg_goals_against_last_5) as home_attack_strength,
    (base.away_avg_goals_for_last_5 - base.home_avg_goals_against_last_5) as away_attack_strength,

    -- 2. Defense strength differentials
    (base.away_avg_goals_for_last_5 - base.home_avg_goals_against_last_5) as home_defense_strength,
    (base.home_avg_goals_for_last_5 - base.away_avg_goals_against_last_5) as away_defense_strength,

    -- 3. Form strength (recent performance - points per match)
    base.home_avg_points_last_5 as home_form_strength,
    base.away_avg_points_last_5 as away_form_strength,

    -- 4. Combined attack potential (total goals expected)
    ((base.home_avg_goals_for_last_5 + base.away_avg_goals_for_last_5) / 2) as total_attack_potential,
    ((base.home_avg_goals_against_last_5 + base.away_avg_goals_against_last_5) / 2) as total_defense_weakness,

    -- 5. Shots efficiency (goals per shot)
    case
        when base.home_avg_shots_for_last_5 > 0
        then base.home_avg_goals_for_last_5 / base.home_avg_shots_for_last_5
        else 0
    end as home_shot_efficiency,

    case
        when base.away_avg_shots_for_last_5 > 0
        then base.away_avg_goals_for_last_5 / base.away_avg_shots_for_last_5
        else 0
    end as away_shot_efficiency,

    -- OPTION C: Odds-based features removed (data leakage)
    -- 6. [REMOVED] odds_home_favorite, odds_total_prob, odds_overround

    -- ============================================================================
    -- PHASE 1 DERIVED FEATURES (Option C: Form-based only, no position)
    -- ============================================================================
    
    -- Momentum difference (positive = home team has better momentum)
    (coalesce(base.home_form_trend_points, 0) - coalesce(base.away_form_trend_points, 0)) as momentum_differential,
    (coalesce(base.home_win_streak, 0) - coalesce(base.away_win_streak, 0)) as win_streak_differential,
    
    -- Form strength differential
    (coalesce(base.home_win_rate_last_5, 0) - coalesce(base.away_win_rate_last_5, 0)) as win_rate_differential,
    
    -- Home advantage factor (team's home performance vs away team's away performance)
    (coalesce(base.home_team_home_win_rate_last_5, 0) - coalesce(base.away_team_away_win_rate_last_5, 0)) as home_advantage_factor,

    -- Prediction targets
    base.target_over_25,
    base.target_under_25,
    base.target_home_win,
    base.target_draw,
    base.target_away_win,
    base.target_home_win_or_draw,
    base.target_away_win_or_draw,
    base.target_btts_yes,
    base.target_btts_no

from {{ ref('fct_model_training_dataset') }} as base
-- OPTION C: No position joins - removed league_position and position_tier to prevent data leakage
-- Only using rolling form features (last 5/10 matches)
