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

    bet365_home_win_odds,
    bet365_draw_odds,
    bet365_away_win_odds,
    avg_home_win_odds,
    avg_draw_odds,
    avg_away_win_odds,
    bet365_over_25_odds,
    bet365_under_25_odds,
    avg_over_25_odds,
    avg_under_25_odds,

    bet365_closing_home_win_odds,
    bet365_closing_draw_odds,
    bet365_closing_away_win_odds,
    avg_closing_home_win_odds,
    avg_closing_draw_odds,
    avg_closing_away_win_odds,
    bet365_closing_over_25_odds,
    bet365_closing_under_25_odds,
    avg_closing_over_25_odds,
    avg_closing_under_25_odds,

    asian_handicap_line,
    closing_asian_handicap_line,

    case when bet365_home_win_odds > 0 then 1.0 / bet365_home_win_odds end as implied_home_win_prob,
    case when bet365_draw_odds > 0 then 1.0 / bet365_draw_odds end as implied_draw_prob,
    case when bet365_away_win_odds > 0 then 1.0 / bet365_away_win_odds end as implied_away_win_prob,
    case when bet365_over_25_odds > 0 then 1.0 / bet365_over_25_odds end as implied_over_25_prob,
    case when bet365_under_25_odds > 0 then 1.0 / bet365_under_25_odds end as implied_under_25_prob,

    bet365_closing_home_win_odds - bet365_home_win_odds as home_win_odds_movement,
    bet365_closing_draw_odds - bet365_draw_odds as draw_odds_movement,
    bet365_closing_away_win_odds - bet365_away_win_odds as away_win_odds_movement,
    bet365_closing_over_25_odds - bet365_over_25_odds as over_25_odds_movement,
    bet365_closing_under_25_odds - bet365_under_25_odds as under_25_odds_movement

from {{ ref('stg_football_matches') }}
