from __future__ import annotations

# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)


import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from research.harness.backtest_engine import run_backtest
from research.harness.campaign52_target_replay import run_capture_or_replay, serialize_targets
from research.harness.cross_asset_state import compute_btc_macro_state, inject_btc_macro_state
from research.harness.resampler import align_equity_curves
from scripts.run_core_v1_sleeve_contribution_audit import (
    load_data,
    make_execution_configs,
    sleeve_df,
    strategy_for,
)
from scripts.run_multi_strategy_fund import _build_sleeves
from scripts.run_multi_strategy_walkforward import _build_folds

# Keep standalone script execution working until the separate packaging migration.


SOURCE_SHA256 = {
    "btc_data": "d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079",
    "eth_data": "73721a1ef1dffbff64bf6ef2d92fb508a59b20d5c847684d96fdc7015912845f",
    "spy_data": "85a24eb44e2377cdcb9c22b0f4062730d332ec276f371e71405e1cbfc0b8ac86",
    "qqq_data": "34867c2b2da4aece23892b8e035e528f547173f3bc137cbe33b1295af0c1ff7b",
    "bil_data": "8c7522487662bc65711deb5a784806fcdb5006f631d2359d3bbaaca9e226ae7a",
    "gld_data": "f740b144a1ceea2ce85afdc503175a5e7c0f96a8cfbd6ddea3ed26cfed7d491b",
}


class Campaign52EquivalenceError(RuntimeError):
    pass


class RecordedIntentStrategy:
    """Replay the exact intents produced by the canonical execution.

    This avoids evaluating the unchanged canonical strategy a second time in
    capture mode. Sequence and dataframe-prefix length are checked fail-closed.
    """

    def __init__(self, intents: Sequence[Any]) -> None:
        self._intents = tuple(intents)
        self._cursor = 0

    def generate_intent(self, df: pd.DataFrame, ctx: Any, closed_only: bool = True) -> Any:
        expected_cursor = len(df) - 1
        if self._cursor != expected_cursor:
            raise Campaign52EquivalenceError(
                f"RECORDED_INTENT_SEQUENCE_MISMATCH:{self._cursor}:{expected_cursor}"
            )
        if self._cursor >= len(self._intents):
            raise Campaign52EquivalenceError("RECORDED_INTENT_EXHAUSTED")
        intent = self._intents[self._cursor]
        self._cursor += 1
        return intent

    def assert_consumed(self) -> None:
        if self._cursor != len(self._intents):
            raise Campaign52EquivalenceError(
                f"RECORDED_INTENT_NOT_FULLY_CONSUMED:{self._cursor}:{len(self._intents)}"
            )


def sha256_file(path: Path) -> str:
    from research.artifact_io.v1 import sha256_file_v1
    return sha256_file_v1(path, chunk_size=1048576, factory=hashlib.sha256)


