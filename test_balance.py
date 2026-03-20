from src.api.client import PolymarketClient
import os

try:
    # Use config in the same directory as this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    client = PolymarketClient(config_path)
    summary = client.get_account_summary()
    print("=== Polymarket 账户余额查询 ===")
    print(f"账户余额: {summary.get('usdc_balance', 0):.2f} USDC")
    print(f"开放订单: {summary.get('open_orders', 0)} 个")
    print(f"持仓价值: ${summary.get('position_value', 0):.4f}")
    print(f"已实现盈亏: ${summary.get('realized_pnl', 0):.2f}")
    print(f"\n--- 总览 ---")
    print(f"总资产: ${(summary.get('usdc_balance', 0) + summary.get('position_value', 0)):.2f}")
except Exception as e:
    print(f"查询失败: {e}")
