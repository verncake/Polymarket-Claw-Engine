from src.api.client import PolymarketClient
import os

try:
    # Use absolute path to the config file
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    client = PolymarketClient(config_path)
    balance = client.get_balance()
    print(f"Result: {balance}")
except Exception as e:
    print(f"Error: {e}")
