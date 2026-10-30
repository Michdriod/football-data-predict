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

    -- Over/Under Goals Targets
    case when total_goals >= 3 then true else false end as target_over_25,
    case when total_goals <= 2 then true else false end as target_under_25,

    -- Match Result Targets (3-way: Home/Draw/Away)
    case when full_time_result = 'H' then true else false end as target_home_win,
    case when full_time_result = 'D' then true else false end as target_draw,
    case when full_time_result = 'A' then true else false end as target_away_win,

    -- Double Chance Targets (combined outcomes)
    case
        when full_time_result in ('H', 'D')
        then true else false
    end as target_home_win_or_draw,

    case
        when full_time_result in ('A', 'D')
        then true else false
    end as target_away_win_or_draw,

    -- BTTS Targets (Both Teams To Score)
    case
        when full_time_home_goals >= 1 and full_time_away_goals >= 1
        then true else false
    end as target_btts_yes,

    case
        when full_time_home_goals = 0 or full_time_away_goals = 0
        then true else false
    end as target_btts_no

from {{ ref('int_match_results') }}
