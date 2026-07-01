#!/usr/bin/env python
"""Mission-control dashboard for the clean Core v1 paper runtime."""

from __future__ import annotations

import html
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from runtime.core_v1.allocation import SELECTED_CORE_V1_SCENARIO, SELECTED_CORE_V1_SLEEVES

STATE_PATH = Path(os.getenv("CORE_V1_STATE_PATH", "/opt/itera/runtime/core_v1/state.json"))
SIGNALS_LOG = Path(os.getenv("CORE_V1_SIGNALS_LOG", "/opt/itera/logs/core_v1_signals.jsonl"))
FILLS_LOG = Path(os.getenv("CORE_V1_FILLS_LOG", "/opt/itera/logs/core_v1_fills.jsonl"))
ERROR_LOG = SIGNALS_LOG.with_name("core_v1_errors.jsonl")
AUDIT_REPORT_PATH = Path(os.getenv("CORE_V1_AUDIT_REPORT_PATH", str(STATE_PATH.with_name("core_v1_audit_report.json"))))
EXPECTED_POLL_SECONDS = int(os.getenv("CORE_V1_POLL_SECONDS", "3600"))
STALE_AFTER_SECONDS = int(os.getenv("CORE_V1_STALE_AFTER_SECONDS", str(EXPECTED_POLL_SECONDS * 2 + 300)))
STALE_AUDIT_AFTER_SECONDS = int(os.getenv("CORE_V1_STALE_AUDIT_AFTER_SECONDS", str(EXPECTED_POLL_SECONDS * 6)))
REFRESH_SECONDS = int(os.getenv("CORE_V1_DASHBOARD_REFRESH_SECONDS", "30"))
DEFAULT_CAPITAL = float(os.getenv("CORE_V1_CAPITAL", "100000"))

SCENARIO = SELECTED_CORE_V1_SCENARIO
EXPECTED_WEIGHTS = {s.label: s.weight for s in SELECTED_CORE_V1_SLEEVES}
SLEEVE_META = {s.label: s for s in SELECTED_CORE_V1_SLEEVES}
SLEEVE_NAMES = {
    "BTC_4H_trend": "BTC 4H",
    "ETH_1H_trend": "ETH 1H",
    "ETH_4H_trend": "ETH 4H",
    "SPY_1D_equity": "SPY",
    "QQQ_1D_equity": "QQQ",
    "GLD_1D_gold": "GLD",
}
ASSET_CLASS = {"trend": "Crypto", "equity": "Equities", "gold": "Gold"}
ASSET_CLASS_COLOR = {"Crypto": "#f59e0b", "Equities": "#38bdf8", "Gold": "#eab308", "Cash": "#64748b"}
REGIME_DISPLAY = {
    "TREND_UP": ("Trend · Up", "regime-up"),
    "TREND_DOWN": ("Trend · Down", "regime-down"),
    "RANGE": ("Range", "regime-neutral"),
    "VOL_COMPRESSION": ("Vol Compression", "regime-vol"),
    "VOL_EXPANSION": ("Vol Expansion", "regime-vol"),
    "HIGH_VOL": ("High Vol", "regime-vol"),
    "UNKNOWN": ("Unknown", "regime-neutral"),
}

st.set_page_config(page_title="Itera Mission Control", page_icon="◎", layout="wide", initial_sidebar_state="collapsed")
st.markdown(f"<meta http-equiv='refresh' content='{REFRESH_SECONDS}'>", unsafe_allow_html=True)