def canonical_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_series(path: Path, series: pd.Series, name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    series.rename(name).to_csv(path, header=True, float_format="%.12f", lineterminator="\n")


def trade_economics(trades: list[Any]) -> list[dict[str, Any]]:
    fields = (
        "bar_index",
        "timestamp",
        "direction",
        "mid_price",
        "effective_price",
        "qty",
        "notional_usd",
        "fee_usd",
        "slippage_usd",
        "spread_usd",
        "cost_bps",
        "prev_exposure",
        "new_exposure",
        "strategy_id",
    )
    return [{field: getattr(t, field) for field in fields} for t in trades]


def assert_series_equal(label: str, a: pd.Series, b: pd.Series) -> None:
    if not a.index.equals(b.index) or not np.array_equal(
        a.to_numpy(), b.to_numpy(), equal_nan=True
    ):
        raise Campaign52EquivalenceError(f"SERIES_MISMATCH:{label}")


def assert_trade_equal(label: str, a: list[Any], b: list[Any]) -> None:
    if trade_economics(a) != trade_economics(b):
        raise Campaign52EquivalenceError(f"TRADE_MISMATCH:{label}")


def verify_sources(args: argparse.Namespace) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, expected in SOURCE_SHA256.items():
        path = Path(getattr(args, key))
        actual = sha256_file(path)
        if actual != expected:
            raise Campaign52EquivalenceError(f"SOURCE_SHA256_MISMATCH:{key}:{actual}")
        out[key] = actual
    return out


def build_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Campaign 52 governed-source capture/replay equivalence only."
    )
    p.add_argument(
        "--btc-data", default="data/btcusd_3600s_2018-01-01_to_2025-12-31.csv"
    )
    p.add_argument(
        "--eth-data", default="data/ethusd_3600s_2018-01-01_to_2025-12-31.csv"
    )
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--bil-data", default="data/BIL_1D.csv")
    p.add_argument("--gld-data", default="data/GLD_1D.csv")
    p.add_argument("--out-dir", default="artifacts/campaign52_governed_equivalence")
    p.add_argument("--data-start", default="2018-01-01")
    p.add_argument("--oos-start", default="2020-01-01")
    p.add_argument("--oos-end", default="2025-12-31")
    p.add_argument("--capital", type=float, default=100000.0)
    p.add_argument("--trend-weight", type=float, default=0.40)
    p.add_argument("--equity-weight", type=float, default=0.35)
    p.add_argument("--gold-weight", type=float, default=0.15)
    p.add_argument("--hedge-weight", type=float, default=0.10)
    p.add_argument("--mr-weight", type=float, default=0.00)
    p.add_argument("--fee", type=float, default=0.0006)
    p.add_argument("--equity-fee", type=float, default=0.0001)
    p.add_argument("--base-slippage", type=float, default=3.0)
    p.add_argument("--slippage-vol-factor", type=float, default=50.0)
    p.add_argument("--cooldown", type=int, default=2)
    p.add_argument("--mr-cooldown", type=int, default=12)
    p.add_argument("--rebalance-threshold", type=float, default=0.02)
    p.add_argument(
        "--pass-workers",
        type=int,
        choices=(1, 2),
        default=2,
        help="Run the two required independent passes concurrently by default.",
    )
    return p.parse_args()


def stage_for_fold(label: str) -> str:
    year = int(str(label)[:4])
    return "development" if year <= 2022 else "validation"


