# Model Audit and Rebuild: 30 October 2026

## Bottom line

- The old performance figures were false. A target leak produced them, and the live model was worse than a coin flip on home and away wins.
- The system is now current to 25 Oct 2026, and a new model is live.
- The new model is much better. It is close to the bookmakers' closing price, but does not beat it.
- There is no evidence of a betting edge. This model should not be used as a reason to stake money yet.

## Results

Same test window for every row: Jul 2024 to Apr 2026, about 700 matches. Log loss: lower is better, and a coin flip scores 0.693.

| Market | Docs claimed (AUC) | Old live AUC | New AUC | Closing price AUC | Old live log loss | New log loss | Closing price log loss |
|---|---|---|---|---|---|---|---|
| Home win / X2 | 0.92 | 0.60 | **0.70** | 0.72 | 0.905 | **0.613** | 0.603 |
| Away win / 1X | 0.91 | 0.57 | **0.71** | 0.72 | 0.825 | **0.573** | 0.566 |
| Draw | 0.80 | 0.51 | 0.50 | 0.54 | 0.654 | **0.572** | 0.567 |
| Over 2.5 | 0.52 | 0.51 | **0.55** | 0.57 | 0.702 | **0.685** | 0.681 |
| BTTS | 0.46 | 0.50 | **0.53** | n/a | 0.693 | **0.686** | n/a |

Hit rate for picking the likelier side:

| Market | Old live | New | Closing price |
|---|---|---|---|
| Home win | 59.5% | **65.6%** | 65.7% |
| Away win | 61.5% | **70.1%** | 70.6% |
| Over 2.5 | 55.9% | **56.9%** | 56.9% |

"Old live" feeds the old models exactly as `predict.py` did. The "new" column uses walk-forward predictions, so each match was predicted only from earlier matches.

**Holdout:** the 460 matches from Aug 2025 on were not used for any tuning. Home win log loss is 0.628 against 0.615 for the closing price. Away win is 0.583 against 0.570. Over 2.5 is 0.690 against 0.683. Holdout figures are lower than the table above because recent seasons have been harder to predict for the market as well.

Reproduce with `python scripts/match_model.py --evaluate`. Results are written to `logs/match_model_evaluation.csv`.

## Betting

Flat one-unit stakes on Bet365 pre-match prices, across over, under, home, draw and away:

| Period | Rule | Bets | Win rate | ROI | 90% interval |
|---|---|---|---|---|---|
| 2021-22 to 2024-25 | Current (p ≥ 70%, edge ≥ 5%, odds 1.50 to 3.00) | 10 | 50% | -19.9% | -67% to +26% |
| 2021-22 to 2024-25 | Any edge ≥ 3% | 1,124 | 35% | -7.6% | -14% to -1% |
| Aug 2025 on (holdout) | Current | 0 | n/a | n/a | n/a |
| Aug 2025 on (holdout) | Any edge ≥ 3% | 347 | 37% | -3.6% | -16% to +9% |

Bet365's average margin is about 5%, so a small negative ROI is what a no-edge model should produce. In the research run, picks also had about 4% worse price than the fair closing price, on average. That is the most reliable sign that the "edges" were not real.

The old rule produced 0 BET picks across the 10 fixtures for 31 Oct to 2 Nov 2026.

**Decision:** the app now runs in practice mode. It never says BET. Any real-priced edge of 3% or more is labelled PRACTICE and saved to `logs/practice_picks.csv`. That wider rule gave about 280 picks a season in testing, whereas the old rule gave about 2. Double chance is excluded because its prices are calculated. Run `python scripts/predict.py --practice-report` to score the picks. Real-money labels should only return if picks beat the closing price over 200 or more settled picks.

## Faults found and fixed

| # | Fault | Effect | Fix |
|---|---|---|---|
| 1 | Streak features counted the current match | Streak above 0 meant a 100% win (967 of 967 rows). This is the source of the 0.92 and the 1.00 AUCs | `fct_team_rolling_features.sql`, plus a new dbt regression test |
| 2 | Calibration refit a clone of the model on validation data | Saved models were trained on 2023-24 only. The training set was ignored | `train_models.py` |
| 3 | Live features came from the last same-venue row, whose window excludes that match | Live form was at least one match stale | New shared feature code |
| 4 | Staging read `BbAv*` columns that ended in 2018-19, and closing odds were hardcoded to NULL | Over 2.5 odds existed for 330 of 3,011 matches, so nearly all market evaluation used missing prices | `stg_football_matches.sql` |
| 5 | `predict.py` read `home_odds` but the parser stores `odds['home_win']` | BET and NO BET logic never ran on live fixtures | `predict.py` |
| 6 | Season reload deleted by calendar year | Reloading a season would wipe half of a neighbouring season. Caught before it ran | `load_raw_data.py`, `auto_update.py` |
| 7 | Loader failed on 14 new CSV columns | The 2026-27 file could not load | Loader keeps to the raw table's columns |
| 8 | Scheduled job broken several ways: wrong flag, missing script, bad download URL, failures hidden by `tee` | No automatic update has ever succeeded | `run_pipeline.sh`, `load_raw_data.py` |
| 9 | The "only update if better" check compared against a fixed 0.70 | The check never measured anything | Removed. Weekly runs retrain and `--evaluate` re-checks |
| 10 | Backtest ROI ignored odds, and `backtest.py` and `evaluate_models.py` crashed on missing columns | Reported ROI was meaningless | Both scripts fixed |
| 11 | Coventry and Hull missing from the team map | Odds API names would not have matched | `team_name_mapping.json` |
| 12 | `.gitignore` excluded `*.sql` | Almost all dbt models were outside git | Exceptions added |

