#!/usr/bin/env python
"""Fund Target Book v3.

Research-only target-book integration for Itera's current fund concept.

This script combines:
  - daily crypto proxy targets from Crypto Target Stream v1
  - daily equity targets from Fund Paper Readiness v2
  - static fund sleeve weights

into a unified daily fund-level instrument target book.

No live trading, broker-paper execution, order generation, fills, runtime
deployment, dashboard integration, or dynamic allocation decisions are made.
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

import numpy as np
import pandas as pd


DEFAULT_CRYPTO_TARGETS = "artifacts/crypto_target_stream_v1/crypto_target_exposure_daily.csv"
DEFAULT_EQUITY_TARGETS = "artifacts/fund_paper_readiness_v2/equity_target_exposure.csv"
DEFAULT_OUT = "artifacts/fund_target_book_v3"
DEFAULT_TARGET_WEIGHTS = "50/50"

CRYPTO_WEIGHT_COLUMNS = [
    "btc_1h_target_weight",
    "btc_4h_target_weight",
    "eth_1h_target_weight",
    "eth_4h_target_weight",
    "crypto_cash_or_risk_off_weight",
]
EQUITY_WEIGHT_COLUMNS = [
    "within_equity_spy_weight",
    "within_equity_qqq_weight",
    "within_equity_bil_weight",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build a unified daily fund-level instrument target book",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--crypto-targets", default=DEFAULT_CRYPTO_TARGETS)
    p.add_argument("--equity-targets", default=DEFAULT_EQUITY_TARGETS)
    p.add_argument("--target-weights", default=DEFAULT_TARGET_WEIGHTS, help="Static sleeve target, e.g. 50/50 or 60/40.")
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    p.add_argument("--accounting-tolerance", type=float, default=1e-6)
    return p.parse_args()


def _detect_time_col(df: pd.DataFrame) -> str:
    lower = {str(c).lower(): c for c in df.columns}
    for name in ["timestamp", "date", "datetime", "time", "unnamed: 0"]:
        if name in lower:
            return str(lower[name])
    return str(df.columns[0])


def _read_indexed(path: Path, label: str) -> pd.DataFrame:
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


def _parse_weights(raw: str) -> tuple[float, float]:
    piece = str(raw).strip()
    if "/" in piece:
        left, right = piece.split("/", 1)
        crypto_w = float(left.strip()) / 100.0
        equity_w = float(right.strip()) / 100.0
    elif ":" in piece:
        left, right = piece.split(":", 1)
        crypto_w = float(left.strip())
        equity_w = float(right.strip())
    else:
        raise ValueError(f"Invalid target weight format '{raw}', expected 50/50 or 0.5:0.5")
    total = crypto_w + equity_w
    if total <= 0:
        raise ValueError(f"Invalid non-positive target weights: {raw}")
    return crypto_w / total, equity_w / total


def _require_columns(df: pd.DataFrame, cols: list[str], label: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}. Available={list(df.columns)}")


def _bool_series(df: pd.DataFrame, col: str, default: bool) -> pd.Series:
    if col not in df.columns:
        return pd.Series(default, index=df.index)
    raw = df[col]
    if raw.dtype == bool:
        return raw.fillna(default)
    return raw.astype(str).str.lower().map({"true": True, "false": False, "1": True, "0": False}).fillna(default).astype(bool)


def _align_inputs(crypto: pd.DataFrame, equity: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    crypto_dates = pd.Index(pd.to_datetime(crypto.index.normalize()), name="timestamp")
    equity_dates = pd.Index(pd.to_datetime(equity.index.normalize()), name="timestamp")
    crypto_daily = crypto.copy()
    equity_daily = equity.copy()
    crypto_daily.index = crypto_dates
    equity_daily.index = equity_dates
    crypto_daily = crypto_daily.groupby(level=0).last()
    equity_daily = equity_daily.groupby(level=0).last()

    common = crypto_daily.index.intersection(equity_daily.index).sort_values()
    aligned_crypto = crypto_daily.reindex(common)
    aligned_equity = equity_daily.reindex(common)
    audit = pd.DataFrame(
        [
            {"input": "crypto", "rows": len(crypto_daily), "start": str(crypto_daily.index.min()), "end": str(crypto_daily.index.max()), "common_rows": len(common)},
            {"input": "equity", "rows": len(equity_daily), "start": str(equity_daily.index.min()), "end": str(equity_daily.index.max()), "common_rows": len(common)},
            {"input": "aligned", "rows": len(common), "start": str(common.min()) if len(common) else None, "end": str(common.max()) if len(common) else None, "common_rows": len(common)},
        ]
    )
    if len(common) == 0:
        raise ValueError("No overlapping daily timestamps between crypto and equity targets")
    return aligned_crypto, aligned_equity, audit


def _build_book(crypto: pd.DataFrame, equity: pd.DataFrame, crypto_w: float, equity_w: float, tol: float) -> pd.DataFrame:
    _require_columns(crypto, CRYPTO_WEIGHT_COLUMNS, "crypto targets")
    _require_columns(equity, EQUITY_WEIGHT_COLUMNS, "equity targets")

    book = pd.DataFrame(index=crypto.index)
    book["fund_crypto_sleeve_weight"] = crypto_w
    book["fund_equity_sleeve_weight"] = equity_w

    book["total_fund_btc_1h_weight"] = crypto_w * pd.to_numeric(crypto["btc_1h_target_weight"], errors="coerce").fillna(0.0)
    book["total_fund_btc_4h_weight"] = crypto_w * pd.to_numeric(crypto["btc_4h_target_weight"], errors="coerce").fillna(0.0)
    book["total_fund_eth_1h_weight"] = crypto_w * pd.to_numeric(crypto["eth_1h_target_weight"], errors="coerce").fillna(0.0)
    book["total_fund_eth_4h_weight"] = crypto_w * pd.to_numeric(crypto["eth_4h_target_weight"], errors="coerce").fillna(0.0)
    book["total_fund_crypto_cash_or_risk_off_weight"] = crypto_w * pd.to_numeric(crypto["crypto_cash_or_risk_off_weight"], errors="coerce").fillna(0.0)

    book["total_fund_spy_weight"] = equity_w * pd.to_numeric(equity["within_equity_spy_weight"], errors="coerce").fillna(0.0)
    book["total_fund_qqq_weight"] = equity_w * pd.to_numeric(equity["within_equity_qqq_weight"], errors="coerce").fillna(0.0)
    book["total_fund_bil_weight"] = equity_w * pd.to_numeric(equity["within_equity_bil_weight"], errors="coerce").fillna(0.0)

    instrument_cols = [
        "total_fund_btc_1h_weight",
        "total_fund_btc_4h_weight",
        "total_fund_eth_1h_weight",
        "total_fund_eth_4h_weight",
        "total_fund_crypto_cash_or_risk_off_weight",
        "total_fund_spy_weight",
        "total_fund_qqq_weight",
        "total_fund_bil_weight",
    ]
    book["total_accounted_weight"] = book[instrument_cols].sum(axis=1)
    book["accounting_error"] = book["total_accounted_weight"] - 1.0
    book["accounting_ok"] = book["accounting_error"].abs() <= tol

    book["crypto_source_status"] = crypto.get("source_status", pd.Series("missing", index=crypto.index)).astype(str)
    book["crypto_broker_ready"] = _bool_series(crypto, "broker_ready", False)
    book["crypto_risk_state"] = crypto.get("crypto_risk_state", pd.Series("UNKNOWN", index=crypto.index)).astype(str)
    book["crypto_cadence_export"] = crypto.get("cadence_export", pd.Series("unknown", index=crypto.index)).astype(str)

    book["equity_source_status"] = "target_ready_research"
    book["equity_broker_ready"] = False
    book["equity_risk_state"] = equity.get("equity_risk_state", pd.Series("UNKNOWN", index=equity.index)).astype(str)

    book["fund_research_ready"] = book["accounting_ok"] & book["crypto_source_status"].notna() & book["equity_risk_state"].notna()
    book["fund_broker_ready"] = book["fund_research_ready"] & book["crypto_broker_ready"] & book["equity_broker_ready"]

    def readiness(row: pd.Series) -> str:
        if not bool(row["accounting_ok"]):
            return "invalid_accounting"
        if bool(row["fund_broker_ready"]):
            return "broker_ready"
        if str(row["crypto_source_status"]) == "proxy_from_component_nav":
            return "research_ready_crypto_proxy"
        return "partial"

    book["readiness_state"] = book.apply(readiness, axis=1)
    book["readiness_reason"] = np.where(
        book["readiness_state"].eq("research_ready_crypto_proxy"),
        "Unified daily target book is research-ready, but broker_ready=false because crypto stream is proxy_from_component_nav and equity broker mapping is not approved.",
        "Readiness depends on accounting, crypto target status, and broker mapping approvals.",
    )
    return book


def _instrument_weights(book: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "total_fund_btc_1h_weight",
        "total_fund_btc_4h_weight",
        "total_fund_eth_1h_weight",
        "total_fund_eth_4h_weight",
        "total_fund_crypto_cash_or_risk_off_weight",
        "total_fund_spy_weight",
        "total_fund_qqq_weight",
        "total_fund_bil_weight",
        "total_accounted_weight",
        "accounting_error",
        "accounting_ok",
        "fund_research_ready",
        "fund_broker_ready",
        "readiness_state",
    ]
    return book[cols].copy()


def _summary(book: pd.DataFrame, alignment: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        {"metric": "rows", "value": int(len(book))},
        {"metric": "start", "value": str(book.index[0]) if len(book) else "n/a"},
        {"metric": "end", "value": str(book.index[-1]) if len(book) else "n/a"},
        {"metric": "fund_research_ready_pct", "value": float(book["fund_research_ready"].mean() * 100.0)},
        {"metric": "fund_broker_ready_pct", "value": float(book["fund_broker_ready"].mean() * 100.0)},
        {"metric": "accounting_ok_pct", "value": float(book["accounting_ok"].mean() * 100.0)},
        {"metric": "max_abs_accounting_error", "value": float(book["accounting_error"].abs().max())},
        {"metric": "avg_total_accounted_weight_pct", "value": float(book["total_accounted_weight"].mean() * 100.0)},
    ]
    for col in [c for c in book.columns if c.startswith("total_fund_") and c.endswith("_weight")]:
        rows.append({"metric": f"avg_{col}_pct", "value": float(book[col].mean() * 100.0)})
    for state, pct in book["readiness_state"].value_counts(normalize=True).to_dict().items():
        rows.append({"metric": f"time_in_{state}_pct", "value": float(pct * 100.0)})
    for state, pct in book["crypto_source_status"].value_counts(normalize=True).to_dict().items():
        rows.append({"metric": f"crypto_source_status_{state}_pct", "value": float(pct * 100.0)})
    rows.append({"metric": "alignment_common_rows", "value": int(alignment[alignment["input"] == "aligned"]["common_rows"].iloc[0])})
    return pd.DataFrame(rows)


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
                vals.append(f"{value:.6f}")
            else:
                vals.append(str(value).replace("|", "\\|").replace("\n", " "))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def _write_summary(path: Path, args: argparse.Namespace, summary: pd.DataFrame, alignment: pd.DataFrame, book: pd.DataFrame) -> None:
    lines = [
        "# Fund Target Book v3",
        "",
        "Research-only unified daily fund target book.",
        "",
        "## Inputs",
        "",
        "```text",
        f"Crypto targets: {args.crypto_targets}",
        f"Equity targets: {args.equity_targets}",
        f"Target weights: {args.target_weights}",
        f"Accounting tolerance: {args.accounting_tolerance}",
        "```",
        "",
        "## Readiness Summary",
        "",
        _md_table(summary, max_rows=80),
        "",
        "## Input Alignment Audit",
        "",
        _md_table(alignment, max_rows=10),
        "",
        "## Latest Unified Target Row",
        "",
        _md_table(book.tail(1).reset_index(names="timestamp"), max_rows=1),
        "",
        "## Guardrail",
        "",
        "```text",
        "Research only. No live trading, broker-paper execution, order generation, fills, runtime deployment, dashboard integration, or dynamic allocator changes are approved.",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.accounting_tolerance < 0:
        raise ValueError("accounting-tolerance must be non-negative")
    crypto_w, equity_w = _parse_weights(args.target_weights)

    crypto = _read_indexed(Path(args.crypto_targets), "crypto targets")
    equity = _read_indexed(Path(args.equity_targets), "equity targets")
    aligned_crypto, aligned_equity, alignment = _align_inputs(crypto, equity)
    book = _build_book(aligned_crypto, aligned_equity, crypto_w, equity_w, args.accounting_tolerance)
    instrument_weights = _instrument_weights(book)
    summary = _summary(book, alignment)

    book.to_csv(out_dir / "fund_daily_target_book.csv")
    instrument_weights.to_csv(out_dir / "fund_instrument_target_weights.csv")
    summary.to_csv(out_dir / "fund_target_readiness_summary.csv", index=False)
    alignment.to_csv(out_dir / "input_alignment_audit.csv", index=False)

    payload = {
        "research_status": "research_only_fund_target_book_v3",
        "inputs": {
            "crypto_targets": args.crypto_targets,
            "equity_targets": args.equity_targets,
            "target_weights": args.target_weights,
            "accounting_tolerance": args.accounting_tolerance,
        },
        "outputs": {
            "fund_daily_target_book": str(out_dir / "fund_daily_target_book.csv"),
            "fund_instrument_target_weights": str(out_dir / "fund_instrument_target_weights.csv"),
            "fund_target_readiness_summary": str(out_dir / "fund_target_readiness_summary.csv"),
            "input_alignment_audit": str(out_dir / "input_alignment_audit.csv"),
            "summary_md": str(out_dir / "summary.md"),
            "summary_json": str(out_dir / "summary.json"),
        },
        "decision": {"status": "research_ready_not_broker_ready", "not_approved": ["live_trading", "broker_integration", "paper_broker_execution", "order_generation", "fills", "runtime_deployment", "dashboard_integration", "dynamic_allocator"]},
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_summary(out_dir / "summary.md", args, summary, alignment, book)

    with pd.option_context("display.max_columns", None, "display.width", 520, "display.float_format", "{:.6f}".format):
        print("\n=== FUND TARGET BOOK V3 ===")
        print(f"Target weights: crypto={crypto_w:.2%}, equity={equity_w:.2%}")
        print("\nInput Alignment Audit:")
        print(alignment.to_string(index=False))
        print("\nReadiness Summary:")
        print(summary.to_string(index=False))
        print("\nLatest Unified Target Row:")
        print(book.tail(1).reset_index(names="timestamp").to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
