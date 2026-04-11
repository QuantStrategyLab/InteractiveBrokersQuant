from notifications.telegram import build_translator, send_telegram_message


def test_build_translator_supports_chinese():
    translate = build_translator("zh")
    assert translate("equity") == "净值"
    assert translate("target_weights_title") == "目标持仓"
    assert translate("market_status_risk_on", asset="SOXL") == "🚀 风险开启（SOXL）"
    assert translate("signal_risk_on", window=150, ratio="40.2%") == "SOXL 站上 150 日均线，持有 SOXL，交易层风险仓位 40.2%"


def test_send_telegram_message_logs_non_200_response(capsys):
    class FakeResponse:
        status_code = 401
        text = "unauthorized"

    class FakeRequests:
        @staticmethod
        def post(*args, **kwargs):
            return FakeResponse()

    send_telegram_message(
        "hello",
        token="token",
        chat_id="chat-id",
        requests_module=FakeRequests,
    )

    captured = capsys.readouterr()
    assert "Telegram send failed with status 401: unauthorized" in captured.out
