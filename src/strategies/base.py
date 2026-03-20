"""
Base Strategy Interface
所有策略必须继承此基类并实现规定的生命周期方法。
"""
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from src.api.client import PolymarketClient


class StrategyStatus:
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class BaseStrategy(ABC):
    """
    策略基类，定义标准生命周期：
        init()      -> on_tick() 循环 -> stop()
    """

    def __init__(self, name: str, client: PolymarketClient, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.client = client
        self.config = config or {}
        self.status = StrategyStatus.IDLE
        self.logger = logging.getLogger(f"strategy.{name}")
        self._position = 0.0  # 当前持仓量
        self._capital = self.config.get("capital", 100.0)  # 初始资金（USDC）

    # ── 生命周期 ──────────────────────────────────────────────────────────────

    def init(self) -> None:
        """策略初始化（挂载指标、加载状态）"""
        self.logger.info(f"[{self.name}] Initializing...")
        self._load_state()
        self.status = StrategyStatus.IDLE

    @abstractmethod
    def on_tick(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        每周期执行的核心策略逻辑。
        返回交易指令字典或 None（无操作）。
        """
        raise NotImplementedError

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

    # ── 工具方法 ───────────────────────────────────────────────────────────────

    def update_position(self, delta: float) -> None:
        """更新持仓量"""
        self._position += delta

    def get_position(self) -> float:
        return self._position

    def can_trade(self, price: float, size: float, side: str) -> bool:
        """基础资金校验"""
        cost = price * size
        if side == "buy" and cost > self._capital:
            return False
        if side == "sell" and self._position < size:
            return False
        return True
