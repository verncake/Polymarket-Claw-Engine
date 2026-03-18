import logging
from src.api.client import PolymarketClient

logging.basicConfig(level=logging.INFO)

class Executor:
    def __init__(self, config_path="config.json"):
        self.client = PolymarketClient(config_path)
        self.logger = logging.getLogger(__name__)

    def execute_trade(self, token_id, side, price, size):
        """核心交易闭环：查余额 -> 余额校验 -> 下单 -> 记录"""
        self.logger.info(f"Starting trade: {side} {size} @ {price} for {token_id}")
        
        # 1. 安全校验 (Balance Guard)
        # 假设 balance 结构为 {"source": "sdk", "data": {"balance": <value>}}
        balance_res = self.client.get_balance()
        if 'error' in balance_res:
            self.logger.error(f"Balance check failed: {balance_res['message']}")
            return {"status": "error", "message": "Failed balance check"}
            
        balance = float(balance_res.get('data', {}).get('balance', 0))
        required_funds = float(price) * float(size)
        
        if balance < required_funds:
            self.logger.error(f"Insufficient funds: Have {balance}, need {required_funds}")
            return {"status": "error", "message": "Insufficient funds"}
        
        # 2. 交易执行
        try:
            result = self.client.place_order(token_id=token_id, price=price, size=size, side=side)
            self.logger.info(f"Order Success: {result}")
            return {"status": "success", "result": result}
        except Exception as e:
            self.logger.error(f"Trade Execution Failed: {str(e)}")
            return {"status": "error", "message": str(e)}
