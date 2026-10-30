select
    concat(
        league_code, '_',
        to_char(match_date, 'YYYYMMDD'), '_',
        replace(home_team, ' ', '_'), '_',
        replace(away_team, ' ', '_')
    ) as match_key,

    league_code,
    match_date,
    home_team,
    away_team,

    home_shots,
    away_shots,
    home_shots_on_target,
    away_shots_on_target,
    home_fouls,
    away_fouls,
    home_corners,
    away_corners,
    home_yellow_cards,
    away_yellow_cards,
    home_red_cards,
    away_red_cards

from {{ ref('stg_football_matches') }}
