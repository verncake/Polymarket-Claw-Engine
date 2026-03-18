import logging
from src.api.client import PolymarketClient

class Executor:
    def __init__(self, config_path="config.json"):
        self.client = PolymarketClient(config_path)
        self.logger = logging.getLogger(__name__)

    def check_and_execute(self, order_data):
        self.logger.info("Checking balance...")
        balance = self.client.get_balance()
        self.logger.info(f"Balance: {balance}")

        self.logger.info("Executing order...")
        result = self.client.place_order(order_data)
        self.logger.info(f"Order Result: {result}")
        return result
