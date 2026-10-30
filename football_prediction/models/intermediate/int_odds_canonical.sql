-- Canonical odds columns with intelligent fallback.
-- 
-- Priority order:
-- 1. AvgCH, AvgCD, AvgCA (Average Closing Odds) - Most reliable
-- 2. AvgH, AvgD, AvgA (Average Pre-Match Odds)
-- 3. B365H, B365D, B365A (Bet365 Pre-Match Odds)
-- 4. MaxH, MaxD, MaxA (Max Market Odds)
--
-- If ANY odds in a set is NULL, skip that set and try the next.
-- Creates flags: has_real_odds, odds_source
-- Only these canonical columns should be used for betting value calculations.

with odds_priority as (
    select
        s.*,
        
        -- Check AvgCH/CD/CA (Priority 1: Closing Average)
        case
            when s.avg_closing_home_win_odds is not null
                and s.avg_closing_draw_odds is not null
                and s.avg_closing_away_win_odds is not null
            then s.avg_closing_home_win_odds
            else null
        end as market_home_odds_p1,
        case
            when s.avg_closing_home_win_odds is not null
                and s.avg_closing_draw_odds is not null
                and s.avg_closing_away_win_odds is not null
            then s.avg_closing_draw_odds
            else null
        end as market_draw_odds_p1,
        case
            when s.avg_closing_home_win_odds is not null
                and s.avg_closing_draw_odds is not null
                and s.avg_closing_away_win_odds is not null
            then s.avg_closing_away_win_odds
            else null
        end as market_away_odds_p1,
        
        -- Check AvgH/D/A (Priority 2: Pre-Match Average)
        case
            when s.avg_home_win_odds is not null
                and s.avg_draw_odds is not null
                and s.avg_away_win_odds is not null
            then s.avg_home_win_odds
            else null
        end as market_home_odds_p2,
        case
            when s.avg_home_win_odds is not null
                and s.avg_draw_odds is not null
                and s.avg_away_win_odds is not null
            then s.avg_draw_odds
            else null
        end as market_draw_odds_p2,
        case
            when s.avg_home_win_odds is not null
                and s.avg_draw_odds is not null
                and s.avg_away_win_odds is not null
            then s.avg_away_win_odds
            else null
        end as market_away_odds_p2,
        
        -- Check B365H/D/A (Priority 3: Bet365)
        case
            when s.bet365_home_win_odds is not null
                and s.bet365_draw_odds is not null
                and s.bet365_away_win_odds is not null
            then s.bet365_home_win_odds
            else null
        end as market_home_odds_p3,
        case
            when s.bet365_home_win_odds is not null
                and s.bet365_draw_odds is not null
                and s.bet365_away_win_odds is not null
            then s.bet365_draw_odds
            else null
        end as market_draw_odds_p3,
        case
            when s.bet365_home_win_odds is not null
                and s.bet365_draw_odds is not null
                and s.bet365_away_win_odds is not null
            then s.bet365_away_win_odds
            else null
        end as market_away_odds_p3
        
    from {{ ref('int_match_odds') }} s
)

select
    match_key,
    league_code,
    match_date,
    home_team,
    away_team,
    
    -- Canonical odds (selected by priority)
    coalesce(
        market_home_odds_p1,
        market_home_odds_p2,
        market_home_odds_p3
    ) as market_home_odds,
    
    coalesce(
        market_draw_odds_p1,
        market_draw_odds_p2,
        market_draw_odds_p3
    ) as market_draw_odds,
    
    coalesce(
        market_away_odds_p1,
        market_away_odds_p2,
        market_away_odds_p3
    ) as market_away_odds,
    
    -- Odds source tracking
    case
        when market_home_odds_p1 is not null then 'Avg Closing Odds'
        when market_home_odds_p2 is not null then 'Avg Pre-Match Odds'
        when market_home_odds_p3 is not null then 'Bet365 Odds'
        else 'Missing'
    end as odds_source,
    
    -- Flag for rows with real odds
    case
        when coalesce(
            market_home_odds_p1,
            market_home_odds_p2,
            market_home_odds_p3
        ) is not null then true
        else false
    end as has_real_odds,
    
    -- Implied probabilities (only from real odds)
    case
        when coalesce(
            market_home_odds_p1,
            market_home_odds_p2,
            market_home_odds_p3
        ) > 0
        then 1.0 / coalesce(
            market_home_odds_p1,
            market_home_odds_p2,
            market_home_odds_p3
        )
        else null
    end as implied_home_win_prob,
    
    case
        when coalesce(
            market_draw_odds_p1,
            market_draw_odds_p2,
            market_draw_odds_p3
        ) > 0
        then 1.0 / coalesce(
            market_draw_odds_p1,
            market_draw_odds_p2,
            market_draw_odds_p3
        )
        else null
    end as implied_draw_prob,
    
    case
        when coalesce(
            market_away_odds_p1,
            market_away_odds_p2,
            market_away_odds_p3
        ) > 0
        then 1.0 / coalesce(
            market_away_odds_p1,
            market_away_odds_p2,
            market_away_odds_p3
        )
        else null
    end as implied_away_win_prob
    
from odds_priority
