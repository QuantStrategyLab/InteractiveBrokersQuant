#!/usr/bin/env python3
"""Research-only reconstruction of a QQQ/TQQQ dual-drive idea.

The referenced video describes a QQQ/TQQQ strategy but does not publish exact
code. This script keeps the reconstruction explicit and parameterized.

Execution timing is the important distinction:

- next_close is implementable: today's close signal affects tomorrow's return.
- same_close_lookahead is intentionally biased: today's close signal is applied
  to today's close-to-close return.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
import yfinance as yf


CURRENT_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS_DIR = CURRENT_DIR / "results"
DEFAULT_DOWNLOAD_START = "2016-01-01"
DEFAULT_PERIOD_START = "2017-01-03"
DEFAULT_PERIOD_END = None
DEFAULT_COSTS_BPS = (0.0, 5.0, 10.0)
CASH_SYMBOL = "CASH"
VIDEO_REPORTED = {
    "CAGR": 0.494,
    "Max Drawdown": -0.361,
    "2022 Return": -0.158,
}


@dataclass(frozen=True)
class VideoConfig:
    name: str
    description: str
    execution_mode: str
    bull_qqq_weight: float = 0.45
    bull_tqqq_weight: float = 0.45
    cash_weight: float = 0.10
    require_ma20_slope: bool = True
    allow_below_ma200_pullback: bool = False
    pullback_qqq_weight: float = 0.45
    pullback_tqqq_weight: float = 0.45
    pullback_cash_weight: float = 0.10
    use_tqqq_overheat_exit: bool = False
    overheat_multiple: float = 2.2
    overheat_exit_qqq_weight: float = 0.45
    overheat_exit_cash_weight: float = 0.55


@dataclass
class StrategyRun:
    strategy_name: str
    display_name: str
    gross_returns: pd.Series
    weights_history: pd.DataFrame
    turnover_history: pd.Series
    metadata: dict[str, object]


VIDEO_CONFIGS = (
    VideoConfig(
        name="video_like_next_close",
        description=(
            "Transcript reconstruction: hold 45% QQQ + 45% TQQQ + 10% cash "
            "when QQQ is above MA200 and MA20 slope is positive; otherwise cash. "
            "Trades take effect on the next close-to-close return."
        ),
        execution_mode="next_close",
    ),
    VideoConfig(
        name="video_like_no_slope_next_close",
        description=(
            "Same as video_like_next_close but does not wait for positive MA20 "
            "slope after reclaiming MA200."
        ),
        execution_mode="next_close",
        require_ma20_slope=False,
    ),
    VideoConfig(
        name="video_like_pullback_next_close",
        description=(
            "Adds a speculative below-MA200 pullback state: if QQQ is below MA200 "
            "but above MA20 with positive MA20 slope, use the same 45/45/10 risk-on "
            "weights. This approximates the video's low buy/high sell below MA200 "
            "comment, but the exact rule is not disclosed."
        ),
        execution_mode="next_close",
        allow_below_ma200_pullback=True,
    ),
    VideoConfig(
        name="video_like_overheat_next_close",
        description=(
            "Adds a speculative TQQQ overheat exit: when TQQQ closes above "
            "2.2x its MA200, drop TQQQ and keep 45% QQQ / 55% cash until the "
            "normal trend condition resumes without overheat."
        ),
        execution_mode="next_close",
        use_tqqq_overheat_exit=True,
    ),
    VideoConfig(
        name="video_like_same_close_lookahead",
        description=(
            "Intentionally biased variant: uses today's close to choose today's "
            "weights for today's close-to-close return. Included only to measure "
            "how much lookahead can inflate the video-like result."
        ),
        execution_mode="same_close_lookahead",
    ),
    VideoConfig(
        name="buy_hold_45_45_10",
        description="Daily-rebalanced 45% QQQ + 45% TQQQ + 10% cash reference.",
        execution_mode="buy_hold",
        require_ma20_slope=False,
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--download-start", default=DEFAULT_DOWNLOAD_START)
    parser.add_argument("--period-start", default=DEFAULT_PERIOD_START)
    parser.add_argument("--period-end", default=DEFAULT_PERIOD_END)
    parser.add_argument("--end", default=None, help="Data download end date, exclusive in yfinance.")
    parser.add_argument("--cost-bps", nargs="*", type=float, default=list(DEFAULT_COSTS_BPS))
    return parser.parse_args()


def download_ohlcv(symbols: Iterable[str], *, start: str, end: str | None) -> dict[str, pd.DataFrame]:
    symbol_list = [symbol.upper() for symbol in symbols]
    data = yf.download(
        symbol_list,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if data.empty:
        raise RuntimeError("No ETF price data downloaded from Yahoo Finance")

    frames: dict[str, pd.DataFrame] = {}
    fields = ("Open", "High", "Low", "Close")
    for field in fields:
        if isinstance(data.columns, pd.MultiIndex):
            frame = data[field].copy()
        else:
            frame = data[[field]].copy()
            frame.columns = symbol_list[:1]
        frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
        frame.columns = frame.columns.map(str).str.upper()
        frames[field.lower()] = frame.reindex(columns=symbol_list)

    missing = [
        symbol
        for symbol in symbol_list
        if symbol not in frames["close"].columns or frames["close"][symbol].dropna().empty
    ]
    if missing:
        raise RuntimeError(f"Failed to download usable ETF price history for: {', '.join(missing)}")
    return frames


def load_market_data(*, start: str, end: str | None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frames = download_ohlcv(("QQQ", "TQQQ"), start=start, end=end)
    qqq_ohlc = pd.DataFrame(
        {
            "open": frames["open"]["QQQ"],
            "high": frames["high"]["QQQ"],
            "low": frames["low"]["QQQ"],
            "close": frames["close"]["QQQ"],
        }
    ).dropna()
    tqqq_ohlc = pd.DataFrame(
        {
            "open": frames["open"]["TQQQ"],
            "high": frames["high"]["TQQQ"],
            "low": frames["low"]["TQQQ"],
            "close": frames["close"]["TQQQ"],
        }
    ).dropna()
    index = qqq_ohlc.index.intersection(tqqq_ohlc.index)
    qqq_ohlc = qqq_ohlc.reindex(index).dropna()
    tqqq_ohlc = tqqq_ohlc.reindex(index).dropna()
    close = pd.DataFrame(
        {
            "QQQ": qqq_ohlc["close"],
            "TQQQ": tqqq_ohlc["close"],
        },
        index=index,
    )
    returns_matrix = close.pct_change(fill_method=None).replace([float("inf"), float("-inf")], pd.NA).fillna(0.0)
    returns_matrix[CASH_SYMBOL] = 0.0
    indicators = build_indicator_frame(qqq_ohlc, tqqq_ohlc)
    return qqq_ohlc, returns_matrix, indicators


def build_indicator_frame(qqq_ohlc: pd.DataFrame, tqqq_ohlc: pd.DataFrame) -> pd.DataFrame:
    index = qqq_ohlc.index.intersection(tqqq_ohlc.index)
    qqq_close = qqq_ohlc["close"].reindex(index)
    tqqq_close = tqqq_ohlc["close"].reindex(index)
    frame = pd.DataFrame(index=index)
    frame["qqq_close"] = qqq_close
    frame["tqqq_close"] = tqqq_close
    frame["qqq_ma20"] = qqq_close.rolling(20).mean()
    frame["qqq_ma200"] = qqq_close.rolling(200).mean()
    frame["qqq_ma20_slope"] = frame["qqq_ma20"].diff()
    frame["tqqq_ma200"] = tqqq_close.rolling(200).mean()
    frame["tqqq_overheat_ratio"] = tqqq_close / frame["tqqq_ma200"]
    return frame


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    cleaned = {symbol: max(0.0, float(weight)) for symbol, weight in weights.items()}
    total = sum(cleaned.values())
    if total <= 0:
        return {CASH_SYMBOL: 1.0}
    if abs(total - 1.0) > 1e-9:
        cleaned = {symbol: weight / total for symbol, weight in cleaned.items()}
    return {symbol: weight for symbol, weight in cleaned.items() if weight > 1e-12}


def decide_video_weights(
    config: VideoConfig,
    row: pd.Series,
    *,
    risk_active: bool,
) -> tuple[dict[str, float], bool]:
    qqq_close = float(row["qqq_close"])
    qqq_ma20 = float(row["qqq_ma20"]) if pd.notna(row["qqq_ma20"]) else float("nan")
    qqq_ma200 = float(row["qqq_ma200"]) if pd.notna(row["qqq_ma200"]) else float("nan")
    qqq_ma20_slope = float(row["qqq_ma20_slope"]) if pd.notna(row["qqq_ma20_slope"]) else float("nan")
    tqqq_overheat_ratio = (
        float(row["tqqq_overheat_ratio"]) if pd.notna(row["tqqq_overheat_ratio"]) else float("nan")
    )

    has_long_history = pd.notna(qqq_ma200)
    above_ma200 = has_long_history and qqq_close > qqq_ma200
    positive_ma20_slope = pd.notna(qqq_ma20_slope) and qqq_ma20_slope > 0.0
    slope_ok = positive_ma20_slope if config.require_ma20_slope else True
    overheat = (
        config.use_tqqq_overheat_exit
        and pd.notna(tqqq_overheat_ratio)
        and tqqq_overheat_ratio >= config.overheat_multiple
    )

    next_risk_active = risk_active
    if risk_active and has_long_history and not above_ma200:
        next_risk_active = False
    elif not risk_active and above_ma200 and slope_ok:
        next_risk_active = True

    if next_risk_active:
        if overheat:
            return normalize_weights({"QQQ": config.overheat_exit_qqq_weight, CASH_SYMBOL: config.overheat_exit_cash_weight}), next_risk_active
        return normalize_weights({"QQQ": config.bull_qqq_weight, "TQQQ": config.bull_tqqq_weight, CASH_SYMBOL: config.cash_weight}), next_risk_active

    pullback_risk_on = (
        config.allow_below_ma200_pullback
        and has_long_history
        and not above_ma200
        and pd.notna(qqq_ma20)
        and qqq_close > qqq_ma20
        and positive_ma20_slope
    )
    if pullback_risk_on:
        return normalize_weights({"QQQ": config.pullback_qqq_weight, "TQQQ": config.pullback_tqqq_weight, CASH_SYMBOL: config.pullback_cash_weight}), next_risk_active

    return {CASH_SYMBOL: 1.0}, next_risk_active


def compute_turnover(old_weights: dict[str, float], new_weights: dict[str, float]) -> float:
    symbols = set(old_weights) | set(new_weights)
    return 0.5 * sum(abs(float(new_weights.get(symbol, 0.0)) - float(old_weights.get(symbol, 0.0))) for symbol in symbols)


def run_video_backtest(config: VideoConfig, returns_matrix: pd.DataFrame, indicators: pd.DataFrame) -> StrategyRun:
    index = returns_matrix.index.intersection(indicators.index)
    asset_columns = ("QQQ", "TQQQ", CASH_SYMBOL)
    weights_history = pd.DataFrame(0.0, index=index, columns=asset_columns)
    portfolio_returns = pd.Series(0.0, index=index, name=config.name)
    turnover_history = pd.Series(0.0, index=index, name="turnover")

    if config.execution_mode == "buy_hold":
        current_weights = normalize_weights(
            {"QQQ": config.bull_qqq_weight, "TQQQ": config.bull_tqqq_weight, CASH_SYMBOL: config.cash_weight}
        )
        for idx in range(1, len(index)):
            date = index[idx]
            for symbol, weight in current_weights.items():
                weights_history.at[date, symbol] = weight
            row_returns = returns_matrix.loc[date]
            portfolio_returns.at[date] = sum(
                weight * float(row_returns.get(symbol, 0.0))
                for symbol, weight in current_weights.items()
                if symbol != CASH_SYMBOL
            )
        limitation = "Daily rebalanced reference, not a disclosed video state machine."
    else:
        current_weights = {CASH_SYMBOL: 1.0}
        risk_active = False
        if config.execution_mode == "next_close":
            for idx in range(len(index) - 1):
                date = index[idx]
                next_date = index[idx + 1]
                target_weights, risk_active = decide_video_weights(config, indicators.loc[date], risk_active=risk_active)
                if target_weights != current_weights:
                    turnover_history.at[next_date] = compute_turnover(current_weights, target_weights)
                    current_weights = target_weights
                for symbol, weight in current_weights.items():
                    weights_history.at[date, symbol] = weight
                row_returns = returns_matrix.loc[next_date]
                portfolio_returns.at[next_date] = sum(
                    weight * float(row_returns.get(symbol, 0.0))
                    for symbol, weight in current_weights.items()
                    if symbol != CASH_SYMBOL
                )
        elif config.execution_mode == "same_close_lookahead":
            for idx in range(1, len(index)):
                date = index[idx]
                target_weights, risk_active = decide_video_weights(config, indicators.loc[date], risk_active=risk_active)
                if target_weights != current_weights:
                    turnover_history.at[date] = compute_turnover(current_weights, target_weights)
                    current_weights = target_weights
                for symbol, weight in current_weights.items():
                    weights_history.at[date, symbol] = weight
                row_returns = returns_matrix.loc[date]
                portfolio_returns.at[date] = sum(
                    weight * float(row_returns.get(symbol, 0.0))
                    for symbol, weight in current_weights.items()
                    if symbol != CASH_SYMBOL
                )
        else:
            raise KeyError(f"Unknown execution mode: {config.execution_mode}")

        for symbol, weight in current_weights.items():
            weights_history.at[index[-1], symbol] = weight
        limitation = "Approximate reconstruction; exact video state machine and high-exit logic are not public."
        if config.execution_mode == "same_close_lookahead":
            limitation = "Biased lookahead control; not implementable as stated."

    return StrategyRun(
        strategy_name=config.name,
        display_name=config.name,
        gross_returns=portfolio_returns,
        weights_history=weights_history,
        turnover_history=turnover_history,
        metadata={
            "family": "video_qqq_tqqq_dual_drive",
            "execution_mode": config.execution_mode,
            "description": config.description,
            "known_limitation": limitation,
        },
    )


def build_buy_hold_run(symbol: str, returns_matrix: pd.DataFrame) -> StrategyRun:
    returns = returns_matrix[symbol].copy().rename(f"{symbol}_buy_hold")
    weights = pd.DataFrame(0.0, index=returns.index, columns=(symbol,))
    weights[symbol] = 1.0
    turnover = pd.Series(0.0, index=returns.index, name="turnover")
    return StrategyRun(
        strategy_name=f"{symbol}_buy_hold",
        display_name=f"{symbol}_buy_hold",
        gross_returns=returns,
        weights_history=weights,
        turnover_history=turnover,
        metadata={
            "family": "reference",
            "execution_mode": "buy_hold",
            "description": f"Buy-and-hold {symbol}.",
            "known_limitation": "Reference only.",
        },
    )


def compute_beta(strategy_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    aligned = pd.concat([strategy_returns.rename("strategy"), benchmark_returns.rename("benchmark")], axis=1).dropna()
    benchmark_var = float(aligned["benchmark"].var(ddof=0))
    if aligned.empty or benchmark_var == 0:
        return float("nan")
    return float(aligned["strategy"].cov(aligned["benchmark"], ddof=0) / benchmark_var)


def compute_information_ratio(strategy_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    aligned = pd.concat([strategy_returns.rename("strategy"), benchmark_returns.rename("benchmark")], axis=1).dropna()
    if aligned.empty:
        return float("nan")
    active_returns = aligned["strategy"] - aligned["benchmark"]
    tracking_error = float(active_returns.std(ddof=0))
    if tracking_error == 0:
        return float("nan")
    return float(active_returns.mean() / tracking_error * math.sqrt(252))


def compute_period_total_return(returns: pd.Series, start: str | None, end: str | None) -> float:
    sliced = returns.copy()
    if start:
        sliced = sliced.loc[start:]
    if end:
        sliced = sliced.loc[:end]
    if sliced.empty:
        return float("nan")
    return float((1.0 + sliced).prod() - 1.0)


def compute_period_cagr(returns: pd.Series, start: str | None, end: str | None) -> float:
    sliced = returns.copy()
    if start:
        sliced = sliced.loc[start:]
    if end:
        sliced = sliced.loc[:end]
    sliced = sliced.dropna()
    if sliced.empty:
        return float("nan")
    equity = float((1.0 + sliced).prod())
    years = max((sliced.index[-1] - sliced.index[0]).days / 365.25, 1 / 365.25)
    return float(equity ** (1.0 / years) - 1.0)


def summarize_run(
    run: StrategyRun,
    benchmark_returns: pd.Series,
    *,
    cost_bps: float,
    start: str | None,
    end: str | None,
) -> dict[str, object]:
    returns = run.gross_returns.copy()
    turnover = run.turnover_history.reindex(returns.index).fillna(0.0)
    net_returns = returns - turnover * (float(cost_bps) / 10_000.0)
    weights = run.weights_history.reindex(returns.index).fillna(0.0)
    if start:
        net_returns = net_returns.loc[start:]
        turnover = turnover.loc[start:]
        weights = weights.loc[start:]
    if end:
        net_returns = net_returns.loc[:end]
        turnover = turnover.loc[:end]
        weights = weights.loc[:end]
    net_returns = net_returns.dropna()
    if net_returns.empty:
        raise RuntimeError(f"No returns remain for {run.strategy_name}")

    benchmark = benchmark_returns.reindex(net_returns.index).fillna(0.0)
    equity_curve = (1.0 + net_returns).cumprod()
    total_return = float(equity_curve.iloc[-1] - 1.0)
    years = max((net_returns.index[-1] - net_returns.index[0]).days / 365.25, 1 / 365.25)
    cagr = float(equity_curve.iloc[-1] ** (1.0 / years) - 1.0)
    drawdown = equity_curve / equity_curve.cummax() - 1.0
    max_drawdown = float(drawdown.min())
    std = float(net_returns.std(ddof=0))
    volatility = std * math.sqrt(252) if std else float("nan")
    sharpe = float(net_returns.mean() / std * math.sqrt(252)) if std else float("nan")
    turnover_per_year = float(turnover.reindex(net_returns.index).fillna(0.0).sum() / years)
    tqqq_weight = weights.get("TQQQ", pd.Series(0.0, index=weights.index))
    qqq_weight = weights.get("QQQ", pd.Series(0.0, index=weights.index))
    cash_weight = weights.get(CASH_SYMBOL, pd.Series(0.0, index=weights.index))
    return {
        "Start": str(net_returns.index[0].date()),
        "End": str(net_returns.index[-1].date()),
        "Total Return": total_return,
        "CAGR": cagr,
        "Max Drawdown": max_drawdown,
        "Volatility": volatility,
        "Sharpe": sharpe,
        "Beta vs QQQ": compute_beta(net_returns, benchmark),
        "Information Ratio vs QQQ": compute_information_ratio(net_returns, benchmark),
        "Turnover/Year": turnover_per_year,
        "2020 Return": compute_period_total_return(net_returns, "2020-01-01", "2020-12-31"),
        "2022 Return": compute_period_total_return(net_returns, "2022-01-01", "2022-12-31"),
        "2023 Return": compute_period_total_return(net_returns, "2023-01-01", "2023-12-31"),
        "2023+ CAGR": compute_period_cagr(net_returns, "2023-01-01", None),
        "Average QQQ Weight": float(qqq_weight.reindex(net_returns.index).fillna(0.0).mean()),
        "Average TQQQ Weight": float(tqqq_weight.reindex(net_returns.index).fillna(0.0).mean()),
        "Average Cash Weight": float(cash_weight.reindex(net_returns.index).fillna(0.0).mean()),
        "TQQQ Days Share": float((tqqq_weight.reindex(net_returns.index).fillna(0.0) > 1e-12).mean()),
    }


def build_summary(
    runs: Iterable[StrategyRun],
    benchmark_returns: pd.Series,
    *,
    costs_bps: Iterable[float],
    period_start: str | None,
    period_end: str | None,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for run in runs:
        for cost_bps in costs_bps:
            metrics = summarize_run(
                run,
                benchmark_returns,
                cost_bps=float(cost_bps),
                start=period_start,
                end=period_end,
            )
            rows.append(
                {
                    "strategy": run.strategy_name,
                    "display_name": run.display_name,
                    "cost_bps_one_way": float(cost_bps),
                    **metrics,
                    **run.metadata,
                }
            )
    return pd.DataFrame(rows)


def frame_to_markdown_table(frame: pd.DataFrame) -> str:
    display = frame.copy()
    for column in display.columns:
        if pd.api.types.is_numeric_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{float(value):.6f}")
        else:
            display[column] = display[column].fillna("").astype(str)
    headers = [str(column) for column in display.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in display.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def choose_recommendation(summary: pd.DataFrame) -> dict[str, object]:
    focus = summary.loc[summary["cost_bps_one_way"] == 5.0].copy()
    video_like = focus.loc[focus["family"] == "video_qqq_tqqq_dual_drive"].copy()
    implementable = video_like.loc[video_like["execution_mode"] != "same_close_lookahead"].copy()
    lookahead = video_like.loc[video_like["execution_mode"] == "same_close_lookahead"].copy()
    findings: list[str] = []

    rule_based = implementable.loc[implementable["strategy"] != "buy_hold_45_45_10"].copy()
    best_impl = rule_based.sort_values("CAGR", ascending=False).iloc[0]
    findings.append(
        f"Best implementable reconstruction is `{best_impl['strategy']}` at "
        f"{best_impl['CAGR']:.2%} CAGR / {best_impl['Max Drawdown']:.2%} MaxDD, "
        "below the video's reported 49.40% CAGR."
    )

    buy_hold_45 = implementable.loc[implementable["strategy"] == "buy_hold_45_45_10"]
    if not buy_hold_45.empty:
        row = buy_hold_45.iloc[0]
        findings.append(
            f"The simple 45/45/10 daily-rebalanced reference is {row['CAGR']:.2%} CAGR "
            f"with {row['Max Drawdown']:.2%} MaxDD."
        )

    if not lookahead.empty:
        lookahead_row = lookahead.iloc[0]
        findings.append(
            f"The intentionally biased same-close version reaches {lookahead_row['CAGR']:.2%} CAGR "
            f"with {lookahead_row['Max Drawdown']:.2%} MaxDD, which shows how much close-to-close "
            "lookahead can inflate this family of tests."
        )

    closest_to_video = focus.assign(
        cagr_gap=(focus["CAGR"] - VIDEO_REPORTED["CAGR"]).abs(),
        drawdown_gap=(focus["Max Drawdown"] - VIDEO_REPORTED["Max Drawdown"]).abs(),
    ).sort_values(["cagr_gap", "drawdown_gap"]).iloc[0]
    findings.append(
        f"Closest CAGR to the video in this local run is `{closest_to_video['strategy']}` at "
        f"{closest_to_video['CAGR']:.2%}; it still misses the reported CAGR by "
        f"{closest_to_video['cagr_gap']:.2%}."
    )

    tqqq_buy_hold = focus.loc[focus["strategy"] == "TQQQ_buy_hold"]
    if not tqqq_buy_hold.empty:
        row = tqqq_buy_hold.iloc[0]
        findings.append(
            f"Raw TQQQ buy-and-hold produces {row['CAGR']:.2%} CAGR but {row['Max Drawdown']:.2%} MaxDD."
        )

    return {"findings": findings}


def build_markdown(summary: pd.DataFrame, recommendation: dict[str, object]) -> str:
    focus = summary.loc[summary["cost_bps_one_way"] == 5.0].copy()
    focus = focus.sort_values("CAGR", ascending=False)
    compact_columns = [
        "strategy",
        "execution_mode",
        "CAGR",
        "Max Drawdown",
        "2020 Return",
        "2022 Return",
        "2023 Return",
        "Turnover/Year",
        "Average QQQ Weight",
        "Average TQQQ Weight",
        "known_limitation",
    ]
    lines = [
        "# Video QQQ/TQQQ Dual-Drive Reconstruction",
        "",
        "## Setup",
        "- Data: Yahoo Finance adjusted daily OHLCV.",
        "- Main comparison window follows the video window as closely as trading days allow.",
        "- Cost focus: 5 bps one-way turnover cost.",
        "- The exact video code is not public, so variants are explicit approximations.",
        "",
        "## 5 bps Comparison",
        frame_to_markdown_table(focus[compact_columns]),
        "",
        "## Video Reported Reference",
        f"- Reported CAGR: {VIDEO_REPORTED['CAGR']:.2%}",
        f"- Reported MaxDD: {VIDEO_REPORTED['Max Drawdown']:.2%}",
        f"- Reported 2022 return: {VIDEO_REPORTED['2022 Return']:.2%}",
        "",
        "## Findings",
    ]
    lines.extend(f"- {item}" for item in recommendation["findings"])
    lines.extend(
        [
            "",
            "## Caveats",
            "- The video mentions six internal states, high-level top escape, and below-MA200 low-buy/high-sell behavior, but does not disclose exact conditions.",
            "- The same-close variant is intentionally non-tradable; it is included only as a bias diagnostic.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(summary: pd.DataFrame, recommendation: dict[str, object], results_dir: Path) -> None:
    comparison_path = results_dir / "video_qqq_tqqq_dual_drive_comparison.csv"
    summary_path = results_dir / "video_qqq_tqqq_dual_drive_summary.md"
    recommendation_path = results_dir / "video_qqq_tqqq_dual_drive_recommendation.json"
    summary.to_csv(comparison_path, index=False)
    summary_path.write_text(build_markdown(summary, recommendation), encoding="utf-8")
    recommendation_path.write_text(json.dumps(recommendation, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {comparison_path}")
    print(f"wrote {summary_path}")
    print(f"wrote {recommendation_path}")


def main() -> None:
    args = parse_args()
    results_dir = Path(args.results_dir).expanduser().resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    _qqq_ohlc, returns_matrix, indicators = load_market_data(start=args.download_start, end=args.end)
    runs: list[StrategyRun] = [
        run_video_backtest(config, returns_matrix, indicators)
        for config in VIDEO_CONFIGS
    ]
    runs.extend([build_buy_hold_run("QQQ", returns_matrix), build_buy_hold_run("TQQQ", returns_matrix)])

    summary = build_summary(
        runs,
        returns_matrix["QQQ"],
        costs_bps=args.cost_bps,
        period_start=args.period_start,
        period_end=args.period_end,
    )
    recommendation = choose_recommendation(summary)
    write_outputs(summary, recommendation, results_dir)


if __name__ == "__main__":
    main()
