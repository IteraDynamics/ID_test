#!/usr/bin/env python
"""Fund Paper Readiness v2 — signal-driven target book.

Research-only target-generation readiness for Itera's promoted two-sleeve fund
view. This script generates a daily Equity Core target stream from SPY/QQQ/BIL
data, audits the crypto sleeve input for target-readiness, and builds a static
50/50 fund-level target book.

No broker orders, live trading, paper-broker execution, runtime integration,
dashboard integration, or dynamic allocation decisions are made.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd


DEFAULT_CRYPTO_REFERENCE = "artifacts/fund_side_by_side_composite_v1_tilted_4s/equity_curves.csv"
DEFAULT_OUT = "artifacts/fund_paper_readiness_v2"
DEFAULT_TARGET_WEIGHTS = "50/50"

TARGET_HINTS = [
    "target",
    "weight",
    "exposure",
    "allocation",
    "desired_exposure",
    "desired_exposure_frac",
]
CURVE_HINTS = [
    "curve",
    "nav",
    "portfolio",
    "sleeve",
    "equity",
    "hodl",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate Fund Paper Readiness v2 daily sleeve target book",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--bil-data", default="data/BIL_1D.csv")
    p.add_argument("--crypto-reference", default=DEFAULT_CRYPTO_REFERENCE)
    p.add_argument("--target-weights", default=DEFAULT_TARGET_WEIGHTS, help="Static fund sleeve target, e.g. 50/50 or 60/40.")
    p.add_argument("--sma-window", type=int, default=175)
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    return p.parse_args()


def _detect_time_col(df: pd.DataFrame) -> str:
    lower = {str(c).lower(): c for c in df.columns}
    for name in ["timestamp", "date", "datetime", "time", "unnamed: 0"]:
        if name in lower:
            return str(lower[name])
    return str(df.columns[0])


def _read_csv_indexed(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Empty {label}: {path}")
    time_col = _detect_time_col(df)
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col]).set_index(time_col).sort_index()
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    return df


def _load_close(path: Path, label: str) -> pd.Series:
    df = _read_csv_indexed(path, label)
    lower = {str(c).lower(): c for c in df.columns}
    if "close" not in lower:
        raise ValueError(f"{label} data missing close column; columns={list(df.columns)}")
    return pd.to_numeric(df[lower["close"]], errors="coerce").dropna().rename(label.upper())


def _parse_weights(raw: str) -> tuple[float, float]:
    piece = str(raw).strip()
    if "/" in piece:
        left, right = piece.split("/", 1)
        cw = float(left.strip()) / 100.0
        ew = float(right.strip()) / 100.0
    elif ":" in piece:
        left, right = piece.split(":", 1)
        cw = float(left.strip())
        ew = float(right.strip())
    else:
        raise ValueError(f"Invalid target weight format '{raw}', expected 50/50 or 0.5:0.5")
    total = cw + ew
    if total <= 0:
        raise ValueError(f"Invalid non-positive target weights: {raw}")
    return cw / total, ew / total


def _build_equity_targets(spy: pd.Series, qqq: pd.Series, bil: pd.Series, sma_window: int) -> pd.DataFrame:
    # Compute SMA state on full SPY/QQQ history first, then intersect with BIL.
    risky = pd.concat([spy.rename("SPY"), qqq.rename("QQQ")], axis=1).dropna().sort_index()
    spy_sma = risky["SPY"].rolling(sma_window, min_periods=sma_window).mean()
    qqq_sma = risky["QQQ"].rolling(sma_window, min_periods=sma_window).mean()

    targets = pd.DataFrame(index=risky.index)
    targets["spy_close"] = risky["SPY"]
    targets["qqq_close"] = risky["QQQ"]
    targets["spy_sma"] = spy_sma
    targets["qqq_sma"] = qqq_sma
    targets["spy_above_sma"] = risky["SPY"] > spy_sma
    targets["qqq_above_sma"] = risky["QQQ"] > qqq_sma
    targets["within_equity_spy_weight"] = 0.5 * targets["spy_above_sma"].astype(float)
    targets["within_equity_qqq_weight"] = 0.5 * targets["qqq_above_sma"].astype(float)
    targets["within_equity_bil_weight"] = 1.0 - targets["within_equity_spy_weight"] - targets["within_equity_qqq_weight"]
    targets["equity_sleeve_gross_risk_exposure"] = targets["within_equity_spy_weight"] + targets["within_equity_qqq_weight"]

    def reason(row: pd.Series) -> str:
        if bool(row["spy_above_sma"]) and bool(row["qqq_above_sma"]):
            return "SPY_QQQ_RISK_ON"
        if bool(row["spy_above_sma"]) and not bool(row["qqq_above_sma"]):
            return "SPY_ON_QQQ_OFF"
        if not bool(row["spy_above_sma"]) and bool(row["qqq_above_sma"]):
            return "SPY_OFF_QQQ_ON"
        return "SPY_QQQ_RISK_OFF"

    targets["equity_risk_state"] = targets.apply(reason, axis=1)
    targets["bil_available"] = bil.reindex(targets.index).notna()
    targets = targets.reindex(pd.concat([risky, bil.rename("BIL")], axis=1).dropna().index)
    return targets


def _audit_crypto_reference(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not path.exists():
        audit = {
            "path": str(path),
            "status": "missing",
            "rows": 0,
            "columns": [],
            "target_like_columns": [],
            "curve_like_columns": [],
            "start": None,
            "end": None,
            "readiness_gap": "Crypto reference file is missing. Need canonical crypto daily target exposure stream.",
        }
        return pd.DataFrame([audit]), audit

    df = _read_csv_indexed(path, "crypto reference")
    cols = [str(c) for c in df.columns]
    lower_cols = {c: c.lower() for c in cols}
    target_like = [c for c, lc in lower_cols.items() if any(h in lc for h in TARGET_HINTS)]
    curve_like = [c for c, lc in lower_cols.items() if any(h in lc for h in CURVE_HINTS)]

    if target_like:
        status = "target_ready"
        gap = "Crypto reference contains target-like columns. Validate semantics before broker-paper execution."
    elif curve_like:
        status = "curve_only"
        gap = "Crypto reference appears to contain curves/NAVs but no canonical daily target exposure stream."
    else:
        status = "invalid"
        gap = "Crypto reference exists but no target-like or curve-like columns were detected."

    audit = {
        "path": str(path),
        "status": status,
        "rows": int(len(df)),
        "columns": cols,
        "target_like_columns": target_like,
        "curve_like_columns": curve_like,
        "start": str(df.index[0]) if len(df) else None,
        "end": str(df.index[-1]) if len(df) else None,
        "readiness_gap": gap,
    }
    return pd.DataFrame([audit]), audit


def _build_fund_target_book(equity_targets: pd.DataFrame, crypto_audit: dict[str, Any], crypto_weight: float, equity_weight: float) -> pd.DataFrame:
    book = pd.DataFrame(index=equity_targets.index)
    book["fund_crypto_target_weight"] = crypto_weight
    book["fund_equity_target_weight"] = equity_weight
    book["within_equity_spy_weight"] = equity_targets["within_equity_spy_weight"]
    book["within_equity_qqq_weight"] = equity_targets["within_equity_qqq_weight"]
    book["within_equity_bil_weight"] = equity_targets["within_equity_bil_weight"]
    book["total_fund_spy_weight"] = equity_weight * book["within_equity_spy_weight"]
    book["total_fund_qqq_weight"] = equity_weight * book["within_equity_qqq_weight"]
    book["total_fund_bil_weight"] = equity_weight * book["within_equity_bil_weight"]
    book["total_fund_crypto_sleeve_weight"] = crypto_weight
    book["total_accounted_weight_ex_crypto_internal"] = (
        book["total_fund_crypto_sleeve_weight"]
        + book["total_fund_spy_weight"]
        + book["total_fund_qqq_weight"]
        + book["total_fund_bil_weight"]
    )
    book["equity_sleeve_gross_risk_exposure"] = equity_targets["equity_sleeve_gross_risk_exposure"]
    book["fund_equity_gross_risk_exposure"] = equity_weight * book["equity_sleeve_gross_risk_exposure"]
    book["equity_risk_state"] = equity_targets["equity_risk_state"]
    book["crypto_target_status"] = str(crypto_audit.get("status", "missing"))
    book["readiness_state"] = "complete" if book["crypto_target_status"].eq("target_ready").all() else "partial"
    return book


def _target_summary(equity_targets: pd.DataFrame, fund_book: pd.DataFrame, crypto_audit: dict[str, Any]) -> pd.DataFrame:
    state_counts = equity_targets["equity_risk_state"].value_counts(normalize=True).to_dict()
    rows = [
        {"metric": "rows", "value": float(len(fund_book))},
        {"metric": "start", "value": str(fund_book.index[0]) if len(fund_book) else "n/a"},
        {"metric": "end", "value": str(fund_book.index[-1]) if len(fund_book) else "n/a"},
        {"metric": "avg_within_equity_spy_weight_pct", "value": float(equity_targets["within_equity_spy_weight"].mean() * 100.0)},
        {"metric": "avg_within_equity_qqq_weight_pct", "value": float(equity_targets["within_equity_qqq_weight"].mean() * 100.0)},
        {"metric": "avg_within_equity_bil_weight_pct", "value": float(equity_targets["within_equity_bil_weight"].mean() * 100.0)},
        {"metric": "avg_equity_sleeve_gross_risk_exposure_pct", "value": float(equity_targets["equity_sleeve_gross_risk_exposure"].mean() * 100.0)},
        {"metric": "avg_total_fund_spy_weight_pct", "value": float(fund_book["total_fund_spy_weight"].mean() * 100.0)},
        {"metric": "avg_total_fund_qqq_weight_pct", "value": float(fund_book["total_fund_qqq_weight"].mean() * 100.0)},
        {"metric": "avg_total_fund_bil_weight_pct", "value": float(fund_book["total_fund_bil_weight"].mean() * 100.0)},
        {"metric": "crypto_target_status", "value": str(crypto_audit.get("status"))},
        {"metric": "readiness_state", "value": "complete" if str(crypto_audit.get("status")) == "target_ready" else "partial"},
    ]
    for state, pct in state_counts.items():
        rows.append({"metric": f"time_in_{state}_pct", "value": float(pct * 100.0)})
    return pd.DataFrame(rows)


def _write_gaps(path: Path, crypto_audit: dict[str, Any]) -> None:
    lines = [
        "# Fund Paper Readiness v2 — Readiness Gaps",
        "",
        "## Crypto Target Stream",
        "",
        "```text",
        f"Status: {crypto_audit.get('status')}",
        f"Path: {crypto_audit.get('path')}",
        f"Rows: {crypto_audit.get('rows')}",
        f"Target-like columns: {crypto_audit.get('target_like_columns')}",
        f"Curve-like columns: {crypto_audit.get('curve_like_columns')}",
        "```",
        "",
        "## Gap",
        "",
        str(crypto_audit.get("readiness_gap")),
        "",
        "## Required Before Broker-Paper Execution",
        "",
        "```text",
        "A canonical crypto daily target exposure stream with timestamped desired exposure/weights.",
        "The stream should be generated by promoted crypto strategy logic or an approved target artifact, not inferred from realized equity curves.",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if df.empty:
        return "_No rows._"
    if max_rows is not None:
        df = df.head(max_rows)
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        vals = []
        for c in df.columns:
            value = row[c]
            if isinstance(value, float):
                vals.append(f"{value:.4f}")
            else:
                vals.append(str(value).replace("|", "\\|").replace("\n", " "))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def _write_summary(path: Path, args: argparse.Namespace, target_summary: pd.DataFrame, crypto_audit_df: pd.DataFrame, fund_book: pd.DataFrame) -> None:
    lines = [
        "# Fund Paper Readiness v2",
        "",
        "Research-only signal-driven sleeve target generation checkpoint.",
        "",
        "## Inputs",
        "",
        "```text",
        f"SPY data: {args.spy_data}",
        f"QQQ data: {args.qqq_data}",
        f"BIL data: {args.bil_data}",
        f"Crypto reference: {args.crypto_reference}",
        f"Target weights: {args.target_weights}",
        f"SMA window: {args.sma_window}",
        "```",
        "",
        "## Target Summary",
        "",
        _md_table(target_summary, max_rows=40),
        "",
        "## Crypto Target Input Audit",
        "",
        _md_table(crypto_audit_df, max_rows=5),
        "",
        "## Latest Fund Target Book Row",
        "",
        _md_table(fund_book.tail(1).reset_index(names="timestamp"), max_rows=1),
        "",
        "## Guardrail",
        "",
        "```text",
        "Research only. No broker orders, paper-broker execution, live trading, runtime deployment, dashboard integration, or dynamic allocator changes are approved.",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.sma_window <= 1:
        raise ValueError("sma-window must be > 1")

    crypto_weight, equity_weight = _parse_weights(args.target_weights)
    spy = _load_close(Path(args.spy_data), "SPY")
    qqq = _load_close(Path(args.qqq_data), "QQQ")
    bil = _load_close(Path(args.bil_data), "BIL")

    equity_targets = _build_equity_targets(spy, qqq, bil, args.sma_window)
    crypto_audit_df, crypto_audit = _audit_crypto_reference(Path(args.crypto_reference))
    fund_book = _build_fund_target_book(equity_targets, crypto_audit, crypto_weight, equity_weight)
    target_summary = _target_summary(equity_targets, fund_book, crypto_audit)

    equity_targets.to_csv(out_dir / "equity_target_exposure.csv")
    crypto_audit_df.to_csv(out_dir / "crypto_target_input_audit.csv", index=False)
    fund_book.to_csv(out_dir / "fund_target_book.csv")
    target_summary.to_csv(out_dir / "sleeve_target_summary.csv", index=False)
    _write_gaps(out_dir / "readiness_gaps.md", crypto_audit)

    payload = {
        "research_status": "research_only_fund_paper_readiness_v2_target_generation",
        "inputs": {
            "spy_data": args.spy_data,
            "qqq_data": args.qqq_data,
            "bil_data": args.bil_data,
            "crypto_reference": args.crypto_reference,
            "target_weights": args.target_weights,
            "sma_window": args.sma_window,
        },
        "outputs": {
            "equity_target_exposure": str(out_dir / "equity_target_exposure.csv"),
            "crypto_target_input_audit": str(out_dir / "crypto_target_input_audit.csv"),
            "fund_target_book": str(out_dir / "fund_target_book.csv"),
            "sleeve_target_summary": str(out_dir / "sleeve_target_summary.csv"),
            "readiness_gaps": str(out_dir / "readiness_gaps.md"),
            "summary_json": str(out_dir / "summary.json"),
            "summary_md": str(out_dir / "summary.md"),
        },
        "decision": {"status": "target_generation_readiness_only", "not_approved": ["live_trading", "broker_integration", "paper_broker_execution", "runtime_deployment", "dashboard_integration", "dynamic_allocator"]},
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_summary(out_dir / "summary.md", args, target_summary, crypto_audit_df, fund_book)

    with pd.option_context("display.max_columns", None, "display.width", 420, "display.float_format", "{:.4f}".format):
        print("\n=== FUND PAPER READINESS V2 — TARGET BOOK ===")
        print(f"Target weights: crypto={crypto_weight:.2%}, equity={equity_weight:.2%}")
        print(f"Equity target rows: {len(equity_targets)}")
        print("\nSleeve Target Summary:")
        print(target_summary.to_string(index=False))
        print("\nCrypto Target Input Audit:")
        print(crypto_audit_df.to_string(index=False))
        print("\nLatest Fund Target Book Row:")
        print(fund_book.tail(1).reset_index(names="timestamp").to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
