from src.api.client import PolymarketClient
import os

try:
    # Use absolute path to the config file
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    client = PolymarketClient(config_path)
    # 修正这里的方法名
    balance = client.get_user_balance()
    print(f"Result: {balance}")
except Exception as e:
    print(f"Error: {e}")
