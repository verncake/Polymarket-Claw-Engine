"""
Base Strategy Interface
所有策略必须继承此基类并实现规定的生命周期方法。
"""
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, Any

from src.api.client import PolymarketClient


class StrategyStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class BaseStrategy(ABC):
    """
    策略基类，定义标准生命周期：
        init() -> on_tick() 循环 -> on_fill() 成交回调 -> stop()
    """

    def __init__(self, name: str, client: PolymarketClient, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.client = client
        self.config = config or {}
        self.status = StrategyStatus.IDLE
        self.logger = logging.getLogger(f"strategy.{name}")
        self._position = 0.0   # 当前净持仓量
        self._capital = self.config.get("capital", 100.0)  # 可用资金（USDC）

    # ── 生命周期 ──────────────────────────────────────────────────────────────

    def init(self) -> None:
        """策略初始化"""
        self.logger.info(f"[{self.name}] Initializing...")
        self._load_state()
        self.status = StrategyStatus.IDLE

    @abstractmethod
    def on_tick(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        每周期执行的核心策略逻辑。
        返回交易指令字典或 None（无操作）。
        重要：不要在此方法内直接更新持仓状态，交给 on_fill 成交回调处理。
        """
        raise NotImplementedError

    def on_fill(self, fill_event: Dict[str, Any]) -> None:
        """
        订单成交回调。由 Runner 在确认订单成交后调用。
        子类可重写此方法以实现持仓更新逻辑。
        """
        pass

    def stop(self) -> None:
        """策略停止（平仓、保存状态）"""
        self.logger.info(f"[{self.name}] Stopping...")
        self._save_state()
        self.status = StrategyStatus.STOPPED

    # ── 状态管理 ──────────────────────────────────────────────────────────────

    def _load_state(self) -> None:
        """从 state/ 加载策略运行状态（可选重载）"""
        pass

    def _save_state(self) -> None:
        """持久化策略状态至 state/（可选重载）"""
        pass

    # ── 资金与持仓管理 ───────────────────────────────────────────────────────

    def update_capital(self, delta: float) -> None:
        """
        更新可用资金。
        delta > 0: 资金增加（如卖出获得收入）
        delta < 0: 资金减少（如买入支出）
        """
        self._capital += delta

    def update_position(self, delta: float, cost: float = 0.0) -> None:
        """
        更新持仓量及可用资金。

        Args:
            delta: 持仓变化量（正=买入增加，负=卖出减少）
            cost:  实际成交金额（买入时为负，卖出时为正）
                   用于同步扣减/增加可用资金
        """
        self._position += delta
        self._capital += cost  # 同步资金：买入 cost 为负(-price*size)，卖出 cost 为正

    def get_position(self) -> float:
        return self._position

    def get_capital(self) -> float:
        return self._capital

    def can_trade(self, price: float, size: float, side: str) -> bool:
        """基础资金校验"""
        cost = price * size
        if side == "buy" and cost > self._capital:
            return False
        if side == "sell" and self._position < size:
            return False
        return True
