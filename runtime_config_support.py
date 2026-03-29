from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

DEFAULT_STRATEGY_PROFILE = "global_etf_rotation"
SUPPORTED_STRATEGY_PROFILES = frozenset({DEFAULT_STRATEGY_PROFILE})
DEFAULT_ACCOUNT_GROUP = "default"


@dataclass(frozen=True)
class PlatformRuntimeSettings:
    project_id: str | None
    ib_gateway_instance_name: str
    ib_gateway_zone: str
    ib_gateway_mode: str
    ib_gateway_ip_mode: str
    ib_client_id: int
    strategy_profile: str
    account_group: str
    tg_token: str | None
    tg_chat_id: str | None
    notify_lang: str


def load_platform_runtime_settings(
    *,
    project_id_resolver: Callable[[], str | None],
    logger: Callable[[str], None] = print,
) -> PlatformRuntimeSettings:
    instance_name = os.getenv("IB_GATEWAY_INSTANCE_NAME")
    if not instance_name:
        raise EnvironmentError("IB_GATEWAY_INSTANCE_NAME is required")

    return PlatformRuntimeSettings(
        project_id=project_id_resolver(),
        ib_gateway_instance_name=instance_name,
        ib_gateway_zone=os.getenv("IB_GATEWAY_ZONE", "").strip(),
        ib_gateway_mode=resolve_ib_gateway_mode(os.getenv("IB_GATEWAY_MODE")),
        ib_gateway_ip_mode=resolve_ib_gateway_ip_mode(os.getenv("IB_GATEWAY_IP_MODE"), logger=logger),
        ib_client_id=int(os.getenv("IB_CLIENT_ID", "1")),
        strategy_profile=resolve_strategy_profile(os.getenv("STRATEGY_PROFILE")),
        account_group=resolve_account_group(os.getenv("ACCOUNT_GROUP")),
        tg_token=os.getenv("TELEGRAM_TOKEN"),
        tg_chat_id=os.getenv("GLOBAL_TELEGRAM_CHAT_ID"),
        notify_lang=os.getenv("NOTIFY_LANG", "en"),
    )


def resolve_strategy_profile(raw_value: str | None) -> str:
    value = (raw_value or DEFAULT_STRATEGY_PROFILE).strip().lower()
    if value not in SUPPORTED_STRATEGY_PROFILES:
        supported = ", ".join(sorted(SUPPORTED_STRATEGY_PROFILES))
        raise ValueError(
            f"Unsupported STRATEGY_PROFILE={raw_value!r}; supported values: {supported}"
        )
    return value


def resolve_account_group(raw_value: str | None) -> str:
    value = (raw_value or DEFAULT_ACCOUNT_GROUP).strip()
    return value or DEFAULT_ACCOUNT_GROUP


def resolve_ib_gateway_mode(raw_value: str | None) -> str:
    mode = (raw_value or "").strip().lower()
    if not mode:
        raise EnvironmentError("IB_GATEWAY_MODE is required and must be either 'live' or 'paper'")
    if mode in {"live", "paper"}:
        return mode
    raise EnvironmentError("IB_GATEWAY_MODE must be either 'live' or 'paper'")


def resolve_ib_gateway_ip_mode(
    raw_value: str | None,
    *,
    logger: Callable[[str], None] = print,
) -> str:
    mode = (raw_value or "internal").strip().lower()
    if mode in {"internal", "external"}:
        return mode
    logger(f"Invalid IB_GATEWAY_IP_MODE={mode!r}, defaulting to internal")
    return "internal"
