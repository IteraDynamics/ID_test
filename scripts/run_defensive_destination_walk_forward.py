#!/usr/bin/env python
"""Research-only walk-forward validation for DefensiveDestinationAllocator.

This script evaluates whether the state-confirmed GLD/BIL allocator survives
chronological validation instead of relying only on full-sample backtests.

It produces three validation views:

1. Fixed-rule subperiods
   - Uses the selected/default rule unchanged across chronological slices.

2. Fixed-rule train/test splits
   - Reports candidate behavior on predefined discovery/test periods.

3. Rolling walk-forward parameter selection
   - Selects from a small allowed grid on each training window.
   - Applies the selected rule to the next unseen test window.

Research-only. No runtime, broker, governor, or live execution code is imported
or modified.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from itertools import product
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from research.harness.metrics import compute_metrics
from scripts.run_risk_off_trigger_sweep import _buy_hold_curve, _load_baseline_cache, _normalized_returns
from scripts.run_state_confirmed_risk_off_sweep import _btc_below_sma, _load_close, _state_confirmed_risk_off


def _fmt_pct(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return "n/a" if math.isnan(v) else f"{v:.2f}%"


def _fmt_num(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return "n/a" if math.isnan(v) else f"{v:.{digits}f}"


def _slice(series: pd.Series, start: str, end: str) -> pd.Series:
    return series.loc[(series.index >= pd.Timestamp(start)) & (series.index <= pd.Timestamp(end))].dropna()


def _split_ranges(raw: list[str]) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for item in raw:
        parts = item.split(":")
        if len(parts) != 3:
            raise ValueError(f"Range must be NAME:YYYY-MM-DD:YYYY-MM-DD, got {item!r}")
        out.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))
    return out


def _train_test_ranges(raw: list[str]) -> list[tuple[str, str, str, str, str]]:
    out: list[tuple[str, str, str, str, str]] = []
    for item in raw:
        parts = item.split(":")
        if len(parts) != 5:
            raise ValueError(
                "Train/test split must be NAME:TRAIN_START:TRAIN_END:TEST_START:TEST_END, "
                f"got {item!r}"
            )
        out.append((parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip(), parts[4].strip()))
    return out


def _blend_destination(gld: pd.Series, bil: pd.Series, gld_weight: float, capital: float) -> pd.Series:
    aligned = pd.DataFrame({"gld": gld, "bil": bil}).dropna(how="any")
    rets = aligned.pct_change(fill_method=None).fillna(0.0)
    blend_rets = gld_weight * rets["gld"] + (1.0 - gld_weight) * rets["bil"]
    out = capital * (1.0 + blend_rets).cumprod()
    out.name = f"gld{int(round(gld_weight * 100))}_bil{int(round((1.0 - gld_weight) * 100))}"
    return out


def _apply_overlay(
    baseline: pd.Series,
    destination: pd.Series,
    btc_close: pd.Series,
    trigger_dd: float,
    release_dd: float,
    btc_sma_window: int,
    gld_weight: float,
    crypto_scale: float,
    capital: float,
    release_mode: str,
) -> tuple[pd.Series, pd.Series]:
    common = baseline.index.intersection(destination.index).sort_values()
    base = baseline.reindex(common).dropna()
    dest = destination.reindex(base.index).dropna()
    common = base.index.intersection(dest.index)
    base = base.reindex(common)
    dest = dest.reindex(common)
    btc_bad = _btc_below_sma(btc_close, base.index, btc_sma_window)
    risk_off = _state_confirmed_risk_off(base, btc_bad, trigger_dd, release_dd, release_mode)
    aligned = pd.DataFrame({"baseline": base, "destination": dest, "risk_off": risk_off.astype(float)}).dropna(how="any")
    crypto_ret = _normalized_returns(aligned["baseline"])
    dest_ret = _normalized_returns(aligned["destination"])
    active = aligned["risk_off"].astype(bool)
    w_crypto = pd.Series(1.0, index=aligned.index)
    w_dest = pd.Series(0.0, index=aligned.index)
    w_crypto.loc[active] = crypto_scale
    w_dest.loc[active] = 1.0 - crypto_scale
    ret = w_crypto * crypto_ret + w_dest * dest_ret
    equity = capital * (1.0 + ret).cumprod()
    equity.name = "overlay"
    return equity, active.rename("risk_off")


def _rebased(series: pd.Series, capital: float) -> pd.Series:
    s = series.dropna()
    if s.empty:
        return s
    rets = s.pct_change(fill_method=None).fillna(0.0)
    out = capital * (1.0 + rets).cumprod()
    out.name = series.name
    return out


def _metrics(label: str, equity: pd.Series, capital: float) -> dict[str, Any]:
    s = equity.dropna()
    if len(s) < 3:
        return {
            "label": label,
            "rows": int(len(s)),
            "final_nav": None,
            "cagr_pct": None,
            "max_drawdown_pct": None,
            "sharpe": None,
            "calmar": None,
        }
    m = compute_metrics(s, trades=[], params={"strategy_id": label, "asset": "PORTFOLIO", "initial_capital": capital})
    return {
        "label": label,
        "rows": int(len(s)),
        "final_nav": float(s.iloc[-1]),
        "cagr_pct": m.cagr_pct,
        "max_drawdown_pct": m.max_drawdown_pct,
        "sharpe": m.sharpe,
        "calmar": m.calmar,
    }


def _eval_rule_on_window(
    name: str,
    start: str,
    end: str,
    baseline: pd.Series,
    destination: pd.Series,
    btc_close: pd.Series,
    args: argparse.Namespace,
    trigger_dd: float,
    release_dd: float,
    btc_sma_window: int,
    gld_weight: float,
) -> dict[str, Any]:
    overlay, risk_off = _apply_overlay(
        baseline,
        destination,
        btc_close,
        trigger_dd,
        release_dd,
        btc_sma_window,
        gld_weight,
        args.crypto_scale,
        args.capital,
        args.release_mode,
    )
    base_w = _rebased(_slice(baseline, start, end), args.capital)
    overlay_w = _rebased(_slice(overlay, start, end), args.capital)
    risk_w = risk_off.reindex(overlay_w.index).ffill().fillna(False).astype(bool)
    bm = _metrics("baseline", base_w, args.capital)
    om = _metrics("overlay", overlay_w, args.capital)
    return {
        "window": name,
        "start": start,
        "end": end,
        "trigger_dd": trigger_dd,
        "release_dd": release_dd,
        "btc_sma_window": btc_sma_window,
        "gld_weight": gld_weight,
        "bil_weight": 1.0 - gld_weight,
        "baseline_cagr_pct": bm["cagr_pct"],
        "baseline_max_drawdown_pct": bm["max_drawdown_pct"],
        "baseline_sharpe": bm["sharpe"],
        "baseline_calmar": bm["calmar"],
        "overlay_cagr_pct": om["cagr_pct"],
        "overlay_max_drawdown_pct": om["max_drawdown_pct"],
        "overlay_sharpe": om["sharpe"],
        "overlay_calmar": om["calmar"],
        "delta_cagr_pct": None if bm["cagr_pct"] is None or om["cagr_pct"] is None else om["cagr_pct"] - bm["cagr_pct"],
        "delta_max_drawdown_pct": None if bm["max_drawdown_pct"] is None or om["max_drawdown_pct"] is None else om["max_drawdown_pct"] - bm["max_drawdown_pct"],
        "delta_sharpe": None if bm["sharpe"] is None or om["sharpe"] is None else om["sharpe"] - bm["sharpe"],
        "delta_calmar": None if bm["calmar"] is None or om["calmar"] is None else om["calmar"] - bm["calmar"],
        "risk_off_days": int(risk_w.sum()) if len(risk_w) else 0,
        "risk_off_pct_days": float(risk_w.mean() * 100.0) if len(risk_w) else 0.0,
        "rows": int(len(overlay_w)),
    }


def _score_row(row: dict[str, Any]) -> tuple[float, float, float, float]:
    calmar = row.get("overlay_calmar")
    sharpe = row.get("overlay_sharpe")
    dd = row.get("overlay_max_drawdown_pct")
    cagr = row.get("overlay_cagr_pct")
    return (
        -9999.0 if calmar is None or math.isnan(float(calmar)) else float(calmar),
        -9999.0 if sharpe is None or math.isnan(float(sharpe)) else float(sharpe),
        -9999.0 if dd is None or math.isnan(float(dd)) else float(dd),
        -9999.0 if cagr is None or math.isnan(float(cagr)) else float(cagr),
    )


def _fixed_rule_subperiods(
    baseline: pd.Series,
    gld: pd.Series,
    bil: pd.Series,
    btc_close: pd.Series,
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    dest = _blend_destination(gld, bil, args.gld_weight, args.capital)
    rows = []
    for name, start, end in _split_ranges(args.subperiods):
        rows.append(
            _eval_rule_on_window(
                name,
                start,
                end,
                baseline,
                dest,
                btc_close,
                args,
                args.trigger_dd,
                args.release_dd,
                args.btc_sma_window,
                args.gld_weight,
            )
        )
    return rows


def _fixed_rule_train_test(
    baseline: pd.Series,
    gld: pd.Series,
    bil: pd.Series,
    btc_close: pd.Series,
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    dest = _blend_destination(gld, bil, args.gld_weight, args.capital)
    rows = []
    for name, train_start, train_end, test_start, test_end in _train_test_ranges(args.train_test_splits):
        train = _eval_rule_on_window(
            f"{name}_train",
            train_start,
            train_end,
            baseline,
            dest,
            btc_close,
            args,
            args.trigger_dd,
            args.release_dd,
            args.btc_sma_window,
            args.gld_weight,
        )
        train["split"] = name
        train["role"] = "train"
        test = _eval_rule_on_window(
            f"{name}_test",
            test_start,
            test_end,
            baseline,
            dest,
            btc_close,
            args,
            args.trigger_dd,
            args.release_dd,
            args.btc_sma_window,
            args.gld_weight,
        )
        test["split"] = name
        test["role"] = "test"
        rows.extend([train, test])
    return rows


def _rolling_walk_forward(
    baseline: pd.Series,
    gld: pd.Series,
    bil: pd.Series,
    btc_close: pd.Series,
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    destinations = {w: _blend_destination(gld, bil, w, args.capital) for w in args.grid_gld_weights}
    rows: list[dict[str, Any]] = []
    for name, train_start, train_end, test_start, test_end in _train_test_ranges(args.rolling_windows):
        candidates = []
        for trigger_dd, release_dd, sma, gld_weight in product(
            args.grid_trigger_dds,
            args.grid_release_dds,
            args.grid_btc_sma_windows,
            args.grid_gld_weights,
        ):
            if release_dd <= trigger_dd:
                continue
            train_row = _eval_rule_on_window(
                f"{name}_train_candidate",
                train_start,
                train_end,
                baseline,
                destinations[gld_weight],
                btc_close,
                args,
                trigger_dd,
                release_dd,
                sma,
                gld_weight,
            )
            candidates.append(train_row)
        if not candidates:
            continue
        selected = sorted(candidates, key=_score_row, reverse=True)[0]
        test_row = _eval_rule_on_window(
            f"{name}_test",
            test_start,
            test_end,
            baseline,
            destinations[selected["gld_weight"]],
            btc_close,
            args,
            selected["trigger_dd"],
            selected["release_dd"],
            selected["btc_sma_window"],
            selected["gld_weight"],
        )
        selected_out = dict(selected)
        selected_out.update({"wf_window": name, "role": "selected_train", "train_start": train_start, "train_end": train_end, "test_start": test_start, "test_end": test_end})
        test_row.update({"wf_window": name, "role": "out_of_sample_test", "selected_train_calmar": selected["overlay_calmar"], "selected_train_cagr_pct": selected["overlay_cagr_pct"]})
        rows.extend([selected_out, test_row])
    return rows


def _summary_stats(rows: list[dict[str, Any]], role_filter: str | None = None) -> dict[str, Any]:
    if role_filter is not None:
        rows = [r for r in rows if r.get("role") == role_filter]
    if not rows:
        return {"count": 0}
    valid = [r for r in rows if r.get("delta_calmar") is not None]
    dd_valid = [r for r in rows if r.get("delta_max_drawdown_pct") is not None]
    return {
        "count": len(rows),
        "calmar_win_count": sum(1 for r in valid if float(r["delta_calmar"]) > 0),
        "calmar_win_rate_pct": round(sum(1 for r in valid if float(r["delta_calmar"]) > 0) / max(len(valid), 1) * 100.0, 4),
        "drawdown_improvement_count": sum(1 for r in dd_valid if float(r["delta_max_drawdown_pct"]) > 0),
        "drawdown_improvement_rate_pct": round(sum(1 for r in dd_valid if float(r["delta_max_drawdown_pct"]) > 0) / max(len(dd_valid), 1) * 100.0, 4),
        "median_delta_calmar": None if not valid else float(pd.Series([r["delta_calmar"] for r in valid]).median()),
        "median_delta_cagr_pct": None if not valid else float(pd.Series([r["delta_cagr_pct"] for r in valid if r.get("delta_cagr_pct") is not None]).median()),
    }


def _write_outputs(
    args: argparse.Namespace,
    fixed_rows: list[dict[str, Any]],
    split_rows: list[dict[str, Any]],
    rolling_rows: list[dict[str, Any]],
) -> Path:
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(fixed_rows).to_csv(out / "fixed_rule_subperiods.csv", index=False)
    pd.DataFrame(split_rows).to_csv(out / "fixed_rule_train_test_splits.csv", index=False)
    pd.DataFrame(rolling_rows).to_csv(out / "rolling_walk_forward.csv", index=False)
    summary = {
        "config": vars(args),
        "fixed_rule_subperiods": _summary_stats(fixed_rows),
        "fixed_rule_train_test_all": _summary_stats(split_rows),
        "fixed_rule_train_test_tests_only": _summary_stats(split_rows, "test"),
        "rolling_walk_forward_tests_only": _summary_stats(rolling_rows, "out_of_sample_test"),
    }
    (out / "walk_forward_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    md = out / "walk_forward_summary.md"
    with md.open("w", encoding="utf-8") as f:
        f.write("# Defensive Destination Walk-Forward Validation\n\n")
        f.write("Research-only chronological validation for the GLD/BIL defensive destination allocator.\n\n")
        f.write("## Default Fixed Rule\n\n")
        f.write(f"- Trigger / release: `{args.trigger_dd:.0%}` / `{args.release_dd:.0%}`\n")
        f.write(f"- BTC SMA: `{args.btc_sma_window}`\n")
        f.write(f"- Destination: `{args.gld_weight:.0%} GLD / {1.0 - args.gld_weight:.0%} BIL`\n")
        f.write(f"- Crypto scale: `{args.crypto_scale:.0%}`\n\n")
        f.write("## Summary Stats\n\n")
        for name, stats in summary.items():
            if name == "config":
                continue
            f.write(f"### {name}\n\n")
            for k, v in stats.items():
                f.write(f"- {k}: `{v}`\n")
            f.write("\n")
        f.write("## Fixed-Rule Subperiods\n\n")
        f.write("| Window | Start | End | Base Calmar | Overlay Calmar | dCalmar | Base DD | Overlay DD | dDD | RiskOff |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for r in fixed_rows:
            f.write(
                f"| {r['window']} | {r['start']} | {r['end']} | {_fmt_num(r['baseline_calmar'])} | "
                f"{_fmt_num(r['overlay_calmar'])} | {_fmt_num(r['delta_calmar'])} | {_fmt_pct(r['baseline_max_drawdown_pct'])} | "
                f"{_fmt_pct(r['overlay_max_drawdown_pct'])} | {_fmt_pct(r['delta_max_drawdown_pct'])} | {r['risk_off_pct_days']:.1f}% |\n"
            )
        f.write("\n## Rolling Walk-Forward Tests\n\n")
        f.write("| Window | Role | Trigger | Release | SMA | GLD | Base Calmar | Overlay Calmar | dCalmar | Base DD | Overlay DD | dDD |\n")
        f.write("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for r in rolling_rows:
            if r.get("role") != "out_of_sample_test":
                continue
            f.write(
                f"| {r['wf_window']} | {r['role']} | {r['trigger_dd']:.0%} | {r['release_dd']:.0%} | {r['btc_sma_window']} | "
                f"{r['gld_weight']:.0%} | {_fmt_num(r['baseline_calmar'])} | {_fmt_num(r['overlay_calmar'])} | {_fmt_num(r['delta_calmar'])} | "
                f"{_fmt_pct(r['baseline_max_drawdown_pct'])} | {_fmt_pct(r['overlay_max_drawdown_pct'])} | {_fmt_pct(r['delta_max_drawdown_pct'])} |\n"
            )
        f.write("\n## Interpretation\n\n")
        f.write("```text\n")
        f.write("This is still historical validation, but it reduces overfit risk by forcing chronological tests and train-selected parameters applied to unseen future windows.\n")
        f.write("Passing does not approve live runtime. Failing or unstable windows should block promotion and drive further research.\n")
        f.write("```\n")
    return md


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Research-only DefensiveDestinationAllocator walk-forward validation")
    p.add_argument("--baseline-cache", required=True)
    p.add_argument("--btc-daily", required=True)
    p.add_argument("--gld-data", required=True)
    p.add_argument("--bil-data", required=True)
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--trigger-dd", type=float, default=-0.18)
    p.add_argument("--release-dd", type=float, default=-0.12)
    p.add_argument("--btc-sma-window", type=int, default=200)
    p.add_argument("--gld-weight", type=float, default=0.50)
    p.add_argument("--crypto-scale", type=float, default=0.0)
    p.add_argument("--release-mode", choices=["either", "both"], default="either")
    p.add_argument("--grid-trigger-dds", nargs="+", type=float, default=[-0.18, -0.20, -0.22])
    p.add_argument("--grid-release-dds", nargs="+", type=float, default=[-0.08, -0.10, -0.12])
    p.add_argument("--grid-btc-sma-windows", nargs="+", type=int, default=[180, 200, 220])
    p.add_argument("--grid-gld-weights", nargs="+", type=float, default=[0.75, 0.50, 0.25])
    p.add_argument(
        "--subperiods",
        nargs="+",
        default=[
            "2019_2020:2019-01-01:2020-12-31",
            "2021_2022:2021-01-01:2022-12-31",
            "2023_2024:2023-01-01:2024-12-31",
            "2025:2025-01-01:2025-12-30",
        ],
    )
    p.add_argument(
        "--train-test-splits",
        nargs="+",
        default=[
            "train_2019_2022_test_2023_2025:2019-01-01:2022-12-31:2023-01-01:2025-12-30",
            "train_2019_2023_test_2024_2025:2019-01-01:2023-12-31:2024-01-01:2025-12-30",
        ],
    )
    p.add_argument(
        "--rolling-windows",
        nargs="+",
        default=[
            "wf_test_2022:2019-01-01:2021-12-31:2022-01-01:2022-12-31",
            "wf_test_2023:2020-01-01:2022-12-31:2023-01-01:2023-12-31",
            "wf_test_2024:2021-01-01:2023-12-31:2024-01-01:2024-12-31",
            "wf_test_2025:2022-01-01:2024-12-31:2025-01-01:2025-12-30",
        ],
    )
    p.add_argument("--out-dir", default="artifacts/defensive_destination_walk_forward")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    baseline = _load_baseline_cache(args.baseline_cache)
    btc_close = _load_close(args.btc_daily, "BTC", args.start, args.end)
    gld = _buy_hold_curve(args.gld_data, "GLD", args.capital, args.start, args.end)
    bil = _buy_hold_curve(args.bil_data, "BIL", args.capital, args.start, args.end)
    common = baseline.index.intersection(gld.index).intersection(bil.index).sort_values()
    baseline, gld, bil = baseline.reindex(common).dropna(), gld.reindex(common).dropna(), bil.reindex(common).dropna()
    common = baseline.index.intersection(gld.index).intersection(bil.index).sort_values()
    baseline, gld, bil = baseline.reindex(common), gld.reindex(common), bil.reindex(common)

    fixed_rows = _fixed_rule_subperiods(baseline, gld, bil, btc_close, args)
    split_rows = _fixed_rule_train_test(baseline, gld, bil, btc_close, args)
    rolling_rows = _rolling_walk_forward(baseline, gld, bil, btc_close, args)
    md = _write_outputs(args, fixed_rows, split_rows, rolling_rows)

    fixed_stats = _summary_stats(fixed_rows)
    rolling_stats = _summary_stats(rolling_rows, "out_of_sample_test")

    print("=" * 148)
    print("  DEFENSIVE DESTINATION — WALK-FORWARD VALIDATION")
    print("=" * 148)
    print(f"  Fixed rule        : {args.trigger_dd:.0%}/{args.release_dd:.0%}, SMA{args.btc_sma_window}, {args.gld_weight:.0%} GLD / {1.0 - args.gld_weight:.0%} BIL")
    print(f"  Rolling grid      : {len(args.grid_trigger_dds)} triggers x {len(args.grid_release_dds)} releases x {len(args.grid_btc_sma_windows)} SMAs x {len(args.grid_gld_weights)} blends")
    print("-" * 148)
    print("  Fixed-rule subperiods:")
    print(f"  {'Window':<14} {'BaseCal':>8} {'OverCal':>8} {'dCal':>8} {'BaseDD':>9} {'OverDD':>9} {'dDD':>9} {'RiskOff':>8}")
    print("  " + "-" * 146)
    for r in fixed_rows:
        print(
            f"  {r['window']:<14} {_fmt_num(r['baseline_calmar']):>8} {_fmt_num(r['overlay_calmar']):>8} {_fmt_num(r['delta_calmar']):>8} "
            f"{_fmt_pct(r['baseline_max_drawdown_pct']):>9} {_fmt_pct(r['overlay_max_drawdown_pct']):>9} {_fmt_pct(r['delta_max_drawdown_pct']):>9} {r['risk_off_pct_days']:>7.1f}%"
        )
    print("-" * 148)
    print("  Rolling out-of-sample tests:")
    print(f"  {'Window':<14} {'Trig':>6} {'Rel':>6} {'SMA':>5} {'GLD':>5} {'BaseCal':>8} {'OverCal':>8} {'dCal':>8} {'BaseDD':>9} {'OverDD':>9} {'dDD':>9}")
    print("  " + "-" * 146)
    for r in rolling_rows:
        if r.get("role") != "out_of_sample_test":
            continue
        print(
            f"  {r['wf_window']:<14} {r['trigger_dd']:>6.0%} {r['release_dd']:>6.0%} {r['btc_sma_window']:>5} {r['gld_weight']:>5.0%} "
            f"{_fmt_num(r['baseline_calmar']):>8} {_fmt_num(r['overlay_calmar']):>8} {_fmt_num(r['delta_calmar']):>8} "
            f"{_fmt_pct(r['baseline_max_drawdown_pct']):>9} {_fmt_pct(r['overlay_max_drawdown_pct']):>9} {_fmt_pct(r['delta_max_drawdown_pct']):>9}"
        )
    print("-" * 148)
    print(f"  Fixed-rule Calmar win rate : {fixed_stats.get('calmar_win_rate_pct')}%")
    print(f"  Rolling OOS Calmar win rate: {rolling_stats.get('calmar_win_rate_pct')}%")
    print(f"  Rolling OOS DD improve rate: {rolling_stats.get('drawdown_improvement_rate_pct')}%")
    print("=" * 148)
    print(f"  Summary: {md}")
    print("  Verdict: research-only walk-forward validation; not production approval.\n")


if __name__ == "__main__":
    main()
