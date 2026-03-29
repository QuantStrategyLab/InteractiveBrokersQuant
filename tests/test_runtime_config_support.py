from runtime_config_support import (
    DEFAULT_ACCOUNT_GROUP,
    DEFAULT_STRATEGY_PROFILE,
    load_platform_runtime_settings,
    parse_account_group_configs,
)


def test_load_platform_runtime_settings_uses_defaults(monkeypatch):
    monkeypatch.setenv("IB_GATEWAY_INSTANCE_NAME", "ib-gateway")
    monkeypatch.setenv("IB_GATEWAY_MODE", "paper")
    monkeypatch.delenv("IB_GATEWAY_ZONE", raising=False)
    monkeypatch.delenv("IB_GATEWAY_IP_MODE", raising=False)
    monkeypatch.delenv("IB_CLIENT_ID", raising=False)
    monkeypatch.delenv("STRATEGY_PROFILE", raising=False)
    monkeypatch.delenv("ACCOUNT_GROUP", raising=False)
    monkeypatch.delenv("IB_ACCOUNT_GROUP_CONFIG_JSON", raising=False)
    monkeypatch.delenv("IB_ACCOUNT_GROUP_CONFIG_SECRET_NAME", raising=False)
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
    assert settings.service_name is None
    assert settings.account_ids == ()
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
    assert settings.service_name is None
    assert settings.account_ids == ()
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



def test_load_platform_runtime_settings_uses_account_group_secret(monkeypatch):
    monkeypatch.setenv("IB_GATEWAY_INSTANCE_NAME", "fallback-host")
    monkeypatch.setenv("IB_GATEWAY_MODE", "paper")
    monkeypatch.setenv("ACCOUNT_GROUP", "ira")
    monkeypatch.setenv("IB_ACCOUNT_GROUP_CONFIG_SECRET_NAME", "ibkr-account-groups")

    payload = """
    {
      "groups": {
        "ira": {
          "ib_gateway_instance_name": "ib-gateway-ira",
          "ib_gateway_zone": "us-central1-a",
          "ib_gateway_mode": "live",
          "ib_gateway_ip_mode": "external",
          "ib_client_id": 9,
          "service_name": "interactive-brokers-quant-ira",
          "account_ids": ["U1234567", "U7654321"]
        }
      }
    }
    """

    class FakeSecretClient:
        def access_secret_version(self, request):
            assert request["name"] == "projects/project-1/secrets/ibkr-account-groups/versions/latest"
            return type(
                "Resp",
                (),
                {"payload": type("Payload", (), {"data": payload.encode("utf-8")})()},
            )()

    settings = load_platform_runtime_settings(
        project_id_resolver=lambda: "project-1",
        secret_client_factory=FakeSecretClient,
    )

    assert settings.ib_gateway_instance_name == "ib-gateway-ira"
    assert settings.ib_gateway_zone == "us-central1-a"
    assert settings.ib_gateway_mode == "live"
    assert settings.ib_gateway_ip_mode == "external"
    assert settings.ib_client_id == 9
    assert settings.account_group == "ira"
    assert settings.service_name == "interactive-brokers-quant-ira"
    assert settings.account_ids == ("U1234567", "U7654321")



def test_load_platform_runtime_settings_falls_back_when_group_config_is_partial(monkeypatch):
    monkeypatch.setenv("IB_GATEWAY_INSTANCE_NAME", "ib-gateway-default")
    monkeypatch.setenv("IB_GATEWAY_MODE", "paper")
    monkeypatch.setenv("IB_GATEWAY_ZONE", "us-central1-b")
    monkeypatch.setenv("IB_CLIENT_ID", "3")
    monkeypatch.setenv("ACCOUNT_GROUP", "default")
    monkeypatch.setenv(
        "IB_ACCOUNT_GROUP_CONFIG_JSON",
        '{"default": {"ib_client_id": 11, "service_name": "interactive-brokers-quant-default"}}',
    )

    settings = load_platform_runtime_settings(project_id_resolver=lambda: "project-1")

    assert settings.ib_gateway_instance_name == "ib-gateway-default"
    assert settings.ib_gateway_zone == "us-central1-b"
    assert settings.ib_gateway_mode == "paper"
    assert settings.ib_client_id == 11
    assert settings.service_name == "interactive-brokers-quant-default"



def test_load_platform_runtime_settings_rejects_unknown_account_group(monkeypatch):
    monkeypatch.setenv("IB_GATEWAY_INSTANCE_NAME", "ib-gateway")
    monkeypatch.setenv("IB_GATEWAY_MODE", "paper")
    monkeypatch.setenv("ACCOUNT_GROUP", "missing")
    monkeypatch.setenv("IB_ACCOUNT_GROUP_CONFIG_JSON", '{"default": {"ib_client_id": 1}}')

    try:
        load_platform_runtime_settings(project_id_resolver=lambda: "project-1")
    except ValueError as exc:
        assert "ACCOUNT_GROUP='missing'" in str(exc)
    else:
        raise AssertionError("expected unknown ACCOUNT_GROUP to fail fast")



def test_parse_account_group_configs_supports_top_level_mapping():
    configs = parse_account_group_configs(
        '{"default": {"ib_client_id": "4", "account_ids": ["U1"], "service_name": "svc"}}'
    )

    assert configs["default"].ib_client_id == 4
    assert configs["default"].account_ids == ("U1",)
    assert configs["default"].service_name == "svc"
