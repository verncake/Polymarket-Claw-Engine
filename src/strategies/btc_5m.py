"""
BTC 5-Minute Strategy
--------------------
Mean-reversion strategy on BTC-related markets.
Requires Polymarket BTC/USD or BTC>X markets.
"""
import json
import logging
import os
from typing import Dict, Any, Optional

from src.strategies.base import BaseStrategy
from src.api.client import PolymarketClient


class BTC5MStrategy(BaseStrategy):
    """
    BTC 5分钟均值回归策略。

    逻辑：
    1. 获取最近5分钟的价格数据
    2. 计算移动均值与当前价格的偏差
    3. 偏差 > entry_threshold -> 买入信号（由 Runner 执行后回调 on_fill 更新状态）
    4. 偏差 < exit_threshold  -> 卖出信号
    5. 亏损 > stop_loss       -> 止损

    重要：on_tick 只产生信号，不更新内部状态。
    状态更新统一在 on_fill 回调中处理。
    """

    def __init__(self, client: PolymarketClient, config: Dict[str, Any]):
        super().__init__(name="btc_5m", client=client, config=config)
        self.logger = logging.getLogger("strategy.btc_5m")

        self.entry_threshold = config.get("entry_threshold", 0.02)
        self.exit_threshold = config.get("exit_threshold", 0.005)
        self.stop_loss = config.get("stop_loss", 0.01)
        self.max_position = config.get("max_position", 50.0)
        self.market_ids = config.get("market_ids", [])

        self._entry_price: Optional[float] = None
        self._ma_price: Optional[float] = None
        self._in_position = False

    def on_tick(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        生成交易信号。不更新内部状态，状态更新由 Runner 在成交后调用 on_fill 处理。
        market_data 格式: {"price": float, "volume": float, "timestamp": int}
        """
        current_price = market_data.get("price")
        if not current_price:
            return None

        if self._ma_price is None:
            self._ma_price = current_price
        else:
            alpha = 0.3
            self._ma_price = alpha * current_price + (1 - alpha) * self._ma_price

        deviation = (current_price - self._ma_price) / self._ma_price

        self.logger.debug(
            f"[{self.name}] price={current_price:.4f} ma={self._ma_price:.4f} "
            f"dev={deviation:.4f} in_pos={self._in_position}"
        )

        if not self._in_position:
            if deviation < -self.entry_threshold:
                size = min(self._capital * 0.95 / current_price, self.max_position)
                self.logger.info(
                    f"[{self.name}] BUY SIGNAL | price={current_price:.4f} "
                    f"ma={self._ma_price:.4f} dev={deviation:.4f} size={size:.4f}"
                )
                return {
                    "action": "buy",
                    "token_id": self.market_ids[0] if self.market_ids else None,
                    "price": current_price,
                    "size": size,
                }
        else:
            pnl_pct = (current_price - self._entry_price) / self._entry_price

            if pnl_pct <= -self.stop_loss:
                self.logger.info(
                    f"[{self.name}] STOP LOSS | pnl={pnl_pct:.4f} "
                    f"entry={self._entry_price:.4f} current={current_price:.4f}"
                )
                return {
                    "action": "sell",
                    "token_id": self.market_ids[0] if self.market_ids else None,
                    "price": current_price,
                    "size": abs(self._position),
                }

            elif pnl_pct >= self.exit_threshold:
                self.logger.info(
                    f"[{self.name}] TAKE PROFIT | pnl={pnl_pct:.4f} "
                    f"entry={self._entry_price:.4f} current={current_price:.4f}"
                )
                return {
                    "action": "sell",
                    "token_id": self.market_ids[0] if self.market_ids else None,
                    "price": current_price,
                    "size": abs(self._position),
                }

        return None

    def on_fill(self, fill_event: Dict[str, Any]) -> None:
        """
        成交回调：更新内部持仓状态。
        只在订单确认成交后调用。
        """
        side = fill_event.get("side")
        price = fill_event.get("price", 0)
        size = fill_event.get("size", 0)

        if side == "buy":
            self._entry_price = price
            self._in_position = True
        elif side == "sell":
            self._in_position = False
            self._entry_price = None

        self.logger.info(
            f"[{self.name}] Fill | side={side} price={price} size={size} "
            f"in_position={self._in_position}"
        )

    def _load_state(self) -> None:
        state_file = os.path.join("state", f"{self.name}_state.json")
        if os.path.exists(state_file):
            with open(state_file) as f:
                data = json.load(f)
                self._in_position = data.get("in_position", False)
                self._entry_price = data.get("entry_price")
                self._position = data.get("position", 0.0)
                self.logger.info(f"[{self.name}] State restored: pos={self._position}")

    def _save_state(self) -> None:
        os.makedirs("state", exist_ok=True)
        state_file = os.path.join("state", f"{self.name}_state.json")
        with open(state_file, "w") as f:
            json.dump({
                "in_position": self._in_position,
                "entry_price": self._entry_price,
                "position": self._position,
            }, f, indent=2)
