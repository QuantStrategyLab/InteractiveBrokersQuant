"""Pure-ish strategy helpers for IBKRQuant."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Callable

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
import pytz


def compute_13612w_momentum(closes: pd.Series, as_of_date=None) -> float:
    """Compute Keller's 13612W momentum score from monthly close prices."""
    if len(closes) < 253:
        return float("nan")

    me = closes.resample("ME").last().dropna()
    if as_of_date is not None:
        me = me[me.index <= as_of_date]

    if len(me) < 13:
        return float("nan")

    cur = me.iloc[-1]
    lookbacks = {1: 12, 3: 4, 6: 2, 12: 1}
    score = 0.0
    for months, weight in lookbacks.items():
        if len(me) < months + 1:
            return float("nan")
        prior = me.iloc[-(months + 1)]
        if prior == 0 or pd.isna(prior):
            return float("nan")
        score += weight * (cur / prior - 1)
    return score / 19


def check_sma(closes: pd.Series, period: int) -> bool:
    """Return True if last close is above the configured SMA period."""
    if len(closes) < period:
        return False
    return bool(closes.iloc[-1] > closes.iloc[-period:].mean())


def compute_signals(
    ib,
    current_holdings,
    *,
    get_historical_close: Callable,
    ranking_pool,
    canary_assets,
    safe_haven: str,
    top_n: int,
    hold_bonus: float,
    canary_bad_threshold: int,
    rebalance_months,
    translator: Callable,
    pacing_sec: float,
    sma_period: int,
):
    """
    Compute target weights.
    Returns (weights_dict, signal_description, is_emergency, canary_str).
    """
    all_tickers = list(set(ranking_pool + canary_assets + [safe_haven]))
    price_data = {}
    for ticker in all_tickers:
        try:
            closes = get_historical_close(ib, ticker)
            if len(closes) > 0:
                price_data[ticker] = closes
        except Exception as exc:
            print(f"Warning: failed to fetch {ticker}: {exc}", flush=True)
        time.sleep(pacing_sec)

    n_bad = 0
    canary_details = []
    for ticker in canary_assets:
        if ticker not in price_data:
            n_bad += 1
            canary_details.append(f"{ticker}:❌(no data)")
            continue
        mom = compute_13612w_momentum(price_data[ticker])
        if np.isnan(mom) or mom < 0:
            n_bad += 1
            canary_details.append(
                f"{ticker}:❌({mom:.3f})" if not np.isnan(mom) else f"{ticker}:❌(nan)"
            )
        else:
            canary_details.append(f"{ticker}:✅({mom:.3f})")

    canary_str = ", ".join(canary_details)
    if n_bad >= canary_bad_threshold:
        signal_desc = translator("emergency", n_bad=n_bad, safe=safe_haven)
        return {safe_haven: 1.0}, signal_desc, True, canary_str

    tz_ny = pytz.timezone("America/New_York")
    now_ny = datetime.now(tz_ny)
    nyse = mcal.get_calendar("NYSE")
    is_rebal_day = False
    if now_ny.month in rebalance_months:
        month_start = now_ny.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        schedule = nyse.schedule(start_date=month_start, end_date=month_end)
        if not schedule.empty:
            last_trading_day = schedule.index[-1].date()
            is_rebal_day = now_ny.date() == last_trading_day

    if not is_rebal_day:
        signal_desc = translator("daily_check")
        return None, signal_desc, False, canary_str

    scores = {}
    for ticker in ranking_pool:
        if ticker not in price_data:
            continue
        mom = compute_13612w_momentum(price_data[ticker])
        if np.isnan(mom):
            continue
        if not check_sma(price_data[ticker], sma_period):
            continue
        bonus = hold_bonus if ticker in current_holdings else 0.0
        scores[ticker] = mom + bonus

    sorted_tickers = sorted(scores.items(), key=lambda item: -item[1])
    top = sorted_tickers[:top_n]
    if len(top) == 0:
        signal_desc = translator("emergency", n_bad="SMA", safe=safe_haven)
        return {safe_haven: 1.0}, signal_desc, False, canary_str

    per_weight = 1.0 / top_n
    weights = {ticker: per_weight for ticker, _score in top}
    if len(top) < top_n:
        weights[safe_haven] = weights.get(safe_haven, 0) + per_weight * (top_n - len(top))

    top_str = ", ".join(f"{ticker}({score:.3f})" for ticker, score in top)
    signal_desc = translator("quarterly", n=top_n) + f"\n  Top: {top_str}"
    return weights, signal_desc, False, canary_str

