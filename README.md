# Polymarket-Claw-Engine

Vernclaw 的量化交易引擎，基于 Polymarket CLOB API 构建。

## 架构原则
- **优先原则 (Priority)**: API > Scrapling > Web-Fetch。
- **治理体系 (Governance)**: 采用 Vernclaw-Evolve L2 机制，所有决策与复盘记录均通过 memory_store 同步至 LanceDB。
- **物理分离**: 工具实体存放在 `~/Work/Tools/`，项目逻辑存放在 `~/Work/Project/`。
- **Git 卫生**: `config.json` 已被 .gitignore 排除，由 `config.json.temp` 作为模板。

## 目录结构
- `src/api/`: 核心 API 封装 (Gamma + CLOB)
- `src/engine/`: 交易与风控引擎
- `src/data/`: 爬虫与数据流水线
- `src/strategies/`: 策略逻辑
- `state/`: 运行状态持久化 (gitignored)
- `logs/`: 运行日志 (gitignored)

## 快速开始
1. 初始化环境: `python3 -m venv venv && source venv/bin/activate && pip install py-clob-client`
2. 配置 `config.json` (参考 `config.json.temp`)
