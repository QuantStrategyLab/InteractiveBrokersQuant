import importlib.util
import sys
from pathlib import Path

import pandas as pd


def load_research_module():
    path = Path(__file__).resolve().parents[1] / "research" / "backtest_qqq_variants.py"
    spec = importlib.util.spec_from_file_location("backtest_qqq_variants_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_configs_includes_voo_xlk_smh_variants():
    module = load_research_module()

    configs = module.build_configs([0.2, 0.3, 0.4])
    configs_by_name = {config.name: config for config in configs}

    assert "baseline_non_tech" in configs_by_name
    assert "current_default_qqq" in configs_by_name
    assert "proposed_voo_xlk_smh" in configs_by_name
    assert "replace_qqq_with_voo" in configs_by_name
    assert "voo_plus_xlk" in configs_by_name
    assert "voo_plus_xlk_plus_smh" in configs_by_name

    assert "VOO" in configs_by_name["replace_qqq_with_voo"].ranking_pool
    assert "XLK" in configs_by_name["voo_plus_xlk"].ranking_pool
    assert "SMH" in configs_by_name["voo_plus_xlk_plus_smh"].ranking_pool


def test_build_configs_includes_lightweight_experiments():
    module = load_research_module()

    configs = module.build_configs([0.2, 0.3, 0.4])
    names = {config.name for config in configs}

    assert "voo_bonus_0_5" in names
    assert "voo_bonus_1_0" in names
    assert "switch_threshold_1_0" in names
    assert "hold_bonus_1_0" in names
    assert "hold_bonus_3_0" in names


def test_compute_rotation_weights_applies_voo_bonus():
    module = load_research_module()

    date = pd.Timestamp("2024-03-31")
    momentum = pd.DataFrame(
        {
            "VOO": [0.08],
            "XLK": [0.09],
            "SMH": [0.12],
        },
        index=[date],
    )
    sma_ok = pd.DataFrame(True, index=[date], columns=momentum.columns)

    config = module.StrategyConfig(
        "voo_bonus_test",
        ("VOO", "XLK", "SMH"),
        voo_bonus=0.02,
    )

    weights = module.compute_rotation_weights(date, config, momentum, sma_ok, current_weights={})

    assert set(weights) == {"VOO", "SMH"}


def test_compute_rotation_weights_respects_switch_threshold():
    module = load_research_module()

    date = pd.Timestamp("2024-03-31")
    momentum = pd.DataFrame(
        {
            "VOO": [0.10],
            "XLK": [0.09],
            "SMH": [0.105],
            "XLE": [0.085],
        },
        index=[date],
    )
    sma_ok = pd.DataFrame(True, index=[date], columns=momentum.columns)
    current_weights = {"VOO": 0.5, "XLK": 0.5}

    config = module.StrategyConfig(
        "switch_threshold_test",
        ("VOO", "XLK", "SMH", "XLE"),
        switch_threshold=0.01,
    )

    weights = module.compute_rotation_weights(date, config, momentum, sma_ok, current_weights=current_weights)

    assert set(weights) == {"VOO", "XLK"}