The documented reason for removing odds, "bookmakers know the outcome", is wrong: pre-match prices are fair inputs. The rule still stands in CLAUDE.md, and the test below shows it costs nothing today. Adding market prices to the model did not beat the market alone.

## New model

`scripts/match_model.py`:

1. A time-weighted Dixon-Coles goal model gives one scoreline grid, so every market is consistent.
2. Elo ratings and weighted shots, goals, corners, points and rest days add recent information.
3. A heavily regularised logistic model combines these per market.

Goal-model settings were tuned on seasons before 2025-26 only. Training and live prediction share the same feature code. Checks passed: changing a match's result left its own features unchanged in 40 of 40 sampled matches, and fixture features matched training features in 3 of 3 matches. No new dbt columns were added.

Compared with the research run on data from 2014-15, the shipped model has less history because the database starts in 2018-19. Backfilling 2015-18 is possible.

## Limits

- Over 2.5 and BTTS are close to coin flips, for the market as well. Do not expect large accuracy gains on them.
- Football has a hard ceiling. On this window the closing price itself reaches only about 66% on home wins, so "a lot more accurate" than that is not realistic from public data.
- The betting samples are small, and the current rule's sample is too small to conclude anything alone.
- BTTS has no market price in these files, so it has no benchmark and no betting evaluation.
- Double chance prices are derived from 1X2 prices, so they are not real bookable prices.
- xG is untested. football-data.co.uk added it this season, so only 80 matches exist. They are now stored as `home_xg` and `away_xg` in staging, ready to test after about a season of data.

## Still open

- `scripts/run_pipeline.sh` passes when run by hand, but cron is blocked by macOS. Grant `/usr/sbin/cron` Full Disk Access in System Settings, or move the project out of Desktop.
- Nothing is committed yet.
- `raw_football_matches_backup_20261030_121210` was kept in the database as a safety copy.
- `src_cashlink_customers` and `stg_cashlink_customers` are unrelated tables in the football database. They were left alone.

## Free data test (30 October 2026)

The question: does free extra data improve predictions on matches the model has not seen?

**Result: no. Nothing was added to the live model.** Lower log loss is better, and differences are compared with the current model. The test used 809 matches from Aug 2024, with every version trained on the same matches from Jan 2023.

| Version | 2024-25 | Aug 2025 on (holdout) | 85%+ picks correct, all 809 matches |
|---|---|---|---|
| Current model | 0.6221 | 0.6378 | 88.6% of 185 |
| Add team xG | -0.0025 (better) | +0.0012 (worse) | 90.1% of 182 |
| Add line-up strength, best case | -0.0007 | +0.0008 | 88.0% of 184 |
| Add both | -0.0030 | +0.0017 | 88.4% of 181 |

On the holdout, every 90% interval for the change includes zero. The small 2024-25 gain did not repeat, so it is treated as noise.

The line-up test used the actual starting XI, which is known only about an hour before kick-off, so it is a best case. It is one simple measure of who was missing, not proof that line-ups never matter. Training history was also short, so xG is worth re-testing after 2026-27.

| Source | Finding |
|---|---|
| Understat | Ruled out. Its robots.txt blocks all automated access |
| vaastav FPL archive | Free, MIT licence, player data to 2026-27, with xG from Nov 2022. It lags results by about two weeks |
| Fantasy Premier League API | Free and unofficial, with live injury flags. No past flags exist, so these cannot be tested yet |
| football-data.org and API-Football | Free tiers appear not to offer usable line-ups. Based on third-party articles, not checked against official pricing |
| ClubElo | Not tested: its API returned errors. The model already has its own Elo |

**Decision:** injury flags are now saved on each pipeline run by `scripts/snapshot_injuries.py`, to `data/fpl_injury_flags.csv`. They can be tested after about a season. They are not a model input.

## First-half goal market (30 October 2026)

Over 0.5 goals in the first half was added on request. It happened in 73% of matches before Aug 2025 and 70% since. Holdout AUC is 0.53 and log loss 0.616, which is no better than saying "about 70%" for every match.

Its probabilities are honest: 0.73 predicted against 0.74 observed in the 70-75% band. It reached 85% on only 12 picks since 2021, and 10 were correct. It has no bookmaker price in our data, so it cannot be compared with the market.

With it included, the 85%+ list is 90.8% correct on 393 picks.

## Absences and the caution label (30 October 2026)

Checked on 2,605 team performances from Nov 2022: did teams with absences do worse than the model predicted?

| Situation | Cases | Actual win rate | Predicted | 90% range of the gap |
|---|---|---|---|---|
| 3+ regulars out | 536 | 37.1% | 39.5% | -5.6 to +0.7 points |
| 2+ defenders or keeper out | 404 | 33.9% | 37.5% | -7.3 to +0.1 points |
| Both top attackers out | 80 | 32.5% | 35.9% | -11.4 to +4.5 points |

The direction fits the idea that absences matter, but no gap is firmly proven and several cuts were tried. These use actual line-ups. Stars already missing the previous match gave inconsistent results: -4.9 points before Aug 2025 and +5.8 since.

**Decision:** the app shows a caution label at 3+ regulars or 2+ defenders or keepers likely out, using Fantasy Premier League status. A regular has started at least half of the season's matches. Probabilities are not changed. Each issued pick records `had_caution`, so flagged picks can be compared with others.
