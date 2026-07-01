#!/usr/bin/env python
"""Mission-control dashboard for the clean Core v1 paper runtime."""

from __future__ import annotations

import html
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
EXPECTED_POLL_SECONDS = int(os.getenv("CORE_V1_POLL_SECONDS", "3600"))
STALE_AFTER_SECONDS = int(os.getenv("CORE_V1_STALE_AFTER_SECONDS", str(EXPECTED_POLL_SECONDS * 2 + 300)))
REFRESH_SECONDS = int(os.getenv("CORE_V1_DASHBOARD_REFRESH_SECONDS", "30"))
DEFAULT_CAPITAL = float(os.getenv("CORE_V1_CAPITAL", "100000"))

SCENARIO = "candidate_btc1h_hedges_to_btc4h_gld_qqq"
EXPECTED_WEIGHTS = {
    "BTC_4H_trend": 0.150,
    "ETH_1H_trend": 0.100,
    "ETH_4H_trend": 0.100,
    "SPY_1D_equity": 0.175,
    "QQQ_1D_equity": 0.275,
    "GLD_1D_gold": 0.200,
}
SLEEVE_NAMES = {
    "BTC_4H_trend": "BTC 4H",
    "ETH_1H_trend": "ETH 1H",
    "ETH_4H_trend": "ETH 4H",
    "SPY_1D_equity": "SPY",
    "QQQ_1D_equity": "QQQ",
    "GLD_1D_gold": "GLD",
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
.command-deck { display:grid; grid-template-columns:1.48fr repeat(4, 1fr); gap:10px; margin:10px 0 12px 0; }
.command-card { background:linear-gradient(180deg,#111827 0%, #0b1220 100%); border:1px solid #1f2a3d; border-radius:18px; padding:16px; box-shadow:0 18px 40px rgba(0,0,0,.24); min-height:108px; }
.command-card.primary { background:linear-gradient(145deg,#132033 0%, #0b1220 62%, #07101d 100%); border-color:#334155; }
.command-label { color:#94a3b8; font-size:.66rem; letter-spacing:.09em; text-transform:uppercase; font-weight:900; }
.command-value { color:#f8fafc; font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; font-size:1.58rem; line-height:1.05; font-weight:950; margin-top:10px; }
.primary .command-value { font-size:2.12rem; }
.command-sub { color:#64748b; font-size:.76rem; margin-top:7px; }
.good { color:#86efac; } .bad { color:#fca5a5; } .muted { color:#94a3b8; } .white { color:#f8fafc; }
.alert-line { border-radius:14px; padding:10px 13px; margin:10px 0 16px 0; font-size:.83rem; display:flex; justify-content:space-between; align-items:center; gap:12px; }
.alert-ok { background:#052e26; border:1px solid #0f766e; color:#ccfbf1; }
.alert-warn { background:#3b2505; border:1px solid #b45309; color:#fde68a; }
.alert-err { background:#3f0a0a; border:1px solid #dc2626; color:#fecaca; }
.section-head { display:flex; justify-content:space-between; align-items:end; gap:12px; margin:18px 0 10px 0; }
.section-title { color:#f8fafc; font-size:1.08rem; font-weight:850; letter-spacing:-.025em; }
.section-sub { color:#64748b; font-size:.76rem; margin-top:2px; }
.position-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }
.position-card { background:linear-gradient(180deg,#111827,#0b1220); border:1px solid #1f2a3d; border-radius:20px; padding:17px; box-shadow:0 18px 40px rgba(0,0,0,.24); }
.position-card.open { border-color:#0f766e; box-shadow:0 0 0 1px rgba(15,118,110,.16), 0 18px 40px rgba(0,0,0,.24); }
.position-card.flat { opacity:.82; }
.position-card.exit { border-color:#7f1d1d; }
.position-top { display:flex; justify-content:space-between; gap:10px; align-items:flex-start; }
.position-name { color:#f8fafc; font-size:1.22rem; font-weight:950; letter-spacing:-.035em; }
.position-meta { color:#94a3b8; font-size:.72rem; margin-top:3px; }
.decision-line { color:#e5e7eb; font-size:.86rem; line-height:1.28; margin-top:13px; min-height:38px; }
.decision-line b { color:#f8fafc; }
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
.regime { display:inline-flex; border-radius:999px; padding:3px 7px; font-size:.62rem; font-weight:900; letter-spacing:.04em; }
.regime-up { background:#052e26; color:#99f6e4; border:1px solid #0f766e; }
.regime-down { background:#3f0a0a; color:#fecaca; border:1px solid #dc2626; }
.regime-vol { background:#162033; color:#bfdbfe; border:1px solid #334155; }
.signal-chip { font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; font-size:.72rem; font-weight:950; padding:5px 8px; border-radius:8px; }
.signal-long { background:#052e26; color:#99f6e4; }
.signal-flat { background:#1e293b; color:#cbd5e1; }
.signal-exit { background:#3f0a0a; color:#fecaca; }
.health-grid { display:grid; grid-template-columns:repeat(6,1fr); gap:10px; }
.health-card { background:#0d1422; border:1px solid #1f2a3d; border-radius:14px; padding:11px 12px; min-height:72px; }
.health-label { color:#94a3b8; font-size:.64rem; letter-spacing:.08em; text-transform:uppercase; font-weight:900; }
.health-value { color:#f8fafc; font-size:.98rem; font-weight:850; margin-top:6px; }
.health-sub { color:#64748b; font-size:.72rem; margin-top:2px; }
.timeline { display:grid; gap:8px; }
.timeline-item { background:#0d1422; border:1px solid #1f2a3d; border-radius:13px; padding:10px 12px; display:flex; justify-content:space-between; gap:12px; }
.timeline-item.buy { border-left:4px solid #22c55e; }
.timeline-item.sell { border-left:4px solid #ef4444; }
.timeline-item.signal { border-left:4px solid #38bdf8; }
.timeline-main { color:#e5e7eb; font-size:.82rem; }
.timeline-sub { color:#64748b; font-size:.72rem; margin-top:2px; }
.audit-table-wrap { background:#0d1422; border:1px solid #1f2a3d; border-radius:14px; padding:10px; overflow-x:auto; margin-bottom:12px; }
table.audit-table { border-collapse:collapse; width:100%; min-width:850px; font-size:.74rem; }
.audit-table th { color:#94a3b8; background:#111827; border-bottom:1px solid #263247; padding:8px; text-align:left; text-transform:uppercase; letter-spacing:.05em; font-size:.61rem; white-space:nowrap; }
.audit-table td { color:#dbe4f0; border-bottom:1px solid #1f2a3d; padding:8px; vertical-align:top; }
.audit-table tr:last-child td { border-bottom:0; }
.audit-note { color:#64748b; font-size:.75rem; margin:4px 0 10px 0; }
.small { color:#94a3b8; font-size:.76rem; }
.mono { font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; }
@media (max-width:1200px) { .command-deck { grid-template-columns:repeat(2,1fr); } .position-grid { grid-template-columns:repeat(2,1fr); } .health-grid { grid-template-columns:repeat(3,1fr); } }
@media (max-width:760px) { .command-deck,.position-grid,.health-grid { grid-template-columns:1fr; } .brand-row { flex-direction:column; align-items:flex-start; } .stat-grid { grid-template-columns:repeat(2,1fr); } .primary .command-value { font-size:1.72rem; } }
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


def signal_class(action: str | None) -> str:
    a = (action or "").upper()
    if "ENTER" in a or a == "HOLD":
        return "signal-long"
    if "EXIT" in a or "SELL" in a:
        return "signal-exit"
    return "signal-flat"


def regime_badge(regime: str) -> str:
    r = regime or "UNKNOWN"
    klass = "regime-up" if "UP" in r else "regime-down" if "DOWN" in r else "regime-vol"
    return f'<span class="regime {klass}">{esc(r)}</span>'


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


state = read_json(STATE_PATH)
events = read_jsonl(SIGNALS_LOG)
fills = read_jsonl(FILLS_LOG)
errors = read_jsonl(ERROR_LOG, 100)
last = events[-1] if events else {}
last_ts = parse_ts(state.get("last_cycle_at") or last.get("timestamp"))
last_age_seconds = None if last_ts is None else max(0, int((pd.Timestamp.now(tz="UTC") - last_ts).total_seconds()))
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

for label, target_w in EXPECTED_WEIGHTS.items():
    payload = sleeves.get(label, {})
    sig = latest_signals.get(label, {})
    tele = sleeve_telemetry.get(label, {})
    last_fill = latest_fills_by_sleeve.get(label, {})
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
    regime = sig.get("regime") or "—"
    reason = sig.get("reason") or "No signal recorded yet."
    actual_w = 0.0 if total_nav <= 0 else nav / total_nav
    exposure = 0.0 if nav <= 0 else position_value / nav
    drift = actual_w - target_w
    bar_ts = sig.get("bar_timestamp") or payload.get("last_timestamp") or "—"
    new_fill_this_cycle = bool(sig.get("fill"))
    position_open = abs(qty) > 1e-12
    position_state = "LONG" if position_open else "FLAT"
    start_nav = day_start_sleeve_navs.get(label, nav)
    sleeve_today_pnl = nav - start_nav
    contribution = sleeve_today_pnl / capital if capital else 0.0
    total_cash += cash
    total_position_value += position_value
    total_cost_basis += cost_basis
    unrealized_pnl_total += unrealized_pnl
    if position_open:
        open_position_count += 1
    sleeve_rows.append({
        "sleeve": label,
        "display": SLEEVE_NAMES[label],
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
        "new_fill_this_cycle": new_fill_this_cycle,
        "position_open": position_open,
        "position_state": position_state,
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

issues: list[str] = []
if is_stale:
    issues.append(f"Runtime stale: last cycle {age_text(last_ts)}; expected every {EXPECTED_POLL_SECONDS}s.")
if missing_sleeves:
    issues.append(f"Missing sleeves in state: {', '.join(missing_sleeves)}.")
if errors:
    issues.append(f"Latest runtime error: {errors[-1].get('error', 'unknown error')}")
if not state_is_v2:
    issues.append("Runtime has not completed a v2 telemetry cycle yet.")
health_status = "err" if is_stale or missing_sleeves else "warn" if errors or not state_is_v2 else "ok"
health_label = "ALERT" if health_status == "err" else "CHECK" if health_status == "warn" else "VERIFIED"

st.markdown(
    f"""
<div class="brand-row">
  <div>
    <div class="brand-kicker">Itera Dynamics</div>
    <div class="brand-title">Core v1 Mission Control</div>
    <div class="brand-sub">Paper portfolio · <span class="mono">{SCENARIO}</span></div>
  </div>
  <div class="badges">{status_badge(health_label, health_status)}{status_badge('PAPER', 'neutral')}</div>
</div>
""",
    unsafe_allow_html=True,
)

primary_class = css_class_for_value(since_inception_pnl)
today_value = signed_money(intraday_pnl) if intraday_pnl is not None else "Awaiting baseline"
today_sub = signed_pct(intraday_return) if intraday_return is not None else "after next cycle"
today_class = css_class_for_value(intraday_pnl or 0.0) if intraday_pnl is not None else "muted"
unrealized_class = css_class_for_value(unrealized_pnl_total)
command_cards = [
    ("Portfolio NAV", money(total_nav), f"Since inception <span class='{primary_class}'>{signed_money(since_inception_pnl)} · {signed_pct(since_inception_return)}</span>", "primary", "white"),
    ("Intraday", today_value, today_sub, "", today_class),
    ("Exposure", pct(invested_pct, 1), f"Cash {pct(cash_pct, 1)} · {open_position_count} open", "", "white"),
    ("Unrealized", signed_money(unrealized_pnl_total), f"Basis {money(total_cost_basis)}", "", unrealized_class),
    ("Heartbeat", age_text(last_ts), f"Cycle {state.get('cycle', last.get('cycle', 0))}", "", "white"),
]
command_html = '<div class="command-deck">'
for label, value, sub, extra, value_class in command_cards:
    command_html += f'<div class="command-card {extra}"><div class="command-label">{esc(label)}</div><div class="command-value {value_class}">{value}</div><div class="command-sub">{sub}</div></div>'
command_html += '</div>'
st.markdown(command_html, unsafe_allow_html=True)

if issues:
    alert_class = "alert-err" if health_status == "err" else "alert-warn"
    alert_text = " · ".join(issues)
    alert_right = "Action required" if health_status == "err" else "Review"
else:
    alert_class = "alert-ok"
    alert_text = "✓ No alerts. Runtime, data freshness, state, and sleeve set look healthy."
    alert_right = "All clear"
st.markdown(f'<div class="alert-line {alert_class}"><span>{esc(alert_text)}</span><span class="mono">{esc(alert_right)}</span></div>', unsafe_allow_html=True)

st.markdown('<div class="section-head"><div><div class="section-title">Positions</div><div class="section-sub">Own it, explain it, monitor it. Details move into diagnostics.</div></div></div>', unsafe_allow_html=True)
position_html = '<div class="position-grid">'
for row in sleeve_rows:
    is_open = bool(row["position_open"])
    is_exit = (row.get("action") or "").upper().startswith("EXIT") or float(row.get("today_pnl") or 0.0) < 0 and not is_open and row.get("last_fill_side") == "SELL"
    card_class = "position-card open" if is_open else "position-card exit" if is_exit else "position-card flat"
    pnl_value = float(row["unrealized_pnl"] if is_open else row["today_pnl"])
    pnl_cls = css_class_for_value(pnl_value)
    headline = signed_money(row["unrealized_pnl"]) if is_open else "FLAT"
    headline_sub = f"Unrealized · {signed_pct(row['unrealized_return'])}" if is_open else f"Cash {money(row['cash'])}"
    signal_cls = signal_class(row["action"])
    changed = " · changed" if row["action_changed"] else ""
    last_fill = "—"
    if row.get("last_fill_side"):
        last_fill = f"{row['last_fill_side']} {num(row.get('last_fill_qty'), 4)} @ {money(row.get('last_fill_price'))}"
    actual_pct = max(0.0, min(100.0, float(row["actual_weight"]) * 100.0))
    target_pct = max(0.0, min(100.0, float(row["target_weight"]) * 100.0))
    primary_detail_1 = num(row['qty'], 4) if is_open else "—"
    primary_detail_2 = money(row['avg_entry']) if row['avg_entry'] else "—"
    position_html += f"""
<div class="{card_class}">
  <div class="position-top">
    <div>
      <div class="position-name">{esc(row['display'])}</div>
      <div class="position-meta">{esc(row['sleeve'])} · target {pct(row['target_weight'])}{changed}</div>
    </div>
    <div class="badges"><span class="badge {'ok' if is_open else 'neutral'}">{esc(row['position_state'])}</span><span class="signal-chip {signal_cls}">{esc(row['action'])}</span></div>
  </div>
  <div class="decision-line"><b>{esc('Holding' if is_open else 'Flat')}</b> — {esc(row['reason'])}</div>
  <div class="position-pnl {pnl_cls}">{headline}</div>
  <div class="position-pnl-sub">{headline_sub}</div>
  <div class="alloc-wrap">
    <div class="alloc-top"><span>Allocation {pct(row['actual_weight'], 1)}</span><span>Target {pct(row['target_weight'], 1)}</span></div>
    <div class="alloc-meter"><div class="alloc-fill" style="width:{actual_pct:.1f}%"></div><div class="target-pin" style="left:{target_pct:.1f}%"></div></div>
  </div>
  <div class="stat-grid">
    <div class="stat"><div class="stat-label">Regime</div><div class="stat-value">{regime_badge(row['regime'])}</div></div>
    <div class="stat"><div class="stat-label">Now</div><div class="stat-value">{money(row['price'])}</div></div>
    <div class="stat"><div class="stat-label">Intraday</div><div class="stat-value {css_class_for_value(float(row['today_pnl']))}">{signed_money(row['today_pnl'])}</div></div>
    <div class="stat"><div class="stat-label">Qty</div><div class="stat-value">{primary_detail_1}</div></div>
    <div class="stat"><div class="stat-label">Avg</div><div class="stat-value">{primary_detail_2}</div></div>
    <div class="stat"><div class="stat-label">Value</div><div class="stat-value">{money(row['position_value']) if is_open else money(row['cash'])}</div></div>
  </div>
  <div class="position-line"><span>Last fill: <span class="mono">{esc(last_fill)}</span></span><span>Drift: <span class="mono">{signed_pct(row['drift'], 1)}</span></span></div>
  <div class="small" style="margin-top:8px;">Last bar: <span class="mono">{esc(row['last_bar'])}</span></div>
</div>
"""
position_html += '</div>'
st.markdown(position_html, unsafe_allow_html=True)

st.markdown('<div class="section-head"><div><div class="section-title">Activity / Flight Recorder</div><div class="section-sub">Trade tape and decision changes, color-coded.</div></div></div>', unsafe_allow_html=True)
activity: list[dict[str, Any]] = []
for row in sleeve_rows:
    if row["action_changed"]:
        activity.append({"kind": "signal", "when": last.get("timestamp") or state.get("last_cycle_at"), "sleeve": row["display"], "event": f"{row['previous_action']} → {row['action']}", "detail": row["reason"]})
for f in fills[-12:][::-1]:
    side = str(f.get("side") or "").upper()
    kind = "buy" if side == "BUY" else "sell" if side == "SELL" else "signal"
    activity.append({"kind": kind, "when": f.get("timestamp"), "sleeve": SLEEVE_NAMES.get(f.get("sleeve"), f.get("sleeve")), "event": f"{side} {num(f.get('qty'), 4)} @ {money(f.get('price'))}", "detail": f"notional {money(f.get('notional'))} · fee {money(f.get('fee'))} · slippage {money(f.get('slippage_cost'))} · realized {signed_money(f.get('realized_pnl', 0.0))}"})
if activity:
    timeline_html = '<div class="timeline">'
    for item in activity[:12]:
        timeline_html += f'<div class="timeline-item {esc(item["kind"])}"><div><div class="timeline-main"><b>{esc(item["sleeve"])}</b> · {esc(item["event"])}</div><div class="timeline-sub">{esc(item["detail"])}</div></div><div class="timeline-sub mono">{esc(item["when"])}</div></div>'
    timeline_html += '</div>'
    st.markdown(timeline_html, unsafe_allow_html=True)
else:
    st.markdown('<div class="audit-note">No signal changes or fills in the latest activity window.</div>', unsafe_allow_html=True)

st.markdown('<div class="section-head"><div><div class="section-title">System Health</div><div class="section-sub">Operational status separated from portfolio status.</div></div></div>', unsafe_allow_html=True)
checks = [
    ("Runtime", "OK" if not is_stale else "STALE", "ok" if not is_stale else "err", f"last {age_text(last_ts)}"),
    ("Data", "OK" if not missing_sleeves else "MISSING", "ok" if not missing_sleeves else "err", f"{len(EXPECTED_WEIGHTS) - len(missing_sleeves)}/{len(EXPECTED_WEIGHTS)} sleeves"),
    ("Errors", "CLEAR" if not errors else "CHECK", "ok" if not errors else "warn", f"{len(errors)} logged"),
    ("Scheduler", "ON", "ok", f"poll {EXPECTED_POLL_SECONDS}s"),
    ("State", "V2" if state_is_v2 else "V1", "ok" if state_is_v2 else "warn", STATE_PATH.name),
    ("Paper Runtime", f"Cycle {state.get('cycle', last.get('cycle', 0))}", "neutral", f"fees/slip {money(fees_total + slippage_total)}"),
]
health_html = '<div class="health-grid">'
for label, value, klass, sub in checks:
    health_html += f'<div class="health-card"><div class="health-label">{esc(label)}</div><div class="health-value">{status_badge(value, klass)}</div><div class="health-sub">{esc(sub)}</div></div>'
health_html += '</div>'
st.markdown(health_html, unsafe_allow_html=True)

left, right = st.columns([1.25, 1])
with left:
    st.markdown('<div class="section-head"><div><div class="section-title">Portfolio NAV</div><div class="section-sub">Equity curve; custom trade-marker chart comes next.</div></div></div>', unsafe_allow_html=True)
    if events:
        hist = pd.DataFrame([{"timestamp": e.get("timestamp"), "nav": e.get("total_nav"), "drawdown": e.get("drawdown_frac")} for e in events])
        hist["timestamp"] = pd.to_datetime(hist["timestamp"], utc=True, errors="coerce")
        hist = hist.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()
        if not hist.empty:
            st.line_chart(hist[["nav"]], use_container_width=True)
    else:
        st.info("No NAV history yet.")
with right:
    st.markdown('<div class="section-head"><div><div class="section-title">Allocation</div><div class="section-sub">Actual sleeve weights.</div></div></div>', unsafe_allow_html=True)
    alloc_df = pd.DataFrame(sleeve_rows)[["display", "actual_weight"]].set_index("display") if sleeve_rows else pd.DataFrame()
    if not alloc_df.empty:
        st.bar_chart(alloc_df, use_container_width=True)

attribution_rows = sorted(sleeve_rows, key=lambda r: abs(float(r["today_pnl"])), reverse=True)
with st.expander("Diagnostics: attribution table", expanded=False):
    st.markdown(html_table(attribution_rows, [("display", "Sleeve"), ("position_state", "Position"), ("today_pnl", "Intraday P&L"), ("contribution", "Contribution"), ("unrealized_pnl", "Unrealized"), ("realized_pnl", "Realized"), ("action", "Signal"), ("regime", "Regime"), ("reason", "Reason")], "No attribution data yet."), unsafe_allow_html=True)
with st.expander("Diagnostics: sleeve table", expanded=False):
    st.markdown(html_table(sleeve_rows, [("display", "Sleeve"), ("position_state", "Position"), ("action", "Signal"), ("previous_action", "Prev"), ("action_changed", "Changed"), ("regime", "Regime"), ("target_weight", "Target"), ("actual_weight", "Actual"), ("drift", "Drift"), ("nav", "NAV"), ("today_pnl", "Intraday"), ("unrealized_pnl", "Unrealized"), ("unrealized_return", "uReturn"), ("realized_pnl", "Realized"), ("cost_basis", "Basis"), ("avg_entry", "Avg entry"), ("cash", "Cash"), ("position_value", "Market value"), ("qty", "Qty"), ("price", "Price"), ("exposure", "Exposure"), ("last_fill_side", "Last fill"), ("last_fill_price", "Last fill px"), ("new_fill_this_cycle", "New fill"), ("last_bar", "Last bar"), ("reason", "Reason")], "No sleeve rows yet."), unsafe_allow_html=True)
with st.expander("Diagnostics: fills and errors", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        st.caption("Recent fills")
        st.markdown(html_table(fills[-50:][::-1], [("timestamp", "Timestamp"), ("sleeve", "Sleeve"), ("asset", "Asset"), ("side", "Side"), ("qty", "Qty"), ("price", "Fill price"), ("mid", "Mid"), ("notional", "Notional"), ("fee", "Fee"), ("slippage_cost", "Slippage"), ("realized_pnl", "Realized P&L"), ("cost_basis_after", "Basis after"), ("avg_entry_after", "Avg entry after")], "No fills yet."), unsafe_allow_html=True)
    with c2:
        st.caption("Recent errors")
        st.markdown(html_table(errors[-50:][::-1], [("timestamp", "Timestamp"), ("version", "Version"), ("error", "Error")], "No runtime errors logged."), unsafe_allow_html=True)

st.caption(f"State {STATE_PATH} · Signals {SIGNALS_LOG} · Fills {FILLS_LOG} · Generated {datetime.now(UTC).isoformat()}")
