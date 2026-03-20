import os
import json
import logging
import requests
import traceback
from typing import Dict, Any
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import AssetType, BalanceAllowanceParams, ApiCreds
from scrapling.fetchers import Fetcher
from markdownify import markdownify as md
from src.api.clob_api import CLOBAPI
from src.api.data_api import DataAPI

logging.basicConfig(level=logging.INFO)

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

        # Helper for Env > Config fallback
        def _get_val(env_var, config_path_list):
            val = os.getenv(env_var)
            if val: return val
            
            temp = self.config
            for k in config_path_list:
                temp = temp.get(k, {})
            if isinstance(temp, str): return temp
            raise ValueError(f"Missing mandatory credential: {env_var} or {config_path_list}")

        self.private_key = _get_val('POLYCLAW_PRIVATE_KEY', ['private_key'])
        self.api_key = _get_val('CLOB_API_KEY', ['clob_api_build_key', 'api_key'])
        self.api_secret = _get_val('CLOB_API_SECRET', ['clob_api_build_key', 'api_secret'])
        self.passphrase = _get_val('CLOB_API_PASSPHRASE', ['clob_api_build_key', 'api_passphrase'])
        self.proxy_wallet = _get_val('PROXY_WALLET', ['proxy_wallet'])

        self.sdk = ClobClient(
            "https://clob.polymarket.com",
            137,
            self.private_key,
            ApiCreds(self.api_key, self.api_secret, self.passphrase),
            1, # signature_type
            self.proxy_wallet
        )

        self.clob = CLOBAPI(self.api_key, self.api_secret, self.passphrase)
        self.data = DataAPI(self.proxy_wallet)

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
            all_orders = self.sdk.get_orders()
            open_orders = [o for o in all_orders if o.get('status') == 'OPEN']
            
            # Position Value
            position_value = self.data.get_positions_value()
            
            # Realized Pnl
            closed_pos = self.data.get_closed_positions()
            realized_pnl = sum(float(p.get('realizedPnl', 0)) for p in closed_pos)
            
            return {
                "usdc_balance": usdc_balance,
                "open_orders": len(open_orders),
                "position_value": position_value,
                "realized_pnl": realized_pnl
            }
        except Exception as e:
            logging.error(f"Account summary fetch failed: {e}\n{traceback.format_exc()}")
            return {"error": str(e)}
