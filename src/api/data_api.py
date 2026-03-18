import requests
import logging

class DataAPI:
    BASE_URL = "https://data-api.polymarket.com"
    
    def get_positions(self, user_address):
        # 用户持仓查询
        resp = requests.get(f"{self.BASE_URL}/positions", params={"user": user_address, "sizeThreshold": 0})
        resp.raise_for_status()
        return resp.json()

    def get_closed_positions(self, user_address):
        # 已平仓记录
        resp = requests.get(f"{self.BASE_URL}/closed-positions", params={"user": user_address})
        resp.raise_for_status()
        return resp.json()
