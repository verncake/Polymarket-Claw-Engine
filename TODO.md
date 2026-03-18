# Polymarket-Claw-Engine TODO List

## Phase 1: API & Client Layer
- [x] Implement `src/api/client.py`: Refine SDK/API/Scrapling fallback route.
- [x] Implement `src/api/client.py`: Add `markdownify` filtering to Scrapling fallback (Token Defense Protocol).

## Phase 2: Execution Engine
- [x] Implement `src/engine/executor.py`: Robust balance check using SDK.
- [x] Implement `src/engine/executor.py`: Core trade execution (Buy/Sell).

## Phase 3: Strategy Migration
- [ ] Migrate `btc-5m-strategy`: Refactor to use new `PolymarketClient`.
- [ ] Debug/Migrate `gabagool22`: Fix market identification logic.
- [ ] Migration of State Files: Ensure `state.json` compatibility.

## Phase 4: Automation & Monitoring
- [ ] Rebuild Cron Scheduler: Restore automated trading loops.
- [ ] Implement `health-check.ts`: Monitoring for strategy processes.