st.markdown(
    """
<style>
:root { color-scheme: dark; }
.stApp { background: radial-gradient(circle at top left, #111827 0%, #080c14 42%, #05070c 100%); color:#e5e7eb; }
.block-container { padding-top:1.0rem; padding-bottom:2.0rem; max-width:1700px; }
#MainMenu, footer, header { visibility:hidden; height:0; }
[data-testid="stHeaderActionElements"] { display:none; }
[data-testid="stMetric"] { background:#0d1422; border:1px solid #1f2a3d; border-radius:16px; padding:12px 14px; }
html, body, [class*="css"] { font-family:-apple-system,BlinkMacSystemFont,"Inter","Segoe UI",Helvetica,Arial,sans-serif; }
.brand-row { display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:12px; }
.brand-kicker { color:#64748b; font-size:.70rem; letter-spacing:.24em; font-weight:850; text-transform:uppercase; }
.brand-title { color:#f8fafc; font-size:1.9rem; line-height:1.0; font-weight:950; letter-spacing:-.055em; margin-top:2px; }
.brand-sub { color:#94a3b8; font-size:.82rem; margin-top:7px; }
.badges { display:flex; gap:8px; align-items:center; justify-content:flex-end; flex-wrap:wrap; }
.badge { display:inline-flex; align-items:center; gap:6px; border-radius:999px; padding:6px 11px; font-size:.66rem; letter-spacing:.07em; font-weight:900; text-transform:uppercase; white-space:nowrap; }
.ok { background:#052e26; color:#99f6e4; border:1px solid #0f766e; }
.warn { background:#3b2505; color:#fde68a; border:1px solid #b45309; }
.err { background:#3f0a0a; color:#fecaca; border:1px solid #dc2626; }
.neutral { background:#111827; color:#cbd5e1; border:1px solid #334155; }
.info { background:#0c1e33; color:#bfdbfe; border:1px solid #1d4ed8; }
.command-deck { display:grid; grid-template-columns:1.5fr repeat(4, 1fr); gap:10px; margin:10px 0 12px 0; }
.command-card { background:linear-gradient(180deg,#111827 0%, #0b1220 100%); border:1px solid #1f2a3d; border-radius:18px; padding:16px; box-shadow:0 18px 40px rgba(0,0,0,.24); min-height:108px; }
.command-card.primary { background:linear-gradient(145deg,#132033 0%, #0b1220 62%, #07101d 100%); border-color:#334155; }
.command-label { color:#94a3b8; font-size:.66rem; letter-spacing:.09em; text-transform:uppercase; font-weight:900; }
.command-value { color:#f8fafc; font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; font-size:1.58rem; line-height:1.05; font-weight:950; margin-top:10px; }
.primary .command-value { font-size:2.12rem; }
.command-sub { color:#64748b; font-size:.76rem; margin-top:7px; }
.good { color:#86efac; } .bad { color:#fca5a5; } .muted { color:#94a3b8; } .white { color:#f8fafc; }
.alert-line { border-radius:14px; padding:10px 13px; margin:10px 0 16px 0; font-size:.83rem; display:flex; justify-content:space-between; align-items:center; gap:12px; }
.alert-line span:first-child { flex:1 1 auto; min-width:0; }
.alert-line span:last-child { white-space:nowrap; flex:none; }
.alert-ok { background:#052e26; border:1px solid #0f766e; color:#ccfbf1; }
.alert-warn { background:#3b2505; border:1px solid #b45309; color:#fde68a; }
.alert-err { background:#3f0a0a; border:1px solid #dc2626; color:#fecaca; }
.section-head { display:flex; justify-content:space-between; align-items:end; gap:12px; margin:22px 0 10px 0; }
.section-title { color:#f8fafc; font-size:1.08rem; font-weight:850; letter-spacing:-.025em; }
.section-sub { color:#64748b; font-size:.76rem; margin-top:2px; }
.chart-card { background:linear-gradient(180deg,#111827 0%, #0b1220 100%); border:1px solid #1f2a3d; border-radius:18px; padding:6px 10px 2px 10px; box-shadow:0 18px 40px rgba(0,0,0,.24); }
.posture-row { display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:12px; }
.posture-card { background:linear-gradient(180deg,#111827 0%, #0b1220 100%); border:1px solid #1f2a3d; border-radius:18px; padding:16px; box-shadow:0 18px 40px rgba(0,0,0,.24); }
.comp-bar { display:flex; width:100%; height:14px; border-radius:999px; overflow:hidden; border:1px solid #1e293b; background:#0b1220; margin:12px 0 14px 0; }
.comp-seg { height:100%; }
.comp-legend { display:flex; flex-wrap:wrap; gap:18px; }
.comp-item { display:flex; flex-direction:column; gap:2px; min-width:110px; }
.comp-dot-row { display:flex; align-items:center; gap:7px; }
.comp-dot { width:9px; height:9px; border-radius:3px; flex:none; }
.comp-name { color:#94a3b8; font-size:.7rem; text-transform:uppercase; letter-spacing:.06em; font-weight:850; }
.comp-value { color:#f8fafc; font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; font-size:1.02rem; font-weight:850; margin-left:16px; }
.comp-sub { color:#64748b; font-size:.72rem; margin-left:16px; }
.position-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }
.position-card { background:linear-gradient(180deg,#111827,#0b1220); border:1px solid #1f2a3d; border-radius:20px; padding:17px; box-shadow:0 18px 40px rgba(0,0,0,.24); }
.position-card.holding { border-color:#0f766e; box-shadow:0 0 0 1px rgba(15,118,110,.16), 0 18px 40px rgba(0,0,0,.24); }
.position-card.flat { opacity:.82; }
.position-card.entering { border-color:#1d4ed8; box-shadow:0 0 0 1px rgba(29,78,216,.18), 0 18px 40px rgba(0,0,0,.24); }
.position-card.exiting { border-color:#b45309; box-shadow:0 0 0 1px rgba(180,83,9,.18), 0 18px 40px rgba(0,0,0,.24); }
.position-top { display:flex; justify-content:space-between; gap:10px; align-items:flex-start; }
.position-name { color:#f8fafc; font-size:1.22rem; font-weight:950; letter-spacing:-.035em; }
.position-meta { color:#94a3b8; font-size:.72rem; margin-top:3px; }
.reason-line { color:#e5e7eb; font-size:.92rem; line-height:1.35; margin-top:13px; min-height:56px; font-weight:560; }
.reason-line b { color:#f8fafc; font-weight:900; }
.position-pnl { font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; font-size:1.76rem; font-weight:950; margin-top:13px; letter-spacing:-.04em; }
.position-pnl-sub { color:#94a3b8; font-size:.78rem; margin-top:2px; }
.alloc-wrap { margin:13px 0 11px 0; }
.alloc-top { display:flex; justify-content:space-between; color:#94a3b8; font-size:.68rem; letter-spacing:.04em; text-transform:uppercase; font-weight:850; margin-bottom:6px; }
.alloc-meter { position:relative; height:9px; background:#111827; border-radius:999px; overflow:hidden; border:1px solid #1e293b; }
.alloc-fill { height:100%; border-radius:999px; background:linear-gradient(90deg,#38bdf8,#22c55e); }
.target-pin { position:absolute; top:-2px; width:2px; height:13px; background:#f8fafc; opacity:.9; }
.stat-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-top:10px; }
.stat { background:#090f1a; border:1px solid #1e293b; border-radius:12px; padding:8px; min-height:52px; }
.stat-label { color:#64748b; font-size:.60rem; text-transform:uppercase; letter-spacing:.08em; font-weight:900; }
.stat-value { color:#f8fafc; font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; font-size:.86rem; margin-top:4px; }
.position-line { display:flex; justify-content:space-between; gap:10px; color:#94a3b8; font-size:.74rem; border-top:1px solid #1f2a3d; padding-top:9px; margin-top:10px; }
.regime { display:inline-flex; border-radius:999px; padding:3px 7px; font-size:.62rem; font-weight:900; letter-spacing:.04em; white-space:nowrap; }
.regime-up { background:#052e26; color:#99f6e4; border:1px solid #0f766e; }
.regime-down { background:#3f0a0a; color:#fecaca; border:1px solid #dc2626; }
.regime-vol { background:#162033; color:#bfdbfe; border:1px solid #334155; }
.regime-neutral { background:#111827; color:#cbd5e1; border:1px solid #334155; }
.state-chip { font-size:.66rem; font-weight:950; letter-spacing:.06em; padding:5px 9px; border-radius:8px; text-transform:uppercase; }
.state-holding { background:#052e26; color:#99f6e4; border:1px solid #0f766e; }
.state-flat { background:#1e293b; color:#cbd5e1; border:1px solid #334155; }
.state-entering { background:#0c1e33; color:#bfdbfe; border:1px solid #1d4ed8; }
.state-exiting { background:#3b2505; color:#fde68a; border:1px solid #b45309; }
.health-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; }
.health-card { background:#0d1422; border:1px solid #1f2a3d; border-radius:14px; padding:11px 12px; min-height:72px; }
.health-label { color:#94a3b8; font-size:.64rem; letter-spacing:.08em; text-transform:uppercase; font-weight:900; }
.health-value { color:#f8fafc; font-size:.98rem; font-weight:850; margin-top:6px; }
.health-sub { color:#64748b; font-size:.72rem; margin-top:2px; }
.timeline { display:grid; gap:8px; }
.timeline-item { background:#0d1422; border:1px solid #1f2a3d; border-radius:13px; padding:12px 14px; display:flex; justify-content:space-between; align-items:center; gap:12px; }
.timeline-item.buy { border-left:4px solid #22c55e; }
.timeline-item.sell { border-left:4px solid #ef4444; }
.timeline-item.signal { border-left:4px solid #38bdf8; }
.timeline-left { display:flex; align-items:center; gap:12px; }
.timeline-tag { font-size:.64rem; font-weight:950; letter-spacing:.06em; padding:5px 9px; border-radius:7px; white-space:nowrap; }
.timeline-tag.buy { background:#052e26; color:#86efac; }
.timeline-tag.sell { background:#3f0a0a; color:#fca5a5; }
.timeline-tag.signal { background:#0c1e33; color:#bfdbfe; }
.timeline-main { color:#f1f5f9; font-size:.92rem; font-weight:650; }
.timeline-sub { color:#64748b; font-size:.74rem; margin-top:2px; }
.audit-table-wrap { background:#0d1422; border:1px solid #1f2a3d; border-radius:14px; padding:10px; overflow-x:auto; margin-bottom:12px; }
table.audit-table { border-collapse:collapse; width:100%; min-width:850px; font-size:.74rem; }
.audit-table th { color:#94a3b8; background:#111827; border-bottom:1px solid #263247; padding:8px; text-align:left; text-transform:uppercase; letter-spacing:.05em; font-size:.61rem; white-space:nowrap; }
.audit-table td { color:#dbe4f0; border-bottom:1px solid #1f2a3d; padding:8px; vertical-align:top; }
.audit-table tr:last-child td { border-bottom:0; }
.audit-note { color:#64748b; font-size:.75rem; margin:4px 0 10px 0; }
.small { color:#94a3b8; font-size:.76rem; }
.mono { font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; }
@media (max-width:1200px) { .command-deck { grid-template-columns:repeat(2,1fr); } .position-grid { grid-template-columns:repeat(2,1fr); } }
@media (max-width:760px) { .command-deck,.position-grid { grid-template-columns:1fr; } .brand-row { flex-direction:column; align-items:flex-start; } .stat-grid { grid-template-columns:repeat(2,1fr); } .primary .command-value { font-size:1.72rem; } .comp-legend { gap:12px; } .comp-item { min-width:42%; } }
</style>
""",
    unsafe_allow_html=True,
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_jsonl(path: Path, n: int = 800) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-n:]:
        if line.strip():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def parse_ts(value: Any) -> pd.Timestamp | None:
    if not value:
        return None
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    return None if pd.isna(ts) else ts


