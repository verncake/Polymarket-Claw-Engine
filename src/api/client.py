import os
import json
import logging
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL
from scrapling.fetchers import Fetcher
from markdownify import markdownify as md

logging.basicConfig(level=logging.INFO)

class PolymarketClient:
    def __init__(self, config_path="config.json"):
        # 读取配置，支持环境变量覆写
        config_full_path = os.path.join(os.getcwd(), config_path)
        with open(config_full_path, 'r') as f:
            self.config = json.load(f)
        
        self.private_key = os.getenv('POLYCLAW_PRIVATE_KEY', self.config.get('private_key'))
        self.api_key = os.getenv('CLOB_API_KEY', self.config['clob_api_build_key']['api_key'])
        self.api_secret = os.getenv('CLOB_API_SECRET', self.config['clob_api_build_key']['api_secret'])
        self.passphrase = os.getenv('CLOB_API_PASSPHRASE', self.config['clob_api_build_key']['passphrase'])
        self.proxy_wallet = os.getenv('PROXY_WALLET', self.config.get('proxy_wallet'))

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

    def fetch_orderbook(self, token_id, retries=3):
        # 遵循协议：SDK -> API -> Scrapling
        for i in range(retries):
            try:
                return self.sdk.get_order_book(token_id)
            except Exception:
                if i == retries - 1:
                    p = Fetcher.get(f"https://polymarket.com/market/{token_id}")
                    html = p.css("#orderbook").get() or "<div>No data</div>"
                    return md(html) # 已经清洗
                continue

    def get_balance(self):
        try:
            return self.sdk.get_balance()
        except Exception as e:
            return {"error": str(e)}

    def place_order(self, token_id, price, size, side):
        """执行下单"""
        order_args = OrderArgs(
            token_id=token_id,
            price=price,
            size=size,
            side=BUY if side == "BUY" else SELL,
            order_type=OrderType.GTC
        )
        # 获取市场参数(tick_size, neg_risk)
        market = self.sdk.get_market(token_id) # 假设 token_id 关联 market
        return self.sdk.create_and_post_order(
            order_args,
            options={"tick_size": str(market.get("minimum_tick_size", "0.01")), "neg_risk": market.get("neg_risk", False)}
        )
