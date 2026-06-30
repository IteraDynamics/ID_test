#!/usr/bin/env python
"""Professional Streamlit dashboard for the clean Core v1 paper runtime."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

STATE_PATH = Path(os.getenv("CORE_V1_STATE_PATH", "/opt/itera/runtime/core_v1/state.json"))
SIGNALS_LOG = Path(os.getenv("CORE_V1_SIGNALS_LOG", "/opt/itera/logs/core_v1_signals.jsonl"))
FILLS_LOG = Path(os.getenv("CORE_V1_FILLS_LOG", "/opt/itera/logs/core_v1_fills.jsonl"))
ERROR_LOG = SIGNALS_LOG.with_name("core_v1_errors.jsonl")
REFRESH_SECONDS = int(os.getenv("CORE_V1_DASHBOARD_REFRESH_SECONDS", "30"))
EXPECTED_POLL_SECONDS = int(os.getenv("CORE_V1_POLL_SECONDS", "3600"))
STALE_AFTER_SECONDS = int(os.getenv("CORE_V1_STALE_AFTER_SECONDS", str(EXPECTED_POLL_SECONDS * 2 + 300)))

SCENARIO = "candidate_btc1h_hedges_to_btc4h_gld_qqq"
EXPECTED_WEIGHTS = {
    "BTC_4H_trend": 0.150,
    "ETH_1H_trend": 0.100,
    "ETH_4H_trend": 0.100,
    "SPY_1D_equity": 0.175,
    "QQQ_1D_equity": 0.275,
    "GLD_1D_gold": 0.200,
}
ZERO_WEIGHT = ["BTC_1H_trend", "BTC_1H_hedge", "ETH_1H_hedge"]

st.set_page_config(
    page_title="Itera Core v1 Paper",
    page_icon="◎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
.stApp { background: #0b0f17; color: #e5e7eb; }
.block-container { padding-top: 1.3rem; padding-bottom: 2.5rem; max-width: 1500px; }
[data-testid="stMetric"] {
  background: linear-gradient(180deg, #121826 0%, #0f172a 100%);
  border: 1px solid #1f2937;
  border-radius: 14px;
  padding: 14px 16px;
  box-shadow: 0 10px 30px rgba(0,0,0,.18);
}
[data-testid="stMetricLabel"] { color: #9ca3af !important; font-size: .76rem !important; letter-spacing: .06em; text-transform: uppercase; }
[data-testid="stMetricValue"] { color: #f9fafb !important; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 1.35rem !important; }
.itera-title { display:flex; justify-content:space-between; align-items:flex-start; gap: 1rem; margin-bottom: .8rem; }
.itera-title h1 { margin:0; font-size: 1.65rem; letter-spacing:-.03em; }
.itera-sub { color:#9ca3af; margin-top:.25rem; font-size:.88rem; }
.badge { display:inline-block; border-radius: 999px; padding: 4px 10px; font-size: .72rem; font-weight: 700; letter-spacing:.04em; text-transform: uppercase; }
.badge-ok { background:#064e3b; color:#a7f3d0; border:1px solid #047857; }
.badge-warn { background:#451a03; color:#fed7aa; border:1px solid #c2410c; }
.badge-err { background:#450a0a; color:#fecaca; border:1px solid #dc2626; }
.card { background:#0f172a; border:1px solid #1f2937; border-radius:14px; padding:14px 16px; margin-bottom:12px; }
.card h3 { margin:0 0 6px 0; font-size: .95rem; }
.small { color:#9ca3af; font-size:.8rem; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
hr { border-color:#1f2937; }
</style>
""",
    unsafe_allow_html=True,
)


def now_utc() -> datetime:
    return datetime.now(UTC)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_jsonl(path: Path, n: int = 500) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-n:]:
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def parse_ts(value: Any) -> pd.Timestamp | None:
    if not value:
        return None
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return None
    return ts


def age_text(ts: pd.Timestamp | None) -> str:
    if ts is None:
        return "unknown"
    seconds = max(0, int((pd.Timestamp.now(tz="UTC") - ts).total_seconds()))
    if seconds < 90:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 90:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


def money(v: Any) -> str:
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return "—"


def pct(v: Any, d: int = 2) -> str:
    try:
        return f"{float(v):.{d}%}"
    except Exception:
        return "—"