def age_seconds(ts: pd.Timestamp | None) -> int | None:
    if ts is None:
        return None
    return max(0, int((pd.Timestamp.now(tz="UTC") - ts).total_seconds()))


def age_text(ts: pd.Timestamp | None) -> str:
    seconds = age_seconds(ts)
    if seconds is None:
        return "unknown"
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
        x = float(v)
        if abs(x) < 0.005:
            x = 0.0
        return f"${x:,.2f}"
    except Exception:
        return "—"


def signed_money(v: Any) -> str:
    try:
        x = float(v)
        if abs(x) < 0.005:
            x = 0.0
        sign = "+" if x >= 0 else "-"
        return f"{sign}${abs(x):,.2f}"
    except Exception:
        return "—"


def pct(v: Any, d: int = 1) -> str:
    try:
        return f"{float(v):.{d}%}"
    except Exception:
        return "—"


def signed_pct(v: Any, d: int = 2) -> str:
    try:
        x = float(v)
        if abs(x) < 0.00005:
            x = 0.0
        sign = "+" if x >= 0 else ""
        return f"{sign}{x:.{d}%}"
    except Exception:
        return "—"


def num(v: Any, d: int = 4) -> str:
    try:
        x = float(v)
        if abs(x) < 10 ** (-(d + 1)):
            x = 0.0
        return f"{x:,.{d}f}"
    except Exception:
        return "—"


def esc(v: Any) -> str:
    return html.escape("" if v is None else str(v))


def css_class_for_value(value: float) -> str:
    if value > 0:
        return "good"
    if value < 0:
        return "bad"
    return "muted"


def status_badge(label: str, status: str) -> str:
    return f'<span class="badge {status}">{esc(label)}</span>'


def regime_badge(regime: str) -> str:
    label, klass = REGIME_DISPLAY.get(regime or "UNKNOWN", (regime or "Unknown", "regime-neutral"))
    return f'<span class="regime {klass}">{esc(label)}</span>'


def sleeve_status(action: str | None, position_open: bool) -> tuple[str, str, str]:
    """Map raw strategy action + position state to an operator-facing status.

    Returns (label, css_key, headline_verb).
    """
    a = (action or "").upper()
    if "ENTER" in a:
        return "ENTERING", "entering", "Entering"
    if "EXIT" in a:
        return "EXITING", "exiting", "Exiting"
    if position_open:
        return "HOLDING", "holding", "Holding"
    return "FLAT", "flat", "Flat"


