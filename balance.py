import json
import os
import requests
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, BalanceAllowanceParams, AssetType

# Load configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
with open(CONFIG_PATH, 'r') as f:
    config = json.load(f)

PRIVATE_KEY = config['private_key']
PROXY_WALLET = config['proxy_wallet']
API_KEY = config['clob_api_build_key']['api_key']
API_SECRET = config['clob_api_build_key']['api_secret']
PASSPHRASE = config['clob_api_build_key']['api_passphrase']

BASE_URL = 'https://clob.polymarket.com'

def get_balance():
    print('=== Polymarket 账户盈亏实时监控 ===\n')
    print(f'Proxy: {PROXY_WALLET}\n')
    
    creds = ApiCreds(API_KEY, API_SECRET, PASSPHRASE)
    
    try:
        # Client setup
        client = ClobClient(
            host=BASE_URL,
            chain_id=137,
            key=PRIVATE_KEY,
            creds=creds,
            signature_type=2,
            funder=PROXY_WALLET
        )
        
        # 1. 查询 USDC 余额
        params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
        collateral_balance = client.get_balance_allowance(params)
        balance_usdc = float(collateral_balance.get('balance', 0)) / 1e6
        
        # 2. 已实现盈亏 & 胜率 (Closed Positions)
        closed_resp = requests.get(f'https://data-api.polymarket.com/closed-positions?user={PROXY_WALLET}')
        closed = closed_resp.json() if closed_resp.status_code == 200 else []
        
        realized_pnl = sum(float(p.get('realizedPnl', 0)) for p in closed)
        
        # Win Rate Calculation
        total_trades = len(closed)
        wins = sum(1 for p in closed if float(p.get('realizedPnl', 0)) > 0)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        # 3. 未实现盈亏 (Open Positions)
        open_resp = requests.get(f'https://data-api.polymarket.com/positions?user={PROXY_WALLET}')
        positions = open_resp.json() if open_resp.status_code == 200 else []
        unrealized_pnl = 0
        total_value = 0
        
        if isinstance(positions, list):
            unrealized_pnl = sum(float(p.get('unrealizedPnl', 0)) for p in positions)
            total_value = sum(float(p.get('value', 0)) for p in positions)

        print(f'账户余额: {balance_usdc:.2f} USDC')
        print(f'交易次数: {total_trades}')
        print(f'胜率: {win_rate:.2f}%')
        print(f'未实现盈亏: ${unrealized_pnl:.2f}')
        print(f'已实现盈亏: ${realized_pnl:.2f}')
        print(f'当前持仓市值: ${total_value:.4f}')
        print(f'总盈亏: ${ (realized_pnl + unrealized_pnl):.2f}')
        print('\n--- 总览 ---')
        print(f'总净资产: ${(balance_usdc + total_value):.2f}')
        
    except Exception as e:
        print(f'查询失败: {e}')

if __name__ == '__main__':
    get_balance()
