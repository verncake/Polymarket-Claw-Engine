from src.api.data_api import DataAPI
from src.api.clob_api import CLOBAPI
import json

class PolymarketClient:
    def __init__(self, config_path="config.json"):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.data = DataAPI()
        self.clob = CLOBAPI(
            self.config['clob_api_build_key']['api_key'],
            self.config['clob_api_build_key']['api_secret'],
            self.config['clob_api_build_key']['passphrase']
        )
    
    def get_user_balance(self):
        # 统一调用接口
        return self.clob.get_balances()
    
    def get_user_positions(self):
        return self.data.get_positions(self.config['proxy_wallet'])