def display_cell(key: str, value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    money_keys = {"nav", "today_pnl", "unrealized_pnl", "realized_pnl", "cost_basis", "avg_entry", "cash", "position_value", "price", "last_fill_price", "fee", "slippage_cost", "notional", "market_value"}
    pct_keys = {"target_weight", "actual_weight", "drift", "contribution", "unrealized_return", "exposure", "target_exposure", "confidence"}
    if key in money_keys:
        return signed_money(value) if key in {"today_pnl", "unrealized_pnl", "realized_pnl"} else money(value)
    if key in pct_keys:
        return signed_pct(value) if key in {"drift", "contribution", "unrealized_return"} else pct(value)
    if isinstance(value, float):
        return num(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (dict, list, tuple)):
        return esc(json.dumps(value, default=str, sort_keys=True))
    text = str(value)
    return "—" if text.strip() == "" else esc(text)


def html_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]], empty: str) -> str:
    if not rows:
        return f'<div class="audit-note">{esc(empty)}</div>'
    head = "".join(f"<th>{esc(label)}</th>" for _, label in columns)
    body = ""
    for row in rows:
        body += "<tr>" + "".join(f"<td>{display_cell(key, row.get(key))}</td>" for key, _ in columns) + "</tr>"
    return f'<div class="audit-table-wrap"><table class="audit-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def intraday_nav_baseline(events: list[dict[str, Any]]) -> tuple[float | None, int]:
    today = pd.Timestamp.now(tz="UTC").date()
    today_events = []
    for e in events:
        ts = parse_ts(e.get("timestamp"))
        if ts is not None and ts.date() == today and e.get("total_nav") is not None:
            today_events.append(e)
    if not today_events:
        return None, 0
    return float(today_events[0].get("total_nav")), len(today_events)


def latest_same_day_navs(events: list[dict[str, Any]]) -> dict[str, float]:
    today = pd.Timestamp.now(tz="UTC").date()
    for e in events:
        ts = parse_ts(e.get("timestamp"))
        if ts is not None and ts.date() == today and e.get("sleeve_navs"):
            return {k: float(v) for k, v in e.get("sleeve_navs", {}).items()}
    return {}


def nav_chart(events: list[dict[str, Any]], fills: list[dict[str, Any]]) -> go.Figure | None:
    if not events:
        return None
    hist = pd.DataFrame([{"timestamp": e.get("timestamp"), "nav": e.get("total_nav"), "drawdown": e.get("drawdown_frac")} for e in events])
    hist["timestamp"] = pd.to_datetime(hist["timestamp"], utc=True, errors="coerce")
    hist = hist.dropna(subset=["timestamp"]).sort_values("timestamp")
    hist["nav"] = pd.to_numeric(hist["nav"], errors="coerce")
    hist = hist.dropna(subset=["nav"])
    if hist.empty:
        return None
    if "drawdown" not in hist or hist["drawdown"].isna().all():
        running_peak = hist["nav"].cummax()
        hist["drawdown"] = hist["nav"] / running_peak - 1.0

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.74, 0.26], vertical_spacing=0.04)
    fig.add_trace(
        go.Scatter(
            x=hist["timestamp"], y=hist["nav"], mode="lines", name="NAV",
            line=dict(color="#38bdf8", width=2.4), fill="tozeroy", fillcolor="rgba(56,189,248,0.10)",
            hovertemplate="%{x|%b %d %H:%M}<br>NAV $%{y:,.2f}<extra></extra>",
        ),
        row=1, col=1,
    )

    fill_df = pd.DataFrame(fills)
    if not fill_df.empty and "timestamp" in fill_df:
        fill_df["timestamp"] = pd.to_datetime(fill_df["timestamp"], utc=True, errors="coerce")
        fill_df = fill_df.dropna(subset=["timestamp"]).sort_values("timestamp")
        merged = pd.merge_asof(fill_df, hist[["timestamp", "nav"]], on="timestamp", direction="nearest")
        for side, color, symbol in (("BUY", "#22c55e", "triangle-up"), ("SELL", "#ef4444", "triangle-down")):
            side_rows = merged[merged["side"].astype(str).str.upper() == side]
            if side_rows.empty:
                continue
            fig.add_trace(
                go.Scatter(
                    x=side_rows["timestamp"], y=side_rows["nav"], mode="markers", name=side,
                    marker=dict(color=color, size=10, symbol=symbol, line=dict(color="#05070c", width=1)),
                    customdata=side_rows[["sleeve", "qty", "price"]].to_numpy() if {"sleeve", "qty", "price"}.issubset(side_rows.columns) else None,
                    hovertemplate=(f"{side} %{{customdata[0]}}<br>qty %{{customdata[1]:.4f}} @ $%{{customdata[2]:,.2f}}<extra></extra>" if {"sleeve", "qty", "price"}.issubset(side_rows.columns) else f"{side}<extra></extra>"),
                ),
                row=1, col=1,
            )

    fig.add_trace(
        go.Scatter(
            x=hist["timestamp"], y=hist["drawdown"], mode="lines", name="Drawdown",
            line=dict(color="#ef4444", width=1.4), fill="tozeroy", fillcolor="rgba(239,68,68,0.16)",
            hovertemplate="%{x|%b %d %H:%M}<br>Drawdown %{y:.2%}<extra></extra>",
        ),
        row=2, col=1,
    )

    fig.update_layout(
        showlegend=False,
        margin=dict(l=6, r=6, t=10, b=6),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94a3b8", size=11, family="ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace"),
        hoverlabel=dict(bgcolor="#111827", font_size=12, font_color="#e5e7eb", bordercolor="#1f2a3d"),
        hovermode="x unified",
        height=380,
    )
    fig.update_xaxes(showgrid=False, showspikes=True, spikemode="across", spikecolor="#334155", spikethickness=1, row=1, col=1)
    fig.update_xaxes(showgrid=False, row=2, col=1)
    fig.update_yaxes(showgrid=True, gridcolor="#182235", tickprefix="$", tickformat=",.0f", row=1, col=1)
    fig.update_yaxes(showgrid=True, gridcolor="#182235", tickformat=".1%", nticks=4, row=2, col=1)
    return fig


state = read_json(STATE_PATH)
events = read_jsonl(SIGNALS_LOG)
fills = read_jsonl(FILLS_LOG)
errors = read_jsonl(ERROR_LOG, 100)
audit_report = read_json(AUDIT_REPORT_PATH)
last = events[-1] if events else {}
last_ts = parse_ts(state.get("last_cycle_at") or last.get("timestamp"))
last_age_seconds = age_seconds(last_ts)
is_stale = last_age_seconds is None or last_age_seconds > STALE_AFTER_SECONDS
missing_sleeves = sorted(set(EXPECTED_WEIGHTS) - set(state.get("sleeves", {})))
state_is_v2 = state.get("version") == "core_v1_paper_runtime_v2"

