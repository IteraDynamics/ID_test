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
import shutil
from pathlib import Path

from scripts import run_campaign52_governed_equivalence as governed


EXPECTED_CONFIG = {
    "capital": 100000.0,
    "data_start": "2018-01-01",
    "oos_start": "2020-01-01",
    "oos_end": "2025-12-31",
    "trend_weight": 0.40,
    "equity_weight": 0.35,
    "gold_weight": 0.15,
    "hedge_weight": 0.10,
    "mr_weight": 0.00,
    "fee": 0.0006,
    "equity_fee": 0.0001,
    "base_slippage": 3.0,
    "slippage_vol_factor": 50.0,
    "cooldown": 2,
    "mr_cooldown": 12,
    "rebalance_threshold": 0.02,
}


class ControlQualificationError(RuntimeError):
    pass


def canonical_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Observation-only qualification of the existing governed Core v1 control seam."
    )
    p.add_argument("--btc-data", default="data/btcusd_3600s_2018-01-01_to_2025-12-31.csv")
    p.add_argument("--eth-data", default="data/ethusd_3600s_2018-01-01_to_2025-12-31.csv")
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--bil-data", default="data/BIL_1D.csv")
    p.add_argument("--gld-data", default="data/GLD_1D.csv")
    p.add_argument("--out-dir", default="artifacts/rre_core_v1_control_qualification")
    p.add_argument("--pass-workers", type=int, choices=(1, 2), default=2)
    return p.parse_args()


def governed_args(args: argparse.Namespace, out: Path) -> argparse.Namespace:
    g = governed.build_args()
    for key in ("btc_data", "eth_data", "spy_data", "qqq_data", "bil_data", "gld_data"):
        setattr(g, key, getattr(args, key))
    g.out_dir = str(out)
    g.pass_workers = args.pass_workers
    for key, value in EXPECTED_CONFIG.items():
        if getattr(g, key) != value:
            raise ControlQualificationError(
                f"GOVERNED_DEFAULT_DRIFT:{key}:{getattr(g, key)!r}:{value!r}"
            )
    return g


def sleeve_inventory(pass_result: dict) -> list[dict]:
    rows = pass_result["sleeves"]
    grouped: dict[str, dict] = {}
    for row in rows:
        key = row["sleeve"]
        item = grouped.setdefault(
            key,
            {"sleeve": key, "folds": 0, "target_rows": 0, "trade_rows": 0, "stages": set()},
        )
        item["folds"] += 1
        item["target_rows"] += int(row["target_rows"])
        item["trade_rows"] += int(row["trade_rows"])
        item["stages"].add(row["stage"])
    result = []
    for key in sorted(grouped):
        item = grouped[key]
        result.append(
            {
                "sleeve": item["sleeve"],
                "folds": item["folds"],
                "target_rows": item["target_rows"],
                "trade_rows": item["trade_rows"],
                "stages": sorted(item["stages"]),
            }
        )
    return result


def main() -> None:
    args = parse_args()
    out = Path(args.out_dir)
    if out.exists():
        raise ControlQualificationError(f"OUTPUT_EXISTS:{out}")
    out.mkdir(parents=True, exist_ok=False)

    g = governed_args(args, out / "governed_equivalence")
    sources = {key: sha256_file(Path(getattr(args, key))) for key in governed.SOURCE_SHA256}

    if g.pass_workers == 2:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(governed.one_pass, g, Path(g.out_dir) / "pass_1")
            f2 = pool.submit(governed.one_pass, g, Path(g.out_dir) / "pass_2")
            pass1 = f1.result()
            pass2 = f2.result()
    else:
        pass1 = governed.one_pass(g, Path(g.out_dir) / "pass_1")
        pass2 = governed.one_pass(g, Path(g.out_dir) / "pass_2")

    if pass1["artifact_hashes"] != pass2["artifact_hashes"]:
        raise ControlQualificationError("INDEPENDENT_PASS_ARTIFACT_MISMATCH")

    inv1 = sleeve_inventory(pass1)
    inv2 = sleeve_inventory(pass2)
    if inv1 != inv2:
        raise ControlQualificationError("INDEPENDENT_PASS_SLEEVE_INVENTORY_MISMATCH")

    stitched_rel = "stitched_nav.csv"
    stitched_hash = pass1["artifact_hashes"].get(stitched_rel)
    if not stitched_hash:
        raise ControlQualificationError("STITCHED_NAV_HASH_MISSING")

    manifest = {
        "status": "PASS",
        "type": "rre_core_v1_fresh_paired_control_qualification",\n        "historical_reproduction_status": "HISTORICAL_SOURCE_BLOCKED",\n        "fresh_paired_control_status": "PASS",\n        "historical_nav_reproduction_claimed": False,\n        "paired_control_dataset_frozen": True,
        "observation_only": True,
        "source_sha256": sources,
        "configuration": EXPECTED_CONFIG,
        "sleeve_inventory": inv1,
        "canonical_capture_equal": True,
        "capture_replay_equal": True,
        "independent_passes": 2,
        "independent_pass_artifact_equal": True,
        "artifact_sha256": pass1["artifact_hashes"],
        "stitched_nav_sha256": stitched_hash,
        "rre_features_computed": False,
        "rre_intervention_applied": False,
        "counterfactuals_generated": False,
        "performance_comparison_calculated": False,
        "runtime_modified": False,
        "strategy_modified": False,
        "weights_modified": False,
        "costs_modified": False,
        "thresholds_modified": False,
        "execution_modified": False,
        "core_labels_modified": False,
        "intervention_seam": "existing sleeve-level pre-execution signed target stream; unchanged-target replay only",
        "known_historical_caveat": (
            "Accepted historical backtest_engine path has a documented narrow equity de-risk "
            "parity gap versus live runtime for a handful of sessions. This qualification "
            "preserves the accepted historical path and does not correct or exploit that branch."
        ),
        "pass_meaning": (
            "Accepted canonical historical Core v1 control and deterministic target-stream seam "
            "reproduced; suitable only for a separately frozen RRE paired experiment."
        ),
    }
    canonical_json(out / "qualification_manifest.json", manifest)

    # Compact share package: manifests only. Full replay artifacts remain local.
    share = out / "share"
    share.mkdir()
    shutil.copy2(out / "qualification_manifest.json", share / "qualification_manifest.json")
    canonical_json(share / "sleeve_inventory.json", inv1)
    canonical_json(
        share / "guardrails.json",
        {
            k: manifest[k]
            for k in (
                "observation_only",
                "rre_features_computed",
                "rre_intervention_applied",
                "counterfactuals_generated",
                "performance_comparison_calculated",
                "runtime_modified",
                "strategy_modified",
                "weights_modified",
                "costs_modified",
                "thresholds_modified",
                "execution_modified",
                "core_labels_modified",
                "known_historical_caveat",
            )
        },
    )

    print("RRE / Core v1 fresh paired-control qualification: PASS")\n    print("Historical reproduction: HISTORICAL_SOURCE_BLOCKED")
    print("Positive-capital sleeve inventory:")
    for row in inv1:
        print(
            f"  {row['sleeve']}: folds={row['folds']} "
            f"targets={row['target_rows']} trades={row['trade_rows']}"
        )
    print(f"Stitched NAV SHA-256: {stitched_hash}")
    print(f"SHARE RESULTS DIRECTORY: {share}")


if __name__ == "__main__":
    main()
