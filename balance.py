import json
import os
from src.api.client import PolymarketClient

# 加载配置
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
client = PolymarketClient(config_path=CONFIG_PATH)

def get_balance():
    print('=== Polymarket 账户盈亏实时监控 ===\n')
    print(f'Proxy: {client.proxy_wallet}\n')
    
    try:
        # 使用 PolymarketClient 的统一接口
        summary = client.get_account_summary()
        
        # 补充历史成交数据以计算胜率
        closed_positions = client.data.get_closed_positions()
        
        # 胜率计算
        total_trades = len(closed_positions)
        wins = sum(1 for p in closed_positions if float(p.get('realizedPnl', 0)) > 0)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        print(f'账户余额: {summary["usdc_balance"]:.2f} USDC')
        print(f'交易次数 (已结算): {total_trades}')
        print(f'胜率: {win_rate:.2f}%')
        print(f'未实现盈亏: ${summary["position_value"]:.2f}')
        print(f'已实现盈亏: ${summary["realized_pnl"]:.2f}')
        print(f'总盈亏: ${ (summary["realized_pnl"] + summary["position_value"]):.2f}')
        
    except Exception as e:
        print(f'查询失败: {e}')

if __name__ == '__main__':
    get_balance()