sleeves = state.get("sleeves", {})
sleeve_navs = state.get("sleeve_navs", {})
sleeve_telemetry = state.get("sleeve_telemetry", {})
capital = float(state.get("capital") or DEFAULT_CAPITAL)
total_nav = float(state.get("last_total_nav") or last.get("total_nav") or sum(float(v) for v in sleeve_navs.values()) or 0.0)
since_inception_pnl = total_nav - capital if total_nav else 0.0
since_inception_return = since_inception_pnl / capital if capital else 0.0
intraday_base, intraday_count = intraday_nav_baseline(events)
intraday_pnl = total_nav - intraday_base if intraday_base and intraday_count > 1 else None
intraday_return = intraday_pnl / intraday_base if intraday_pnl is not None and intraday_base else None
fees_total = float(state.get("realized_fees") or last.get("fees_total") or 0.0)
slippage_total = float(state.get("realized_slippage") or last.get("slippage_total") or 0.0)
realized_pnl = float(state.get("realized_pnl") or last.get("realized_pnl") or 0.0)
high_water_nav = float(state.get("high_water_nav") or max(total_nav, capital))
drawdown_frac = float(state.get("drawdown_frac") if state.get("drawdown_frac") is not None else (total_nav / high_water_nav - 1.0 if high_water_nav else 0.0))
latest_signals = {s.get("sleeve"): s for s in last.get("signals", [])}
latest_fills_by_sleeve: dict[str, dict[str, Any]] = {}
for fill in reversed(fills):
    label = fill.get("sleeve")
    if label and label not in latest_fills_by_sleeve:
        latest_fills_by_sleeve[label] = fill

day_start_sleeve_navs = latest_same_day_navs(events)
sleeve_rows: list[dict[str, Any]] = []
total_cash = 0.0
total_position_value = 0.0
total_cost_basis = 0.0
unrealized_pnl_total = 0.0
open_position_count = 0
class_value: dict[str, float] = {"Crypto": 0.0, "Equities": 0.0, "Gold": 0.0}
up_regime_open = 0

for label, target_w in EXPECTED_WEIGHTS.items():
    payload = sleeves.get(label, {})
    sig = latest_signals.get(label, {})
    tele = sleeve_telemetry.get(label, {})
    last_fill = latest_fills_by_sleeve.get(label, {})
    meta = SLEEVE_META.get(label)
    price = float(payload.get("last_price") or sig.get("price") or 0.0)
    qty = float(tele.get("qty") or payload.get("qty") or 0.0)
    cash = float(payload.get("cash") or 0.0)
    position_value = float(tele.get("position_value") or qty * price)
    nav = float(sleeve_navs.get(label) or cash + position_value)
    initial_capital = capital * target_w
    fallback_basis = initial_capital if abs(qty) > 1e-12 else 0.0
    cost_basis = float(tele.get("cost_basis") or payload.get("cost_basis") or fallback_basis)
    avg_entry = float(tele.get("avg_entry") or payload.get("avg_entry") or (cost_basis / qty if abs(qty) > 1e-12 and cost_basis > 0 else 0.0))
    unrealized_pnl = float(tele.get("unrealized_pnl") if tele.get("unrealized_pnl") is not None else (position_value - cost_basis if abs(qty) > 1e-12 else 0.0))
    unrealized_return = float(tele.get("unrealized_return") if tele.get("unrealized_return") is not None else (unrealized_pnl / cost_basis if cost_basis > 0 else 0.0))
    sleeve_realized = float(payload.get("realized_pnl") or sig.get("realized_pnl") or 0.0)
    action = sig.get("action") or payload.get("last_action") or "—"
    previous_action = sig.get("previous_action") or "—"
    action_changed = bool(sig.get("action_changed"))
    regime = sig.get("regime") or "UNKNOWN"
    reason = sig.get("reason") or "No signal recorded yet."
    actual_w = 0.0 if total_nav <= 0 else nav / total_nav
    exposure = 0.0 if nav <= 0 else position_value / nav
    drift = actual_w - target_w
    bar_ts = sig.get("bar_timestamp") or payload.get("last_timestamp") or "—"
    position_open = abs(qty) > 1e-12
    asset_class = ASSET_CLASS.get(meta.family if meta else "", "Equities")
    start_nav = day_start_sleeve_navs.get(label, nav)
    sleeve_today_pnl = nav - start_nav
    contribution = sleeve_today_pnl / capital if capital else 0.0
    total_cash += cash
    total_position_value += position_value
    total_cost_basis += cost_basis
    unrealized_pnl_total += unrealized_pnl
    class_value[asset_class] = class_value.get(asset_class, 0.0) + position_value
    if position_open:
        open_position_count += 1
        if regime == "TREND_UP":
            up_regime_open += 1
    sleeve_rows.append({
        "sleeve": label,
        "display": SLEEVE_NAMES[label],
        "asset_class": asset_class,
        "timeframe": meta.timeframe if meta else "—",
        "target_weight": target_w,
        "actual_weight": actual_w,
        "drift": drift,
        "nav": nav,
        "today_pnl": sleeve_today_pnl,
        "contribution": contribution,
        "cash": cash,
        "position_value": position_value,
        "cost_basis": cost_basis,
        "avg_entry": avg_entry,
        "qty": qty,
        "price": price,
        "exposure": exposure,
        "target_exposure": float(payload.get("last_target_exposure") or sig.get("target_exposure") or 0.0),
        "action": action,
        "previous_action": previous_action,
        "action_changed": action_changed,
        "regime": regime,
        "last_bar": bar_ts,
        "unrealized_pnl": unrealized_pnl,
        "unrealized_return": unrealized_return,
        "realized_pnl": sleeve_realized,
        "reason": reason,
        "position_open": position_open,
        "last_fill_side": last_fill.get("side"),
        "last_fill_ts": last_fill.get("timestamp"),
        "last_fill_price": last_fill.get("price"),
        "last_fill_qty": last_fill.get("qty"),
    })

