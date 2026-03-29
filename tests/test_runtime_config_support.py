from runtime_config_support import (
    DEFAULT_ACCOUNT_GROUP,
    DEFAULT_STRATEGY_PROFILE,
    load_platform_runtime_settings,
)


def test_load_platform_runtime_settings_uses_defaults(monkeypatch):
    monkeypatch.setenv("IB_GATEWAY_INSTANCE_NAME", "ib-gateway")
    monkeypatch.setenv("IB_GATEWAY_MODE", "paper")
    monkeypatch.delenv("IB_GATEWAY_ZONE", raising=False)
    monkeypatch.delenv("IB_GATEWAY_IP_MODE", raising=False)
    monkeypatch.delenv("IB_CLIENT_ID", raising=False)
    monkeypatch.delenv("STRATEGY_PROFILE", raising=False)
    monkeypatch.delenv("ACCOUNT_GROUP", raising=False)
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    monkeypatch.delenv("GLOBAL_TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("NOTIFY_LANG", raising=False)

    settings = load_platform_runtime_settings(project_id_resolver=lambda: "project-1")

    assert settings.project_id == "project-1"
    assert settings.ib_gateway_instance_name == "ib-gateway"
    assert settings.ib_gateway_zone == ""
    assert settings.ib_gateway_mode == "paper"
    assert settings.ib_gateway_ip_mode == "internal"
    assert settings.ib_client_id == 1
    assert settings.strategy_profile == DEFAULT_STRATEGY_PROFILE
    assert settings.account_group == DEFAULT_ACCOUNT_GROUP
    assert settings.notify_lang == "en"
    assert settings.tg_token is None
    assert settings.tg_chat_id is None


def test_load_platform_runtime_settings_supports_explicit_platform_values(monkeypatch):
    monkeypatch.setenv("IB_GATEWAY_INSTANCE_NAME", "ib-gateway")
    monkeypatch.setenv("IB_GATEWAY_ZONE", "us-central1-a")
    monkeypatch.setenv("IB_GATEWAY_MODE", "live")
    monkeypatch.setenv("IB_GATEWAY_IP_MODE", "external")
    monkeypatch.setenv("IB_CLIENT_ID", "7")
    monkeypatch.setenv("STRATEGY_PROFILE", "global_etf_rotation")
    monkeypatch.setenv("ACCOUNT_GROUP", "taxable_main")
    monkeypatch.setenv("TELEGRAM_TOKEN", "token-1")
    monkeypatch.setenv("GLOBAL_TELEGRAM_CHAT_ID", "chat-1")
    monkeypatch.setenv("NOTIFY_LANG", "zh")

    settings = load_platform_runtime_settings(project_id_resolver=lambda: None)

    assert settings.ib_gateway_zone == "us-central1-a"
    assert settings.ib_gateway_mode == "live"
    assert settings.ib_gateway_ip_mode == "external"
    assert settings.ib_client_id == 7
    assert settings.strategy_profile == "global_etf_rotation"
    assert settings.account_group == "taxable_main"
    assert settings.tg_token == "token-1"
    assert settings.tg_chat_id == "chat-1"
    assert settings.notify_lang == "zh"


def test_load_platform_runtime_settings_rejects_unknown_strategy_profile(monkeypatch):
    monkeypatch.setenv("IB_GATEWAY_INSTANCE_NAME", "ib-gateway")
    monkeypatch.setenv("IB_GATEWAY_MODE", "paper")
    monkeypatch.setenv("STRATEGY_PROFILE", "balanced_income")

    try:
        load_platform_runtime_settings(project_id_resolver=lambda: None)
    except ValueError as exc:
        assert "Unsupported STRATEGY_PROFILE" in str(exc)
    else:
        raise AssertionError("expected Unsupported STRATEGY_PROFILE to fail fast")
