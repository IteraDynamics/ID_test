#!/usr/bin/env python
"""Equity Alpha Rule Replay v1 — soft overlay pass.

Research-only companion to the hard-overlay replay. Tests smaller exposure tilts
instead of forcing full SPY/QQQ exposure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_equity_alpha_rule_replay_v1 import (
    DEFAULT_OPTIONAL_ASSETS,
    DEFAULT_SECTORS,
    START_CAPITAL,
    WINDOWS,
    _asset_curve,
    _base_weights,
    _build_signal_panel,
    _curve_from_weights,
    _event_counts,
    _exposure_summary,
    _fmt_md_value,
    _load_assets,
    _load_close,
    _parse_csv_list,
    _passive_curve,
    _perf,
    _slice,
)

DEFAULT_OUT = "artifacts/equity_alpha_rule_replay_v1_soft"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Replay soft equity alpha overlays")
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--bil-data", default="data/BIL_1D.csv")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--sectors", default=DEFAULT_SECTORS)
    p.add_argument("--optional-assets", default=DEFAULT_OPTIONAL_ASSETS)
    p.add_argument("--equity-core-window", type=int, default=175)
    p.add_argument("--sector-sma-window", type=int, default=200)
    p.add_argument("--momentum-lookback", type=int, default=126)
    p.add_argument("--correlation-lookback", type=int, default=63)
    p.add_argument("--tilt-size", type=float, default=0.10)
    p.add_argument("--larger-tilt-size", type=float, default=0.15)
    p.add_argument("--reduce-scale", type=float, default=0.75)
    p.add_argument("--capital", type=float, default=START_CAPITAL)
    p.add_argument("--min-bars", type=int, default=252)
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    return p.parse_args()


def _md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if df.empty:
        return "_No rows._"
    if max_rows is not None:
        df = df.head(max_rows)
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(_fmt_md_value(row[c]) for c in df.columns) + " |")
    return "\n".join(lines)


def _tilt_equity(w: pd.DataFrame, tilt: float) -> pd.DataFrame:
    out = w.copy()
    add = np.minimum(float(tilt), out["BIL"].clip(lower=0.0))
    out["SPY"] = out["SPY"] + add / 2.0
    out["QQQ"] = out["QQQ"] + add / 2.0
    out["BIL"] = 1.0 - out["SPY"] - out["QQQ"]
    return out


def _tilt_active_only(w: pd.DataFrame, tilt: float) -> pd.DataFrame:
    out = w.copy()
    active = (out["SPY"] + out["QQQ"]) > 0.0
    out.loc[active] = _tilt_equity(out.loc[active], tilt)
    return out


def _floor_equity(w: pd.DataFrame, floor: float) -> pd.DataFrame:
    out = w.copy()
    eq = out["SPY"] + out["QQQ"]
    add = (float(floor) - eq).clip(lower=0.0)
    add = np.minimum(add, out["BIL"].clip(lower=0.0))
    out["SPY"] = out["SPY"] + add / 2.0
    out["QQQ"] = out["QQQ"] + add / 2.0
    out["BIL"] = 1.0 - out["SPY"] - out["QQQ"]
    return out


def _reduce_equity(w: pd.DataFrame, scale: float) -> pd.DataFrame:
    out = w.copy()
    out["SPY"] = out["SPY"] * float(scale)
    out["QQQ"] = out["QQQ"] * float(scale)
    out["BIL"] = 1.0 - out["SPY"] - out["QQQ"]
    return out


def _apply_soft_rules(base: pd.DataFrame, panel: pd.DataFrame, tilt: float, larger_tilt: float, reduce_scale: float) -> dict[str, pd.DataFrame]:
    p = panel.reindex(base.index)
    weak_leading = p["fragility_state"].eq("weak_breadth__qqq_leading")
    weak_lagging = p["fragility_state"].eq("weak_breadth__qqq_lagging")
    high_corr = p["corr_bucket"].eq("high_corr")
    low_corr = p["corr_bucket"].eq("low_corr")
    active = (base["SPY"] + base["QQQ"]) > 0.0

    rules = {"BASE_EQUITY_CORE_BIL": base.copy()}

    a = base.copy(); a.loc[weak_leading] = _tilt_equity(a.loc[weak_leading], tilt)
    rules[f"SOFT_WEAK_LEADING_TILT_{int(round(tilt * 100)):02d}"] = a

    b = base.copy(); b.loc[weak_leading] = _tilt_equity(b.loc[weak_leading], larger_tilt)
    rules[f"SOFT_WEAK_LEADING_TILT_{int(round(larger_tilt * 100)):02d}"] = b

    c = base.copy(); c.loc[weak_leading & active] = _tilt_active_only(c.loc[weak_leading & active], larger_tilt)
    rules[f"SOFT_WEAK_LEADING_ACTIVE_ONLY_{int(round(larger_tilt * 100)):02d}"] = c

    d = base.copy(); d.loc[weak_leading] = _floor_equity(d.loc[weak_leading], 0.50)
    rules["SUPPRESS_DERISK_WEAK_LEADING_FLOOR50"] = d

    e = base.copy(); e.loc[high_corr] = _tilt_equity(e.loc[high_corr], tilt)
    rules[f"SOFT_HIGH_CORR_TILT_{int(round(tilt * 100)):02d}"] = e

    f = base.copy(); f.loc[high_corr & active] = _tilt_active_only(f.loc[high_corr & active], larger_tilt)
    rules[f"SOFT_HIGH_CORR_ACTIVE_ONLY_{int(round(larger_tilt * 100)):02d}"] = f

    g = base.copy(); g.loc[weak_lagging] = _reduce_equity(g.loc[weak_lagging], reduce_scale)
    rules[f"SOFT_WEAK_LAGGING_REDUCE_{int(round(reduce_scale * 100)):02d}"] = g

    h = base.copy()
    bullish = weak_leading | high_corr
    caution = weak_lagging | low_corr
    h.loc[bullish] = _tilt_equity(h.loc[bullish], tilt)
    h.loc[caution] = _reduce_equity(base.loc[caution], reduce_scale)
    rules[f"SOFT_COMBINED_TILT{int(round(tilt * 100)):02d}_REDUCE{int(round(reduce_scale * 100)):02d}"] = h

    return rules


def _write_summary_md(path: Path, perf: pd.DataFrame, exposure: pd.DataFrame, events: pd.DataFrame, windows: pd.DataFrame, args: argparse.Namespace) -> None:
    lines = [
        "# Equity Alpha Rule Replay v1 — Soft Overlay Pass",
        "",
        "Research-only replay of smaller exposure tilts on Equity Core SMA175 + BIL.",
        "",
        "## Inputs",
        "",
        "```text",
        f"Tilt size: {args.tilt_size}",
        f"Larger tilt size: {args.larger_tilt_size}",
        f"Reduce scale: {args.reduce_scale}",
        "```",
        "",
        "## Performance Summary",
        "",
        _md_table(perf, max_rows=80),
        "",
        "## Exposure Summary",
        "",
        _md_table(exposure, max_rows=80),
        "",
        "## Rule Event Counts",
        "",
        _md_table(events, max_rows=20),
        "",
        "## Window Performance Summary",
        "",
        _md_table(windows, max_rows=120),
        "",
        "## Guardrail",
        "",
        "```text",
        "Research only. No paper trading, live allocation, broker/execution, runtime, dashboard, crypto allocator, or global allocator changes are approved.",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in ["tilt_size", "larger_tilt_size", "reduce_scale"]:
        value = float(getattr(args, name))
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between 0 and 1, got {value}")

    sectors = _parse_csv_list(args.sectors)
    optional_assets = _parse_csv_list(args.optional_assets)
    loaded_sectors, skipped_sectors = _load_assets(sectors, Path(args.data_dir), args.min_bars, "sector")
    loaded_optional, skipped_optional = _load_assets(optional_assets, Path(args.data_dir), 20, "optional")
    skipped = pd.concat([skipped_sectors, skipped_optional], ignore_index=True) if not skipped_sectors.empty or not skipped_optional.empty else pd.DataFrame()
    if len(loaded_sectors) < 3:
        raise SystemExit(f"Need at least 3 sectors; loaded {len(loaded_sectors)}")

    spy = _load_close(Path(args.spy_data), "SPY")
    qqq = _load_close(Path(args.qqq_data), "QQQ")
    bil = _load_close(Path(args.bil_data), "BIL")
    prices = pd.concat([spy.rename("SPY"), qqq.rename("QQQ"), bil.rename("BIL")], axis=1).dropna()
    panel = _build_signal_panel(spy, qqq, loaded_sectors, loaded_optional, args.sector_sma_window, args.momentum_lookback, args.correlation_lookback).reindex(prices.index)

    base = _base_weights(spy, qqq, bil, args.equity_core_window).reindex(prices.index).dropna()
    prices = prices.reindex(base.index).dropna()
    base = base.reindex(prices.index)
    rules = _apply_soft_rules(base, panel.reindex(base.index), args.tilt_size, args.larger_tilt_size, args.reduce_scale)

    curves = {}
    exposure_rows = []
    history_frames = []
    for name, weights in rules.items():
        curve, _ = _curve_from_weights(prices, weights, args.capital)
        curve.name = name
        curves[name] = curve
        exposure_rows.append(_exposure_summary(weights, name))
        h = weights.copy().reset_index(names="timestamp")
        h.insert(0, "series", name)
        history_frames.append(h)

    curves["PASSIVE_SPY_QQQ_50_50"] = _passive_curve(spy, qqq, args.capital).reindex(prices.index).dropna().rename("PASSIVE_SPY_QQQ_50_50")
    curves["SPY_HODL"] = _asset_curve(spy, args.capital, "SPY_HODL").reindex(prices.index).dropna().rename("SPY_HODL")
    curves["QQQ_HODL"] = _asset_curve(qqq, args.capital, "QQQ_HODL").reindex(prices.index).dropna().rename("QQQ_HODL")

    perf_rows = []
    for name, curve in curves.items():
        clean = curve.dropna()
        perf_rows.append({"series": name, "start": str(clean.index[0]), "end": str(clean.index[-1]), "bars": len(clean), **_perf(clean)})
    perf = pd.DataFrame(perf_rows).sort_values(["calmar", "sharpe", "cagr_pct"], ascending=[False, False, False])
    exposure = pd.DataFrame(exposure_rows).sort_values("series")
    events = _event_counts(panel.reindex(prices.index))
    history = pd.concat(history_frames, ignore_index=True) if history_frames else pd.DataFrame()
    curve_df = pd.concat(curves.values(), axis=1)

    window_rows = []
    for win_name, start, end in WINDOWS:
        for name, curve in curves.items():
            sub = _slice(curve, start, end)
            if len(sub) < 20:
                continue
            window_rows.append({"window": win_name, "series": name, "start": str(sub.index[0]), "end": str(sub.index[-1]), "bars": len(sub), **_perf(sub)})
    window_perf = pd.DataFrame(window_rows).sort_values(["window", "calmar", "sharpe"], ascending=[True, False, False]) if window_rows else pd.DataFrame()

    curve_df.to_csv(out_dir / "equity_curves.csv")
    perf.to_csv(out_dir / "performance_summary.csv", index=False)
    window_perf.to_csv(out_dir / "window_performance_summary.csv", index=False)
    exposure.to_csv(out_dir / "exposure_summary.csv", index=False)
    history.to_csv(out_dir / "rule_exposure_history.csv", index=False)
    events.to_csv(out_dir / "rule_event_counts.csv", index=False)
    skipped.to_csv(out_dir / "skipped_assets.csv", index=False)

    payload = {
        "research_status": "research_only_equity_alpha_rule_replay_v1_soft_overlay",
        "inputs": vars(args),
        "artifacts": {
            "equity_curves": str(out_dir / "equity_curves.csv"),
            "performance_summary": str(out_dir / "performance_summary.csv"),
            "window_performance_summary": str(out_dir / "window_performance_summary.csv"),
            "exposure_summary": str(out_dir / "exposure_summary.csv"),
            "rule_exposure_history": str(out_dir / "rule_exposure_history.csv"),
            "rule_event_counts": str(out_dir / "rule_event_counts.csv"),
            "skipped_assets": str(out_dir / "skipped_assets.csv"),
            "summary_json": str(out_dir / "summary.json"),
            "summary_md": str(out_dir / "summary.md"),
        },
        "decision": {"status": "soft_overlay_replay_only", "not_approved": ["paper_trading", "live_allocation", "broker_change", "runtime_change", "dashboard_change", "global_allocator"]},
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_summary_md(out_dir / "summary.md", perf, exposure, events, window_perf, args)

    with pd.option_context("display.max_columns", None, "display.width", 500, "display.float_format", "{:.4f}".format):
        print("\n=== EQUITY ALPHA RULE REPLAY V1 — SOFT OVERLAYS ===")
        print(f"Loaded sectors: {', '.join(loaded_sectors.keys())}")
        print(f"Loaded optional assets: {', '.join(loaded_optional.keys()) if loaded_optional else 'none'}")
        if not skipped.empty:
            print("\nSkipped assets:")
            print(skipped.to_string(index=False))
        print("\nPerformance Summary:")
        print(perf.to_string(index=False))
        print("\nExposure Summary:")
        print(exposure.to_string(index=False))
        print("\nRule Event Counts:")
        print(events.to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
