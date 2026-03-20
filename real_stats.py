import requests
import json
import os

# Configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
with open(CONFIG_PATH, 'r') as f:
    config = json.load(f)

PROXY_WALLET = config['proxy_wallet']
BASE_DATA_API = "https://data-api.polymarket.com"

def get_real_stats():
    print(f"=== 分析账户: {PROXY_WALLET} ===\n")
    
    try:
        # 1. 获取所有成交记录 (Trades)
        trades_resp = requests.get(f"{BASE_DATA_API}/trades?user={PROXY_WALLET}")
        trades = trades_resp.json() if trades_resp.status_code == 200 else []
        
        # 2. 获取已结算盈亏 (Closed Positions)
        closed_resp = requests.get(f"{BASE_DATA_API}/closed-positions?user={PROXY_WALLET}")
        closed = closed_resp.json() if closed_resp.status_code == 200 else []
        
        # 3. 获取当前持仓 (Positions)
        pos_resp = requests.get(f"{BASE_DATA_API}/positions?user={PROXY_WALLET}&sizeThreshold=0")
        positions = pos_resp.json() if pos_resp.status_code == 200 else []
        
        # --- 计算 ---
        
        # Realized P&L
        realized_pnl = sum(float(p.get('realizedPnl', 0)) for p in closed)
        
        # Win Rate (Based on closed positions)
        total_closed = len(closed)
        winning_closed = sum(1 for p in closed if float(p.get('realizedPnl', 0)) > 0)
        win_rate = (winning_closed / total_closed * 100) if total_closed > 0 else 0
        
        # Unrealized P&L (Floating)
        unrealized_pnl = sum(float(p.get('unrealizedPnl', 0)) for p in positions)
        total_value = sum(float(p.get('value', 0)) for p in positions)
        
        print(f"成交总数 (Trades): {len(trades)}")
        print(f"已结算笔数 (Closed): {total_closed}")
        print(f"胜率 (已结算): {win_rate:.2f}%")
        print(f"已实现盈亏: ${realized_pnl:.2f}")
        print(f"未实现盈亏: ${unrealized_pnl:.2f}")
        print(f"总盈亏: ${realized_pnl + unrealized_pnl:.2f}")
        print(f"当前持仓市值: ${total_value:.2f}")
        
    except Exception as e:
        print(f"查询失败: {e}")

if __name__ == "__main__":
    get_real_stats()