def one_pass(args: argparse.Namespace, pass_dir: Path) -> dict[str, Any]:
    pass_label = pass_dir.name
    raw = load_data(args)
    specs = [s for s in _build_sleeves(args) if s.capital > 0]
    folds = _build_folds(args.data_start, args.oos_start, args.oos_end)
    base_cfg, mr_cfg, equity_cfg = make_execution_configs(args)
    btc_state_full = compute_btc_macro_state(raw["BTC"])
    spy_close = raw["SPY"]["close"]
    spy_sma175_full = (spy_close > spy_close.rolling(175).mean()).rename(
        "spy_above_sma175"
    )
    btc_para_full = btc_state_full["btc_parabolic_hard"].rename("btc_in_parabolic")
    bil_df = pd.read_csv(args.bil_data, index_col=0, parse_dates=True)
    bil_yield_full = pd.to_numeric(bil_df["close"], errors="raise").pct_change().fillna(0.0)

    fold_navs: list[pd.Series] = []
    running_nav = float(args.capital)
    sleeve_rows: list[dict[str, Any]] = []

    for fold in folds:
        stage = stage_for_fold(fold.label)
        print(f"{pass_label} START fold={fold.label} stage={stage}", flush=True)
        raw_window = {asset: df.loc[fold.is_start : fold.oos_end] for asset, df in raw.items()}
        btc_state_window = btc_state_full.loc[fold.is_start : fold.oos_end]
        spy_window = spy_sma175_full.loc[fold.is_start : fold.oos_end]
        btc_para_window = btc_para_full.loc[fold.is_start : fold.oos_end]
        bil_window = bil_yield_full.loc[fold.is_start : fold.oos_end]
        canonical_curves: dict[str, pd.Series] = {}
        capture_curves: dict[str, pd.Series] = {}
        replay_curves: dict[str, pd.Series] = {}

        for spec in specs:
            print(f"{pass_label} START canonical fold={fold.label} sleeve={spec.label}", flush=True)
            df = sleeve_df(raw_window, spec)
            if spec.family == "trend":
                df = inject_btc_macro_state(df, btc_state_window)
            if spec.family in ("trend", "hedge"):
                df = df.copy()
                df["spy_above_sma175"] = spy_window.reindex(df.index, method="ffill")
            if spec.family == "equity":
                df = df.copy()
                df["btc_in_parabolic"] = btc_para_window.reindex(df.index, method="ffill")
            cfg = (
                equity_cfg
                if spec.family in ("equity", "gold")
                else mr_cfg
                if spec.family == "mr"
                else base_cfg
            )
            cash_yield = bil_window if spec.family in ("equity", "gold") else None
            strategy = strategy_for(spec)

            canonical = run_backtest(
                df=df,
                strategy_module=strategy,
                initial_capital=spec.capital,
                exec_config=cfg,
                asset=spec.asset,
                rebalance_threshold=args.rebalance_threshold,
                cash_yield_series=cash_yield,
            )
            if len(canonical.intent_series) != len(df):
                raise Campaign52EquivalenceError(
                    f"CANONICAL_INTENT_COUNT_MISMATCH:{fold.label}:{spec.label}:"
                    f"{len(canonical.intent_series)}:{len(df)}"
                )
            print(f"{pass_label} DONE canonical fold={fold.label} sleeve={spec.label}", flush=True)

            recorded_strategy = RecordedIntentStrategy(canonical.intent_series)
            capture = run_capture_or_replay(
                df=df,
                strategy_module=recorded_strategy,
                initial_capital=spec.capital,
                exec_config=cfg,
                asset=spec.asset,
                rebalance_threshold=args.rebalance_threshold,
                cash_yield_series=cash_yield,
                stage=stage,
                fold=fold.label,
                sleeve_label=spec.label,
                native_timeframe=spec.timeframe,
            )
            recorded_strategy.assert_consumed()
            replay = run_capture_or_replay(
                df=df,
                strategy_module=None,
                target_records=capture.targets,
                initial_capital=spec.capital,
                exec_config=cfg,
                asset=spec.asset,
                rebalance_threshold=args.rebalance_threshold,
                cash_yield_series=cash_yield,
                stage=stage,
                fold=fold.label,
                sleeve_label=spec.label,
                native_timeframe=spec.timeframe,
            )

            assert_series_equal(
                f"canonical_capture_equity:{fold.label}:{spec.label}",
                canonical.equity_curve,
                capture.result.equity_curve,
            )
            assert_series_equal(
                f"canonical_capture_exposure:{fold.label}:{spec.label}",
                canonical.position_series,
                capture.result.position_series,
            )
            assert_trade_equal(
                f"canonical_capture:{fold.label}:{spec.label}",
                canonical.trades,
                capture.result.trades,
            )
            assert_series_equal(
                f"capture_replay_equity:{fold.label}:{spec.label}",
                capture.result.equity_curve,
                replay.result.equity_curve,
            )
            assert_series_equal(
                f"capture_replay_exposure:{fold.label}:{spec.label}",
                capture.result.position_series,
                replay.result.position_series,
            )
            assert_trade_equal(
                f"capture_replay:{fold.label}:{spec.label}",
                capture.result.trades,
                replay.result.trades,
            )

            base = pass_dir / stage / fold.label / spec.label
            serialize_targets(capture.targets, base / "targets.csv")
            canonical_json(base / "trades.json", trade_economics(capture.result.trades))
            write_series(base / "exposure.csv", capture.result.position_series, "exposure")
            write_series(base / "equity.csv", capture.result.equity_curve, "equity")
            canonical_curves[spec.label] = canonical.equity_curve
            capture_curves[spec.label] = capture.result.equity_curve
            replay_curves[spec.label] = replay.result.equity_curve
            sleeve_rows.append(
                {
                    "stage": stage,
                    "fold": fold.label,
                    "sleeve": spec.label,
                    "target_rows": len(capture.targets),
                    "trade_rows": len(capture.result.trades),
                }
            )
            print(f"{pass_label} PASS equivalence fold={fold.label} sleeve={spec.label}", flush=True)

        canonical_fund = (
            align_equity_curves(canonical_curves, base_freq="1h")
            .sum(axis=1)
            .loc[fold.oos_start : fold.oos_end]
            .dropna()
        )
        capture_fund = (
            align_equity_curves(capture_curves, base_freq="1h")
            .sum(axis=1)
            .loc[fold.oos_start : fold.oos_end]
            .dropna()
        )
        replay_fund = (
            align_equity_curves(replay_curves, base_freq="1h")
            .sum(axis=1)
            .loc[fold.oos_start : fold.oos_end]
            .dropna()
        )
        assert_series_equal(
            f"fold_fund_canonical_capture:{fold.label}", canonical_fund, capture_fund
        )
        assert_series_equal(
            f"fold_fund_capture_replay:{fold.label}", capture_fund, replay_fund
        )
        scale = running_nav / float(capture_fund.iloc[0])
        scaled = capture_fund * scale
        running_nav = float(scaled.iloc[-1])
        fold_navs.append(scaled)
        write_series(pass_dir / stage / fold.label / "fold_fund_nav.csv", scaled, "nav")
        print(f"{pass_label} PASS fold={fold.label}", flush=True)

    stitched = pd.concat(fold_navs).sort_index()
    stitched = stitched[~stitched.index.duplicated(keep="last")]
    write_series(pass_dir / "stitched_nav.csv", stitched, "nav")
    canonical_json(pass_dir / "sleeve_counts.json", sleeve_rows)

    files = sorted(p for p in pass_dir.rglob("*") if p.is_file())
    hashes = {p.relative_to(pass_dir).as_posix(): sha256_file(p) for p in files}
    canonical_json(pass_dir / "artifact_sha256.json", hashes)
    print(f"{pass_label} PASS complete", flush=True)
    return {"artifact_hashes": hashes, "sleeves": sleeve_rows}


