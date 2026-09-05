# Repository map

This map describes the architecture at the staged refactor baseline `83e4e11` and
its compatibility-preserving extractions. It is navigation, not authorization to
run research, change an investment decision, or deploy a branch.

## Start here

- `CLAUDE.md`: operating constraints and governance index.
- `ops/status.md`: current session snapshot.
- `docs/ITERA_CAMPAIGN_BOARD.md`: authoritative campaign history and scope.
- `docs/research/ML_LAB_EXPLORATION_CHARTER.md`: exploratory boundary.
- `docs/engineering/STAGED_REFACTOR.md`: refactor scope and verification record.

## Runtime and research ownership

| Area | Role | Entry point / dependencies |
| --- | --- | --- |
| Core v1 paper runtime | Frozen six-sleeve system | `scripts/run_core_v1_paper_live.py`; allocation in `runtime/core_v1/allocation.py`; imports canonical strategies, regimes and resampling |
| Core v1 dashboard | Read-only view of state, audits and logs | `scripts/core_v1_dashboard.py`; trust rules in `scripts/core_v1_dashboard_health.py` |
| Original Argus runtime | Earlier architecture and supported test/backtest interfaces | `runtime/argus/`, `scripts/run_paper.py`; not the Core v1 paper runner |
| Canonical research | Strategies, regimes, execution simulation, portfolio studies | `research/strategies/`, `research/regimes/`, `research/harness/` |
| Governed campaigns | Numbered, scoped research and retained evidence | `docs/research/CAMPAIGN_*`, campaign-specific runners and validation modules |
| ML Lab | Exploratory, non-confirmatory work | `scripts/run_ml_lab_experiment_*.py`; packaged cross-sectional work in `research/ml_lab/` |
| Historical experiments | Reproduction and provenance | Existing strategy versions, scripts, campaign records and artifacts remain available |

Runtime may depend on canonical research primitives. It must not import ML Lab
experiment orchestration. A retired research direction can still contain helpers
used by active work; retirement alone does not prove code is safe to delete.

## Reproduction and evidence

Use the documented environment and `python -m pytest`, not an unrelated global
pytest executable. Market data is predominantly local to the operator. Synthetic
verification does not establish parity on unavailable historical market inputs.
Although `artifacts/*` is ignored for new files, the repository already tracks
selected historical artifacts. Preserve those bytes and their references.

Closed campaigns and governance history are immutable/append-only under the
operating conventions. Current navigation must link to them, not rewrite them.
The known backtest `HOLD`/desired-exposure discrepancy is a behavioral issue;
it is deliberately outside the structural refactor.