def badge(label: str, status: str) -> str:
    klass = {"ok": "badge-ok", "warn": "badge-warn", "err": "badge-err"}.get(status, "badge-warn")
    return f'<span class="badge {klass}">{label}</span>'


state = read_json(STATE_PATH)
events = read_jsonl(SIGNALS_LOG, 800)
fills = read_jsonl(FILLS_LOG, 800)
errors = read_jsonl(ERROR_LOG, 100)
last = events[-1] if events else {}
last_ts = parse_ts(state.get("last_cycle_at") or last.get("timestamp"))
last_age_seconds = None if last_ts is None else max(0, int((pd.Timestamp.now(tz="UTC") - last_ts).total_seconds()))
is_stale = last_age_seconds is None or last_age_seconds > STALE_AFTER_SECONDS
has_recent_errors = bool(errors)
expected_present = set(EXPECTED_WEIGHTS)
actual_present = set(state.get("sleeves", {}))
missing_sleeves = sorted(expected_present - actual_present)
health_status = "err" if is_stale or missing_sleeves else "warn" if has_recent_errors else "ok"
health_label = "ATTENTION" if health_status == "err" else "WARN" if health_status == "warn" else "HEALTHY"

st.markdown(
    f"""
<div class="itera-title">
  <div>
    <h1>Itera Core v1 Paper Operations</h1>
    <div class="itera-sub">Selected allocation: <span class="mono">{SCENARIO}</span></div>
  </div>
  <div>{badge(health_label, health_status)} {badge('PAPER', 'ok')}</div>
</div>
""",
    unsafe_allow_html=True,
)

if is_stale:
    st.error(f"Core v1 paper cycle is stale. Last cycle: {age_text(last_ts)}. Expected cadence: {EXPECTED_POLL_SECONDS}s.")
if missing_sleeves:
    st.error(f"Missing expected sleeves in state: {missing_sleeves}")
if has_recent_errors:
    latest_err = errors[-1]
    st.warning(f"Recent runtime error logged: {latest_err.get('error', 'unknown error')}")

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Portfolio NAV", money(state.get("last_total_nav", last.get("total_nav", 0.0))))
m2.metric("P/L vs $100k", money(float(state.get("last_total_nav", last.get("total_nav", 0.0)) or 0.0) - 100000.0))
m3.metric("Drawdown", pct(state.get("drawdown_frac", 0.0)))
m4.metric("Cycle", state.get("cycle", last.get("cycle", 0)))
m5.metric("Last cycle", age_text(last_ts))
m6.metric("Fills total", len(fills))

st.divider()

left, right = st.columns([1.65, 1])

with left:
    st.subheader("Sleeve status")
    sleeves = state.get("sleeves", {})
    sleeve_navs = state.get("sleeve_navs", {})
    rows = []
    for label, target_weight in EXPECTED_WEIGHTS.items():
        payload = sleeves.get(label, {})
        price = float(payload.get("last_price") or 0.0)
        qty = float(payload.get("qty") or 0.0)
        cash = float(payload.get("cash") or 0.0)
        nav = float(sleeve_navs.get(label) or cash + qty * price)
        total_nav = float(state.get("last_total_nav") or sum(float(v) for v in sleeve_navs.values()) or 0.0)
        sleeve_weight = 0.0 if total_nav <= 0 else nav / total_nav
        exposure = 0.0 if nav <= 0 else qty * price / nav
        latest_signal = None
        if last.get("signals"):
            latest_signal = next((s for s in last["signals"] if s.get("sleeve") == label), None)
        rows.append(
            {
                "sleeve": label,
                "target_weight": target_weight,
                "actual_weight": sleeve_weight,
                "drift": sleeve_weight - target_weight,
                "nav": nav,
                "cash": cash,
                "position_qty": qty,
                "price": price,
                "exposure": exposure,
                "target_exposure": float(payload.get("last_target_exposure") or 0.0),
                "action": None if latest_signal is None else latest_signal.get("action"),
                "regime": None if latest_signal is None else latest_signal.get("regime"),
                "last_bar": payload.get("last_timestamp"),
            }
        )
    sleeve_df = pd.DataFrame(rows)
    if not sleeve_df.empty:
        st.dataframe(
            sleeve_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "target_weight": st.column_config.ProgressColumn("Target", format="%.1f%%", min_value=0, max_value=1),
                "actual_weight": st.column_config.ProgressColumn("Actual", format="%.1f%%", min_value=0, max_value=1),
                "drift": st.column_config.NumberColumn("Drift", format="%.2%"),
                "nav": st.column_config.NumberColumn("NAV", format="$%.2f"),
                "cash": st.column_config.NumberColumn("Cash", format="$%.2f"),
                "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                "exposure": st.column_config.ProgressColumn("Exposure", format="%.0f%%", min_value=0, max_value=1),
                "target_exposure": st.column_config.ProgressColumn("Target exp", format="%.0f%%", min_value=0, max_value=1),
            },
        )

    st.subheader("Latest signal explanations")
    sig_rows = []
    for s in last.get("signals", []):
        sig_rows.append(
            {
                "sleeve": s.get("sleeve"),
                "asset": s.get("asset"),
                "tf": s.get("timeframe"),
                "action": s.get("action"),
                "target": s.get("target_exposure"),
                "confidence": s.get("confidence"),
                "regime": s.get("regime"),
                "price": s.get("price"),
                "fill": "yes" if s.get("fill") else "no",
                "reason": s.get("reason"),
            }
        )
    if sig_rows:
        st.dataframe(
            pd.DataFrame(sig_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "target": st.column_config.NumberColumn("Target", format="%.2f"),
                "confidence": st.column_config.NumberColumn("Conf", format="%.2f"),
                "price": st.column_config.NumberColumn("Price", format="$%.2f"),
            },
        )
    else:
        st.info("No signal records yet.")

