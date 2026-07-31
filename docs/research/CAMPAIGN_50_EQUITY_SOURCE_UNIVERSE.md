# Campaign #50 — Frozen Equity Source Universe

## Status

**SOURCE-UNIVERSE FREEZE — source identity and session reconciliation only.**

No Campaign #50 predictor, breadth value, return outcome, candidate ranking, statistical result, economic backtest, paper-trading result, runtime change, or strategy change is authorized by this document.

## Purpose

Freeze the small, economically justified equity universe selected for Campaign #50 before any breadth predictor or SPY/QQQ outcome is generated.

The universe is designed to represent domestic equity participation across market-cap, style, and sector dimensions while avoiding duplicate economic roles and unnecessary multiplicity.

## Target assets

- `SPY_1D.csv`
- `QQQ_1D.csv`

SPY and QQQ are future outcome targets and are not counted as breadth members.

## Breadth members

### Market-cap participation

- `RSP_1D.csv`
- `MDY_1D.csv`
- `IWM_1D.csv`

### Style participation

- `IWD_1D.csv`
- `IWF_1D.csv`

### Sector participation

- `XLB_1D.csv`
- `XLE_1D.csv`
- `XLF_1D.csv`
- `XLI_1D.csv`
- `XLK_1D.csv`
- `XLP_1D.csv`
- `XLU_1D.csv`
- `XLV_1D.csv`
- `XLY_1D.csv`

The frozen breadth-member count is 14.

## Excluded nearby alternatives

The following are intentionally excluded from this breadth universe:

- `XLC` because its history begins during 2018 and would shorten the common development interval;
- `IJR` because it duplicates the small-cap role represented by IWM;
- `VTV` and `VUG` because they duplicate the value/growth roles represented by IWD and IWF;
- `SMH`, `IGV`, and `XBI` because they are concentrated industries rather than broad participation components;
- `EEM`, `EFA`, `VEA`, and `VWO` because they represent international risk appetite rather than domestic breadth;
- bond, cash-like, gold, volatility, and factor ETFs because they belong to separate defensive, cross-asset, or factor-state hypotheses.

## Exact source identities

All selected files use the exact ordered schema:

`timestamp,open,high,low,close,volume`

Every selected file had zero duplicate timestamps and zero unparseable timestamps in the source-only inventory.

| File | Rows | First date | Last date | SHA-256 |
|---|---:|---|---|---|
| `IWD_1D.csv` | 5,372 | 2005-01-03 | 2026-05-11 | `c609169db6f6d6220f64877da52fd707c78308af67bf793422d87c8c777e2d29` |
| `IWF_1D.csv` | 5,372 | 2005-01-03 | 2026-05-11 | `b5c1b73bcb75deac3329dd6e089071a8b2ecfb189240acb259617d29509b3788` |
| `IWM_1D.csv` | 5,372 | 2005-01-03 | 2026-05-11 | `e6cafc5ba4de5749770d439859e024b8e8026686c8e4f420da3d5f11743cea12` |
| `MDY_1D.csv` | 5,372 | 2005-01-03 | 2026-05-11 | `0d314431aff35303893a31f5eed4fba1fa4320a0064441b70ec989a96cbda53c` |
| `QQQ_1D.csv` | 2,010 | 2018-01-02 | 2025-12-30 | `34867c2b2da4aece23892b8e035e528f547173f3bc137cbe33b1295af0c1ff7b` |
| `RSP_1D.csv` | 5,369 | 2005-01-03 | 2026-05-06 | `9cf41b9eaa50ee49a8e28153ac2240fc4fbb62bf2eaa678b439a481f0d54fbdd` |
| `SPY_1D.csv` | 2,010 | 2018-01-02 | 2025-12-30 | `85a24eb44e2377cdcb9c22b0f4062730d332ec276f371e71405e1cbfc0b8ac86` |
| `XLB_1D.csv` | 5,369 | 2005-01-03 | 2026-05-06 | `e85d3d0107eb8ed8d8044c00e5bdbddd4cf0ef64ba6a1d82b5541d2f2ef64087` |
| `XLE_1D.csv` | 5,369 | 2005-01-03 | 2026-05-06 | `18547a4e322f75f2ab6b1f1b79418f6bbe240880eb9ee60b4cfe009c67c2e4a6` |
| `XLF_1D.csv` | 5,369 | 2005-01-03 | 2026-05-06 | `205026d65898a823681b768213032bb89a7ea37f474251807d3d3e6f92b87d73` |
| `XLI_1D.csv` | 5,369 | 2005-01-03 | 2026-05-06 | `e6b9f3abdbe83c4561d8bb03fe6dd6a924e9a7dfb9d3da8e9f3aadc929d76d4e` |
| `XLK_1D.csv` | 5,369 | 2005-01-03 | 2026-05-06 | `1c63e414fac5090059d684b0736fc046517ae377b79887ffb0d5686d06fba874` |
| `XLP_1D.csv` | 5,372 | 2005-01-03 | 2026-05-11 | `a4ccb5e2d5cd8c191133f9977afaa70ddbfceb422767dd70ce81b4ef9ff75536` |
| `XLU_1D.csv` | 5,372 | 2005-01-03 | 2026-05-11 | `930b10eed5679c1acd2f9dc8329242f0510a97b1c23cbff692c700e59be00471` |
| `XLV_1D.csv` | 5,372 | 2005-01-03 | 2026-05-11 | `346d1f5f43e7bd357d041276914db95a539e1906549898102c8a387ac918e902` |
| `XLY_1D.csv` | 5,369 | 2005-01-03 | 2026-05-06 | `1a7b600eced3e741a56d0c98012f8163256848aeefb471e3aab2c6ecbaf1ec34` |

## Frozen temporal boundary

The common governed analysis endpoint is the SPY/QQQ endpoint:

`2025-12-30`

The provisional intervals remain:

- development: 2018-01-02 through 2022-12-30;
- validation: 2023-01-03 through 2024-12-31;
- untouched confirmation holdout: 2025-01-02 through 2025-12-30.

Exact session counts and any source-specific missing sessions must be reconciled before the statistical specification is locked.

## Required source-only reconciliation

Before any Campaign #50 implementation or outcome generation, a deterministic source-only process must verify:

- each file hash against this annex;
- exact ordered schema;
- unique and parseable timestamps;
- strictly increasing daily rows;
- OHLCV field validity;
- target-session calendar defined by the intersection of SPY and QQQ sessions through 2025-12-30;
- missing-session inventory for each breadth member relative to the target-session calendar;
- common eligible session counts by development, validation, and holdout interval;
- no predictor, return, or candidate outcome generation.

## Governance boundary

This source-universe freeze does not authorize:

- breadth calculation;
- moving averages or transformations;
- SPY/QQQ future-return calculation;
- candidate construction or ranking;
- statistical testing;
- economic backtesting;
- paper trading;
- runtime or strategy changes.
