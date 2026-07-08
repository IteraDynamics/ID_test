from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from research.jump_risk_engine import JumpRiskConfig, run_jump_risk_lab


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Research-only Jump / Discontinuity Risk Engine lab. Does not touch Core v1 runtime.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--asset", required=True, help="Asset label, e.g. BTC, ETH, SPY, QQQ, GLD")
    p.add_argument("--data", required=True, help="CSV containing timestamp/date + OHLCV columns")
    p.add_argument("--out-dir", default="artifacts/jump_risk_engine_v0")
    p.add_argument("--horizon-bars", type=int, default=24)
    p.add_argument("--vol-window", type=int, default=96)
    p.add_argument("--fast-window", type=int, default=24)
    p.add_argument("--slow-window", type=int, default=240)
    p.add_argument("--jump-z", type=float, default=3.0)
    p.add_argument("--absolute-jump", type=float, default=0.05)
    p.add_argument("--test-start-year", type=int, default=2020)
    p.add_argument("--models", default="logistic,gbm", help="Comma-separated: logistic,gbm,rf")
    p.add_argument("--targets", default="any,down,up", help="Comma-separated: any,down,up")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = JumpRiskConfig(
        asset=args.asset.upper(),
        horizon_bars=args.horizon_bars,
        vol_window=args.vol_window,
        fast_window=args.fast_window,
        slow_window=args.slow_window,
        jump_z=args.jump_z,
        absolute_jump=args.absolute_jump,
        test_start_year=args.test_start_year,
    )
    models = tuple(x.strip() for x in args.models.split(",") if x.strip())
    targets = tuple(x.strip() for x in args.targets.split(",") if x.strip())
    report = run_jump_risk_lab(args.data, cfg, args.out_dir, models=models, targets=targets)

    print("Jump Risk Engine v0 research complete")
    print(f"Asset: {cfg.asset}")
    print(f"Rows: {report['label_summary']['rows']}")
    print(f"Window: {report['label_summary']['start']} -> {report['label_summary']['end']}")
    print(f"Jump-any rate: {report['label_summary']['jump_any_rate']:.2%}")
    print(f"Jump-down rate: {report['label_summary']['jump_down_rate']:.2%}")
    print(f"Jump-up rate: {report['label_summary']['jump_up_rate']:.2%}")
    print(f"Out dir: {args.out_dir}")
    print()
    print("Model summary:")
    for run in report["runs"]:
        agg = run["aggregate"]
        auc = agg.get("roc_auc")
        ap = agg.get("average_precision")
        status = agg.get("status")
        print(
            f"- target={run['target']:<4} model={run['model']:<8} status={status:<7} "
            f"auc={auc if auc is not None else 'n/a'} ap={ap if ap is not None else 'n/a'}"
        )


if __name__ == "__main__":
    main()
