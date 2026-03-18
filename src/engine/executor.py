import logging
from src.api.client import PolymarketClient

class Executor:
    def __init__(self, config_path="config.json"):
        self.client = PolymarketClient(config_path)
        self.logger = logging.getLogger(__name__)

    def execute_trade(self, token_id, side, price, size):
        """核心交易闭环：查余额 -> 下单 -> 记录"""
        self.logger.info(f"Starting trade: {side} {size} @ {price} for {token_id}")
        
        # 1. 安全校验 (Balance Guard)
        balance = self.client.get_balance()
        if 'error' in balance:
            self.logger.error("Failed to check balance.")
            return {"status": "error", "message": "Failed balance check"}
        
        # 2. 交易执行
        try:
            result = self.client.place_order(token_id, price, size, side)
            self.logger.info(f"Order Success: {result}")
            return {"status": "success", "result": result}
        except Exception as e:
            self.logger.error(f"Trade Execution Failed: {str(e)}")
            return {"status": "error", "message": str(e)}
