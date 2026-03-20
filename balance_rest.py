import json
import os
import requests
import time
import hmac
import hashlib
import base64
from eth_account import Account
from eth_account.messages import encode_defunct

# Load configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
with open(CONFIG_PATH, 'r') as f:
    config = json.load(f)

PRIVATE_KEY = config['private_key'].replace('0x', '')
PROXY_WALLET = config['proxy_wallet']
API_KEY = config['clob_api_build_key']['api_key']
API_SECRET = config['clob_api_build_key']['api_secret']
PASSPHRASE = config['clob_api_build_key']['api_passphrase']

BASE_URL = 'https://clob.polymarket.com'

def get_signature_headers(endpoint, method, body, timestamp):
    # Standard Polymarket CLOB signature headers
    # This is simplified for balance query
    message = f"{timestamp}{method}{endpoint}{body}"
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return {
        'CLOB-API-KEY': API_KEY,
        'CLOB-API-TIMESTAMP': str(timestamp),
        'CLOB-API-SIGNATURE': signature,
        'CLOB-API-PASSPHRASE': PASSPHRASE,
        'Content-Type': 'application/json'
    }

def get_balance():
    print('=== Polymarket 账户余额查询 (REST API) ===\n')
    print(f'Proxy: {PROXY_WALLET}\n')
    
    # 1. 查询 USDC 余额
    endpoint = "/balance-allowance?asset_type=2"
    timestamp = str(int(time.time()))
    headers = get_signature_headers(endpoint, "GET", "", timestamp)
    
    try:
        resp = requests.get(BASE_URL + endpoint, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            balance_usdc = int(data.get('balance', 0)) / 1e6
            print(f'账户余额: {balance_usdc:.2f} USDC')
        else:
            print(f'获取余额失败: {resp.text}')

        # 2. 查询开放订单
        # Simplified: just count open orders
        # (Usually requires similar auth)
        
        # 3. 持仓价值
        value_resp = requests.get(f'https://data-api.polymarket.com/value?user={PROXY_WALLET}')
        value_data = value_resp.json()
        position_value = value_data[0]['value'] if value_data and isinstance(value_data, list) and len(value_data) > 0 else 0
        print(f'持仓价值: ${position_value:.4f}')
        
        # 4. 已实现盈亏
        closed_resp = requests.get(f'https://data-api.polymarket.com/closed-positions?user={PROXY_WALLET}')
        closed_positions = closed_resp.json()
        realized_pnl = 0
        if isinstance(closed_positions, list):
            btc_closed = [p for p in closed_positions if 'btc-updown-5m' in (p.get('slug') or "")]
            realized_pnl = sum(float(p.get('realizedPnl', 0)) for p in btc_closed)
        print(f'已实现盈亏 (BTC 5m): ${realized_pnl:.2f}')
        
        print('\n--- 总览 ---')
        print(f'持仓价值: ${position_value:.4f}')
        
    except Exception as e:
        print(f'查询失败: {e}')

if __name__ == '__main__':
    get_balance()
