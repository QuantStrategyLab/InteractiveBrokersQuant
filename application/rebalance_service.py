"""Application orchestration for IBKRQuant."""

from __future__ import annotations


def build_dashboard(positions, account_values, signal_desc, canary_str, *, translator, separator):
    equity = account_values.get("equity", 0)
    buying_power = account_values.get("buying_power", 0)
    position_lines = []
    for symbol in sorted(positions.keys()):
        qty = positions[symbol]["quantity"]
        avg = positions[symbol]["avg_cost"]
        market_value = qty * avg
        position_lines.append(f"  {symbol}: {qty}股 ${market_value:,.2f}")
    position_text = "\n".join(position_lines) if position_lines else "  (空仓)"
    return (
        f"{translator('equity')}: ${equity:,.2f} | {translator('buying_power')}: ${buying_power:,.2f}\n"
        f"{separator}\n"
        f"{position_text}\n"
        f"{separator}\n"
        f"🐤 {canary_str}\n"
        f"🎯 {signal_desc}"
    )


def run_strategy_core(
    *,
    connect_ib,
    get_current_portfolio,
    compute_signals,
    execute_rebalance,
    send_tg_message,
    translator,
    separator,
):
    ib = None
    try:
        ib = connect_ib()
        positions, account_values = get_current_portfolio(ib)
        current_holdings = set(positions.keys())
        target_weights, signal_desc, _is_emergency, canary_str = compute_signals(ib, current_holdings)

        dashboard = build_dashboard(
            positions,
            account_values,
            signal_desc,
            canary_str,
            translator=translator,
            separator=separator,
        )

        if target_weights is None:
            message = f"{translator('heartbeat_title')}\n{dashboard}\n{separator}\n{translator('no_trades')}"
            send_tg_message(message)
            print(message, flush=True)
            return "OK - heartbeat"

        trade_logs = execute_rebalance(ib, target_weights, positions, account_values)
        if trade_logs:
            trade_lines = "\n".join(trade_logs)
            message = (
                f"{translator('rebalance_title')}\n"
                f"{dashboard}\n"
                f"{separator}\n"
                f"{trade_lines}"
            )
        else:
            message = f"{translator('heartbeat_title')}\n{dashboard}\n{separator}\n{translator('no_trades')}"

        send_tg_message(message)
        print(message, flush=True)
        return "OK - executed"
    finally:
        if ib is not None and ib.isConnected():
            ib.disconnect()

