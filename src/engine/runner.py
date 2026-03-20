"""
Strategy Runner
---------------
定时调度器，负责加载配置、驱动各个策略的 on_tick 循环，
并将交易指令提交给 Executor 执行。
"""
import argparse
import json
import logging
import os
import threading
import time
from typing import Dict, Any, Optional

from src.api.client import PolymarketClient
from src.engine.executor import Executor
from src.strategies.base import BaseStrategy
from src.strategies.btc_5m import BTC5MStrategy
from src.strategies.gabagool import GabagoolStrategy


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("engine.runner")


STRATEGY_MAP = {
    "btc_5m": BTC5MStrategy,
    "gabagool": GabagoolStrategy,
}


class StrategyRunner:
    """
    策略运行器：
    - 加载 config.json 中的策略配置
    - 每 tick_interval 秒调度所有策略的 on_tick
    - 将返回的交易指令路由至 Executor 执行
    - 在订单成交后回调策略的 on_fill 方法
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
        self.strategies: Dict[str, BaseStrategy] = {}
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

            if name not in STRATEGY_MAP:
                logger.warning(f"Unknown strategy: '{name}', skipping.")
                continue

            try:
                strat_class = STRATEGY_MAP[name]
                strat = strat_class(client=self.client, config=cfg)
                strat.init()
                self.strategies[name] = strat
                logger.info(f"Strategy '{name}' loaded and initialized.")
            except Exception as e:
                logger.error(f"Failed to load strategy '{name}': {e}")

    def _fetch_market_data(self) -> Dict[str, Any]:
        """
        从 PolymarketClient 获取当前市场数据。
        返回包含价格信息的数据字典，格式与各策略 on_tick 期望一致。
        """
        try:
            # 1. 账户余额（用于参考）
            summary = self.client.get_account_summary()

            # 2. 开放仓位
            positions = self.client.data.get_positions()

            # 3. 构造统一的市场数据格式
            # 包含公共价格信息（从开放仓位中提取）
            market_data = {
                "timestamp": int(time.time()),
                "balance": summary.get("usdc_balance", 0),
                "open_orders": summary.get("open_orders", 0),
                "positions": positions,
            }

            # 如果有开放仓位，提取第一个的价格作为参考
            if positions:
                first = positions[0]
                market_data["price"] = float(first.get("avgPrice", 0))
                market_data["yes_price"] = float(first.get("avgPrice", 0))
                market_data["no_price"] = 1.0 - market_data["yes_price"]
                market_data["current_value"] = float(first.get("currentValue", 0))
                market_data["size"] = float(first.get("size", 0))

            return market_data

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
                    self._execute_signal(name, strat, signal)
            except Exception as e:
                logger.exception(f"Strategy '{name}' error in on_tick: {e}")

        logger.info("=== Tick complete ===")

    def _execute_signal(
        self, strategy_name: str, strat: BaseStrategy, signal: Dict[str, Any]
    ) -> None:
        """将策略信号提交给 Executor 执行，并在成交后回调 on_fill"""
        action = signal.get("action")

        if action == "batch":
            for order in signal.get("orders", []):
                self._execute_single(strategy_name, strat, order)
        else:
            self._execute_single(strategy_name, strat, signal)

    def _execute_single(
        self, strategy_name: str, strat: BaseStrategy, order: Dict[str, Any]
    ) -> None:
        """执行单个订单，成交后回调策略的 on_fill"""
        token_id = order.get("token_id")
        action = order.get("action")
        price = order.get("price")
        size = order.get("size")

        logger.info(
            f"[{strategy_name}] Executing: {action} {size} @ {price} (token={token_id})"
        )

        try:
            result = self.executor.execute_trade(
                token_id=token_id,
                side=action,
                price=price,
                size=size,
            )
            logger.info(f"[{strategy_name}] Execution result: {result}")

            # 只有在确认成功后才回调 on_fill
            if result.get("status") == "success":
                fill_event = {
                    "side": action,
                    "price": price,
                    "size": size,
                    "order_id": result.get("order_id"),
                }
                # 同步更新基类持仓
                cost = -price * size if action == "buy" else price * size
                strat.update_position(
                    delta=size if action == "buy" else -size,
                    cost=cost,
                )
                # 回调策略的 on_fill
                strat.on_fill(fill_event)

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
    parser = argparse.ArgumentParser(description="Polymarket Strategy Runner")
    parser.add_argument(
        "--config", default="config.json", help="Path to config file."
    )
    parser.add_argument(
        "--interval", type=int, default=300, help="Tick interval in seconds."
    )
    parser.add_argument(
        "--once", action="store_true", help="Run once and exit."
    )

    args = parser.parse_args()

    runner = StrategyRunner(config_path=args.config, tick_interval=args.interval)

    if args.once:
        runner.run_once()
    else:
        try:
            runner.start()
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            runner.stop()
