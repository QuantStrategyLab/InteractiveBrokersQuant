#!/usr/bin/env python3
"""Compare current ATR entry gate vs direct MA200 entry for tqqq_growth_income."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import backtest_stock_alpha_suite as suite  # noqa: E402
import backtest_tqqq_growth_indicator_variants as base  # noqa: E402

DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent / "results"
DEFAULT_START = "2018-01-01"
DEFAULT_COSTS_BPS = (5.0,)

BASELINE_ENTRY_PARAMS = {
    "atr_entry_scale": 2.5,
    "entry_line_floor": 1.02,
    "entry_line_cap": 1.08,
}
MA200_ENTRY_PARAMS = {
    "atr_entry_scale": 0.0,
    "entry_line_floor": 1.0,
    "entry_line_cap": 1.0,
}
COMMON_TQQQ_PARAMS = {
    "starting_equity": base.RUNTIME_FULL_STARTING_EQUITY,
    "income_threshold_usd": 100_000.0,
    "qqqi_income_ratio": 0.50,
    "cash_reserve_ratio": 0.05,
    "rebalance_threshold_ratio": 0.01,
    "alloc_tier1_breakpoints": (0, 15_000, 30_000, 70_000),
    "alloc_tier1_values": (1.0, 0.95, 0.85, 0.70),
    "alloc_tier2_breakpoints": (70_000, 140_000),
    "alloc_tier2_values": (0.70, 0.50),
    "risk_leverage_factor": 3.0,
    "risk_agg_cap": 0.50,
    "risk_numerator": 0.30,
    "atr_exit_scale": 2.0,
    "exit_line_floor": 0.92,
    "exit_line_cap": 0.98,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=None)
    parser.add_argument("--cost-bps", nargs="*", type=float, default=list(DEFAULT_COSTS_BPS))
    return parser.parse_args()


def load_market_data(*, start: str, end: str | None):
    etf_frames = suite.download_etf_ohlcv(("QQQ", "TQQQ", "BOXX", "SPYI", "QQQI"), start=start, end=end)
    qqq_ohlc = pd.DataFrame(
        {
            "open": etf_frames["open"]["QQQ"],
            "high": etf_frames["high"]["QQQ"],
            "low": etf_frames["low"]["QQQ"],
            "close": etf_frames["close"]["QQQ"],
        }
    ).dropna()
    master_index = qqq_ohlc.index
    rows = suite.build_extra_etf_price_history(etf_frames, symbols=("QQQ", "TQQQ", "BOXX", "SPYI", "QQQI"))
    _close_matrix, returns_matrix = suite.build_asset_return_matrix(
        rows,
        master_index=master_index,
        required_symbols=("QQQ", "TQQQ", "BOXX", "SPYI", "QQQI"),
    )
    returns_matrix[base.CASH_SYMBOL] = 0.0
    indicators = base.build_indicator_frame(qqq_ohlc, etf_frames["volume"]["QQQ"].reindex(master_index).fillna(0.0))
    return qqq_ohlc, returns_matrix, indicators


def build_runtime_variant(qqq_ohlc: pd.DataFrame, returns_matrix: pd.DataFrame, *, name: str, description: str, params: dict[str, float]) -> base.StrategyRun:
    gross_returns, weights_history, turnover_history = suite.run_tqqq_growth_income_backtest(
        qqq_ohlc,
        returns_matrix,
        **COMMON_TQQQ_PARAMS,
        **params,
    )
    index = gross_returns.index
    return base.StrategyRun(
        strategy_name=f"tqqq_growth_income::{name}",
        display_name=f"tqqq_growth_income::{name}",
        gross_returns=gross_returns,
        weights_history=weights_history.reindex(index).fillna(0.0),
        turnover_history=turnover_history.reindex(index).fillna(0.0),
        metadata={
            "family": "tqqq_growth_entry_gate_followup",
            "overlay": name,
            "overlay_description": description,
            "idle_asset": base.SAFE_HAVEN,
            "entry_confirm_days": 0,
            "exit_confirm_days": 0,
            "income_mode": "runtime_full",
        },
        raw_gate=pd.Series(True, index=index),
        active_gate=pd.Series(True, index=index),
    )


def build_attack_only_variant(qqq_ohlc: pd.DataFrame, returns_matrix: pd.DataFrame, indicators: pd.DataFrame, *, name: str, description: str, params: dict[str, float]) -> base.StrategyRun:
    overlay = base.OverlayConfig(name="baseline", description="Current MA200 + ATR baseline with no extra daily gate.")
    run = base.run_attack_only_variant_backtest(
        qqq_ohlc,
        returns_matrix,
        indicators,
        config=base.BacktestConfig(overlay=overlay, idle_asset=base.SAFE_HAVEN, income_mode="attack_only"),
        **params,
    )
    run.strategy_name = f"tqqq_attack_only::{name}"
    run.display_name = f"tqqq_attack_only::{name}"
    run.metadata = {
        **run.metadata,
        "family": "tqqq_growth_entry_gate_followup",
        "overlay": name,
        "overlay_description": description,
    }
    return run


def choose_recommendation(summary: pd.DataFrame) -> dict[str, object]:
    focus = summary.loc[(summary["period"] == "2023+") & (summary["cost_bps_one_way"] == 5.0)].copy()
    pivot = focus.pivot(index="income_mode", columns="overlay", values=["CAGR", "Max Drawdown", "Information Ratio vs QQQ", "Turnover/Year"])
    runtime = focus.loc[focus["income_mode"] == "runtime_full"].set_index("overlay")
    attack = focus.loc[focus["income_mode"] == "attack_only"].set_index("overlay")
    stress = summary.loc[(summary["period"] == "2022") & (summary["cost_bps_one_way"] == 5.0)].copy()
    runtime_stress = stress.loc[stress["income_mode"] == "runtime_full"].set_index("overlay")
    attack_stress = stress.loc[stress["income_mode"] == "attack_only"].set_index("overlay")

    def delta(frame: pd.DataFrame, metric: str) -> float:
        return float(frame.loc["ma200_entry", metric] - frame.loc["current_atr_entry", metric])

    recommendation = {
        "runtime_full_deltas_ma200_minus_current_2023_plus_5bps": {
            "cagr": delta(runtime, "CAGR"),
            "max_drawdown": delta(runtime, "Max Drawdown"),
            "ir_vs_qqq": delta(runtime, "Information Ratio vs QQQ"),
            "turnover_per_year": delta(runtime, "Turnover/Year"),
        },
        "attack_only_deltas_ma200_minus_current_2023_plus_5bps": {
            "cagr": delta(attack, "CAGR"),
            "max_drawdown": delta(attack, "Max Drawdown"),
            "ir_vs_qqq": delta(attack, "Information Ratio vs QQQ"),
            "turnover_per_year": delta(attack, "Turnover/Year"),
        },
        "runtime_full_deltas_ma200_minus_current_2022_5bps": {
            "total_return": delta(runtime_stress, "Total Return"),
            "max_drawdown": delta(runtime_stress, "Max Drawdown"),
            "turnover_per_year": delta(runtime_stress, "Turnover/Year"),
        },
        "attack_only_deltas_ma200_minus_current_2022_5bps": {
            "total_return": delta(attack_stress, "Total Return"),
            "max_drawdown": delta(attack_stress, "Max Drawdown"),
            "turnover_per_year": delta(attack_stress, "Turnover/Year"),
        },
    }
    ma200_wins_oos = recommendation["runtime_full_deltas_ma200_minus_current_2023_plus_5bps"]["cagr"] > 0
    ma200_hurts_stress = recommendation["runtime_full_deltas_ma200_minus_current_2022_5bps"]["total_return"] < -0.03
    recommendation["verdict"] = (
        "MA200 direct entry improves the 2023+ rebound but materially worsens the 2022 stress period; do not switch production directly without an extra risk guard."
        if ma200_wins_oos and ma200_hurts_stress
        else "Keep the current ATR entry gate for production until a stronger variant clears the risk tradeoff."
    )
    recommendation["pivot_2023_plus_5bps"] = {
        f"{metric}::{overlay}": {str(mode): float(value) for mode, value in values.items()}
        for (metric, overlay), values in pivot.to_dict().items()
    }
    return recommendation


def build_markdown(summary: pd.DataFrame, recommendation: dict[str, object]) -> str:
    focus = summary.loc[(summary["period"] == "2023+") & (summary["cost_bps_one_way"] == 5.0)].copy()
    focus = focus.sort_values(["income_mode", "overlay"])
    risk_2022 = summary.loc[(summary["period"] == "2022") & (summary["cost_bps_one_way"] == 5.0)].copy()
    risk_2022 = risk_2022.sort_values(["income_mode", "overlay"])

    lines = [
        "# TQQQ entry-gate follow-up",
        "",
        "## Setup",
        "- Current baseline: flat entry waits for the ATR-adjusted entry line above MA200 (`entry_line_floor=1.02`, `atr_entry_scale=2.5`, cap `1.08`).",
        "- Test variant: when flat, enter as soon as QQQ is above MA200 (`entry_line_floor=1.00`, `atr_entry_scale=0.0`, cap `1.00`).",
        "- Exit and reduce rules are unchanged.",
        "- Both runtime-full and attack-only BOXX variants are included; numbers below use 5 bps one-way turnover cost.",
        "",
        "## OOS 2023+ (5 bps)",
        base.frame_to_markdown_table(
            focus[[
                "income_mode",
                "overlay",
                "CAGR",
                "Max Drawdown",
                "Information Ratio vs QQQ",
                "Turnover/Year",
                "Average TQQQ Weight",
                "TQQQ Days Share",
            ]]
        ),
        "",
        "## 2022 stress period (5 bps)",
        base.frame_to_markdown_table(
            risk_2022[[
                "income_mode",
                "overlay",
                "Total Return",
                "Max Drawdown",
                "Turnover/Year",
                "Average TQQQ Weight",
                "TQQQ Days Share",
            ]]
        ),
        "",
        "## Recommendation",
        f"- {recommendation['verdict']}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    results_dir = Path(args.results_dir).expanduser().resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    qqq_ohlc, returns_matrix, indicators = load_market_data(start=args.start, end=args.end)

    runs = [
        build_runtime_variant(
            qqq_ohlc,
            returns_matrix,
            name="current_atr_entry",
            description="Current ATR-adjusted entry line above MA200.",
            params=BASELINE_ENTRY_PARAMS,
        ),
        build_runtime_variant(
            qqq_ohlc,
            returns_matrix,
            name="ma200_entry",
            description="Enter immediately above MA200 when flat; exits unchanged.",
            params=MA200_ENTRY_PARAMS,
        ),
        build_attack_only_variant(
            qqq_ohlc,
            returns_matrix,
            indicators,
            name="current_atr_entry",
            description="Current ATR-adjusted entry line above MA200.",
            params=BASELINE_ENTRY_PARAMS,
        ),
        build_attack_only_variant(
            qqq_ohlc,
            returns_matrix,
            indicators,
            name="ma200_entry",
            description="Enter immediately above MA200 when flat; exits unchanged.",
            params=MA200_ENTRY_PARAMS,
        ),
    ]
    summary = base.build_summary_rows(runs, returns_matrix["QQQ"], args.cost_bps)
    recommendation = choose_recommendation(summary)

    comparison_path = results_dir / "tqqq_hybrid_entry_gate_followup_comparison.csv"
    summary_path = results_dir / "tqqq_hybrid_entry_gate_followup_summary.md"
    recommendation_path = results_dir / "tqqq_hybrid_entry_gate_followup_recommendation.json"
    summary.to_csv(comparison_path, index=False)
    summary_path.write_text(build_markdown(summary, recommendation), encoding="utf-8")
    recommendation_path.write_text(json.dumps(recommendation, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"comparison": str(comparison_path), "summary": str(summary_path), "recommendation": str(recommendation_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
