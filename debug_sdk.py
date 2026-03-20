from src.api.client import PolymarketClient
client = PolymarketClient("config.json")
print([m for m in dir(client.sdk) if not m.startswith('_')])