with right:
    st.subheader("Operational health")
    st.markdown(
        f"""
<div class="card">
  <h3>Runtime</h3>
  <div class="small">State file</div><div class="mono">{STATE_PATH}</div>
  <div class="small" style="margin-top:8px;">Signals log</div><div class="mono">{SIGNALS_LOG}</div>
  <div class="small" style="margin-top:8px;">Fills log</div><div class="mono">{FILLS_LOG}</div>
</div>
<div class="card">
  <h3>Expected zero-weight sleeves</h3>
  <div class="mono">{', '.join(ZERO_WEIGHT)}</div>
</div>
<div class="card">
  <h3>Cadence</h3>
  <div>Poll: <span class="mono">{EXPECTED_POLL_SECONDS}s</span></div>
  <div>Stale after: <span class="mono">{STALE_AFTER_SECONDS}s</span></div>
  <div>Last cycle: <span class="mono">{age_text(last_ts)}</span></div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.subheader("Last fills")
    if fills:
        fill_df = pd.DataFrame(fills[-12:][::-1])
        keep = [c for c in ["timestamp", "sleeve", "side", "qty", "price", "notional", "fee"] if c in fill_df.columns]
        st.dataframe(fill_df[keep], use_container_width=True, hide_index=True)
    else:
        st.info("No fills yet.")

st.divider()

c_nav, c_alloc = st.columns([1.35, 1])
with c_nav:
    st.subheader("NAV history")
    if events:
        hist = pd.DataFrame(
            [
                {
                    "timestamp": e.get("timestamp"),
                    "nav": e.get("total_nav"),
                    "drawdown": e.get("drawdown_frac"),
                    "fills": len(e.get("fills", [])),
                }
                for e in events
            ]
        )
        hist["timestamp"] = pd.to_datetime(hist["timestamp"], utc=True, errors="coerce")
        hist = hist.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()
        if not hist.empty:
            st.line_chart(hist[["nav"]], use_container_width=True)
    else:
        st.info("No NAV history yet.")

with c_alloc:
    st.subheader("Current allocation")
    if not sleeve_df.empty:
        alloc = sleeve_df[["sleeve", "actual_weight"]].copy()
        alloc = alloc.set_index("sleeve")
        st.bar_chart(alloc, use_container_width=True)

st.subheader("Recent errors")
if errors:
    err_df = pd.DataFrame(errors[-20:][::-1])
    st.dataframe(err_df, use_container_width=True, hide_index=True)
else:
    st.success("No runtime errors logged.")

st.caption(
    f"Itera Core v1 Paper | {SCENARIO} | dashboard refresh target {REFRESH_SECONDS}s | "
    f"generated {now_utc().isoformat()}"
)
