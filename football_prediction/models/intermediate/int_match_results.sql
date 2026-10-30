select
    league_code,
    match_date,
    match_time,
    home_team,
    away_team,
    referee,

    full_time_home_goals,
    full_time_away_goals,
    full_time_result,
    half_time_home_goals,
    half_time_away_goals,
    half_time_result,

    full_time_home_goals + full_time_away_goals as total_goals,

    case when full_time_result = 'H' then true else false end as is_home_win,
    case when full_time_result = 'D' then true else false end as is_draw,
    case when full_time_result = 'A' then true else false end as is_away_win,

    concat(
        league_code, '_',
        to_char(match_date, 'YYYYMMDD'), '_',
        replace(home_team, ' ', '_'), '_',
        replace(away_team, ' ', '_')
    ) as match_key

from {{ ref('stg_football_matches') }}
