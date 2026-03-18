import requests

class DataAPI:
    BASE_URL = "https://data-api.polymarket.com"
    
    @staticmethod
    def get_positions(user_address, size_threshold=0):
        # Query user positions
        resp = requests.get(f"{DataAPI.BASE_URL}/positions", params={"user": user_address, "sizeThreshold": size_threshold})
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def get_closed_positions(user_address):
        # Get records of closed positions
        resp = requests.get(f"{DataAPI.BASE_URL}/closed-positions", params={"user": user_address})
        resp.raise_for_status()
        return resp.json()
