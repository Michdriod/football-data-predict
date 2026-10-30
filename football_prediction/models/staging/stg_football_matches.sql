select
    "Div" as league_code,
    to_date("Date", 'DD/MM/YYYY') as match_date,
    null::time as match_time,  -- Time column not available in 2015-2018 data

    "HomeTeam" as home_team,
    "AwayTeam" as away_team,

    case when "FTHG" ~ '^\d+$' then nullif("FTHG", '')::int else null end as full_time_home_goals,
    case when "FTAG" ~ '^\d+$' then nullif("FTAG", '')::int else null end as full_time_away_goals,
    "FTR" as full_time_result,

    case when "HTHG" ~ '^\d+$' then nullif("HTHG", '')::int else null end as half_time_home_goals,
    case when "HTAG" ~ '^\d+$' then nullif("HTAG", '')::int else null end as half_time_away_goals,
    "HTR" as half_time_result,

    "Referee" as referee,

    case when "HS" ~ '^\d+$' then nullif("HS", '')::int else null end as home_shots,
    case when "AS" ~ '^\d+$' then nullif("AS", '')::int else null end as away_shots,
    case when "HST" ~ '^\d+$' then nullif("HST", '')::int else null end as home_shots_on_target,
    case when "AST" ~ '^\d+$' then nullif("AST", '')::int else null end as away_shots_on_target,

    case when "HF" ~ '^\d+$' then nullif("HF", '')::int else null end as home_fouls,
    case when "AF" ~ '^\d+$' then nullif("AF", '')::int else null end as away_fouls,
    case when "HC" ~ '^\d+$' then nullif("HC", '')::int else null end as home_corners,
    case when "AC" ~ '^\d+$' then nullif("AC", '')::int else null end as away_corners,

    case when "HY" ~ '^\d+$' then nullif("HY", '')::int else null end as home_yellow_cards,
    case when "AY" ~ '^\d+$' then nullif("AY", '')::int else null end as away_yellow_cards,
    case
        when "HR" ~ '^\d+$' then nullif("HR", '')::int
        else null
    end as home_red_cards,
    case
        when "AR" ~ '^\d+$' then nullif("AR", '')::int
        else null
    end as away_red_cards,

    -- Expected goals: published from 2026-27 on, NULL for earlier seasons
    nullif("HxG", '')::numeric as home_xg,
    nullif("AxG", '')::numeric as away_xg,

    nullif("B365H", '')::numeric as bet365_home_win_odds,
    nullif("B365D", '')::numeric as bet365_draw_odds,
    nullif("B365A", '')::numeric as bet365_away_win_odds,

    -- Market averages use Avg* from 2019-20 on; 2018-19 files carry Betbrain BbAv* instead
    coalesce(nullif("AvgH", '')::numeric, nullif("BbAvH", '')::numeric) as avg_home_win_odds,
    coalesce(nullif("AvgD", '')::numeric, nullif("BbAvD", '')::numeric) as avg_draw_odds,
    coalesce(nullif("AvgA", '')::numeric, nullif("BbAvA", '')::numeric) as avg_away_win_odds,

    -- Over/Under odds
    coalesce(nullif("B365>2.5", '')::numeric, nullif("BbAv>2.5", '')::numeric) as bet365_over_25_odds,
    coalesce(nullif("B365<2.5", '')::numeric, nullif("BbAv<2.5", '')::numeric) as bet365_under_25_odds,
    coalesce(nullif("Avg>2.5", '')::numeric, nullif("BbAv>2.5", '')::numeric) as avg_over_25_odds,
    coalesce(nullif("Avg<2.5", '')::numeric, nullif("BbAv<2.5", '')::numeric) as avg_under_25_odds,

    -- Closing odds. 2018-19 only has Pinnacle closing 1X2, so it stands in for that season
    coalesce(nullif("B365CH", '')::numeric, nullif("PSCH", '')::numeric) as bet365_closing_home_win_odds,
    coalesce(nullif("B365CD", '')::numeric, nullif("PSCD", '')::numeric) as bet365_closing_draw_odds,
    coalesce(nullif("B365CA", '')::numeric, nullif("PSCA", '')::numeric) as bet365_closing_away_win_odds,

    coalesce(nullif("AvgCH", '')::numeric, nullif("PSCH", '')::numeric) as avg_closing_home_win_odds,
    coalesce(nullif("AvgCD", '')::numeric, nullif("PSCD", '')::numeric) as avg_closing_draw_odds,
    coalesce(nullif("AvgCA", '')::numeric, nullif("PSCA", '')::numeric) as avg_closing_away_win_odds,

    coalesce(nullif("B365C>2.5", '')::numeric) as bet365_closing_over_25_odds,
    coalesce(nullif("B365C<2.5", '')::numeric) as bet365_closing_under_25_odds,
    coalesce(nullif("AvgC>2.5", '')::numeric) as avg_closing_over_25_odds,
    coalesce(nullif("AvgC<2.5", '')::numeric) as avg_closing_under_25_odds,

    nullif("BbAHh", '')::numeric as asian_handicap_line,
    null::numeric as closing_asian_handicap_line

from raw_football_matches