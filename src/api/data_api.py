import os
import requests
from typing import Optional, Dict, Any

class GammaClient:
    def __init__(self, base_url: str = "https://gamma-api.polymarket.com"):
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

if __name__ == "__main__":
    client = GammaClient()
    try:
        markets = client.get_markets(limit=1)
        print(f"Successfully fetched market: {markets[0]['question']}")
    except Exception as e:
        print(f"Error: {e}")
