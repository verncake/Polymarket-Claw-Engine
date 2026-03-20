"""
Strategy Runner
---------------
定时调度器，负责加载配置、驱动各个策略的 on_tick 循环，
并将交易指令提交给 Executor 执行。
"""
import logging
import threading
import time
import json
import os
from typing import Dict, Any, List, Optional

from src.api.client import PolymarketClient
from src.engine.executor import Executor
from src.strategies.btc_5m import BTC5MStrategy
from src.strategies.gabagool import GabagoolStrategy


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("engine.runner")


class StrategyRunner:
    """
    策略运行器：
    - 加载 config.json 中的策略配置
    - 每 tick_interval 秒调度所有策略的 on_tick
    - 将返回的交易指令路由至 Executor 执行
    """

    def __init__(self, config_path: str = "config.json", tick_interval: int = 300):
        """
        Args:
            config_path: config.json 路径
            tick_interval: 调度周期（秒），默认 300s = 5分钟
        """
        self.tick_interval = tick_interval
        self.client = PolymarketClient(config_path)
        self.executor = Executor(config_path)
        self.strategies: Dict[str, Any] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._load_strategies(config_path)

    def _load_strategies(self, config_path: str) -> None:
        """根据 config.json 加载所有已启用策略"""
        if not os.path.exists(config_path):
            logger.warning(f"Config file {config_path} not found, no strategies loaded.")
            return

        with open(config_path) as f:
            full_config = json.load(f)

        strategy_configs = full_config.get("strategies", {})
        for name, cfg in strategy_configs.items():
            if not cfg.get("enabled", False):
                continue

            try:
                if name == "btc_5m":
                    strat = BTC5MStrategy(client=self.client, config=cfg)
                elif name == "gabagool":
                    strat = GabagoolStrategy(client=self.client, config=cfg)
                else:
                    logger.warning(f"Unknown strategy: {name}, skipping.")
                    continue

                strat.init()
                self.strategies[name] = strat
                logger.info(f"Strategy '{name}' loaded and initialized.")

            except Exception as e:
                logger.error(f"Failed to load strategy '{name}': {e}")

    def _fetch_market_data(self) -> Dict[str, Any]:
        """
        从 PolymarketClient 获取当前市场数据。
        目前返回模拟数据，实际实现应调用真实的市场行情接口。
        """
        try:
            # TODO: 接入真实市场数据源（orderbook / trade feeds）
            balance = self.client.get_balance()
            return {
                "timestamp": int(time.time()),
                "balance": balance,
            }
        except Exception as e:
            logger.error(f"Failed to fetch market data: {e}")
            return {"error": str(e)}

    def _tick(self) -> None:
        """单次调度轮次"""
        logger.info(f"=== Tick start | {len(self.strategies)} strategies active ===")

        market_data = self._fetch_market_data()
        if "error" in market_data:
            logger.error(f"Market data fetch failed, skipping tick.")
            return

        for name, strat in self.strategies.items():
            try:
                signal = strat.on_tick(market_data)
                if signal:
                    self._execute_signal(name, signal)
            except Exception as e:
                logger.exception(f"Strategy '{name}' error in on_tick: {e}")

        logger.info("=== Tick complete ===")

    def _execute_signal(self, strategy_name: str, signal: Dict[str, Any]) -> None:
        """将策略信号提交给 Executor 执行"""
        action = signal.get("action")

        if action == "batch":
            # 批量订单
            for order in signal.get("orders", []):
                self._execute_single(strategy_name, order)
        else:
            self._execute_single(strategy_name, signal)

    def _execute_single(self, strategy_name: str, order: Dict[str, Any]) -> None:
        """执行单个订单"""
        action = order.get("action")
        token_id = order.get("token_id")
        price = order.get("price")
        size = order.get("size")

        logger.info(
            f"[{strategy_name}] Executing: {action} {size} @ {price} "
            f"(token={token_id})"
        )

        try:
            result = self.executor.execute_trade(
                token_id=token_id,
                side=action,
                price=price,
                size=size,
            )
            logger.info(f"[{strategy_name}] Execution result: {result}")

            # 同步更新策略持仓
            if result.get("status") == "success":
                delta = size if action == "buy" else -size
                self.strategies[strategy_name].update_position(delta)

        except Exception as e:
            logger.error(f"[{strategy_name}] Execution failed: {e}")

    def start(self) -> None:
        """启动策略运行循环（后台线程）"""
        if self._running:
            logger.warning("Runner already running.")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(
            f"StrategyRunner started | tick_interval={self.tick_interval}s | "
            f"{len(self.strategies)} strategies"
        )

    def _run_loop(self) -> None:
        """后台运行循环"""
        while self._running:
            self._tick()
            time.sleep(self.tick_interval)

    def stop(self) -> None:
        """停止所有策略并关闭 Runner"""
        logger.info("Stopping StrategyRunner...")
        self._running = False

        for name, strat in self.strategies.items():
            try:
                strat.stop()
            except Exception as e:
                logger.error(f"Error stopping strategy '{name}': {e}")

        if self._thread:
            self._thread.join(timeout=10)

        logger.info("StrategyRunner stopped.")

    def run_once(self) -> None:
        """单次执行（用于测试或手动触发）"""
        self._tick()


if __name__ == "__main__":
    import sys

    config = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 300

    runner = StrategyRunner(config_path=config, tick_interval=interval)

    if "--once" in sys.argv:
        runner.run_once()
    else:
        try:
            runner.start()
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            runner.stop()
