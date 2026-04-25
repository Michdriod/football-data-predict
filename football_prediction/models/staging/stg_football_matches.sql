select
    "Div" as league_code,
    to_date("Date", 'DD/MM/YYYY') as match_date,
    "Time"::time as match_time,

    "HomeTeam" as home_team,
    "AwayTeam" as away_team,

    "FTHG"::int as full_time_home_goals,
    "FTAG"::int as full_time_away_goals,
    "FTR" as full_time_result,

    "HTHG"::int as half_time_home_goals,
    "HTAG"::int as half_time_away_goals,
    "HTR" as half_time_result,

    "Referee" as referee,

    "HS"::int as home_shots,
    "AS"::int as away_shots,
    "HST"::int as home_shots_on_target,
    "AST"::int as away_shots_on_target,

    "HF"::int as home_fouls,
    "AF"::int as away_fouls,
    "HC"::int as home_corners,
    "AC"::int as away_corners,

    "HY"::int as home_yellow_cards,
    "AY"::int as away_yellow_cards,
    "HR"::int as home_red_cards,
    "AR"::int as away_red_cards,

    "B365H"::numeric as bet365_home_win_odds,
    "B365D"::numeric as bet365_draw_odds,
    "B365A"::numeric as bet365_away_win_odds,

    "AvgH"::numeric as avg_home_win_odds,
    "AvgD"::numeric as avg_draw_odds,
    "AvgA"::numeric as avg_away_win_odds,

    "B365>2.5"::numeric as bet365_over_25_odds,
    "B365<2.5"::numeric as bet365_under_25_odds,
    "Avg>2.5"::numeric as avg_over_25_odds,
    "Avg<2.5"::numeric as avg_under_25_odds,

    "B365CH"::numeric as bet365_closing_home_win_odds,
    "B365CD"::numeric as bet365_closing_draw_odds,
    "B365CA"::numeric as bet365_closing_away_win_odds,

    "AvgCH"::numeric as avg_closing_home_win_odds,
    "AvgCD"::numeric as avg_closing_draw_odds,
    "AvgCA"::numeric as avg_closing_away_win_odds,

    "B365C>2.5"::numeric as bet365_closing_over_25_odds,
    "B365C<2.5"::numeric as bet365_closing_under_25_odds,
    "AvgC>2.5"::numeric as avg_closing_over_25_odds,
    "AvgC<2.5"::numeric as avg_closing_under_25_odds,

    "AHh"::numeric as asian_handicap_line,
    "AHCh"::numeric as closing_asian_handicap_line

from raw_football_matches