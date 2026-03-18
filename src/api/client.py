import os
import json
import time
from py_clob_client.client import ClobClient
from scrapling.fetchers import Fetcher
from markdownify import markdownify as md

class PolymarketClient:
    def __init__(self):
        # 从环境变量加载，不再依赖明文文件
        self.private_key = os.getenv('POLYCLAW_PRIVATE_KEY')
        self.api_key = os.getenv('CLOB_API_KEY')
        self.api_secret = os.getenv('CLOB_API_SECRET')
        self.passphrase = os.getenv('CLOB_API_PASSPHRASE')
        
        if not self.private_key:
            raise ValueError("Missing POLYCLAW_PRIVATE_KEY")
            
        self.sdk = ClobClient(
            "https://clob.polymarket.com",
            chain_id=137,
            key=self.private_key,
            signature_type=2,
            funder=os.getenv('PROXY_WALLET')
        )
        self.sdk.creds = {
            "key": self.api_key,
            "secret": self.api_secret,
            "passphrase": self.passphrase
        }

    def fetch_orderbook(self, token_id, retries=3):
        for i in range(retries):
            try:
                return self.sdk.get_order_book(token_id)
            except Exception as e:
                if i == retries - 1:
                    # 最后尝试 Scrapling
                    p = Fetcher.get(f"https://polymarket.com/market/{token_id}")
                    return md(p.css("#orderbook").get() or "No data")
                time.sleep(1)