total_cash = float(state.get("total_cash") if state.get("total_cash") is not None else total_cash)
total_position_value = float(state.get("total_position_value") if state.get("total_position_value") is not None else total_position_value)
total_cost_basis = float(state.get("total_cost_basis") if state.get("total_cost_basis") is not None else total_cost_basis)
unrealized_pnl_total = float(state.get("unrealized_pnl") if state.get("unrealized_pnl") is not None else unrealized_pnl_total)
open_position_count = int(state.get("open_position_count") if state.get("open_position_count") is not None else open_position_count)
cash_pct = total_cash / total_nav if total_nav else 0.0
invested_pct = total_position_value / total_nav if total_nav else 0.0

if invested_pct >= 0.60:
    posture_label, posture_status = "RISK ON", "ok"
elif invested_pct <= 0.25:
    posture_label, posture_status = "DEFENSIVE", "warn"
else:
    posture_label, posture_status = "BALANCED", "neutral"

audit_ts = parse_ts(audit_report.get("timestamp")) if audit_report else None
audit_age = age_seconds(audit_ts)
audit_available = bool(audit_report)
audit_ok = bool(audit_report.get("ok")) if audit_available else None
audit_stale = audit_available and audit_age is not None and audit_age > STALE_AUDIT_AFTER_SECONDS

issues: list[str] = []
if is_stale:
    issues.append(f"Runtime stale: last cycle {age_text(last_ts)}; expected every {EXPECTED_POLL_SECONDS}s.")
if missing_sleeves:
    issues.append(f"Missing sleeves in state: {', '.join(missing_sleeves)}.")
if errors:
    issues.append(f"Latest runtime error: {errors[-1].get('error', 'unknown error')}")
if not state_is_v2:
    issues.append("Runtime has not completed a v2 telemetry cycle yet.")
if audit_available and not audit_ok:
    issues.append(f"Price/accounting audit failing: {audit_report.get('failures', ['unknown'])[0]}")
if audit_stale:
    issues.append(f"Audit report stale: last run {age_text(audit_ts)}.")
health_status = "err" if is_stale or missing_sleeves or (audit_available and not audit_ok) else "warn" if errors or not state_is_v2 or audit_stale else "ok"
health_label = "ALERT" if health_status == "err" else "CHECK" if health_status == "warn" else "VERIFIED"

