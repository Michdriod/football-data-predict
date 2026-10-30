-- Regression guard: streaks must describe results BEFORE the match. If every row
-- with a positive streak shares one outcome, the current result has leaked in.
with labelled as (
    select
        f.win_streak,
        f.unbeaten_streak,
        h.team_result
    from {{ ref('fct_team_rolling_features') }} f
    join {{ ref('int_team_match_history') }} h
        on f.match_key = h.match_key and f.team = h.team
)

select
    'win_streak' as feature,
    count(*) as positive_rows
from labelled
where win_streak > 0
having count(*) = count(*) filter (where team_result = 'W')

union all

select
    'unbeaten_streak' as feature,
    count(*) as positive_rows
from labelled
where unbeaten_streak > 0
having count(*) = count(*) filter (where team_result in ('W', 'D'))
