# Campaign #48 — Simple BTC Price-State Predictive Baselines

## Source

- Path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`
- Governed missing hours: `36`

## Inventory

- Anchors: `403`
- Predictors: `8`
- Outcome families: `3`
- Horizons: `3`
- Candidates: `72`
- Rankable: `72`

## Status counts

- `SUPPORTED_RESEARCH_ASSOCIATION`: `15`
- `MULTIPLICITY_NOT_MET`: `55`
- `DIRECTION_INCONSISTENT`: `2`
- `INSUFFICIENT_SUPPORT`: `0`
- `OUTCOME_OR_PREDICTOR_UNAVAILABLE`: `0`
- `ZERO_OR_NONFINITE_VARIANCE`: `0`
- `RANK_DEFICIENT_DESIGN`: `0`
- `ESTIMATOR_FAILURE`: `0`

## Supported candidates

| Candidate | Coefficient | Adjusted q |
|---|---:|---:|
| `realized_volatility_trailing_24h__M__24h` | 0.0081461565650519877 | 0.0033826571058039475 |
| `realized_volatility_trailing_24h__M__72h` | 0.0079936671973496222 | 0.04385904588732914 |
| `realized_volatility_trailing_24h__M__168h` | 0.011504330470319324 | 0.0058472440114221008 |
| `realized_volatility_trailing_24h__V__24h` | 0.012745964338183912 | 1.8474310822804302e-35 |
| `realized_volatility_trailing_24h__V__72h` | 0.017333481107299483 | 1.1315784452388253e-18 |
| `realized_volatility_trailing_24h__V__168h` | 0.025369673184088996 | 2.7028084661938287e-19 |
| `realized_volatility_trailing_168h__M__24h` | 0.0089640817407684956 | 0.0006377965044904435 |
| `realized_volatility_trailing_168h__M__72h` | 0.0091519387176430596 | 0.021052099543401953 |
| `realized_volatility_trailing_168h__M__168h` | 0.0099489363911283348 | 0.024992776829785637 |
| `realized_volatility_trailing_168h__V__24h` | 0.012790454777499053 | 6.2442767692199801e-50 |
| `realized_volatility_trailing_168h__V__72h` | 0.018186085457430962 | 1.7962705147077251e-23 |
| `realized_volatility_trailing_168h__V__168h` | 0.025390178989595225 | 3.2140285598570125e-25 |
| `drawdown_from_high_trailing_168h__V__24h` | -0.010415498081226644 | 2.7943205348962069e-20 |
| `drawdown_from_high_trailing_168h__V__72h` | -0.014828553880830526 | 2.070369990409075e-15 |
| `drawdown_from_high_trailing_168h__V__168h` | -0.02058168074771272 | 4.2530582965718319e-14 |

## Interpretation boundary

This is a research-only association study. A supported association does not establish deployable alpha, economic value, transaction-cost robustness, portfolio improvement, superiority to Core v1, or production readiness.

No runtime, threshold, regime, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change is authorized.
