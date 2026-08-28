# Campaign #52 Governed-Source Capture/Replay Equivalence PASS Evidence

## Scope

This record captures the exact top-level PASS result reported from the corrected local command:

```text
python -m scripts.run_campaign52_governed_equivalence
```

The uninterrupted successful run began at 08:27 local time on 2026-08-05. A prior run was stopped only because the computer needed to be shut down and is not treated as evidence.

## Reported manifest result

```json
{
  "status": "PASS",
  "campaign": 52,
  "type": "governed_source_capture_replay_equivalence",
  "canonical_capture_equal": true,
  "canonical_intents_reused_for_capture": true,
  "capture_replay_equal": true,
  "independent_passes": 2,
  "parallel_pass_workers": 2,
  "counterfactuals_generated": false,
  "performance_metrics_calculated": false,
  "bootstrap_run": false,
  "runtime_modified": false,
  "strategy_modified": false,
  "weights_modified": false
}
```

## Governed source identities

All six frozen source SHA-256 identities matched before execution:

- BTC: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`
- ETH: `73721a1ef1dffbff64bf6ef2d92fb508a59b20d5c847684d96fdc7015912845f`
- SPY: `85a24eb44e2377cdcb9c22b0f4062730d332ec276f371e71405e1cbfc0b8ac86`
- QQQ: `34867c2b2da4aece23892b8e035e528f547173f3bc137cbe33b1295af0c1ff7b`
- BIL: `8c7522487662bc65711deb5a784806fcdb5006f631d2359d3bbaaca9e226ae7a`
- GLD: `f740b144a1ceea2ce85afdc503175a5e7c0f96a8cfbd6ddea3ed26cfed7d491b`

## Aggregate artifact identities

The complete per-file SHA-256 map was printed in the successful console manifest and written locally to both pass artifact manifests. Aggregate identities reported include:

- `sleeve_counts.json`: `33feb8cbb175ad3f517805c298f04fef9354b40b658fb12d47de27ed221b1c84`
- `stitched_nav.csv`: `84c5d96658a14526ae1e5cf761fb73c367373a83db5528a02d8124429960c596`
- development 2020 fold fund NAV: `874c98b9cb45bd346581171618551c3b813d12ecce1e0b2f4a3d1dc7394632c6`
- development 2021 fold fund NAV: `82fcead81a5b223684f076dc7faa6be647cb2f0a43816b0b3b64ccf3f8540c36`
- development 2022 fold fund NAV: `81988044a3c29aed42774f3492bc3547f7e7bba721a9fdf0d1dc12ca2d09e569`
- validation 2023 fold fund NAV: `2400498566733e13b0ed8b5ab819176915caaf0972eca7c7f2e60091b70d08d5`
- validation 2024 fold fund NAV: `85f0c806ebf0c64ec26c0a38e24fbfaa524002f5700d798fc25ff5acbb00a3cc`
- validation 2025 fold fund NAV: `706e60401a391dfca162aacea35a135dcde20ae4fcfb400aef2857074adbcfeb`

## Gate interpretation

This PASS establishes only that, on the six exact governed sources and frozen Core v1 scenario:

1. canonical execution and capture execution were economically identical;
2. capture execution and unchanged-target replay were economically identical;
3. sleeve equity, realized exposure, trade economics, fold fund NAV, and stitched NAV comparisons passed;
4. two independent passes produced identical artifact SHA-256 maps;
5. the capture/replay research adapter is fit to support a separately authorized Campaign #52 execution stage.

This PASS does not establish any Campaign #52 alpha, performance, statistical, ranking, support, development-versus-validation, or economic conclusion.

## Prohibited work not performed

- no static control;
- no lagged controls;
- no block-permuted controls;
- no Campaign #52 return, drawdown, Calmar, bootstrap, Holm, ranking, or support calculation;
- no Core logic, weights, thresholds, costs, folds, orders, exposure, strategy, runtime, dashboard, or model-training change;
- no paper or live execution.
