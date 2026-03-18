import os
import json
import logging
import requests
from typing import Dict, Any, Union
from py_clob_client.client import ClobClient
from scrapling.fetchers import Fetcher
from markdownify import markdownify as md

# Configuration validation at startup
def validate_config():
    required_envs = ['POLYCLAW_PRIVATE_KEY', 'CLOB_API_KEY', 'CLOB_API_SECRET', 'CLOB_API_PASSPHRASE', 'PROXY_WALLET']
    for env in required_envs:
        if not os.getenv(env):
            raise EnvironmentError(f"Missing mandatory environment variable: {env}")

class PolymarketClient:
    def __init__(self, config_path="config.json"):
        # Validate Env before proceeding
        validate_config()
        
        # Load local config if needed (but ignore API keys in it)
        config_full_path = os.path.join(os.getcwd(), config_path)
        with open(config_full_path, 'r') as f:
            self.config = json.load(f)
        
        self.sdk = ClobClient(
            "https://clob.polymarket.com",
            chain_id=137,
            key=os.getenv('POLYCLAW_PRIVATE_KEY'),
            signature_type=2,
            funder=os.getenv('PROXY_WALLET')
        )
        self.sdk.creds = {
            "key": os.getenv('CLOB_API_KEY'),
            "secret": os.getenv('CLOB_API_SECRET'),
            "passphrase": os.getenv('CLOB_API_PASSPHRASE')
        }

    def fetch_orderbook(self, token_id: str) -> Dict[str, Any]:
        """Fetch orderbook with consistent Dict return type."""
        try:
            # 1. Try SDK
            return {"source": "sdk", "data": self.sdk.get_order_book(token_id)}
        except Exception as e:
            logging.warning(f"SDK fetch failed: {e}. Falling back to API.")
            
        try:
            # 2. Gamma API Fallback
            resp = requests.get(f"https://clob.polymarket.com/book?token_id={token_id}", timeout=5)
            resp.raise_for_status()
            return {"source": "api", "data": resp.json()}
        except requests.exceptions.RequestException as e:
            logging.error(f"API fetch failed: {e}. Falling back to Scrapling.")
            
        try:
            # 3. Scrapling Fallback
            p = Fetcher.get(f"https://polymarket.com/market/{token_id}")
            html = p.css("#orderbook").get() or "<div>No data</div>"
            return {"source": "scrapling", "data": md(html)}
        except Exception as e:
            logging.error(f"All fetch methods failed: {e}")
            return {"source": "error", "message": str(e)}

    def get_balance(self) -> Dict[str, Any]:
        try:
            return {"source": "sdk", "data": self.sdk.get_balance()}
        except Exception as e:
            return {"source": "error", "message": str(e)}