def main() -> None:
    args = build_args()
    sources = verify_sources(args)
    out = Path(args.out_dir)

    if args.pass_workers == 2:
        with ProcessPoolExecutor(max_workers=2) as pool:
            future1 = pool.submit(one_pass, args, out / "pass_1")
            future2 = pool.submit(one_pass, args, out / "pass_2")
            pass1 = future1.result()
            pass2 = future2.result()
    else:
        pass1 = one_pass(args, out / "pass_1")
        pass2 = one_pass(args, out / "pass_2")

    if pass1["artifact_hashes"] != pass2["artifact_hashes"]:
        raise Campaign52EquivalenceError("INDEPENDENT_PASS_ARTIFACT_MISMATCH")
    manifest = {
        "status": "PASS",
        "campaign": 52,
        "type": "governed_source_capture_replay_equivalence",
        "source_sha256": sources,
        "artifact_sha256": pass1["artifact_hashes"],
        "independent_passes": 2,
        "canonical_capture_equal": True,
        "capture_replay_equal": True,
        "counterfactuals_generated": False,
        "performance_metrics_calculated": False,
        "bootstrap_run": False,
        "runtime_modified": False,
        "strategy_modified": False,
        "weights_modified": False,
        "canonical_intents_reused_for_capture": True,
        "parallel_pass_workers": args.pass_workers,
    }
    canonical_json(out / "equivalence_manifest.json", manifest)
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
