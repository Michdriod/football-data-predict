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
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between unbounded preceding and 1 preceding
    ) as matches_played_before,

    avg(goals_for) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as avg_goals_for_last_5,

    avg(goals_against) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as avg_goals_against_last_5,

    avg(shots_for) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as avg_shots_for_last_5,

    avg(shots_on_target_for) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as avg_shots_on_target_for_last_5,

    avg(corners_for) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as avg_corners_for_last_5,

    avg(points) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as avg_points_last_5,

    avg(case when over_25 then 1.0 else 0.0 end) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as over_25_rate_last_5,

    avg(case when btts then 1.0 else 0.0 end) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as btts_rate_last_5,

    avg(case when clean_sheet then 1.0 else 0.0 end) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as clean_sheet_rate_last_5,

    avg(case when failed_to_score then 1.0 else 0.0 end) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as failed_to_score_rate_last_5,

    avg(goals_for) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 10 preceding and 1 preceding
    ) as avg_goals_for_last_10,

    avg(goals_against) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 10 preceding and 1 preceding
    ) as avg_goals_against_last_10,

    avg(case when over_25 then 1.0 else 0.0 end) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 10 preceding and 1 preceding
    ) as over_25_rate_last_10,

    avg(case when btts then 1.0 else 0.0 end) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 10 preceding and 1 preceding
    ) as btts_rate_last_10,

    -- ========================================================================
    -- GOAL-SPECIFIC FEATURES (For Over 2.5 & BTTS Prediction)
    -- ========================================================================
    
    -- Shot Efficiency: Measures finishing quality (goals per shot)
    avg(
        case 
            when shots_for > 0 then goals_for::numeric / shots_for
            else 0 
        end
    ) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as shot_efficiency_last_5,

    -- Shot on Target Efficiency: Goals per shot on target (better than total shots)
    avg(
        case 
            when shots_on_target_for > 0 then goals_for::numeric / shots_on_target_for
            else 0 
        end
    ) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as shot_on_target_efficiency_last_5,

    -- Defensive Solidity: Goals conceded per opponent shot on target (lower = better defense)
    avg(
        case 
            when shots_on_target_against > 0 then goals_against::numeric / shots_on_target_against
            else 0 
        end
    ) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as defensive_solidity_last_5,

    -- Shots Conceded: Average shots allowed (defensive pressure)
    avg(shots_against) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as avg_shots_against_last_5,

    avg(shots_on_target_against) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as avg_shots_on_target_against_last_5,

    -- Goal Variance: Consistency of scoring (high variance = unpredictable)
    stddev(goals_for) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as goal_scoring_variance_last_5,

    stddev(goals_against) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as goal_conceding_variance_last_5,

    -- Home vs Away Split (teams behave differently at home/away)
    avg(case when is_home then goals_for else null end) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as avg_goals_for_home_last_5,

    avg(case when not is_home then goals_for else null end) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as avg_goals_for_away_last_5,

    avg(case when is_home then goals_against else null end) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as avg_goals_against_home_last_5,

    avg(case when not is_home then goals_against else null end) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as avg_goals_against_away_last_5,

    -- ========================================================================
    -- PHASE 1 ENHANCEMENTS: League Position, Momentum, Home/Away Splits
    -- ========================================================================
    
    -- LEAGUE STANDINGS (Cumulative metrics up to this point)
    sum(points) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between unbounded preceding and 1 preceding
    ) as cumulative_points,
    
    sum(goals_for) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between unbounded preceding and 1 preceding
    ) - sum(goals_against) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between unbounded preceding and 1 preceding
    ) as cumulative_goal_difference,
    
    -- HOME/AWAY WIN RATES (Last 5 matches split by venue)
    avg(case when is_home and team_result = 'W' then 1.0 else 0.0 end) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as home_win_rate_last_5,
    
    avg(case when not is_home and team_result = 'W' then 1.0 else 0.0 end) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as away_win_rate_last_5,
    
    avg(case when is_home and clean_sheet then 1.0 else 0.0 end) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as home_clean_sheet_rate_last_5,
    
    avg(case when not is_home and clean_sheet then 1.0 else 0.0 end) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as away_clean_sheet_rate_last_5,
    
    avg(case when is_home and btts then 1.0 else 0.0 end) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as home_btts_rate_last_5,
    
    avg(case when not is_home and btts then 1.0 else 0.0 end) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as away_btts_rate_last_5,
    
    -- MOMENTUM FEATURES (Win/Loss Streaks, Form Trends)
    -- Streak groups come from results BEFORE this match (see base), so these
    -- counts cannot depend on the result of the current match.

    -- Win streak: consecutive wins immediately BEFORE this match
    count(*) over (
        partition by team, grp_win_streak
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between unbounded preceding and 1 preceding
    ) as win_streak,

    -- Unbeaten streak: consecutive W/D immediately BEFORE this match
    count(*) over (
        partition by team, grp_unbeaten_streak
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between unbounded preceding and 1 preceding
    ) as unbeaten_streak,
    
    -- Form trend: Recent 3 avg points - Previous 3 avg points (positive = improving)
    avg(points) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 3 preceding and 1 preceding
    ) - avg(points) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 6 preceding and 4 preceding
    ) as form_trend_points,
    
    -- Goal scoring trend: Recent 3 avg - Previous 3 avg
    avg(goals_for) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 3 preceding and 1 preceding
    ) - avg(goals_for) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 6 preceding and 4 preceding
    ) as form_trend_goals,
    
    -- Win rate last 5 (overall, not split by venue)
    avg(case when team_result = 'W' then 1.0 else 0.0 end) over (
        partition by team
        order by match_date, coalesce(match_time, '00:00:00'::time), match_key
        rows between 5 preceding and 1 preceding
    ) as win_rate_last_5

from (
    select 
        *,
        -- Streak group calculations (for identifying consecutive streaks)
        coalesce(sum(case when team_result != 'W' then 1 else 0 end) over (
            partition by team
            order by match_date, coalesce(match_time, '00:00:00'::time), match_key
            rows between unbounded preceding and 1 preceding
        ), 0) as grp_win_streak,
        
        coalesce(sum(case when team_result = 'L' then 1 else 0 end) over (
            partition by team
            order by match_date, coalesce(match_time, '00:00:00'::time), match_key
            rows between unbounded preceding and 1 preceding
        ), 0) as grp_unbeaten_streak
    from {{ ref('int_team_match_history') }}
) base
