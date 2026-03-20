import os
import requests
from typing import Dict, Any

class DataAPI:
    def __init__(self, proxy_wallet: str, base_url: str = "https://data-api.polymarket.com"):
        self.proxy_wallet = proxy_wallet
        self.base_url = base_url

    def get_markets(self, active: bool = True, closed: bool = False, limit: int = 10) -> Any:
        params = {
            "active": str(active).lower(),
            "closed": str(closed).lower(),
            "limit": limit
        }
        response = requests.get(f"{self.base_url}/markets", params=params)
        response.raise_for_status()
        return response.json()

    def get_market_details(self, market_slug: str) -> Any:
        response = requests.get(f"{self.base_url}/markets/{market_slug}")
        response.raise_for_status()
        return response.json()

    def get_trades(self, user: str = None) -> Any:
        user = user or self.proxy_wallet
        response = requests.get(f"{self.base_url}/trades?user={user}", timeout=5)
        response.raise_for_status()
        return response.json()

    def get_positions_value(self, user: str = None) -> float:
        user = user or self.proxy_wallet
        response = requests.get(f"{self.base_url}/value?user={user}", timeout=5)
        response.raise_for_status()
        value_data = response.json()
        return value_data[0]['value'] if value_data and len(value_data) > 0 else 0.0

    def get_closed_positions(self, user: str = None) -> Any:
        user = user or self.proxy_wallet
        response = requests.get(f"{self.base_url}/closed-positions?user={user}", timeout=5)
        response.raise_for_status()
        return response.json()

    def get_positions(self, user: str = None) -> Any:
        user = user or self.proxy_wallet
        response = requests.get(f"{self.base_url}/positions?user={user}&sizeThreshold=0", timeout=5)
        response.raise_for_status()
        return response.json()
