"""
Polymarket 账户盈亏实时监控
==============================
支持两种余额查询模式：
  Mode 1 - Direct Chain:  通过 Polygon RPC + eth_call 直接查链上 USDC 合约
  Mode 2 - SDK / CLOB API:  通过 ClobClient.getBalanceAllowance 查 Polymarket 平台账户余额

两种模式的区别：
  | 模式         | 数据来源                       | 能看到的信息               |
  |-------------|------------------------------|--------------------------|
  | Direct Chain | Polygon RPC (无需认证)         | 钱包真实 USDC 余额        |
  | SDK / CLOB  | clob.polymarket.com (签名认证) | 平台账户、挂单冻结、保证金 |
"""
import json
import logging
import os
import requests
from src.api.client import PolymarketClient

logger = logging.getLogger("balance")

# Polygon RPC 节点（无 API Key 公共端）
POLYGON_RPC = "https://rpc-mainnet.matic.quiknode.pro"
USDC_CONTRACT = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
USDC_DIVISOR = 1_000_000

# 加载配置
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
client = PolymarketClient(config_path=CONFIG_PATH)


def to_usdc_hex(address: str) -> str:
    """将 0x 地址转换为 balanceOf 参数（24字节 padding）"""
    return address.lower().replace("0x", "").zfill(64)


# ══════════════════════════════════════════════════════════════════════
# Mode 1: Direct Chain Query（无需签名，直接读链）
# ══════════════════════════════════════════════════════════════════════

def get_chain_balance(address: str) -> float:
    """
    Mode 1 - Direct Chain Query
    通过 Polygon RPC + eth_call 直接查询链上 USDC 合约余额。
    无需签名认证，返回钱包真实持有的 USDC 数量。
    """
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{
            "to": USDC_CONTRACT,
            "data": "0x70a08231" + to_usdc_hex(address)
        }, "latest"],
        "id": 1
    }
    resp = requests.post(POLYGON_RPC, json=payload, timeout=15)
    resp.raise_for_status()
    result = resp.json().get("result", "0x0")
    balance_wei = int(result, 16)
    return balance_wei / USDC_DIVISOR


# ══════════════════════════════════════════════════════════════════════
# Mode 2: SDK / CLOB API Query（签名认证，查平台账户）
# ══════════════════════════════════════════════════════════════════════

def get_clob_account_balance() -> dict:
    """
    Mode 2 - SDK / CLOB API Query
    通过 ClobClient.getBalanceAllowance(AssetType.COLLATERAL)
    查询 Polymarket 平台账户的 USDC 余额（含挂单冻结、保证金等）。

    返回: {
        "balance": float,       # 账户余额（USDC）
        "allowance": float,     # 已授权额度
        "raw": dict             # SDK 原始返回
    }
    """
    try:
        from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
        params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
        raw = client.sdk.get_balance_allowance(params)
        balance = int(raw.get("balance", 0)) / USDC_DIVISOR
        allowance = int(raw.get("allowance", 0)) / USDC_DIVISOR
        return {"balance": balance, "allowance": allowance, "raw": raw}
    except Exception as e:
        logger.error(f"[Mode 2] SDK query failed: {e}")
        return {"balance": None, "allowance": None, "error": str(e)}


def get_data_api_positions_value() -> float:
    """通过 Data API 查询当前持仓总价值"""
    try:
        return client.data.get_positions_value()
    except Exception:
        return -1.0


# ══════════════════════════════════════════════════════════════════════
# 仓位与统计
# ══════════════════════════════════════════════════════════════════════

def get_open_positions():
    try:
        return client.data.get_positions()
    except Exception as e:
        logger.warning(f"Failed to get open positions: {e}")
        return []


def get_closed_positions():
    try:
        return client.data.get_closed_positions()
    except Exception as e:
        logger.warning(f"Failed to get closed positions: {e}")
        return []


