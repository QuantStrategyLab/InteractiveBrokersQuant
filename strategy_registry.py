from __future__ import annotations

from us_equity_strategies.platform_registry_support import (
    build_platform_profile_matrix,
    get_enabled_profiles_for_platform,
    resolve_platform_strategy_definition,
)

from quant_platform_kit.common.strategies import StrategyDefinition, US_EQUITY_DOMAIN

IBKR_PLATFORM = "ibkr"

DEFAULT_STRATEGY_PROFILE = "global_etf_rotation"
ROLLBACK_STRATEGY_PROFILE = DEFAULT_STRATEGY_PROFILE

# 平台启用状态从策略定义层拆出来；当前只让 IBKR 明确启用这三条。
IBKR_ENABLED_PROFILES = frozenset(
    {
        "cash_buffer_branch_default",
        "global_etf_rotation",
        "russell_1000_multi_factor_defensive",
    }
)

PLATFORM_SUPPORTED_DOMAINS: dict[str, frozenset[str]] = {
    IBKR_PLATFORM: frozenset({US_EQUITY_DOMAIN}),
}

SUPPORTED_STRATEGY_PROFILES = IBKR_ENABLED_PROFILES


def get_supported_profiles_for_platform(platform_id: str) -> frozenset[str]:
    return get_enabled_profiles_for_platform(
        platform_id,
        expected_platform_id=IBKR_PLATFORM,
        enabled_profiles=IBKR_ENABLED_PROFILES,
    )


def get_platform_profile_matrix() -> list[dict[str, object]]:
    return build_platform_profile_matrix(
        platform_id=IBKR_PLATFORM,
        enabled_profiles=IBKR_ENABLED_PROFILES,
        default_profile=DEFAULT_STRATEGY_PROFILE,
        rollback_profile=ROLLBACK_STRATEGY_PROFILE,
    )


def resolve_strategy_definition(
    raw_value: str | None,
    *,
    platform_id: str,
) -> StrategyDefinition:
    return resolve_platform_strategy_definition(
        raw_value,
        platform_id=platform_id,
        expected_platform_id=IBKR_PLATFORM,
        enabled_profiles=IBKR_ENABLED_PROFILES,
        platform_supported_domains=PLATFORM_SUPPORTED_DOMAINS,
        require_explicit=True,
    )
