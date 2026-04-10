# TQQQ entry-gate follow-up

## Setup
- Current baseline: flat entry waits for the ATR-adjusted entry line above MA200 (`entry_line_floor=1.02`, `atr_entry_scale=2.5`, cap `1.08`).
- Test variant: when flat, enter as soon as QQQ is above MA200 (`entry_line_floor=1.00`, `atr_entry_scale=0.0`, cap `1.00`).
- Exit and reduce rules are unchanged.
- Both runtime-full and attack-only BOXX variants are included; numbers below use 5 bps one-way turnover cost.

## OOS 2023+ (5 bps)
| income_mode | overlay | CAGR | Max Drawdown | Information Ratio vs QQQ | Turnover/Year | Average TQQQ Weight | TQQQ Days Share |
| --- | --- | --- | --- | --- | --- | --- | --- |
| attack_only | current_atr_entry | 0.237838 | -0.201122 | -0.268218 | 1.233362 | 0.455497 | 0.924390 |
| attack_only | ma200_entry | 0.294860 | -0.201304 | 0.078699 | 1.735072 | 0.469801 | 0.935366 |
| runtime_full | current_atr_entry | 0.185358 | -0.177757 | -1.387069 | 0.475787 | 0.184326 | 0.924390 |
| runtime_full | ma200_entry | 0.202364 | -0.178725 | -1.269141 | 0.601761 | 0.190789 | 0.935366 |

## 2022 stress period (5 bps)
| income_mode | overlay | Total Return | Max Drawdown | Turnover/Year | Average TQQQ Weight | TQQQ Days Share |
| --- | --- | --- | --- | --- | --- | --- |
| attack_only | current_atr_entry | -0.161162 | -0.173794 | 0.512380 | 0.027606 | 0.067729 |
| attack_only | ma200_entry | -0.301284 | -0.311831 | 4.549421 | 0.052123 | 0.147410 |
| runtime_full | current_atr_entry | -0.077000 | -0.100511 | 0.217928 | 0.011754 | 0.067729 |
| runtime_full | ma200_entry | -0.136888 | -0.158867 | 1.760707 | 0.020834 | 0.147410 |

## Recommendation
- MA200 direct entry improves the 2023+ rebound but materially worsens the 2022 stress period; do not switch production directly without an extra risk guard.
