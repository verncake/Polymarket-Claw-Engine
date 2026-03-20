"""
Gabagool Market-Making Strategy
-------------------------------
提供双边流动性，在买卖价差中赚取收益。
适用于 Polymarket 的 YES/NO 二元预测市场。

配置示例 (config.json):
{
  "strategies": {
    "gabagool": {
      "enabled": true,
      "capital": 200.0,
      "spread": 0.02,            # 买卖价差 (2%)
      "size_per_side": 10.0,     # 每边下单量
      "inventory_limit": 50.0,    # 单边最大持仓
      "rebalance_threshold": 0.1, # 再平衡阈值
      "markets": ["BTC/USD-..."]  # 市场ID列表
    }
  }
}
"""
import logging
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

        # 做市状态
        self._bid_price = None
        self._ask_price = None
        self._inventory_yes = 0.0   # YES 边持仓
        self._inventory_no = 0.0    # NO 边持仓
        self._active_bids = []
        self._active_asks = []

    def on_tick(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        每调度周期检杢库存并重新挂单。
        market_data: {"yes_price": float, "no_price": float, "volume": float}
        """
        yes_price = market_data.get("yes_price")
        no_price = market_data.get("no_price")

        if not yes_price or not no_price:
            return None

        # ── 计算买卖价 ──────────────────────────────────────────────
        mid_price = (yes_price + no_price) / 2.0
        half_spread = mid_price * self.spread / 2

        bid_price = round(mid_price - half_spread, 4)  # 买方价格（期望更低）
        ask_price = round(mid_price + half_spread, 4)  # 卖方价格

        # ── 库存再平衡检查 ─────────────────────────────────────────
        net_inventory = self._inventory_yes - self._inventory_no
        total_inventory = abs(net_inventory)

        if total_inventory > self.inventory_limit:
            # 库存超限，发出平仓指令
            self.logger.warning(
                f"[{self.name}] Inventory limit exceeded: {total_inventory:.2f}, "
                f"rebalancing..."
            )
            return self._rebalance(bid_price, ask_price)

        # ── 挂单策略 ───────────────────────────────────────────────
        orders = []

        # 买 YES（做买方流动性）
        if self._inventory_yes < self.inventory_limit:
            orders.append({
                "action": "buy",
                "token_id": self.markets[0] if self.markets else None,
                "price": bid_price,
                "size": self.size_per_side,
            })

        # 卖 YES（平仓或做空）
        if self._inventory_yes > 0:
            orders.append({
                "action": "sell",
                "token_id": self.markets[0] if self.markets else None,
                "price": ask_price,
                "size": min(self._inventory_yes, self.size_per_side),
            })

        # 检杢是否需要重新挂单（价格变动 > 阈值）
        should_refresh = (
            self._bid_price is None
            or abs(bid_price - self._bid_price) / self._bid_price
            > self.rebalance_threshold
        )

        if should_refresh:
            self._bid_price = bid_price
            self._ask_price = ask_price
            self.logger.info(
                f"[{self.name}] Refreshing quotes | "
                f"bid={bid_price:.4f} ask={ask_price:.4f} "
                f"inv_yes={self._inventory_yes:.2f} inv_no={self._inventory_no:.2f}"
            )
            return {"action": "batch", "orders": orders} if orders else None

        return None

    def _rebalance(self, bid_price: float, ask_price: float) -> Dict[str, Any]:
        """
        库存再平衡：当一方持仓过多时，强制平掉部分仓位。
        """
        net = self._inventory_yes - self._inventory_no

        if net > 0:
            # YES 边超限，卖出一部分
            size_to_sell = min(net * 0.5, self._inventory_yes)
            self.logger.info(f"[{self.name}] Rebalancing: selling {size_to_sell} YES @ {ask_price}")
            return {
                "action": "sell",
                "token_id": self.markets[0] if self.markets else None,
                "price": ask_price,
                "size": size_to_sell,
            }
        else:
            # NO 边超限，卖出部分 NO（相当于买 YES）
            size_to_buy = min(abs(net) * 0.5, self._inventory_no)
            self.logger.info(f"[{self.name}] Rebalancing: buying {size_to_buy} YES @ {bid_price}")
            return {
                "action": "buy",
                "token_id": self.markets[0] if self.markets else None,
                "price": bid_price,
                "size": size_to_buy,
            }

    def on_fill(self, fill_event: Dict[str, Any]) -> None:
        """
        订单成交后更新库存记录。
        由 Engine 在订单成交回调中触发。
        """
        side = fill_event.get("side")
        size = fill_event.get("size", 0)
        price = fill_event.get("price", 0)

        if side == "buy":
            self._inventory_yes += size
        else:
            self._inventory_yes -= size

        self.logger.info(
            f"[{self.name}] Fill update | side={side} size={size} "
            f"inv_yes={self._inventory_yes:.2f}"
        )

    def _load_state(self) -> None:
        import os, json
        state_file = os.path.join("state", f"{self.name}_state.json")
        if os.path.exists(state_file):
            with open(state_file) as f:
                data = json.load(f)
                self._inventory_yes = data.get("inventory_yes", 0.0)
                self._inventory_no = data.get("inventory_no", 0.0)
                self._bid_price = data.get("bid_price")
                self._ask_price = data.get("ask_price")
                self.logger.info(
                    f"[{self.name}] State restored: "
                    f"inv_yes={self._inventory_yes}, inv_no={self._inventory_no}"
                )

    def _save_state(self) -> None:
        import os, json
        os.makedirs("state", exist_ok=True)
        state_file = os.path.join("state", f"{self.name}_state.json")
        with open(state_file, "w") as f:
            json.dump({
                "inventory_yes": self._inventory_yes,
                "inventory_no": self._inventory_no,
                "bid_price": self._bid_price,
                "ask_price": self._ask_price,
            }, f, indent=2)
