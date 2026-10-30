-- Calculate league position for each team at each match date
-- This allows us to know team standings at the time of prediction

with team_standings_by_date as (
    select distinct
        match_date,
        team,
        cumulative_points,
        cumulative_goal_difference,
        row_number() over (
            partition by match_date
            order by 
                cumulative_points desc nulls last,
                cumulative_goal_difference desc nulls last,
                team
        ) as league_position
    from {{ ref('fct_team_rolling_features') }}
    where cumulative_points is not null
)

select
    match_date,
    team,
    cumulative_points,
    cumulative_goal_difference,
    league_position,
    
    -- Position tier (for categorical analysis)
    case
        when league_position <= 4 then 'Top 4'
        when league_position <= 6 then 'Top 6'
        when league_position <= 10 then 'Mid Table Upper'
        when league_position <= 14 then 'Mid Table Lower'
        when league_position <= 17 then 'Relegation Battle'
        else 'Bottom 3'
    end as position_tier
    
from team_standings_by_date
