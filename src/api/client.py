import os
import json
import logging
import requests
from typing import Dict, Any
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import AssetType, BalanceAllowanceParams
from scrapling.fetchers import Fetcher
from markdownify import markdownify as md
from src.api.clob_api import CLOBAPI
from src.api.data_api import DataAPI

logging.basicConfig(level=logging.INFO)

class Credentials:
    def __init__(self, key, secret, passphrase):
        self.api_key = key
        self.api_secret = secret
        self.api_passphrase = passphrase

class PolymarketClient:
    def __init__(self, config_path="config.json"):
        # Resolve config path
        if os.path.isabs(config_path):
            config_full_path = config_path
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_full_path = os.path.join(current_dir, '..', '..', config_path)
            
        with open(config_full_path, 'r') as f:
            self.config = json.load(f)

        # Direct access
        self.private_key = self.config['private_key']
        self.api_key = self.config['clob_api_build_key']['api_key']
        self.api_secret = self.config['clob_api_build_key']['api_secret']
        self.passphrase = self.config['clob_api_build_key']['api_passphrase']
        self.proxy_wallet = self.config['proxy_wallet']

        # Initialize SDK with positional arguments
        self.sdk = ClobClient(
            "https://clob.polymarket.com",
            137,
            self.private_key,
            Credentials(self.api_key, self.api_secret, self.passphrase),
            1, # signature_type
            self.proxy_wallet
        )

        self.clob = CLOBAPI(self.api_key, self.api_secret, self.passphrase)
        self.data = DataAPI()

    # ... (rest of methods)
    def fetch_orderbook(self, token_id: str) -> Dict[str, Any]:
        """Fetch orderbook with SDK/API/Scrapling fallback."""
        try:
            return {"source": "sdk", "data": self.sdk.get_order_book(token_id)}
        except Exception as e:
            logging.warning(f"SDK fetch failed: {e}")
            
        try:
            resp = requests.get(f"https://clob.polymarket.com/book?token_id={token_id}", timeout=5)
            resp.raise_for_status()
            return {"source": "api", "data": resp.json()}
        except Exception as e:
            logging.error(f"API fetch failed: {e}")
            
        try:
            p = Fetcher.get(f"https://polymarket.com/market/{token_id}")
            html = p.css("#orderbook").get() or "<div>No data</div>"
            return {"source": "scrapling", "data": md(html)}
        except Exception as e:
            logging.error(f"All fetch methods failed: {e}")
            return {"source": "error", "message": str(e)}

    def get_user_balance(self) -> Dict[str, Any]:
        try:
            return {"source": "clob_api", "data": self.clob.get_balances()}
        except Exception as e:
            return {"source": "error", "message": str(e)}

    def get_account_summary(self) -> Dict[str, Any]:
        """Get all market data and balances."""
        try:
            # USDC Balance
            params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
            collateral = self.sdk.get_balance_allowance(params)
            usdc_balance = int(collateral['balance']) / 1e6
            
            # Open Orders
            # Assuming get_orders returns all orders, filter them
            all_orders = self.sdk.get_orders()
            open_orders = [o for o in all_orders if o.get('status') == 'OPEN']
            
            # Position Value
            val_resp = requests.get(f"https://data-api.polymarket.com/value?user={self.proxy_wallet}", timeout=5)
            val_resp.raise_for_status()
            value_data = val_resp.json()
            position_value = value_data[0]['value'] if value_data else 0
            
            # Realized Pnl
            closed_resp = requests.get(f"https://data-api.polymarket.com/closed-positions?user={self.proxy_wallet}", timeout=5)
            closed_resp.raise_for_status()
            closed_pos = closed_resp.json()
            realized_pnl = sum(p.get('realizedPnl', 0) for p in closed_pos)
            
            return {
                "usdc_balance": usdc_balance,
                "open_orders": len(open_orders),
                "position_value": position_value,
                "realized_pnl": realized_pnl
            }
        except Exception as e:
            import traceback
            logging.error(f"Account summary fetch failed: {e}\n{traceback.format_exc()}")
            return {"error": str(e)}
