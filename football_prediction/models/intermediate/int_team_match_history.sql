with base as (
    select
        r.match_key,
        r.league_code,
        r.match_date,
        r.match_time,
        r.home_team,
        r.away_team,
        r.full_time_home_goals,
        r.full_time_away_goals,
        r.full_time_result,
        r.total_goals,

        s.home_shots,
        s.away_shots,
        s.home_shots_on_target,
        s.away_shots_on_target,
        s.home_corners,
        s.away_corners,
        s.home_fouls,
        s.away_fouls,
        s.home_yellow_cards,
        s.away_yellow_cards,
        s.home_red_cards,
        s.away_red_cards

    from {{ ref('int_match_results') }} r
    left join {{ ref('int_match_stats') }} s
        on r.match_key = s.match_key
),

home_rows as (
    select
        match_key,
        league_code,
        match_date,
        match_time,
        home_team as team,
        away_team as opponent,
        true as is_home,

        full_time_home_goals as goals_for,
        full_time_away_goals as goals_against,
        home_shots as shots_for,
        away_shots as shots_against,
        home_shots_on_target as shots_on_target_for,
        away_shots_on_target as shots_on_target_against,
        home_corners as corners_for,
        away_corners as corners_against,
        home_fouls as fouls_committed,
        away_fouls as fouls_received,
        home_yellow_cards as yellow_cards,
        home_red_cards as red_cards,

        case
            when full_time_result = 'H' then 'W'
            when full_time_result = 'D' then 'D'
            else 'L'
        end as team_result,

        case
            when full_time_result = 'H' then 3
            when full_time_result = 'D' then 1
            else 0
        end as points,

        case when total_goals >= 3 then true else false end as over_25,
        case when full_time_home_goals >= 1 and full_time_away_goals >= 1 then true else false end as btts,
        case when full_time_away_goals = 0 then true else false end as clean_sheet,
        case when full_time_home_goals = 0 then true else false end as failed_to_score

    from base
),

away_rows as (
    select
        match_key,
        league_code,
        match_date,
        match_time,
        away_team as team,
        home_team as opponent,
        false as is_home,

        full_time_away_goals as goals_for,
        full_time_home_goals as goals_against,
        away_shots as shots_for,
        home_shots as shots_against,
        away_shots_on_target as shots_on_target_for,
        home_shots_on_target as shots_on_target_against,
        away_corners as corners_for,
        home_corners as corners_against,
        away_fouls as fouls_committed,
        home_fouls as fouls_received,
        away_yellow_cards as yellow_cards,
        away_red_cards as red_cards,

        case
            when full_time_result = 'A' then 'W'
            when full_time_result = 'D' then 'D'
            else 'L'
        end as team_result,

        case
            when full_time_result = 'A' then 3
            when full_time_result = 'D' then 1
            else 0
        end as points,

        case when total_goals >= 3 then true else false end as over_25,
        case when full_time_home_goals >= 1 and full_time_away_goals >= 1 then true else false end as btts,
        case when full_time_home_goals = 0 then true else false end as clean_sheet,
        case when full_time_away_goals = 0 then true else false end as failed_to_score

    from base
)

select * from home_rows
union all
select * from away_rows
