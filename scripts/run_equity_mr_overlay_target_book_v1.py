#!/usr/bin/env python
"""Equity MR Overlay Target Book v1.

Research-only target-book generator for the successfully gated
CORE_PLUS_10_MEAN_REVERSION_1D candidate.

Purpose:
    Move the candidate from precomputed curves to deterministic, signal-driven
    daily targets that can later be consumed by the Argus/runtime layer.

Architecture:
    - Research harness only.
    - Imports research modules only; never imports runtime modules.
    - Uses closed-bar daily CSV data only.
    - Fails closed if required data is missing, HMM attribution is unavailable,
      or accounting is not exact within tolerance.

Candidate:
    Base Equity Core: SPY/QQQ SMA175 + BIL risk-off.
    Overlay: Add 10% QQQ when QQQ 1D return <= -2% and QQQ > SMA200.

Outputs:
    artifacts/equity_mr_overlay_target_book_v1/
      equity_mr_overlay_target_book.csv
      equity_mr_overlay_diagnostics.csv
      equity_mr_overlay_readiness_summary.csv
      summary.md
      summary.json
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd


DEFAULT_OUT = "artifacts/equity_mr_overlay_target_book_v1"
START_CAPITAL = 100_000.0
TRADING_DAYS = 252.0
CANDIDATE_NAME = "CORE_PLUS_10_MEAN_REVERSION_1D"
READINESS_STATE = "equity_mr_overlay_target_book_diagnostic_only"
REFERENCE_CAGR_PCT = 14.91
REFERENCE_MAX_DD_PCT = -19.28


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate daily target book for CORE_PLUS_10_MEAN_REVERSION_1D",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--bil-data", default="data/BIL_1D.csv")
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    p.add_argument("--capital", type=float, default=START_CAPITAL)
    p.add_argument("--core-window", type=int, default=175)
    p.add_argument("--overlay-trend-window", type=int, default=200)
    p.add_argument("--overlay-return-threshold", type=float, default=-0.02)
    p.add_argument("--overlay-weight", type=float, default=0.10)
    p.add_argument("--accounting-tolerance", type=float, default=1e-10)
    return p.parse_args()


def _detect_time_col(df: pd.DataFrame) -> str:
    lower = {str(c).lower(): c for c in df.columns}
    for name in ["timestamp", "date", "datetime", "time", "unnamed: 0"]:
        if name in lower:
            return str(lower[name])
    return str(df.columns[0])


def _read_price_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required {label} data file: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Empty required {label} data file: {path}")
    time_col = _detect_time_col(df)
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col]).set_index(time_col).sort_index()
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    df.columns = [str(c).strip().lower() for c in df.columns]
    df = df.rename(columns={"adj close": "close", "adj_close": "close", "adjusted_close": "close"})
    required = ["open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{label} data missing required OHLC columns: {missing}. Got: {list(df.columns)}")
    cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    out = df[cols].copy()
    for col in out.columns:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["open", "high", "low", "close"])
    if out.empty:
        raise ValueError(f"No valid OHLC rows after cleanup for required {label} data: {path}")
    return out


def _load_panel(spy_path: Path, qqq_path: Path, bil_path: Path) -> pd.DataFrame:
    spy = _read_price_csv(spy_path, "SPY").add_prefix("SPY_")
    qqq = _read_price_csv(qqq_path, "QQQ").add_prefix("QQQ_")
    bil = _read_price_csv(bil_path, "BIL").add_prefix("BIL_")
    panel = pd.concat([spy, qqq, bil], axis=1).sort_index().ffill()
    panel = panel.dropna(subset=["SPY_close", "QQQ_close", "BIL_close"])
    if panel.empty:
        raise ValueError("No common valid SPY/QQQ/BIL daily rows after alignment")
    return panel


def _build_base_core(panel: pd.DataFrame, core_window: int) -> pd.DataFrame:
    spy_sma = panel["SPY_close"].rolling(core_window, min_periods=core_window).mean()
    qqq_sma = panel["QQQ_close"].rolling(core_window, min_periods=core_window).mean()
    base = pd.DataFrame(index=panel.index)
    base["base_spy_weight"] = 0.5 * (panel["SPY_close"] > spy_sma).astype(float)
    base["base_qqq_weight"] = 0.5 * (panel["QQQ_close"] > qqq_sma).astype(float)
    base["base_bil_weight"] = 1.0 - base["base_spy_weight"] - base["base_qqq_weight"]
    base["spy_sma175"] = spy_sma
    base["qqq_sma175"] = qqq_sma
    return base


def _apply_mr_overlay(panel: pd.DataFrame, base: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    out = base.copy()
    qqq_sma200 = panel["QQQ_close"].rolling(args.overlay_trend_window, min_periods=args.overlay_trend_window).mean()
    qqq_ret_1d = panel["QQQ_close"].pct_change(fill_method=None)
    signal = (qqq_ret_1d <= args.overlay_return_threshold) & (panel["QQQ_close"] > qqq_sma200)

    out["qqq_sma200"] = qqq_sma200
    out["qqq_ret_1d"] = qqq_ret_1d
    out["signal_active"] = signal.fillna(False).astype(bool)
    out["overlay_requested_weight"] = np.where(out["signal_active"], args.overlay_weight, 0.0)
    out["overlay_funded_from_bil"] = 0.0
    out["overlay_funded_from_core"] = 0.0
    out["final_spy_weight"] = out["base_spy_weight"]
    out["final_qqq_weight"] = out["base_qqq_weight"]
    out["final_bil_weight"] = out["base_bil_weight"]

    for ts in out.index[out["signal_active"]]:
        requested = float(args.overlay_weight)
        bil_available = float(out.loc[ts, "final_bil_weight"])
        funded_from_bil = min(requested, bil_available)
        residual = requested - funded_from_bil

        if funded_from_bil > 0.0:
            out.loc[ts, "final_bil_weight"] -= funded_from_bil
            out.loc[ts, "final_qqq_weight"] += funded_from_bil

        funded_from_core = 0.0
        if residual > 0.0:
            core_spy = float(out.loc[ts, "final_spy_weight"])
            core_qqq = float(out.loc[ts, "final_qqq_weight"])
            risky = core_spy + core_qqq
            if risky > 1e-12:
                funded_from_core = min(residual, risky)
                scale = (risky - funded_from_core) / risky
                out.loc[ts, "final_spy_weight"] = core_spy * scale
                out.loc[ts, "final_qqq_weight"] = core_qqq * scale + funded_from_core
            else:
                raise ValueError(f"Signal active on {ts}, but no BIL or core exposure available to fund overlay")

        out.loc[ts, "overlay_funded_from_bil"] = funded_from_bil
        out.loc[ts, "overlay_funded_from_core"] = funded_from_core

    out["total_accounted_weight"] = out[["final_spy_weight", "final_qqq_weight", "final_bil_weight"]].sum(axis=1)
    out["accounting_error"] = out["total_accounted_weight"] - 1.0
    out["accounting_ok"] = out["accounting_error"].abs() <= args.accounting_tolerance
    out["negative_weight_flag"] = (out[["final_spy_weight", "final_qqq_weight", "final_bil_weight"]] < -args.accounting_tolerance).any(axis=1)
    out["leverage_flag"] = out["total_accounted_weight"] > (1.0 + args.accounting_tolerance)
    return out


def _price_frame(panel: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"SPY": panel["SPY_close"], "QQQ": panel["QQQ_close"], "BIL": panel["BIL_close"]}, index=panel.index)


def _weights_from_diag(diag: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "SPY": diag["final_spy_weight"],
        "QQQ": diag["final_qqq_weight"],
        "BIL": diag["final_bil_weight"],
    }, index=diag.index)


def _curve_from_weights(prices: pd.DataFrame, weights: pd.DataFrame, capital: float) -> tuple[pd.Series, pd.Series]:
    data = prices.reindex(weights.index).dropna()
    w = weights.reindex(data.index).fillna(0.0)
    rets = data[["SPY", "QQQ", "BIL"]].pct_change(fill_method=None).fillna(0.0)
    exec_w = w.shift(1).fillna({"SPY": 0.0, "QQQ": 0.0, "BIL": 1.0})
    port_rets = (exec_w * rets).sum(axis=1)
    curve = capital * (1.0 + port_rets).cumprod()
    return curve, port_rets


def _bars_per_year(index: pd.DatetimeIndex) -> float:
    if len(index) < 3:
        return TRADING_DAYS
    deltas = index.to_series().diff().dropna().dt.total_seconds()
    if deltas.empty:
        return TRADING_DAYS
    med = float(deltas.median())
    if med <= 0 or med >= 20 * 3600:
        return TRADING_DAYS
    return float(365.25 * 24 * 3600 / med)


def _max_time_underwater_days(eq: pd.Series) -> float:
    eq = eq.dropna().astype(float)
    dd = eq / eq.cummax() - 1.0
    start = None
    max_days = 0.0
    for ts, flag in (dd < 0).items():
        if flag and start is None:
            start = ts
        elif not flag and start is not None:
            max_days = max(max_days, (ts - start).total_seconds() / 86400.0)
            start = None
    if start is not None and len(eq):
        max_days = max(max_days, (eq.index[-1] - start).total_seconds() / 86400.0)
    return float(max_days)


def _perf(eq: pd.Series) -> dict[str, float]:
    eq = eq.dropna().astype(float)
    if len(eq) < 2:
        return {k: 0.0 for k in ["total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "calmar", "ann_vol_pct", "max_time_underwater_days"]}
    rets = eq.pct_change(fill_method=None).dropna()
    years = max((eq.index[-1] - eq.index[0]).total_seconds() / (365.25 * 24 * 3600), 1e-9)
    total = float(eq.iloc[-1] / eq.iloc[0] - 1.0)
    cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0)
    dd = eq / eq.cummax() - 1.0
    max_dd = float(dd.min())
    std = float(rets.std(ddof=0))
    bpy = _bars_per_year(eq.index)
    sharpe = float((rets.mean() / std) * math.sqrt(bpy)) if std > 1e-12 else 0.0
    ann_vol = float(std * math.sqrt(bpy)) if std > 0 else 0.0
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else 0.0
    return {
        "total_return_pct": total * 100.0,
        "cagr_pct": cagr * 100.0,
        "max_drawdown_pct": max_dd * 100.0,
        "sharpe": sharpe,
        "calmar": calmar,
        "ann_vol_pct": ann_vol * 100.0,
        "max_time_underwater_days": _max_time_underwater_days(eq),
    }


def _fit_shadow_hmm(panel: pd.DataFrame) -> pd.Series:
    try:
        hmm_module = importlib.import_module("research.regimes.hmm_regime_v1")
    except Exception as exc:
        raise ImportError("Required research.regimes.hmm_regime_v1 module is unavailable; fail-closed per Shadow HMM requirement") from exc

    required_attrs = ["HMMConfig", "fit_hmm_regime", "build_hmm_features"]
    missing_attrs = [name for name in required_attrs if not hasattr(hmm_module, name)]
    if missing_attrs:
        raise AttributeError(f"research.regimes.hmm_regime_v1 missing required attributes: {missing_attrs}")

    HMMConfig = getattr(hmm_module, "HMMConfig")
    fit_hmm_regime = getattr(hmm_module, "fit_hmm_regime")
    build_hmm_features = getattr(hmm_module, "build_hmm_features")

    hmm_input = pd.DataFrame({"close": panel["QQQ_close"].astype(float)}, index=panel.index)
    features = build_hmm_features(hmm_input)
    if features.empty:
        raise ValueError("Shadow HMM feature set is empty after closed-bar feature construction")

    config = HMMConfig()
    _fit_result, probs = fit_hmm_regime(features, config)
    if "hmm_state_label" not in probs.columns:
        raise ValueError(f"HMM probability output missing hmm_state_label. Columns: {list(probs.columns)}")

    regimes = probs["hmm_state_label"].reindex(panel.index).ffill().bfill()
    if regimes.isna().any():
        raise ValueError("Shadow HMM regime output contains missing labels after alignment")
    return regimes.astype(str).rename("shadow_hmm_regime")


def _target_book_from_diag(diag: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ts, row in diag.iterrows():
        for instrument, col in [("SPY", "final_spy_weight"), ("QQQ", "final_qqq_weight"), ("BIL", "final_bil_weight")]:
            rows.append({
                "timestamp": ts,
                "candidate_name": CANDIDATE_NAME,
                "instrument": instrument,
                "target_weight": float(row[col]),
                "target_notional_pct": float(row[col] * 100.0),
                "sleeve": "equity",
                "component": "base_core" if instrument in ["SPY", "BIL"] else "base_core_plus_mr_overlay",
                "source_status": "signal_driven_daily_target_book",
                "research_ready": bool(row["research_ready"]),
                "broker_ready": False,
                "readiness_state": READINESS_STATE,
            })
    return pd.DataFrame(rows)


def _write_summary_md(path: Path, readiness: pd.DataFrame, perf: dict[str, float], signal_days: int, rows: int) -> None:
    lines = [
        "# Equity MR Overlay Target Book v1",
        "",
        f"Candidate: `{CANDIDATE_NAME}`",
        "",
        "## Purpose",
        "",
        "Generate deterministic, closed-bar daily target weights for the successfully gated 10% QQQ mean-reversion overlay candidate.",
        "",
        "## Readiness",
        "",
        readiness.to_markdown(index=False),
        "",
        "## Performance Parity Check",
        "",
        "```text",
        f"Computed CAGR: {perf['cagr_pct']:.4f}% vs reference approximately {REFERENCE_CAGR_PCT:.2f}%",
        f"Computed MaxDD: {perf['max_drawdown_pct']:.4f}% vs reference approximately {REFERENCE_MAX_DD_PCT:.2f}%",
        f"Signal active days: {signal_days}",
        f"Aligned daily rows: {rows}",
        "```",
        "",
        "## Guardrail",
        "",
        "```text",
        "Research only. No runtime imports, no fund target book changes, no crypto target stream changes, no live trading, no broker integration, no paper-broker execution, no order generation, and no fill simulation.",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not 0.0 <= args.overlay_weight <= 1.0:
        raise ValueError("overlay-weight must be between 0 and 1")
    for name in ["core_window", "overlay_trend_window"]:
        if int(getattr(args, name)) < 2:
            raise ValueError(f"{name} must be >= 2")

    panel = _load_panel(Path(args.spy_data), Path(args.qqq_data), Path(args.bil_data))
    base = _build_base_core(panel, args.core_window)
    diag = _apply_mr_overlay(panel, base, args)
    shadow_hmm_regime = _fit_shadow_hmm(panel)
    diag["shadow_hmm_regime"] = shadow_hmm_regime.reindex(diag.index)

    fail_reasons: list[str] = []
    if diag["shadow_hmm_regime"].isna().any():
        fail_reasons.append("missing_shadow_hmm_regime")
    if not bool(diag["accounting_ok"].all()):
        fail_reasons.append("accounting_not_100pct")
    if bool(diag["negative_weight_flag"].any()):
        fail_reasons.append("negative_weight_detected")
    if bool(diag["leverage_flag"].any()):
        fail_reasons.append("leverage_detected")
    if int(diag["signal_active"].sum()) <= 0:
        fail_reasons.append("no_signal_days")

    research_ready = len(fail_reasons) == 0
    diag["research_ready"] = research_ready
    diag["broker_ready"] = False
    diag["readiness_state"] = READINESS_STATE
    diag["candidate_name"] = CANDIDATE_NAME

    prices = _price_frame(panel)
    weights = _weights_from_diag(diag)
    curve, rets = _curve_from_weights(prices, weights, args.capital)
    perf = _perf(curve)
    signal_days = int(diag["signal_active"].sum())
    accounting_ok_pct = float(diag["accounting_ok"].mean() * 100.0)

    readiness = pd.DataFrame([
        {
            "candidate_name": CANDIDATE_NAME,
            "research_ready": research_ready,
            "broker_ready": False,
            "promotion_eligible": False,
            "readiness_state": READINESS_STATE,
            "accounting_ok_pct": accounting_ok_pct,
            "signal_active_days": signal_days,
            "rows": int(len(diag)),
            "fail_reasons": ",".join(fail_reasons) if fail_reasons else "none",
        }
    ])

    if not research_ready:
        diag.reset_index(names="timestamp").to_csv(out_dir / "equity_mr_overlay_diagnostics.csv", index=False)
        readiness.to_csv(out_dir / "equity_mr_overlay_readiness_summary.csv", index=False)
        raise SystemExit("Fail-closed readiness failure: " + ", ".join(fail_reasons))

    target_book = _target_book_from_diag(diag)
    diag_out = diag.reset_index(names="timestamp")
    diag_out["equity_curve"] = curve.reindex(diag.index).to_numpy()
    diag_out["daily_return"] = rets.reindex(diag.index).to_numpy()

    target_book.to_csv(out_dir / "equity_mr_overlay_target_book.csv", index=False)
    diag_out.to_csv(out_dir / "equity_mr_overlay_diagnostics.csv", index=False)
    readiness.to_csv(out_dir / "equity_mr_overlay_readiness_summary.csv", index=False)

    payload: dict[str, Any] = {
        "candidate_name": CANDIDATE_NAME,
        "research_status": "signal_driven_daily_target_book",
        "readiness_state": READINESS_STATE,
        "research_ready": research_ready,
        "broker_ready": False,
        "promotion_eligible": False,
        "inputs": vars(args),
        "performance_parity_check": {
            "computed_cagr_pct": perf["cagr_pct"],
            "reference_cagr_pct": REFERENCE_CAGR_PCT,
            "computed_max_drawdown_pct": perf["max_drawdown_pct"],
            "reference_max_drawdown_pct": REFERENCE_MAX_DD_PCT,
            "computed_total_return_pct": perf["total_return_pct"],
            "computed_sharpe": perf["sharpe"],
            "computed_calmar": perf["calmar"],
        },
        "outputs": {
            "target_book": str(out_dir / "equity_mr_overlay_target_book.csv"),
            "diagnostics": str(out_dir / "equity_mr_overlay_diagnostics.csv"),
            "readiness_summary": str(out_dir / "equity_mr_overlay_readiness_summary.csv"),
            "summary_md": str(out_dir / "summary.md"),
            "summary_json": str(out_dir / "summary.json"),
        },
        "guardrails": {
            "imports_runtime": False,
            "closed_bar_only": True,
            "fail_closed": True,
            "generates_orders": False,
            "broker_integration": False,
            "paper_broker_execution": False,
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_summary_md(out_dir / "summary.md", readiness, perf, signal_days, len(diag))

    print("\n=== EQUITY MR OVERLAY TARGET BOOK V1 ===")
    print(readiness.to_string(index=False))
    print("\nPerformance parity check:")
    print(f"Computed CAGR: {perf['cagr_pct']:.4f}% vs reference approximately {REFERENCE_CAGR_PCT:.2f}%")
    print(f"Computed MaxDD: {perf['max_drawdown_pct']:.4f}% vs reference approximately {REFERENCE_MAX_DD_PCT:.2f}%")
    print(f"Computed Total Return: {perf['total_return_pct']:.4f}%")
    print(f"Computed Sharpe: {perf['sharpe']:.4f}")
    print(f"Computed Calmar: {perf['calmar']:.4f}")
    print(f"Signal active days: {signal_days}")
    print(f"Artifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
