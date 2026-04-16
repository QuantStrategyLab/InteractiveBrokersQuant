# Video QQQ/TQQQ Dual-Drive Reconstruction

## Setup
- Data: Yahoo Finance adjusted daily OHLCV.
- Main comparison window follows the video window as closely as trading days allow.
- Cost focus: 5 bps one-way turnover cost.
- The exact video code is not public, so variants are explicit approximations.

## 5 bps Comparison
| strategy | execution_mode | CAGR | Max Drawdown | 2020 Return | 2022 Return | 2023 Return | Turnover/Year | Average QQQ Weight | Average TQQQ Weight | known_limitation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| video_like_same_close_lookahead | same_close_lookahead | 0.414960 | -0.238003 | 1.130881 | -0.081932 | 0.692347 | 2.719947 | 0.367146 | 0.367146 | Biased lookahead control; not implementable as stated. |
| TQQQ_buy_hold | buy_hold | 0.377678 | -0.816599 | 1.100519 | -0.790900 | 1.980486 | 0.000000 | 0.000000 | 1.000000 | Reference only. |
| video_like_pullback_next_close | next_close | 0.339629 | -0.314770 | 0.796966 | -0.116838 | 0.667092 | 3.885638 | 0.387811 | 0.387811 | Approximate reconstruction; exact video state machine and high-exit logic are not public. |
| buy_hold_45_45_10 | buy_hold | 0.296118 | -0.589118 | 0.810858 | -0.558120 | 1.029582 | 0.000000 | 0.450000 | 0.450000 | Daily rebalanced reference, not a disclosed video state machine. |
| video_like_next_close | next_close | 0.279509 | -0.316426 | 0.800494 | -0.209692 | 0.510220 | 2.719947 | 0.367146 | 0.367146 | Approximate reconstruction; exact video state machine and high-exit logic are not public. |
| video_like_overheat_next_close | next_close | 0.279509 | -0.316426 | 0.800494 | -0.209692 | 0.510220 | 2.719947 | 0.367146 | 0.367146 | Approximate reconstruction; exact video state machine and high-exit logic are not public. |
| video_like_no_slope_next_close | next_close | 0.257004 | -0.380455 | 0.659450 | -0.287483 | 0.646723 | 3.885638 | 0.371781 | 0.371781 | Approximate reconstruction; exact video state machine and high-exit logic are not public. |
| QQQ_buy_hold | buy_hold | 0.201805 | -0.351187 | 0.484061 | -0.325770 | 0.548556 | 0.000000 | 1.000000 | 0.000000 | Reference only. |

## Video Reported Reference
- Reported CAGR: 49.40%
- Reported MaxDD: -36.10%
- Reported 2022 return: -15.80%

## Findings
- Best implementable reconstruction is `video_like_pullback_next_close` at 33.96% CAGR / -31.48% MaxDD, below the video's reported 49.40% CAGR.
- The simple 45/45/10 daily-rebalanced reference is 29.61% CAGR with -58.91% MaxDD.
- The intentionally biased same-close version reaches 41.50% CAGR with -23.80% MaxDD, which shows how much close-to-close lookahead can inflate this family of tests.
- Closest CAGR to the video in this local run is `video_like_same_close_lookahead` at 41.50%; it still misses the reported CAGR by 7.90%.
- Raw TQQQ buy-and-hold produces 37.77% CAGR but -81.66% MaxDD.

## Caveats
- The video mentions six internal states, high-level top escape, and below-MA200 low-buy/high-sell behavior, but does not disclose exact conditions.
- The same-close variant is intentionally non-tradable; it is included only as a bias diagnostic.