st.markdown(
    f"""
<div class="brand-row">
  <div>
    <div class="brand-kicker">Itera Dynamics</div>
    <div class="brand-title">Core v1 Mission Control</div>
    <div class="brand-sub">Paper portfolio · <span class="mono">{SCENARIO}</span></div>
  </div>
  <div class="badges">{status_badge(health_label, health_status)}{status_badge(posture_label, posture_status)}{status_badge('PAPER', 'neutral')}</div>
</div>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# 1. Am I making money? — command deck + NAV / drawdown chart
# ---------------------------------------------------------------------------
primary_class = css_class_for_value(since_inception_pnl)
today_value = signed_money(intraday_pnl) if intraday_pnl is not None else "Awaiting baseline"
today_sub = signed_pct(intraday_return) if intraday_return is not None else "after next cycle"
today_class = css_class_for_value(intraday_pnl or 0.0) if intraday_pnl is not None else "muted"
since_class = css_class_for_value(since_inception_pnl)
unrealized_class = css_class_for_value(unrealized_pnl_total)
drawdown_class = "bad" if drawdown_frac < -0.0005 else "muted"
drawdown_value = signed_pct(drawdown_frac, 1) if total_nav > 0 else "—"
drawdown_sub = f"Peak {money(high_water_nav)}" if total_nav > 0 else "Awaiting first cycle"
command_cards = [
    ("Portfolio NAV", money(total_nav), f"{open_position_count} open · cycle {state.get('cycle', last.get('cycle', 0))}", "primary", "white"),
    ("Intraday P&L", today_value, today_sub, "", today_class),
    ("Since Inception", signed_money(since_inception_pnl), signed_pct(since_inception_return), "", since_class),
    ("Drawdown", drawdown_value, drawdown_sub, "", drawdown_class if total_nav > 0 else "muted"),
    ("Unrealized", signed_money(unrealized_pnl_total), f"Basis {money(total_cost_basis)}", "", unrealized_class),
]
command_html = '<div class="command-deck">'
for label, value, sub, extra, value_class in command_cards:
    command_html += f'<div class="command-card {extra}"><div class="command-label">{esc(label)}</div><div class="command-value {value_class}">{value}</div><div class="command-sub">{sub}</div></div>'
command_html += "</div>"
st.markdown(command_html, unsafe_allow_html=True)

if issues:
    alert_class = "alert-err" if health_status == "err" else "alert-warn"
    alert_text = " · ".join(issues)
    alert_right = "Action required" if health_status == "err" else "Review"
else:
    alert_class = "alert-ok"
    alert_text = "✓ No alerts. Runtime, data freshness, state, and audit all look healthy."
    alert_right = "All clear"
st.markdown(f'<div class="alert-line {alert_class}"><span>{esc(alert_text)}</span><span class="mono">{esc(alert_right)}</span></div>', unsafe_allow_html=True)

st.markdown('<div class="section-head"><div><div class="section-title">Portfolio NAV</div><div class="section-sub">Equity curve with drawdown and trade markers.</div></div></div>', unsafe_allow_html=True)
fig = nav_chart(events, fills)
if fig is not None:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)
else:
    st.info("No NAV history yet.")

# ---------------------------------------------------------------------------
# 2. What do I own? — portfolio composition
# ---------------------------------------------------------------------------
st.markdown('<div class="section-head"><div><div class="section-title">Portfolio Composition</div><div class="section-sub">Where capital is deployed right now.</div></div></div>', unsafe_allow_html=True)
composition = [("Crypto", class_value.get("Crypto", 0.0)), ("Equities", class_value.get("Equities", 0.0)), ("Gold", class_value.get("Gold", 0.0)), ("Cash", total_cash)]
comp_bar = '<div class="comp-bar">'
for name, value in composition:
    w = 0.0 if total_nav <= 0 else max(0.0, value) / total_nav * 100.0
    comp_bar += f'<div class="comp-seg" style="width:{w:.2f}%;background:{ASSET_CLASS_COLOR[name]}"></div>'
comp_bar += "</div>"
comp_legend = '<div class="comp-legend">'
for name, value in composition:
    w = 0.0 if total_nav <= 0 else value / total_nav
    comp_legend += (
        f'<div class="comp-item"><div class="comp-dot-row"><span class="comp-dot" style="background:{ASSET_CLASS_COLOR[name]}"></span>'
        f'<span class="comp-name">{esc(name)}</span></div><div class="comp-value">{pct(w, 1)}</div><div class="comp-sub">{money(value)}</div></div>'
    )
comp_legend += "</div>"
st.markdown(f'<div class="posture-card">{comp_bar}{comp_legend}</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 3. Why do I own it? — position cards
# ---------------------------------------------------------------------------
st.markdown('<div class="section-head"><div><div class="section-title">Positions</div><div class="section-sub">Own it, explain it, monitor it. Details move into diagnostics.</div></div></div>', unsafe_allow_html=True)
position_html = '<div class="position-grid">'
for row in sleeve_rows:
    is_open = bool(row["position_open"])
    state_label, state_key, verb = sleeve_status(row["action"], is_open)
    card_class = f"position-card {state_key}"
    pnl_value = float(row["unrealized_pnl"] if is_open else row["today_pnl"])
    pnl_cls = css_class_for_value(pnl_value)
    headline = signed_money(row["unrealized_pnl"]) if is_open else "FLAT"
    headline_sub = f"Unrealized · {signed_pct(row['unrealized_return'])}" if is_open else f"Cash {money(row['cash'])}"
    last_fill = "—"
    if row.get("last_fill_side"):
        last_fill = f"{row['last_fill_side']} {num(row.get('last_fill_qty'), 4)} @ {money(row.get('last_fill_price'))}"
    actual_pct = max(0.0, min(100.0, float(row["actual_weight"]) * 100.0))
    target_pct = max(0.0, min(100.0, float(row["target_weight"]) * 100.0))
    primary_detail_1 = num(row["qty"], 4) if is_open else "—"
    primary_detail_2 = money(row["avg_entry"]) if row["avg_entry"] else "—"
    position_html += f"""
<div class="{card_class}">
  <div class="position-top">
    <div>
      <div class="position-name">{esc(row['display'])}</div>
      <div class="position-meta">{esc(row['asset_class'])} · {esc(row['timeframe'])} · target {pct(row['target_weight'])}</div>
    </div>
    <div class="badges">{regime_badge(row['regime'])}<span class="state-chip state-{state_key}">{esc(state_label)}</span></div>
  </div>
  <div class="reason-line"><b>{esc(verb)}</b> — {esc(row['reason'])}</div>
  <div class="position-pnl {pnl_cls}">{headline}</div>
  <div class="position-pnl-sub">{headline_sub}</div>
  <div class="alloc-wrap">
    <div class="alloc-top"><span>Allocation {pct(row['actual_weight'], 1)}</span><span>Target {pct(row['target_weight'], 1)}</span></div>
    <div class="alloc-meter"><div class="alloc-fill" style="width:{actual_pct:.1f}%"></div><div class="target-pin" style="left:{target_pct:.1f}%"></div></div>
  </div>
  <div class="stat-grid">
    <div class="stat"><div class="stat-label">Now</div><div class="stat-value">{money(row['price'])}</div></div>
    <div class="stat"><div class="stat-label">Intraday</div><div class="stat-value {css_class_for_value(float(row['today_pnl']))}">{signed_money(row['today_pnl'])}</div></div>
    <div class="stat"><div class="stat-label">Market value</div><div class="stat-value">{money(row['position_value']) if is_open else money(row['cash'])}</div></div>
    <div class="stat"><div class="stat-label">Qty</div><div class="stat-value">{primary_detail_1}</div></div>
    <div class="stat"><div class="stat-label">Avg entry</div><div class="stat-value">{primary_detail_2}</div></div>
    <div class="stat"><div class="stat-label">Realized</div><div class="stat-value {css_class_for_value(float(row['realized_pnl']))}">{signed_money(row['realized_pnl'])}</div></div>
  </div>
  <div class="position-line"><span>Last fill: <span class="mono">{esc(last_fill)}</span></span><span>Drift: <span class="mono">{signed_pct(row['drift'], 1)}</span></span></div>
  <div class="small" style="margin-top:8px;">Last bar: <span class="mono">{esc(row['last_bar'])}</span></div>
</div>
"""
position_html += "</div>"
st.markdown(position_html, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 4. What changed? — activity / flight recorder
# ---------------------------------------------------------------------------
st.markdown('<div class="section-head"><div><div class="section-title">Activity / Flight Recorder</div><div class="section-sub">Trade tape and decision changes, newest first.</div></div></div>', unsafe_allow_html=True)
activity: list[dict[str, Any]] = []
for row in sleeve_rows:
    if row["action_changed"]:
        activity.append({"kind": "signal", "when": last.get("timestamp") or state.get("last_cycle_at"), "sleeve": row["display"], "event": f"{row['previous_action']} → {row['action']}", "detail": row["reason"]})
for f in fills[-12:][::-1]:
    side = str(f.get("side") or "").upper()
    kind = "buy" if side == "BUY" else "sell" if side == "SELL" else "signal"
    activity.append({"kind": kind, "when": f.get("timestamp"), "sleeve": SLEEVE_NAMES.get(f.get("sleeve"), f.get("sleeve")), "event": f"{num(f.get('qty'), 4)} @ {money(f.get('price'))}", "detail": f"notional {money(f.get('notional'))} · fee {money(f.get('fee'))} · slippage {money(f.get('slippage_cost'))} · realized {signed_money(f.get('realized_pnl', 0.0))}"})
if activity:
    timeline_html = '<div class="timeline">'
    for item in activity[:12]:
        tag = item["kind"].upper() if item["kind"] in ("buy", "sell") else "SIGNAL"
        timeline_html += (
            f'<div class="timeline-item {esc(item["kind"])}"><div class="timeline-left">'
            f'<span class="timeline-tag {esc(item["kind"])}">{esc(tag)}</span>'
            f'<div><div class="timeline-main"><b>{esc(item["sleeve"])}</b> · {esc(item["event"])}</div><div class="timeline-sub">{esc(item["detail"])}</div></div>'
            f'</div><div class="timeline-sub mono">{esc(item["when"])}</div></div>'
        )
    timeline_html += "</div>"
    st.markdown(timeline_html, unsafe_allow_html=True)
else:
    st.markdown('<div class="audit-note">No signal changes or fills in the latest activity window.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 5. Is everything healthy? — operational status
# ---------------------------------------------------------------------------
st.markdown('<div class="section-head"><div><div class="section-title">System Health</div><div class="section-sub">Operational status, separated from portfolio performance.</div></div></div>', unsafe_allow_html=True)
if not audit_available:
    audit_value, audit_klass, audit_sub = "PENDING", "neutral", "No audit report found yet"
elif not audit_ok:
    audit_value, audit_klass, audit_sub = "FAIL", "err", f"last run {age_text(audit_ts)}"
elif audit_stale:
    audit_value, audit_klass, audit_sub = "STALE", "warn", f"last run {age_text(audit_ts)}"
else:
    audit_value, audit_klass, audit_sub = "PASS", "ok", f"last run {age_text(audit_ts)}"
checks = [
    ("Runtime", "OK" if not is_stale else "STALE", "ok" if not is_stale else "err", f"last {age_text(last_ts)}"),
    ("Market Data", "OK" if not missing_sleeves else "MISSING", "ok" if not missing_sleeves else "err", f"{len(EXPECTED_WEIGHTS) - len(missing_sleeves)}/{len(EXPECTED_WEIGHTS)} sleeves"),
    ("Price Audit", audit_value, audit_klass, audit_sub),
    ("Errors", "CLEAR" if not errors else "CHECK", "ok" if not errors else "warn", f"{len(errors)} logged"),
    ("Scheduler", "ON", "ok", f"poll {EXPECTED_POLL_SECONDS}s"),
    ("State Persistence", "V2" if state_is_v2 else "V1", "ok" if state_is_v2 else "warn", STATE_PATH.name),
    ("Cost & Fees", money(fees_total + slippage_total), "neutral", "fees + slippage to date"),
]
health_html = '<div class="health-grid">'
for label, value, klass, sub in checks:
    health_html += f'<div class="health-card"><div class="health-label">{esc(label)}</div><div class="health-value">{status_badge(value, klass)}</div><div class="health-sub">{esc(sub)}</div></div>'
health_html += "</div>"
st.markdown(health_html, unsafe_allow_html=True)

attribution_rows = sorted(sleeve_rows, key=lambda r: abs(float(r["today_pnl"])), reverse=True)
with st.expander("Diagnostics: attribution table", expanded=False):
    st.markdown(html_table(attribution_rows, [("display", "Sleeve"), ("today_pnl", "Intraday P&L"), ("contribution", "Contribution"), ("unrealized_pnl", "Unrealized"), ("realized_pnl", "Realized"), ("action", "Signal"), ("regime", "Regime"), ("reason", "Reason")], "No attribution data yet."), unsafe_allow_html=True)
with st.expander("Diagnostics: sleeve table", expanded=False):
    st.markdown(html_table(sleeve_rows, [("sleeve", "Sleeve"), ("action", "Signal"), ("previous_action", "Prev"), ("action_changed", "Changed"), ("regime", "Regime"), ("target_weight", "Target"), ("actual_weight", "Actual"), ("drift", "Drift"), ("nav", "NAV"), ("today_pnl", "Intraday"), ("unrealized_pnl", "Unrealized"), ("unrealized_return", "uReturn"), ("realized_pnl", "Realized"), ("cost_basis", "Basis"), ("avg_entry", "Avg entry"), ("cash", "Cash"), ("position_value", "Market value"), ("qty", "Qty"), ("price", "Price"), ("exposure", "Exposure"), ("last_fill_side", "Last fill"), ("last_fill_price", "Last fill px"), ("last_bar", "Last bar"), ("reason", "Reason")], "No sleeve rows yet."), unsafe_allow_html=True)
with st.expander("Diagnostics: fills and errors", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        st.caption("Recent fills")
        st.markdown(html_table(fills[-50:][::-1], [("timestamp", "Timestamp"), ("sleeve", "Sleeve"), ("asset", "Asset"), ("side", "Side"), ("qty", "Qty"), ("price", "Fill price"), ("mid", "Mid"), ("notional", "Notional"), ("fee", "Fee"), ("slippage_cost", "Slippage"), ("realized_pnl", "Realized P&L"), ("cost_basis_after", "Basis after"), ("avg_entry_after", "Avg entry after")], "No fills yet."), unsafe_allow_html=True)
    with c2:
        st.caption("Recent errors")
        st.markdown(html_table(errors[-50:][::-1], [("timestamp", "Timestamp"), ("version", "Version"), ("error", "Error")], "No runtime errors logged."), unsafe_allow_html=True)
with st.expander("Diagnostics: price audit report", expanded=False):
    if not audit_available:
        st.markdown(f'<div class="audit-note">No audit report found at {esc(str(AUDIT_REPORT_PATH))}. Run <span class="mono">scripts/audit_core_v1_prices.py --json &gt; {esc(str(AUDIT_REPORT_PATH))}</span> on a schedule to populate this.</div>', unsafe_allow_html=True)
    else:
        st.markdown(html_table(audit_report.get("rows", []), [("sleeve", "Sleeve"), ("asset", "Asset"), ("state_price", "State price"), ("fresh_price", "Fresh price"), ("price_diff_pct", "Diff"), ("bar_age_hours", "Bar age (h)"), ("price_ok", "Price OK"), ("position_value_ok", "Value OK"), ("unrealized_ok", "uPnL OK"), ("avg_entry_ok", "Avg OK")], "No audit rows recorded."), unsafe_allow_html=True)

st.caption(f"State {STATE_PATH} · Signals {SIGNALS_LOG} · Fills {FILLS_LOG} · Generated {datetime.now(UTC).isoformat()}")
