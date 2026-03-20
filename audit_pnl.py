import json
import os
import sys
from src.api.data_api import DataAPI

# 加载配置
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
with open(CONFIG_PATH, 'r') as f:
    config = json.load(f)

# Allow overriding with sys.argv[1]
target_wallet = sys.argv[1] if len(sys.argv) > 1 else config['proxy_wallet']
api = DataAPI(proxy_wallet=target_wallet)

def get_audited_pnl():
    try:
        print(f"Auditing wallet: {target_wallet}")
        # 1. 获取已结算盈亏
        closed = api.get_closed_positions(user=target_wallet)
        
        # 2. 获取所有成交记录 (用于筛选 BTC 5m 策略)
        trades = api.get_trades(user=target_wallet)
        
        # 3. 获取持仓 (未结算)
        positions = api.get_positions(user=target_wallet)
        
        # 过滤策略: 'btc-updown-5m'
        btc_closed = [p for p in closed if 'btc-updown-5m' in (p.get('slug') or "")]
        btc_trades = [t for t in trades if 'btc-updown-5m' in (t.get('slug') or "")]
        btc_positions = [p for p in positions if 'btc-updown-5m' in (p.get('slug') or "")]
        
        # --- 计算 ---
        realized_pnl = sum(float(p.get('realizedPnl', 0)) for p in btc_closed)
        unrealized_pnl = sum(float(p.get('unrealizedPnl', 0)) for p in btc_positions)
        
        # 胜率计算: 
        total_closed = len(btc_closed)
        wins = sum(1 for p in btc_closed if float(p.get('realizedPnl', 0)) > 0)
        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0
        
        print(f"=== BTC 5m 策略审计 ===")
        print(f"相关成交总数: {len(btc_trades)}")
        print(f"已结算笔数: {total_closed}")
        print(f"未结算(持仓)笔数: {len(btc_positions)}")
        print(f"胜率 (已结算): {win_rate:.2f}%")
        print(f"已实现盈亏: ${realized_pnl:.2f}")
        print(f"未实现盈亏: ${unrealized_pnl:.2f}")
        print(f"策略总盈亏: ${realized_pnl + unrealized_pnl:.2f}")
        
    except Exception as e:
        print(f"审计失败: {e}")

if __name__ == "__main__":
    get_audited_pnl()