def get_all_trades():
    try:
        return client.data.get_trades()
    except Exception as e:
        logger.warning(f"Failed to get trades: {e}")
        return []


def calc_win_rate(closed_positions, open_positions):
    """
    计算胜率：
    - 已结算仓位：realizedPnl > 0 为赢
    - 开放仓位：percentPnl > 0 为赢
    """
    wins, total = 0, 0

    for p in closed_positions:
        pnl = float(p.get("realizedPnl", 0))
        if pnl != 0:
            total += 1
            if pnl > 0:
                wins += 1

    for p in open_positions:
        pnl_pct = float(p.get("percentPnl", 0))
        if pnl_pct != 0:
            total += 1
            if pnl_pct > 0:
                wins += 1

    return (wins / total * 100) if total > 0 else 0.0, wins, total


# ══════════════════════════════════════════════════════════════════════
# 主输出
# ══════════════════════════════════════════════════════════════════════

def print_banner():
    print("=" * 62)
    print("  Polymarket 账户盈亏实时监控 (双模式)")
    print("=" * 62)


def main():
    print_banner()
    print(f"\nProxy: {client.proxy_wallet}\n")

    # ── Mode 1: Direct Chain ──────────────────────────────────
    chain_balance = get_chain_balance(client.proxy_wallet)
    print(f"[Mode 1 - Direct Chain]")
    print(f"  RPC:        {POLYGON_RPC}")
    print(f"  Contract:   {USDC_CONTRACT}")
    print(f"  USDC 余额:  {chain_balance:.6f} USDC  (链上合约实时)\n")

    # ── Mode 2: SDK / CLOB API ──────────────────────────────
    clob_info = get_clob_account_balance()
    if "error" not in clob_info:
        print(f"[Mode 2 - SDK / CLOB API]")
        print(f"  Endpoint:   clob.polymarket.com (L2 签名认证)")
        print(f"  USDC 余额:  {clob_info['balance']:.6f} USDC  (平台账户)")
        print(f"  授权额度:   {clob_info['allowance']:.6f} USDC\n")
    else:
        print(f"[Mode 2 - SDK / CLOB API]  查询失败: {clob_info['error']}\n")

    # ── 平台账户摘要 ─────────────────────────────────────────
    summary = client.get_account_summary()
    print(f"[账户摘要]")
    print(f"  开放订单数:   {summary.get('open_orders', 0)}")

    # ── 仓位与 PnL ──────────────────────────────────────────
    closed_positions = get_closed_positions()
    open_positions = get_open_positions()
    trades = get_all_trades()

    print(f"\n[仓位]")
    print(f"  开放仓位:     {len(open_positions)} 笔")
    for p in open_positions:
        title = p.get("title", "Unknown")[:52]
        size = p.get("size", 0)
        pnl_pct = p.get("percentPnl", 0)
        val = p.get("currentValue", 0)
        print(f"    - {title}")
        print(f"      size={size} | pnl%={pnl_pct:.2f}% | value=${val:.4f}")

    print(f"  已结算仓位:   {len(closed_positions)} 笔")

    realized_pnl = sum(float(p.get("realizedPnl", 0)) for p in closed_positions)
    unrealized_pnl = summary.get("position_value", 0.0)

    print(f"\n[PnL]")
    print(f"  已实现 PnL:   +${realized_pnl:.6f}")
    print(f"  浮动 PnL:     ${unrealized_pnl:.6f}")
    print(f"  总 PnL:       ${(realized_pnl + unrealized_pnl):.6f}")

    # ── 胜率统计 ─────────────────────────────────────────────
    win_rate, wins, total = calc_win_rate(closed_positions, open_positions)
    print(f"\n[胜率统计]")
    print(f"  总成交笔数:   {len(trades)} 笔")
    print(f"  已结算:       {len(closed_positions)} 笔 | 赢: {wins}/{total} | 胜率: {win_rate:.2f}%")


if __name__ == "__main__":
    main()
