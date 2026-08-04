# Campaign #52 Source-Identity and Calendar Preflight Evidence

## Status

**PASS — source-only identity and calendar gate completed.**

This record captures the local evidence supplied after running the governed Campaign #52 source/calendar preflight. It does not authorize canonical Core execution, target capture, counterfactual generation, NAV construction, performance calculation, or development/validation execution.

Focused synthetic tests were reported as passed. The exact pytest output and test count were not supplied and are not asserted here.

## Governed lineage

- statistical specification: `14a96b4078eec516570fce0c289baa061398a995`
- frozen Core reference: `1b556e599fd962469f8b7eace595b15e9d6d6cf6`
- preflight implementation: `597c32fd0b5ba3846b7ca74d13223ea3fdfa2ea1`
- calendar-date coverage correction: `0ba18dfcb0193fc267b07691cf81fb36efd46593`
- focused test correction: `c3ce60580a973305da7c05e91cea656e91126a6f`

## Source identities

### BTC

- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`
- bytes: `4,792,028`
- rows: `70,069`
- schema: `timestamp,open,high,low,close,volume`
- coverage: `2018-01-01 00:00:00` through `2025-12-31 00:00:00`
- cadence: `3600` seconds
- missing expected timestamps: `36`
- duplicate timestamps: `0`
- strictly increasing: `true`

### ETH

- path: `data/ethusd_3600s_2018-01-01_to_2025-12-31.csv`
- SHA-256: `73721a1ef1dffbff64bf6ef2d92fb508a59b20d5c847684d96fdc7015912845f`
- bytes: `4,550,061`
- rows: `70,086`
- schema: `timestamp,open,high,low,close,volume`
- coverage: `2018-01-01 00:00:00` through `2025-12-31 00:00:00`
- cadence: `3600` seconds
- missing expected timestamps: `19`
- duplicate timestamps: `0`
- strictly increasing: `true`

### SPY

- path: `data/SPY_1D.csv`
- SHA-256: `85a24eb44e2377cdcb9c22b0f4062730d332ec276f371e71405e1cbfc0b8ac86`
- bytes: `213,839`
- rows: `2,010`
- schema: `timestamp,open,high,low,close,volume`
- coverage: `2018-01-02 00:00:00` through `2025-12-30 00:00:00`
- cadence: `86400` seconds
- calendar gaps relative to daily cadence: `910`
- duplicate timestamps: `0`
- strictly increasing: `true`

### QQQ

- path: `data/QQQ_1D.csv`
- SHA-256: `34867c2b2da4aece23892b8e035e528f547173f3bc137cbe33b1295af0c1ff7b`
- bytes: `214,940`
- rows: `2,010`
- schema: `timestamp,open,high,low,close,volume`
- coverage: `2018-01-02 00:00:00` through `2025-12-30 00:00:00`
- cadence: `86400` seconds
- calendar gaps relative to daily cadence: `910`
- duplicate timestamps: `0`
- strictly increasing: `true`

### BIL

- path: `data/BIL_1D.csv`
- SHA-256: `8c7522487662bc65711deb5a784806fcdb5006f631d2359d3bbaaca9e226ae7a`
- bytes: `156,266`
- rows: `1,714`
- schema: `timestamp,open,high,low,close,volume`
- coverage: `2019-03-08 00:00:00` through `2025-12-30 00:00:00`
- cadence: `86400` seconds
- calendar gaps relative to daily cadence: `776`
- duplicate timestamps: `0`
- strictly increasing: `true`

### GLD

- path: `data/GLD_1D.csv`
- SHA-256: `f740b144a1ceea2ce85afdc503175a5e7c0f96a8cfbd6ddea3ed26cfed7d491b`
- bytes: `216,737`
- rows: `2,010`
- schema: `timestamp,open,high,low,close,volume`
- coverage: `2018-01-02 00:00:00` through `2025-12-30 00:00:00`
- cadence: `86400` seconds
- calendar gaps relative to daily cadence: `910`
- duplicate timestamps: `0`
- strictly increasing: `true`

All six sources passed development and validation calendar-date coverage under the governed inclusive-date semantics. No source substitution, repair, interpolation, fill, or acquisition occurred.

## Stage geometry

Both retrospective stages contain:

- `39` complete 28-day wall-clock blocks;
- one terminal remainder of `4` days (`345,600` seconds).

Stages:

- development: `2020-01-01` through `2022-12-31`
- validation: `2023-01-01` through `2025-12-31`

## Exact lag-mapping facts

### Development

Crypto sources, each with `26,301` timestamps:

- 24h: `26,274` exact mappings; `27` uncovered
- 168h: `26,130` exact mappings; `171` uncovered
- 672h: `25,626` exact mappings; `675` uncovered

Daily market sources, each with `756` timestamps:

- 24h: `596` exact mappings; `160` uncovered
- 168h: `727` exact mappings; `29` uncovered
- 672h: `714` exact mappings; `42` uncovered

### Validation

Crypto sources, each with `26,273` timestamps:

- 24h: `26,241` exact mappings; `32` uncovered
- 168h: `26,097` exact mappings; `176` uncovered
- 672h: `25,593` exact mappings; `680` uncovered

Daily market sources, each with `751` timestamps:

- 24h: `583` exact mappings; `168` uncovered
- 168h: `719` exact mappings; `32` uncovered
- 672h: `705` exact mappings; `46` uncovered

These counts reflect exact timestamp matching only. No nearest matching, resampling, forward fill, wraparound, cross-stage carry, or cross-fold carry was used.

## Safety state

The emitted preflight reported:

- `prices_parsed`: `false`
- `targets_generated`: `false`
- `signals_generated`: `false`
- `positions_generated`: `false`
- `trades_generated`: `false`
- `costs_generated`: `false`
- `returns_generated`: `false`
- `nav_generated`: `false`
- `performance_metrics_calculated`: `false`
- `capture_replay_implemented`: `false`
- `runtime_modified`: `false`
- `strategy_modified`: `false`
- `weights_modified`: `false`

## Gate conclusion

The six governed sources and frozen stage calendar are mechanically suitable for Campaign #52 implementation planning. The source/calendar preflight gate passes.

This result authorizes nothing beyond returning to the campaign board for a separate capture/replay implementation decision.
