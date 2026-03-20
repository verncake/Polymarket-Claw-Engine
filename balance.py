"""
Polymarket 账户盈亏实时监控
==============================
查询真实账户状态：
  - Gnosis Safe USDC 余额（通过 Polygon RPC，erc-20 balanceOf）
  - CLOB 锁定余额
  - 已实现 / 未实现 PnL
  - 交易胜率统计
"""
import json
import os
import requests
from src.api.client import PolymarketClient

# Polygon RPC 节点（无 API Key 公共端）
POLYGON_RPC = "https://rpc-mainnet.matic.quiknode.pro"
USDC_CONTRACT = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

# 加载配置
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
client = PolymarketClient(config_path=CONFIG_PATH)


def to_usdc_hex(address: str) -> str:
    """将 0x 地址转换为 balanceOf 参数（24字节 padding）"""
    return address.lower().replace("0x", "").zfill(64)


def get_gnosis_usdc_balance(address: str) -> float:
    """
    通过 Polygon RPC + eth_call 查询 Gnosis Safe 代理钱包的 USDC 余额。
    不需要私钥签名，直接查链上合约存储。
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
    # 返回的值是 16 进制，USDC 精度 1e6
    balance_wei = int(result, 16)
    return balance_wei / 1_000_000


def get_clob_locked_balance() -> float:
    """
    通过 CLOB SDK 查询 CLOB 合约内锁定的 USDC 余额。
    （不等于 Gnosis Safe 总余额）
    """
    try:
        from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
        params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
        raw = client.sdk.get_balance_allowance(params)
        return int(raw.get("balance", 0)) / 1_000_000
    except Exception as e:
        return -1.0


def get_open_positions():
    """获取当前开放仓位"""
    try:
        return client.data.get_positions()
    except Exception:
        return []


def get_closed_positions():
    """获取已结算仓位"""
    try:
        return client.data.get_closed_positions()
    except Exception:
        return []


def calc_win_rate(closed_positions, open_positions):
    """
    计算胜率：
    - 已结算仓位：PnL > 0 为赢，PnL < 0 为输
    - 开放仓位：浮盈 > 0 为赢，浮亏 < 0 为输
    """
    wins, total = 0, 0

    # 已结算
    for p in closed_positions:
        pnl = float(p.get("realizedPnl", 0))
        if pnl > 0:
            wins += 1
        if pnl != 0:
            total += 1

    # 开放仓位
    for p in open_positions:
        pnl_pct = float(p.get("percentPnl", 0))
        if pnl_pct > 0:
            wins += 1
        if pnl_pct != 0:
            total += 1

    return (wins / total * 100) if total > 0 else 0.0, wins, total


def get_all_trades():
    """获取所有历史成交（用于统计总交易笔数）"""
    try:
        return client.data.get_trades()
    except Exception:
        return []


def print_banner():
    print("=" * 60)
    print("  Polymarket 账户盈亏实时监控")
    print("=" * 60)


def main():
    print_banner()
    print(f"\nProxy: {client.proxy_wallet}\n")

    # ── 1. Gnosis Safe USDC 总余额（通过 Polygon RPC）──────────
    gnosis_usdc = get_gnosis_usdc_balance(client.proxy_wallet)
    print(f"[链上] Gnosis Safe USDC 余额: {gnosis_usdc:.6f} USDC")

    # ── 2. CLOB 锁定余额 ───────────────────────────────────────
    clob_locked = get_clob_locked_balance()
    if clob_locked >= 0:
        print(f"[CLOB] CLOB 合约锁定 USDC:  {clob_locked:.6f} USDC")
    else:
        print(f"[CLOB] CLOB 锁定余额查询失败")

    # ── 3. 账户摘要 ────────────────────────────────────────────
    summary = client.get_account_summary()
    print(f"\n[账户摘要]")
    print(f"  开放订单数:     {summary.get('open_orders', 0)}")

    # ── 4. 仓位与 PnL ─────────────────────────────────────────
    closed_positions = get_closed_positions()
    open_positions = get_open_positions()
    trades = get_all_trades()

    print(f"\n[仓位]")
    print(f"  开放仓位:       {len(open_positions)} 笔")
    for p in open_positions:
        title = p.get("title", "Unknown")[:50]
        size = p.get("size", 0)
        pnl_pct = p.get("percentPnl", 0)
        print(f"    - {title} | size={size} | pnl%={pnl_pct:.2f}%")

    print(f"  已结算仓位:     {len(closed_positions)} 笔")

    # ── 5. PnL 统计 ───────────────────────────────────────────
    realized_pnl = sum(float(p.get("realizedPnl", 0)) for p in closed_positions)
    unrealized_pnl = sum(
        float(p.get("size", 0)) * float(p.get("percentPnl", 0)) / 100
        for p in open_positions
    )

    print(f"\n[PnL]")
    print(f"  已实现 PnL:     +${realized_pnl:.6f}")
    print(f"  浮动 PnL:       ${unrealized_pnl:.6f}")
    print(f"  总 PnL:         ${(realized_pnl + unrealized_pnl):.6f}")

    # ── 6. 胜率统计 ───────────────────────────────────────────
    win_rate, wins, total = calc_win_rate(closed_positions, open_positions)
    print(f"\n[胜率统计]")
    print(f"  总交易笔数:     {len(trades)} 笔")
    print(f"  已结算:         {len(closed_positions)} 笔 | 赢: {wins} / {total} (胜率 {win_rate:.2f}%)")

    # ── 7. 综合余额 ───────────────────────────────────────────
    # 已实现 PnL 已累积在 gnosis_usdc 中（不是独立新增的资金）
    net_assets = gnosis_usdc + unrealized_pnl
    print(f"\n[综合账户]")
    print(f"  Gnosis Safe USDC: {gnosis_usdc:.6f} USDC  (含历史利润)")
    print(f"  浮动盈亏:         {unrealized_pnl:.6f} USDC")
    print(f"  ≈ 净资产:         {net_assets:.6f} USDC")


if __name__ == "__main__":
    main()
