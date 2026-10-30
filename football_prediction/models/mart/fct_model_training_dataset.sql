with home_features as (
    select * from {{ ref('fct_team_rolling_features') }} where is_home = true
),

away_features as (
    select * from {{ ref('fct_team_rolling_features') }} where is_home = false
),

results as (select * from {{ ref('int_match_results') }}),
targets as (select * from {{ ref('int_prediction_targets') }}),
odds_raw as (select * from {{ ref('int_match_odds') }}),
odds_canonical as (select * from {{ ref('int_odds_canonical') }})

select
    r.match_key,
    r.league_code,
    r.match_date,
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

    -- Goal-specific features for home team
    hf.shot_efficiency_last_5 as home_shot_efficiency_last_5,
    hf.shot_on_target_efficiency_last_5 as home_shot_on_target_efficiency_last_5,
    hf.defensive_solidity_last_5 as home_defensive_solidity_last_5,
    hf.avg_shots_against_last_5 as home_avg_shots_against_last_5,
    hf.avg_shots_on_target_against_last_5 as home_avg_shots_on_target_against_last_5,
    hf.goal_scoring_variance_last_5 as home_goal_scoring_variance_last_5,
    hf.goal_conceding_variance_last_5 as home_goal_conceding_variance_last_5,
    hf.avg_goals_for_home_last_5 as home_avg_goals_for_home_last_5,
    hf.avg_goals_for_away_last_5 as home_avg_goals_for_away_last_5,
    hf.avg_goals_against_home_last_5 as home_avg_goals_against_home_last_5,
    hf.avg_goals_against_away_last_5 as home_avg_goals_against_away_last_5,

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

    -- Goal-specific features for away team
    af.shot_efficiency_last_5 as away_shot_efficiency_last_5,
    af.shot_on_target_efficiency_last_5 as away_shot_on_target_efficiency_last_5,
    af.defensive_solidity_last_5 as away_defensive_solidity_last_5,
    af.avg_shots_against_last_5 as away_avg_shots_against_last_5,
    af.avg_shots_on_target_against_last_5 as away_avg_shots_on_target_against_last_5,
    af.goal_scoring_variance_last_5 as away_goal_scoring_variance_last_5,
    af.goal_conceding_variance_last_5 as away_goal_conceding_variance_last_5,
    af.avg_goals_for_home_last_5 as away_avg_goals_for_home_last_5,
    af.avg_goals_for_away_last_5 as away_avg_goals_for_away_last_5,
    af.avg_goals_against_home_last_5 as away_avg_goals_against_home_last_5,
    af.avg_goals_against_away_last_5 as away_avg_goals_against_away_last_5,

    -- ========================================================================
    -- PHASE 1 ENHANCEMENTS: League Position, Momentum, Home/Away Splits
    -- ========================================================================
    
    -- League standings
    hf.cumulative_points as home_cumulative_points,
    af.cumulative_points as away_cumulative_points,
    hf.cumulative_goal_difference as home_cumulative_goal_difference,
    af.cumulative_goal_difference as away_cumulative_goal_difference,
    
    -- Home/Away win rates (venue-specific)
    hf.home_win_rate_last_5 as home_team_home_win_rate_last_5,
    af.away_win_rate_last_5 as away_team_away_win_rate_last_5,
    hf.home_clean_sheet_rate_last_5 as home_team_home_clean_sheet_rate_last_5,
    af.away_clean_sheet_rate_last_5 as away_team_away_clean_sheet_rate_last_5,
    hf.home_btts_rate_last_5 as home_team_home_btts_rate_last_5,
    af.away_btts_rate_last_5 as away_team_away_btts_rate_last_5,
    
    -- Momentum features
    hf.win_streak as home_win_streak,
    af.win_streak as away_win_streak,
    hf.unbeaten_streak as home_unbeaten_streak,
    af.unbeaten_streak as away_unbeaten_streak,
    hf.form_trend_points as home_form_trend_points,
    af.form_trend_points as away_form_trend_points,
    hf.form_trend_goals as home_form_trend_goals,
    af.form_trend_goals as away_form_trend_goals,
    hf.win_rate_last_5 as home_win_rate_last_5,
    af.win_rate_last_5 as away_win_rate_last_5,

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

    -- Canonical odds (real market odds or NULL)
    oc.market_home_odds,
    oc.market_draw_odds,
    oc.market_away_odds,
    oc.odds_source,
    oc.has_real_odds,
    oc.implied_home_win_prob as market_implied_home_win_prob,
    oc.implied_draw_prob as market_implied_draw_prob,
    oc.implied_away_win_prob as market_implied_away_win_prob,

    -- Targets
    t.target_over_25,
    t.target_under_25,
    t.target_home_win,
    t.target_draw,
    t.target_away_win,
    t.target_home_win_or_draw,
    t.target_away_win_or_draw,
    t.target_btts_yes,
    t.target_btts_no

from results r
left join home_features hf on r.match_key = hf.match_key and r.home_team = hf.team
left join away_features af on r.match_key = af.match_key and r.away_team = af.team
left join odds_raw o on r.match_key = o.match_key
left join odds_canonical oc on r.match_key = oc.match_key
left join targets t on r.match_key = t.match_key

where hf.matches_played_before >= 5
  and af.matches_played_before >= 5
