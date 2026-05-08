#!/usr/bin/env python
"""Crypto Target Stream v1.

Research-only crypto target-stream readiness tool.

This script audits crypto sleeve artifacts and attempts to build a crypto target
exposure stream for the promoted Crypto Risk Budget v2 candidate:

    hybrid_eth4h_cap75_only

Default candidate mapping:

    BTC_1H: ecap75
    BTC_4H: ecap75
    ETH_1H: ecap75
    ETH_4H: cap75

If true target/exposure columns exist, the artifact is marked target-ready. If
only component NAV/account columns exist, a clearly labeled component-NAV proxy
stream is emitted with broker_ready=false.

No live trading, broker-paper execution, runtime deployment, dashboard
integration, or dynamic allocation decisions are made.
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


DEFAULT_PRIMARY = "artifacts/fund_tilted_cal_4s_2019-03-08_2025-12-31/equity_curves.csv"
DEFAULT_FALLBACK = "artifacts/fund_side_by_side_composite_v1_tilted_4s/equity_curves.csv"
DEFAULT_OUT = "artifacts/crypto_target_stream_v1"
DEFAULT_CANDIDATE = "hybrid_eth4h_cap75_only"

COMPONENT_COLUMNS = ["BTC_1H", "BTC_4H", "ETH_1H", "ETH_4H"]
PORTFOLIO_CANDIDATES = ["portfolio", "PORTFOLIO", "Crypto_Sleeve", "CRYPTO_SLEEVE"]
TARGET_HINTS = ["target", "weight", "exposure", "allocation", "desired_exposure", "desired_exposure_frac"]
CURVE_HINTS = ["curve", "nav", "portfolio", "sleeve", "equity", "hodl"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Create or audit a crypto target exposure stream for fund paper readiness",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--primary-artifact", default=DEFAULT_PRIMARY)
    p.add_argument("--fallback-artifact", default=DEFAULT_FALLBACK)
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    p.add_argument("--component-columns", default=",".join(COMPONENT_COLUMNS))
    p.add_argument("--portfolio-column", default="portfolio")
    p.add_argument("--candidate-name", default=DEFAULT_CANDIDATE)
    p.add_argument("--btc-1h-config", default="ecap75")
    p.add_argument("--btc-4h-config", default="ecap75")
    p.add_argument("--eth-1h-config", default="ecap75")
    p.add_argument("--eth-4h-config", default="cap75")
    return p.parse_args()


def _detect_time_col(df: pd.DataFrame) -> str:
    lower = {str(c).lower(): c for c in df.columns}
    for name in ["timestamp", "date", "datetime", "time", "unnamed: 0"]:
        if name in lower:
            return str(lower[name])
    return str(df.columns[0])


def _read_csv_indexed(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Empty file: {path}")
    time_col = _detect_time_col(df)
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col]).set_index(time_col).sort_index()
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    return df


def _parse_csv_list(raw: str) -> list[str]:
    return [x.strip() for x in str(raw).split(",") if x.strip()]


def _lineage(args: argparse.Namespace) -> dict[str, str]:
    return {
        "candidate_name": args.candidate_name,
        "btc_1h_config": args.btc_1h_config,
        "btc_4h_config": args.btc_4h_config,
        "eth_1h_config": args.eth_1h_config,
        "eth_4h_config": args.eth_4h_config,
    }


def _find_portfolio_column(df: pd.DataFrame, preferred: str) -> str | None:
    if preferred in df.columns:
        return preferred
    lower = {str(c).lower(): str(c) for c in df.columns}
    if preferred.lower() in lower:
        return lower[preferred.lower()]
    for candidate in PORTFOLIO_CANDIDATES:
        if candidate in df.columns:
            return candidate
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    return None


def _target_like_columns(df: pd.DataFrame) -> list[str]:
    out = []
    for c in df.columns:
        lc = str(c).lower()
        if any(h in lc for h in TARGET_HINTS):
            out.append(str(c))
    return out


def _curve_like_columns(df: pd.DataFrame) -> list[str]:
    out = []
    for c in df.columns:
        lc = str(c).lower()
        if any(h in lc for h in CURVE_HINTS):
            out.append(str(c))
    return out


def _audit_artifact(path: Path, component_cols: list[str], portfolio_column: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "status": "missing",
            "rows": 0,
            "start": None,
            "end": None,
            "columns": [],
            "target_like_columns": [],
            "component_columns_present": [],
            "component_columns_missing": component_cols,
            "portfolio_column": None,
            "curve_like_columns": [],
            "broker_ready": False,
            "readiness_gap": "Artifact is missing.",
        }

    try:
        df = _read_csv_indexed(path)
    except Exception as exc:
        return {
            "path": str(path),
            "exists": True,
            "status": "invalid",
            "rows": 0,
            "start": None,
            "end": None,
            "columns": [],
            "target_like_columns": [],
            "component_columns_present": [],
            "component_columns_missing": component_cols,
            "portfolio_column": None,
            "curve_like_columns": [],
            "broker_ready": False,
            "readiness_gap": f"Failed to load artifact: {exc}",
        }

    lower_map = {str(c).lower(): str(c) for c in df.columns}
    present_components = []
    missing_components = []
    for col in component_cols:
        if col in df.columns:
            present_components.append(col)
        elif col.lower() in lower_map:
            present_components.append(lower_map[col.lower()])
        else:
            missing_components.append(col)

    portfolio_col = _find_portfolio_column(df, portfolio_column)
    target_cols = _target_like_columns(df)
    curve_cols = _curve_like_columns(df)

    if target_cols:
        status = "target_ready"
        gap = "Artifact contains target-like columns. Validate semantics before broker-paper execution."
        broker_ready = True
    elif portfolio_col and len(present_components) == len(component_cols):
        status = "component_nav_proxy_ready"
        gap = "Artifact contains portfolio and component NAV columns. Can create proxy target stream, but intended target weights are still required before broker-paper execution."
        broker_ready = False
    elif curve_cols:
        status = "curve_only"
        gap = "Artifact appears to contain curves/NAVs but lacks component target or component NAV columns needed for a target stream."
        broker_ready = False
    else:
        status = "invalid"
        gap = "Artifact exists but does not contain recognizable target, component, or curve columns."
        broker_ready = False

    return {
        "path": str(path),
        "exists": True,
        "status": status,
        "rows": int(len(df)),
        "start": str(df.index[0]) if len(df) else None,
        "end": str(df.index[-1]) if len(df) else None,
        "columns": [str(c) for c in df.columns],
        "target_like_columns": target_cols,
        "component_columns_present": present_components,
        "component_columns_missing": missing_components,
        "portfolio_column": portfolio_col,
        "curve_like_columns": curve_cols,
        "broker_ready": broker_ready,
        "readiness_gap": gap,
    }


def _choose_source(audits: list[dict[str, Any]]) -> dict[str, Any]:
    rank = {
        "target_ready": 0,
        "component_nav_proxy_ready": 1,
        "curve_only": 2,
        "invalid": 3,
        "missing": 4,
    }
    return sorted(audits, key=lambda x: rank.get(str(x.get("status")), 99))[0]


def _load_selected_source(audit: dict[str, Any]) -> pd.DataFrame:
    return _read_csv_indexed(Path(str(audit["path"])))


def _with_lineage(out: pd.DataFrame, lineage: dict[str, str]) -> pd.DataFrame:
    for k, v in lineage.items():
        out[k] = v
    return out


def _build_proxy_stream(df: pd.DataFrame, audit: dict[str, Any], component_cols: list[str], lineage: dict[str, str]) -> pd.DataFrame:
    portfolio_col = str(audit.get("portfolio_column"))
    if portfolio_col not in df.columns:
        raise ValueError("Selected source lacks portfolio column for proxy stream")

    actual_components = list(audit.get("component_columns_present") or [])
    if len(actual_components) != len(component_cols):
        raise ValueError("Selected source lacks required component columns for proxy stream")

    portfolio = pd.to_numeric(df[portfolio_col], errors="coerce")
    out = pd.DataFrame(index=df.index)
    out = _with_lineage(out, lineage)
    out["source_status"] = "proxy_from_component_nav"
    out["broker_ready"] = False
    out["source_strategy_version"] = Path(str(audit["path"])).parent.name
    out["source_path"] = str(audit["path"])

    weight_cols = []
    for canonical, actual in zip(component_cols, actual_components):
        values = pd.to_numeric(df[actual], errors="coerce")
        weight_col = canonical.lower() + "_target_weight"
        out[weight_col] = (values / portfolio).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        weight_cols.append(weight_col)

    component_sum = out[weight_cols].sum(axis=1)
    out["crypto_cash_or_risk_off_weight"] = (1.0 - component_sum).clip(lower=0.0)
    out["crypto_target_exposure"] = component_sum.clip(lower=0.0)

    def state(x: float) -> str:
        if x <= 1e-9:
            return "RISK_OFF_PROXY"
        if x < 0.999:
            return "PARTIAL_RISK_PROXY"
        return "RISK_ON_PROXY"

    out["crypto_risk_state"] = out["crypto_target_exposure"].map(state)
    out["reason"] = "Proxy stream inferred from component NAV/account values for promoted candidate lineage; not broker-executable intended targets."

    preferred = [
        "candidate_name",
        "crypto_target_exposure",
        "btc_1h_target_weight",
        "btc_4h_target_weight",
        "eth_1h_target_weight",
        "eth_4h_target_weight",
        "crypto_cash_or_risk_off_weight",
        "crypto_risk_state",
        "btc_1h_config",
        "btc_4h_config",
        "eth_1h_config",
        "eth_4h_config",
        "reason",
        "source_strategy_version",
        "source_status",
        "broker_ready",
        "source_path",
    ]
    existing = [c for c in preferred if c in out.columns]
    return out[existing]


def _build_target_ready_stream(df: pd.DataFrame, audit: dict[str, Any], lineage: dict[str, str]) -> pd.DataFrame:
    target_cols = list(audit.get("target_like_columns") or [])
    out = pd.DataFrame(index=df.index)
    out = _with_lineage(out, lineage)
    out["source_status"] = "target_ready"
    out["broker_ready"] = True
    out["source_strategy_version"] = Path(str(audit["path"])).parent.name
    out["source_path"] = str(audit["path"])
    for col in target_cols:
        out[str(col)] = pd.to_numeric(df[col], errors="coerce")
    out["reason"] = "Target-like columns detected for promoted candidate lineage; semantics require human validation before broker-paper execution."
    return out


def _empty_stream(audit: dict[str, Any], lineage: dict[str, str]) -> pd.DataFrame:
    row = {
        "timestamp": pd.NaT,
        **lineage,
        "crypto_target_exposure": np.nan,
        "btc_1h_target_weight": np.nan,
        "btc_4h_target_weight": np.nan,
        "eth_1h_target_weight": np.nan,
        "eth_4h_target_weight": np.nan,
        "crypto_cash_or_risk_off_weight": np.nan,
        "crypto_risk_state": "MISSING",
        "reason": str(audit.get("readiness_gap")),
        "source_strategy_version": "missing",
        "source_status": str(audit.get("status")),
        "broker_ready": False,
        "source_path": str(audit.get("path")),
    }
    return pd.DataFrame([row]).set_index("timestamp")


def _build_stream_from_selected(audit: dict[str, Any], component_cols: list[str], lineage: dict[str, str]) -> pd.DataFrame:
    status = str(audit.get("status"))
    if status in {"missing", "invalid", "curve_only"}:
        return _empty_stream(audit, lineage)
    df = _load_selected_source(audit)
    if status == "target_ready":
        return _build_target_ready_stream(df, audit, lineage)
    if status == "component_nav_proxy_ready":
        return _build_proxy_stream(df, audit, component_cols, lineage)
    return _empty_stream(audit, lineage)


def _schema_payload() -> dict[str, Any]:
    return {
        "schema_name": "crypto_target_stream_v1",
        "description": "Canonical or proxy crypto target exposure stream for Fund Paper Readiness.",
        "default_candidate": DEFAULT_CANDIDATE,
        "default_candidate_mapping": {
            "btc_1h_config": "ecap75",
            "btc_4h_config": "ecap75",
            "eth_1h_config": "ecap75",
            "eth_4h_config": "cap75",
        },
        "required_columns": {
            "timestamp": "Datetime index or column.",
            "candidate_name": "Promoted candidate lineage, default hybrid_eth4h_cap75_only.",
            "crypto_target_exposure": "Total intended/proxy crypto risk exposure inside crypto sleeve.",
            "btc_1h_target_weight": "BTC 1H component target/proxy weight inside crypto sleeve.",
            "btc_4h_target_weight": "BTC 4H component target/proxy weight inside crypto sleeve.",
            "eth_1h_target_weight": "ETH 1H component target/proxy weight inside crypto sleeve.",
            "eth_4h_target_weight": "ETH 4H component target/proxy weight inside crypto sleeve.",
            "crypto_cash_or_risk_off_weight": "Residual unallocated/risk-off sleeve weight.",
            "crypto_risk_state": "Descriptive risk state.",
            "btc_1h_config": "Candidate config lineage for BTC_1H.",
            "btc_4h_config": "Candidate config lineage for BTC_4H.",
            "eth_1h_config": "Candidate config lineage for ETH_1H.",
            "eth_4h_config": "Candidate config lineage for ETH_4H.",
            "reason": "Human-readable source/reason.",
            "source_strategy_version": "Artifact/strategy lineage.",
            "source_status": "target_ready, proxy_from_component_nav, curve_only, missing, or invalid.",
            "broker_ready": "Boolean. True only for validated target-ready streams.",
        },
        "important_note": "proxy_from_component_nav streams are not broker-executable intended targets.",
    }


def _summary_rows(stream: pd.DataFrame, selected: dict[str, Any], lineage: dict[str, str]) -> pd.DataFrame:
    rows = [
        {"metric": "candidate_name", "value": lineage["candidate_name"]},
        {"metric": "btc_1h_config", "value": lineage["btc_1h_config"]},
        {"metric": "btc_4h_config", "value": lineage["btc_4h_config"]},
        {"metric": "eth_1h_config", "value": lineage["eth_1h_config"]},
        {"metric": "eth_4h_config", "value": lineage["eth_4h_config"]},
        {"metric": "selected_source", "value": str(selected.get("path"))},
        {"metric": "selected_status", "value": str(selected.get("status"))},
        {"metric": "broker_ready", "value": bool(selected.get("broker_ready"))},
        {"metric": "rows", "value": int(len(stream))},
        {"metric": "start", "value": str(stream.index[0]) if len(stream) else "n/a"},
        {"metric": "end", "value": str(stream.index[-1]) if len(stream) else "n/a"},
    ]
    numeric_cols = [c for c in stream.columns if c.endswith("_target_weight") or c in {"crypto_target_exposure", "crypto_cash_or_risk_off_weight"}]
    for col in numeric_cols:
        vals = pd.to_numeric(stream[col], errors="coerce").dropna()
        if vals.empty:
            continue
        rows.extend(
            [
                {"metric": f"avg_{col}_pct", "value": float(vals.mean() * 100.0)},
                {"metric": f"min_{col}_pct", "value": float(vals.min() * 100.0)},
                {"metric": f"max_{col}_pct", "value": float(vals.max() * 100.0)},
            ]
        )
    if "crypto_risk_state" in stream.columns:
        dist = stream["crypto_risk_state"].value_counts(normalize=True).to_dict()
        for state, pct in dist.items():
            rows.append({"metric": f"time_in_{state}_pct", "value": float(pct * 100.0)})
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
                vals.append(f"{value:.4f}")
            else:
                vals.append(str(value).replace("|", "\\|").replace("\n", " "))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def _write_gaps(path: Path, selected: dict[str, Any], audits: list[dict[str, Any]], lineage: dict[str, str]) -> None:
    lines = [
        "# Crypto Target Stream v1 — Readiness Gaps",
        "",
        "## Candidate Lineage",
        "",
        "```text",
        f"candidate_name: {lineage['candidate_name']}",
        f"BTC_1H: {lineage['btc_1h_config']}",
        f"BTC_4H: {lineage['btc_4h_config']}",
        f"ETH_1H: {lineage['eth_1h_config']}",
        f"ETH_4H: {lineage['eth_4h_config']}",
        "```",
        "",
        "## Selected Source",
        "",
        "```text",
        f"Path: {selected.get('path')}",
        f"Status: {selected.get('status')}",
        f"Broker ready: {selected.get('broker_ready')}",
        f"Gap: {selected.get('readiness_gap')}",
        "```",
        "",
        "## Interpretation",
        "",
    ]
    status = str(selected.get("status"))
    if status == "target_ready":
        lines.extend([
            "A target-like artifact was found. Before broker-paper execution, validate that the detected target columns represent intended target exposures rather than realized allocations or reporting weights.",
            "",
        ])
    elif status == "component_nav_proxy_ready":
        lines.extend([
            "A component-NAV proxy stream was created for the promoted candidate lineage. This is useful for fund readiness and adapter development, but it is not broker-ready because it is inferred from component account values rather than intended strategy targets.",
            "",
            "Required next step: export intended crypto target weights directly from the promoted crypto strategy logic.",
            "",
        ])
    else:
        lines.extend([
            "No target-ready or component-proxy-ready crypto artifact was found.",
            "",
            "Required next step: create a canonical crypto daily target exposure export from promoted strategy logic.",
            "",
        ])
    lines.extend(["## Input Audit", "", _md_table(pd.DataFrame(audits), max_rows=10), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_summary(path: Path, summary_df: pd.DataFrame, audits_df: pd.DataFrame, selected: dict[str, Any], stream: pd.DataFrame, lineage: dict[str, str]) -> None:
    lines = [
        "# Crypto Target Stream v1",
        "",
        "Research-only crypto target-stream readiness output.",
        "",
        "## Candidate Lineage",
        "",
        "```text",
        f"candidate_name: {lineage['candidate_name']}",
        f"BTC_1H: {lineage['btc_1h_config']}",
        f"BTC_4H: {lineage['btc_4h_config']}",
        f"ETH_1H: {lineage['eth_1h_config']}",
        f"ETH_4H: {lineage['eth_4h_config']}",
        "```",
        "",
        "## Selected Source",
        "",
        "```text",
        f"Path: {selected.get('path')}",
        f"Status: {selected.get('status')}",
        f"Broker ready: {selected.get('broker_ready')}",
        f"Rows: {selected.get('rows')}",
        f"Start: {selected.get('start')}",
        f"End: {selected.get('end')}",
        "```",
        "",
        "## Target Stream Summary",
        "",
        _md_table(summary_df, max_rows=80),
        "",
        "## Input Audit",
        "",
        _md_table(audits_df, max_rows=10),
        "",
        "## Latest Target Row",
        "",
        _md_table(stream.tail(1).reset_index(names="timestamp"), max_rows=1),
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
    component_cols = _parse_csv_list(args.component_columns)
    if not component_cols:
        raise ValueError("component-columns must not be empty")

    lineage = _lineage(args)
    primary = Path(args.primary_artifact)
    fallback = Path(args.fallback_artifact)
    audits = [
        _audit_artifact(primary, component_cols, args.portfolio_column),
        _audit_artifact(fallback, component_cols, args.portfolio_column),
    ]
    selected = _choose_source(audits)
    stream = _build_stream_from_selected(selected, component_cols, lineage)
    summary_df = _summary_rows(stream, selected, lineage)
    audits_df = pd.DataFrame(audits)

    stream.to_csv(out_dir / "crypto_target_exposure.csv")
    summary_df.to_csv(out_dir / "crypto_target_summary.csv", index=False)
    audits_df.to_csv(out_dir / "crypto_target_input_audit.csv", index=False)
    (out_dir / "crypto_target_schema.json").write_text(json.dumps(_schema_payload(), indent=2), encoding="utf-8")

    payload = {
        "research_status": "research_only_crypto_target_stream_v1",
        "candidate_lineage": lineage,
        "inputs": {
            "primary_artifact": args.primary_artifact,
            "fallback_artifact": args.fallback_artifact,
            "component_columns": component_cols,
            "portfolio_column": args.portfolio_column,
        },
        "selected_source": selected,
        "outputs": {
            "crypto_target_exposure": str(out_dir / "crypto_target_exposure.csv"),
            "crypto_target_schema": str(out_dir / "crypto_target_schema.json"),
            "crypto_target_summary": str(out_dir / "crypto_target_summary.csv"),
            "crypto_target_input_audit": str(out_dir / "crypto_target_input_audit.csv"),
            "readiness_gaps": str(out_dir / "readiness_gaps.md"),
            "summary_md": str(out_dir / "summary.md"),
            "summary_json": str(out_dir / "summary.json"),
        },
        "decision": {"status": "target_stream_readiness_only", "not_approved": ["live_trading", "broker_integration", "paper_broker_execution", "runtime_deployment", "dashboard_integration", "dynamic_allocator"]},
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_gaps(out_dir / "readiness_gaps.md", selected, audits, lineage)
    _write_summary(out_dir / "summary.md", summary_df, audits_df, selected, stream, lineage)

    with pd.option_context("display.max_columns", None, "display.width", 560, "display.float_format", "{:.4f}".format):
        print("\n=== CRYPTO TARGET STREAM V1 ===")
        print("\nCandidate Lineage:")
        print(pd.DataFrame([lineage]).to_string(index=False))
        print("\nInput Audit:")
        print(audits_df.to_string(index=False))
        print("\nSelected Source:")
        print(pd.DataFrame([selected]).to_string(index=False))
        print("\nTarget Stream Summary:")
        print(summary_df.to_string(index=False))
        print("\nLatest Target Row:")
        print(stream.tail(1).reset_index(names="timestamp").to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
