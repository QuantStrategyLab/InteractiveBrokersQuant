from notifications.telegram import build_translator, send_telegram_message


def test_build_translator_supports_chinese():
    translate = build_translator("zh")
    assert translate("equity") == "净值"


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
