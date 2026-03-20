"""
BTC 5-Minute Strategy
--------------------
Mean-reversion strategy on BTC-related markets.
Requires Polymarket BTC/USD or BTC>X markets.

配置示例 (config.json):
{
  "strategies": {
    "btc_5m": {
      "enabled": true,
      "capital": 100.0,
      "entry_threshold": 0.02,    # 入场偏差阈值 (2%)
      "exit_threshold": 0.005,     # 止盈阈值 (0.5%)
      "stop_loss": 0.01,           # 止损阈值 (1%)
      "max_position": 50.0,
      "market_ids": ["BTC/USD-..."] # Polymarket condition_id
    }
  }
}
"""
import logging
from typing import Dict, Any, Optional

from src.strategies.base import BaseStrategy
from src.api.client import PolymarketClient


class BTC5MStrategy(BaseStrategy):
    """
    BTC 5分钟均值回归策略。

    逻辑：
    1. 获取最近5分钟的价格数据
    2. 计算移动均值与当前价格的偏差
    3. 偏差 > entry_threshold -> 买入
    4. 偏差 < exit_threshold  -> 卖出
    5. 亏损 > stop_loss       -> 止损
    """

    def __init__(self, client: PolymarketClient, config: Dict[str, Any]):
        super().__init__(name="btc_5m", client=client, config=config)
        self.logger = logging.getLogger("strategy.btc_5m")

        # 策略参数
        self.entry_threshold = config.get("entry_threshold", 0.02)
        self.exit_threshold = config.get("exit_threshold", 0.005)
        self.stop_loss = config.get("stop_loss", 0.01)
        self.max_position = config.get("max_position", 50.0)
        self.market_ids = config.get("market_ids", [])

        # 状态
        self._entry_price = None
        self._ma_price = None
        self._in_position = False

    def on_tick(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        每5分钟被 engine 调度一次。
        market_data 格式: {"price": float, "volume": float, "timestamp": int}
        """
        current_price = market_data.get("price")
        if not current_price:
            return None

        # ── 更新移动均值（简化版 SMA）─────────────────────────────
        if self._ma_price is None:
            self._ma_price = current_price
        else:
            # EMA 平滑
            alpha = 0.3
            self._ma_price = alpha * current_price + (1 - alpha) * self._ma_price

        deviation = (current_price - self._ma_price) / self._ma_price

        self.logger.debug(
            f"[{self.name}] price={current_price:.4f} ma={self._ma_price:.4f} "
            f"dev={deviation:.4f} pos={self._in_position}"
        )

        # ── 交易逻辑 ───────────────────────────────────────────────

        if not self._in_position:
            # 买入信号：价格低于均值达到阈值
            if deviation < -self.entry_threshold:
                size = min(self._capital * 0.95 / current_price, self.max_position)
                self._entry_price = current_price
                self._in_position = True
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
            # 持有多头仓位，检杢止盈/止损
            pnl_pct = (current_price - self._entry_price) / self._entry_price

            if pnl_pct <= -self.stop_loss:
                # 止损
                self.logger.info(
                    f"[{self.name}] STOP LOSS | pnl={pnl_pct:.4f} "
                    f"entry={self._entry_price:.4f} current={current_price:.4f}"
                )
                self._in_position = False
                self._entry_price = None
                return {
                    "action": "sell",
                    "token_id": self.market_ids[0] if self.market_ids else None,
                    "price": current_price,
                    "size": abs(self._position),
                }

            elif pnl_pct >= self.exit_threshold:
                # 止盈
                self.logger.info(
                    f"[{self.name}] TAKE PROFIT | pnl={pnl_pct:.4f} "
                    f"entry={self._entry_price:.4f} current={current_price:.4f}"
                )
                self._in_position = False
                self._entry_price = None
                return {
                    "action": "sell",
                    "token_id": self.market_ids[0] if self.market_ids else None,
                    "price": current_price,
                    "size": abs(self._position),
                }

        return None

    def _load_state(self) -> None:
        """从 state/btc_5m_state.json 恢复仓位"""
        import os, json
        state_file = os.path.join("state", f"{self.name}_state.json")
        if os.path.exists(state_file):
            with open(state_file) as f:
                data = json.load(f)
                self._in_position = data.get("in_position", False)
                self._entry_price = data.get("entry_price")
                self._position = data.get("position", 0.0)
                self.logger.info(f"[{self.name}] State restored: pos={self._position}")

    def _save_state(self) -> None:
        """持久化仓位至 state/"""
        import os, json
        os.makedirs("state", exist_ok=True)
        state_file = os.path.join("state", f"{self.name}_state.json")
        with open(state_file, "w") as f:
            json.dump({
                "in_position": self._in_position,
                "entry_price": self._entry_price,
                "position": self._position,
            }, f, indent=2)
