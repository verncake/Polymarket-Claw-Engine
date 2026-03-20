import os
import json
import logging
from typing import Dict, Any
from py_clob_client.client import ClobClient
from scrapling.fetchers import Fetcher
from markdownify import markdownify as md

logging.basicConfig(level=logging.INFO)

class PolymarketClient:
    def __init__(self, config_path="config.json"):
        config_full_path = os.path.join(os.getcwd(), config_path)
        with open(config_full_path, 'r') as f:
            self.config = json.load(f)

        def _get_val(env_var, config_path_list):
            val = os.getenv(env_var)
            if val: return val
            temp = self.config
            for k in config_path_list:
                temp = temp.get(k, {})
            return temp if isinstance(temp, str) else None

        self.private_key = _get_val('POLYCLAW_PRIVATE_KEY', ['private_key'])
        if not self.private_key: raise ValueError("Missing POLYCLAW_PRIVATE_KEY")
        
        self.api_key = _get_val('CLOB_API_KEY', ['clob_api_build_key', 'api_key'])
        self.api_secret = _get_val('CLOB_API_SECRET', ['clob_api_build_key', 'api_secret'])
        self.passphrase = _get_val('CLOB_API_PASSPHRASE', ['clob_api_build_key', 'passphrase'])
        self.proxy_wallet = _get_val('PROXY_WALLET', ['proxy_wallet'])

        if not self.proxy_wallet: raise ValueError("Missing PROXY_WALLET")

        self.sdk = ClobClient(
            "https://clob.polymarket.com",
            chain_id=137,
            key=self.private_key,
            signature_type=2,
            funder=self.proxy_wallet
        )
        self.sdk.creds = {
            "key": self.api_key,
            "secret": self.api_secret,
            "passphrase": self.passphrase
        }

    def fetch_orderbook(self, token_id: str) -> Dict[str, Any]:
        try:
            return {"source": "sdk", "data": self.sdk.get_order_book(token_id)}
        except Exception as e:
            logging.warning(f"SDK fetch failed: {e}")
            
        try:
            import requests
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
            return {"source": "sdk", "data": self.sdk.get_balance()}
        except Exception as e:
            return {"source": "error", "message": str(e)}
