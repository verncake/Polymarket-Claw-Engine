"""
Gabagool Market-Making Strategy
-------------------------------
提供双边流动性，在买卖价差中赚取收益。
适用于 Polymarket 的 YES/NO 二元预测市场。
"""
import json
import logging
import os
from typing import Dict, Any, Optional

from src.strategies.base import BaseStrategy
from src.api.client import PolymarketClient


class GabagoolStrategy(BaseStrategy):
    """
    Gabagool 做市策略：
    - 在当前市场价格的上下两侧同时挂单
    - 价差（spread）覆盖手续费并产生利润
    - 持仓偏向一方时触发再平衡
    """

    def __init__(self, client: PolymarketClient, config: Dict[str, Any]):
        super().__init__(name="gabagool", client=client, config=config)
        self.logger = logging.getLogger("strategy.gabagool")

        self.spread = config.get("spread", 0.02)
        self.size_per_side = config.get("size_per_side", 10.0)
        self.inventory_limit = config.get("inventory_limit", 50.0)
        self.rebalance_threshold = config.get("rebalance_threshold", 0.1)
        self.markets = config.get("markets", [])

        self._bid_price: Optional[float] = None
        self._ask_price: Optional[float] = None
        self._inventory_yes = 0.0

    def on_tick(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        每调度周期检查库存并重新挂单。
        market_data: {"yes_price": float, "no_price": float, "volume": float}
        """
        yes_price = market_data.get("yes_price")
        no_price = market_data.get("no_price")

        if not yes_price or not no_price:
            return None

        mid_price = (yes_price + no_price) / 2.0
        half_spread = mid_price * self.spread / 2

        bid_price = round(mid_price - half_spread, 4)
        ask_price = round(mid_price + half_spread, 4)

        net_inventory = self._inventory_yes
        total_inventory = abs(net_inventory)

        if total_inventory > self.inventory_limit:
            self.logger.warning(
                f"[{self.name}] Inventory limit exceeded: {total_inventory:.2f}, rebalancing..."
            )
            return self._rebalance(bid_price, ask_price)

        orders = []

        if self._inventory_yes < self.inventory_limit:
            orders.append({
                "action": "buy",
                "token_id": self.markets[0] if self.markets else None,
                "price": bid_price,
                "size": self.size_per_side,
            })

        if self._inventory_yes > 0:
            orders.append({
                "action": "sell",
                "token_id": self.markets[0] if self.markets else None,
                "price": ask_price,
                "size": min(self._inventory_yes, self.size_per_side),
            })

        should_refresh = (
            self._bid_price is None
            or (
                self._bid_price > 0
                and abs(bid_price - self._bid_price) / self._bid_price
                > self.rebalance_threshold
            )
        )

        if should_refresh:
            self._bid_price = bid_price
            self._ask_price = ask_price
            self.logger.info(
                f"[{self.name}] Refreshing quotes | bid={bid_price:.4f} ask={ask_price:.4f} "
                f"inv_yes={self._inventory_yes:.2f}"
            )
            return {"action": "batch", "orders": orders} if orders else None

        return None

    def _rebalance(self, bid_price: float, ask_price: float) -> Dict[str, Any]:
        """库存再平衡：当 YES 边持仓过多时，强制平掉部分仓位。"""
        if self._inventory_yes > 0:
            size_to_sell = min(self._inventory_yes * 0.5, self._inventory_yes)
            self.logger.info(
                f"[{self.name}] Rebalancing: selling {size_to_sell} YES @ {ask_price}"
            )
            return {
                "action": "sell",
                "token_id": self.markets[0] if self.markets else None,
                "price": ask_price,
                "size": size_to_sell,
            }
        return None

    def on_fill(self, fill_event: Dict[str, Any]) -> None:
        """
        成交回调：根据实际成交更新库存记录。
        由 Runner 在订单成交后调用。
        """
        side = fill_event.get("side")
        size = fill_event.get("size", 0)

        if side == "buy":
            self._inventory_yes += size
        elif side == "sell":
            self._inventory_yes -= size

        self.logger.info(
            f"[{self.name}] Fill | side={side} size={size} "
            f"inv_yes={self._inventory_yes:.2f}"
        )

    def _load_state(self) -> None:
        state_file = os.path.join("state", f"{self.name}_state.json")
        if os.path.exists(state_file):
            with open(state_file) as f:
                data = json.load(f)
                self._inventory_yes = data.get("inventory_yes", 0.0)
                self._bid_price = data.get("bid_price")
                self._ask_price = data.get("ask_price")
                self.logger.info(
                    f"[{self.name}] State restored: inv_yes={self._inventory_yes:.2f}"
                )

    def _save_state(self) -> None:
        os.makedirs("state", exist_ok=True)
        state_file = os.path.join("state", f"{self.name}_state.json")
        with open(state_file, "w") as f:
            json.dump({
                "inventory_yes": self._inventory_yes,
                "bid_price": self._bid_price,
                "ask_price": self._ask_price,
            }, f, indent=2)
