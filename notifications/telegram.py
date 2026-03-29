"""Telegram notification and i18n helpers for IBKRQuant."""

from __future__ import annotations


I18N = {
    "zh": {
        "rebalance_title": "🔔 【调仓指令】",
        "heartbeat_title": "💓 【心跳检测】",
        "error_title": "🚨 【策略异常】",
        "canary_title": "🐤 【金丝雀检查】",
        "equity": "净值",
        "buying_power": "购买力",
        "signal_label": "信号",
        "no_trades": "✅ 无需调仓",
        "emergency": "🛡️ 金丝雀应急: {n_bad}/4 坏, 全部转入 {safe}",
        "quarterly": "📊 季度调仓: Top {n} 轮动",
        "daily_check": "📋 每日检查: 金丝雀正常, 持仓不变",
        "hold": "💎 持仓不变",
        "market_sell": "📉 [市价卖出] {symbol}: {qty}股",
        "limit_buy": "📈 [限价买入] {symbol}: {qty}股 @ ${price}",
        "submitted": "已下发 (ID: {order_id})",
        "failed": "失败: {reason}",
        "order_filled": "✅ 订单成交 | {symbol} {side} {qty}股 均价 ${price} (ID: {order_id})",
        "order_partial": "⚠️ 部分成交 | {symbol} {side} {executed}/{qty}股 均价 ${price} (ID: {order_id})",
        "order_rejected": "❌ 订单异常 | {symbol} {side} {qty}股 状态: {status} (ID: {order_id})",
    },
    "en": {
        "rebalance_title": "🔔 【Trade Execution Report】",
        "heartbeat_title": "💓 【Heartbeat】",
        "error_title": "🚨 【Strategy Error】",
        "canary_title": "🐤 【Canary Check】",
        "equity": "Equity",
        "buying_power": "Buying Power",
        "signal_label": "Signal",
        "no_trades": "✅ No rebalance needed",
        "emergency": "🛡️ Canary Emergency: {n_bad}/4 bad, rotating to {safe}",
        "quarterly": "📊 Quarterly Rebalance: Top {n} rotation",
        "daily_check": "📋 Daily Check: canary OK, holding",
        "hold": "💎 Hold positions",
        "market_sell": "📉 [Market sell] {symbol}: {qty} shares",
        "limit_buy": "📈 [Limit buy] {symbol}: {qty} shares @ ${price}",
        "submitted": "submitted (ID: {order_id})",
        "failed": "failed: {reason}",
        "order_filled": "✅ Filled | {symbol} {side} {qty} shares avg ${price} (ID: {order_id})",
        "order_partial": "⚠️ Partial | {symbol} {side} {executed}/{qty} shares avg ${price} (ID: {order_id})",
        "order_rejected": "❌ Rejected | {symbol} {side} {qty} shares status: {status} (ID: {order_id})",
    },
}


def build_translator(lang):
    def translate(key, **kwargs):
        active_lang = lang if lang in I18N else "en"
        template = I18N[active_lang].get(key, key)
        return template.format(**kwargs) if kwargs else template

    return translate


def send_telegram_message(
    message,
    *,
    token,
    chat_id,
    requests_module,
    printer=print,
):
    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        printer(f"TG:\n{message}", flush=True)
        response = requests_module.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=10,
        )
        if not 200 <= response.status_code < 300:
            printer(
                f"Telegram send failed with status {response.status_code}: {response.text}",
                flush=True,
            )
    except Exception as exc:
        printer(f"Telegram send failed: {exc}", flush=True)
