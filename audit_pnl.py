import requests
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
with open(CONFIG_PATH, 'r') as f:
    config = json.load(f)

PROXY_WALLET = config['proxy_wallet']
BASE_DATA_API = "https://data-api.polymarket.com"

def get_audited_pnl():
    try:
        # 1. 获取已结算盈亏
        closed_resp = requests.get(f"{BASE_DATA_API}/closed-positions?user={PROXY_WALLET}")
        closed = closed_resp.json() if closed_resp.status_code == 200 else []
        
        # 2. 获取所有成交记录 (用于筛选 BTC 5m 策略)
        trades_resp = requests.get(f"{BASE_DATA_API}/trades?user={PROXY_WALLET}")
        trades = trades_resp.json() if trades_resp.status_code == 200 else []
        
        # 过滤策略: 'btc-updown-5m'
        btc_closed = [p for p in closed if 'btc-updown-5m' in (p.get('slug') or "")]
        btc_trades = [t for t in trades if 'btc-updown-5m' in (t.get('slug') or "")]
        
        # 3. 获取持仓 (未结算)
        pos_resp = requests.get(f"{BASE_DATA_API}/positions?user={PROXY_WALLET}&sizeThreshold=0")
        positions = pos_resp.json() if pos_resp.status_code == 200 else []
        btc_positions = [p for p in positions if 'btc-updown-5m' in (p.get('slug') or "")]
        
        # --- 计算 ---
        realized_pnl = sum(float(p.get('realizedPnl', 0)) for p in btc_closed)
        unrealized_pnl = sum(float(p.get('unrealizedPnl', 0)) for p in btc_positions)
        
        # 胜率计算: 
        # 用户指出 state.json 中记录 52 笔，closed 只有 10 笔
        # 胜率定义: 已结算盈利笔数 / 已结算总笔数
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
