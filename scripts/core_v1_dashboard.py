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
.stApp { background:#080c14; color:#e5e7eb; }
.block-container { padding-top:1.05rem; padding-bottom:2rem; max-width:1600px; }
#MainMenu, footer, header { visibility:hidden; height:0; }
[data-testid="stMetric"] { background:linear-gradient(180deg,#121a2a 0%,#0c1422 100%); border:1px solid #1f2a3d; border-radius:16px; padding:15px 16px; box-shadow:0 14px 35px rgba(0,0,0,.22); }
[data-testid="stMetricLabel"] { color:#94a3b8 !important; font-size:.68rem !important; letter-spacing:.08em; text-transform:uppercase; }
[data-testid="stMetricValue"] { color:#f8fafc !important; font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; font-size:1.38rem !important; }
.title-row { display:flex; justify-content:space-between; align-items:flex-start; gap:1rem; margin:0 0 14px 0; }
.brand { color:#64748b; font-size:.72rem; letter-spacing:.22em; font-weight:800; text-transform:uppercase; }
.title { color:#f8fafc; font-size:1.86rem; line-height:1.05; font-weight:800; letter-spacing:-.05em; margin-top:2px; }
.subtitle { color:#94a3b8; font-size:.83rem; margin-top:7px; }
.badges { display:flex; gap:8px; align-items:center; justify-content:flex-end; flex-wrap:wrap; }
.badge { display:inline-flex; align-items:center; gap:6px; border-radius:999px; padding:6px 11px; font-size:.68rem; letter-spacing:.07em; font-weight:850; text-transform:uppercase; white-space:nowrap; }
.ok { background:#052e26; color:#99f6e4; border:1px solid #0f766e; }
.warn { background:#3b2505; color:#fde68a; border:1px solid #b45309; }
.err { background:#3f0a0a; color:#fecaca; border:1px solid #dc2626; }
.neutral { background:#111827; color:#cbd5e1; border:1px solid #334155; }
.strip { display:grid; grid-template-columns:repeat(6,1fr); gap:10px; margin:4px 0 16px 0; }
.health-card { background:#0d1422; border:1px solid #1f2a3d; border-radius:14px; padding:11px 12px; min-height:72px; }
.health-label { color:#94a3b8; font-size:.66rem; letter-spacing:.08em; text-transform:uppercase; font-weight:850; }
.health-value { color:#f8fafc; font-size:1.02rem; font-weight:800; margin-top:6px; }
.health-sub { color:#64748b; font-size:.74rem; margin-top:2px; }
.attention { border:1px solid #334155; background:linear-gradient(180deg,#101827,#0b1220); border-radius:16px; padding:14px 16px; margin-bottom:16px; }
.attention h3 { margin:0 0 8px 0; font-size:.90rem; letter-spacing:.06em; text-transform:uppercase; color:#cbd5e1; }
.attention ul { margin:.35rem 0 0 1.1rem; color:#cbd5e1; }
.section-title { margin-top:10px; margin-bottom:10px; color:#f8fafc; font-size:1.05rem; font-weight:780; letter-spacing:-.02em; }
.pnl-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin:12px 0 18px 0; }
.pnl-card { background:linear-gradient(180deg,#101827,#0b1220); border:1px solid #1f2a3d; border-radius:16px; padding:14px 15px; }
.pnl-label { color:#94a3b8; font-size:.65rem; text-transform:uppercase; letter-spacing:.08em; font-weight:850; }
.pnl-value { color:#f8fafc; font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; font-size:1.20rem; font-weight:850; margin-top:6px; }
.pnl-sub { color:#64748b; font-size:.73rem; margin-top:4px; }
.good { color:#86efac; } .bad { color:#fca5a5; } .muted { color:#94a3b8; }
.sleeve-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }
.sleeve-card { background:linear-gradient(180deg,#111827,#0b1220); border:1px solid #1f2a3d; border-radius:18px; padding:15px; box-shadow:0 14px 35px rgba(0,0,0,.20); }
.sleeve-open { border-color:#0f766e; box-shadow:0 0 0 1px rgba(15,118,110,.16), 0 14px 35px rgba(0,0,0,.20); }
.sleeve-top { display:flex; justify-content:space-between; align-items:flex-start; gap:8px; margin-bottom:10px; }
.sleeve-name { font-size:1.12rem; color:#f8fafc; font-weight:850; letter-spacing:-.03em; }
.sleeve-meta { color:#94a3b8; font-size:.72rem; margin-top:2px; }
.action { font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; font-size:.76rem; font-weight:900; padding:5px 8px; border-radius:8px; }
.action-long { background:#052e26; color:#99f6e4; }
.action-flat { background:#1e293b; color:#cbd5e1; }
.action-exit { background:#3f0a0a; color:#fecaca; }
.position-open { background:#052e26; color:#99f6e4; border:1px solid #0f766e; }
.position-flat { background:#111827; color:#cbd5e1; border:1px solid #334155; }
.regime { display:inline-flex; border-radius:999px; padding:3px 7px; font-size:.64rem; font-weight:850; letter-spacing:.04em; }
.regime-up { background:#052e26; color:#99f6e4; border:1px solid #0f766e; }
.regime-down { background:#3f0a0a; color:#fecaca; border:1px solid #dc2626; }
.regime-vol { background:#162033; color:#bfdbfe; border:1px solid #334155; }
.kv { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin:10px 0; }
.kv div { background:#090f1a; border:1px solid #1e293b; border-radius:12px; padding:8px; }
.k { color:#64748b; font-size:.61rem; text-transform:uppercase; letter-spacing:.08em; font-weight:850; }
.v { color:#f8fafc; font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; font-size:.88rem; margin-top:3px; }
.position-line { display:flex; justify-content:space-between; gap:10px; color:#94a3b8; font-size:.75rem; border-top:1px solid #1f2a3d; padding-top:9px; margin-top:9px; }
.reason { color:#cbd5e1; font-size:.77rem; line-height:1.34; border-top:1px solid #1f2a3d; padding-top:10px; margin-top:10px; min-height:45px; }
.progress-outer { height:7px; background:#111827; border-radius:999px; overflow:hidden; margin-top:8px; border:1px solid #1e293b; }
.progress-inner { height:100%; background:linear-gradient(90deg,#38bdf8,#22c55e); border-radius:999px; }
.audit-table-wrap { background:#0d1422; border:1px solid #1f2a3d; border-radius:14px; padding:10px; overflow-x:auto; margin-bottom:12px; }
table.audit-table { border-collapse:collapse; width:100%; min-width:850px; font-size:.75rem; }
.audit-table th { color:#94a3b8; background:#111827; border-bottom:1px solid #263247; padding:8px; text-align:left; text-transform:uppercase; letter-spacing:.05em; font-size:.63rem; white-space:nowrap; }
.audit-table td { color:#dbe4f0; border-bottom:1px solid #1f2a3d; padding:8px; vertical-align:top; }
.audit-table tr:last-child td { border-bottom:0; }
.audit-note { color:#64748b; font-size:.75rem; margin:4px 0 10px 0; }
.timeline { display:grid; gap:8px; }
.timeline-item { background:#0d1422; border:1px solid #1f2a3d; border-radius:12px; padding:10px 12px; display:flex; justify-content:space-between; gap:12px; }
.timeline-main { color:#e5e7eb; font-size:.82rem; }
.timeline-sub { color:#64748b; font-size:.72rem; margin-top:2px; }
.small { color:#94a3b8; font-size:.78rem; }
.mono { font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; }
@media (max-width:1000px) { .strip,.pnl-grid { grid-template-columns:repeat(2,1fr); } .sleeve-grid { grid-template-columns:1fr; } .title-row { flex-direction:column; } [data-testid="stMetricValue"] { font-size:1.12rem !important; } }
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
        return f"${float(v):,.2f}"
    except Exception:
        return "—"


def signed_money(v: Any) -> str:
    try:
        x = float(v)
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
        sign = "+" if x >= 0 else ""
        return f"{sign}{x:.{d}%}"
    except Exception:
        return "—"


def num(v: Any, d: int = 4) -> str:
    try:
        return f"{float(v):,.{d}f}"
    except Exception:
        return "—"


def esc(v: Any) -> str:
    return html.escape("" if v is None else str(v))


def cell(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return num(v, 4)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, (dict, list, tuple)):
        return esc(json.dumps(v, default=str, sort_keys=True))
    text = str(v)
    return "—" if text.strip() == "" else esc(text)


def html_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]], empty: str) -> str:
    if not rows:
        return f'<div class="audit-note">{esc(empty)}</div>'
    head = "".join(f"<th>{esc(label)}</th>" for key, label in columns)
    body = ""
    for row in rows:
        body += "<tr>" + "".join(f"<td>{cell(row.get(key))}</td>" for key, label in columns) + "</tr>"
    return f'<div class="audit-table-wrap"><table class="audit-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def status_badge(label: str, status: str) -> str:
    return f'<span class="badge {status}">{esc(label)}</span>'


def action_class(action: str | None) -> str:
    a = (action or "").upper()
    if "ENTER" in a or a == "HOLD":
        return "action-long"
    if "EXIT" in a or "SELL" in a:
        return "action-exit"
    return "action-flat"


def regime_badge(regime: str) -> str:
    r = regime or "UNKNOWN"
    klass = "regime-up" if "UP" in r else "regime-down" if "DOWN" in r else "regime-vol"
    return f'<span class="regime {klass}">{esc(r)}</span>'


def pnl_class(value: float) -> str:
    if value > 0:
        return "good"
    if value < 0:
        return "bad"
    return "muted"


state = read_json(STATE_PATH)
events = read_jsonl(SIGNALS_LOG)
fills = read_jsonl(FILLS_LOG)
errors = read_jsonl(ERROR_LOG, 100)
last = events[-1] if events else {}
last_ts = parse_ts(state.get("last_cycle_at") or last.get("timestamp"))
last_age_seconds = None if last_ts is None else max(0, int((pd.Timestamp.now(tz="UTC") - last_ts).total_seconds()))
is_stale = last_age_seconds is None or last_age_seconds > STALE_AFTER_SECONDS
missing_sleeves = sorted(set(EXPECTED_WEIGHTS) - set(state.get("sleeves", {})))
has_errors = bool(errors)
health = "err" if is_stale or missing_sleeves else "warn" if has_errors else "ok"
health_label = "ATTENTION" if health == "err" else "WARN" if health == "warn" else "HEALTHY"

sleeves = state.get("sleeves", {})
sleeve_navs = state.get("sleeve_navs", {})
sleeve_telemetry = state.get("sleeve_telemetry", {})
capital = float(state.get("capital") or DEFAULT_CAPITAL)
total_nav = float(state.get("last_total_nav") or last.get("total_nav") or sum(float(v) for v in sleeve_navs.values()) or 0.0)
since_inception_pnl = total_nav - capital if total_nav else 0.0
since_inception_return = since_inception_pnl / capital if capital else 0.0
fees_total = float(state.get("realized_fees") or last.get("fees_total") or 0.0)
slippage_total = float(state.get("realized_slippage") or last.get("slippage_total") or 0.0)
realized_pnl = float(state.get("realized_pnl") or last.get("realized_pnl") or 0.0)
today_pnl = float(state.get("today_pnl") or last.get("today_pnl") or 0.0)
today_return = float(state.get("today_return") or last.get("today_return") or 0.0)
latest_signals = {s.get("sleeve"): s for s in last.get("signals", [])}
latest_fills_by_sleeve: dict[str, dict[str, Any]] = {}
for fill in reversed(fills):
    label = fill.get("sleeve")
    if label and label not in latest_fills_by_sleeve:
        latest_fills_by_sleeve[label] = fill

today = pd.Timestamp.now(tz="UTC").date()
day_start_sleeve_navs: dict[str, float] = {}
for e in events:
    ts = parse_ts(e.get("timestamp"))
    if ts is not None and ts.date() == today and e.get("sleeve_navs"):
        day_start_sleeve_navs = {k: float(v) for k, v in e.get("sleeve_navs", {}).items()}
        break

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
    position_state = "OPEN LONG" if position_open else "FLAT"
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
        "initial_capital": initial_capital,
        "nav": nav,
        "pnl_since_start": nav - initial_capital,
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

total_cash = float(state.get("total_cash") or total_cash)
total_position_value = float(state.get("total_position_value") or total_position_value)
total_cost_basis = float(state.get("total_cost_basis") or total_cost_basis)
unrealized_pnl_total = float(state.get("unrealized_pnl") if state.get("unrealized_pnl") is not None else unrealized_pnl_total)
open_position_count = int(state.get("open_position_count") or open_position_count)
cash_pct = total_cash / total_nav if total_nav else 0.0
invested_pct = total_position_value / total_nav if total_nav else 0.0
exposure_pct = invested_pct

st.markdown(
    f"""
<div class="title-row">
  <div>
    <div class="brand">Itera Dynamics</div>
    <div class="title">Core v1 Mission Control</div>
    <div class="subtitle">Paper portfolio · <span class="mono">{SCENARIO}</span></div>
  </div>
  <div class="badges">{status_badge(health_label, health)}{status_badge('PAPER', 'neutral')}</div>
</div>
""",
    unsafe_allow_html=True,
)

checks = [
    ("Runtime", "OK" if not is_stale else "STALE", "ok" if not is_stale else "err", f"last {age_text(last_ts)}"),
    ("Data", "OK" if not missing_sleeves else "MISSING", "ok" if not missing_sleeves else "err", f"{len(EXPECTED_WEIGHTS) - len(missing_sleeves)}/{len(EXPECTED_WEIGHTS)} sleeves"),
    ("Errors", "CLEAR" if not has_errors else "CHECK", "ok" if not has_errors else "warn", f"{len(errors)} logged"),
    ("Scheduler", "ON", "ok", f"poll {EXPECTED_POLL_SECONDS}s"),
    ("Exposure", pct(exposure_pct, 1), "neutral", f"cash {pct(cash_pct, 1)}"),
    ("State", "V2" if state.get("version") == "core_v1_paper_runtime_v2" else "V1", "ok" if state.get("version") == "core_v1_paper_runtime_v2" else "warn", STATE_PATH.name),
]
strip_html = '<div class="strip">'
for label, value, klass, sub in checks:
    strip_html += f'<div class="health-card"><div class="health-label">{esc(label)}</div><div class="health-value">{status_badge(value, klass)}</div><div class="health-sub">{esc(sub)}</div></div>'
strip_html += '</div>'
st.markdown(strip_html, unsafe_allow_html=True)

issues: list[str] = []
if is_stale:
    issues.append(f"Paper runtime stale: last cycle {age_text(last_ts)}; expected every {EXPECTED_POLL_SECONDS}s.")
if missing_sleeves:
    issues.append(f"Missing sleeves in state: {', '.join(missing_sleeves)}.")
if errors:
    issues.append(f"Latest error: {errors[-1].get('error', 'unknown error')}")
if state.get("version") != "core_v1_paper_runtime_v2":
    issues.append("Runtime has not completed a v2 telemetry cycle yet. Cost basis / realized P&L will lock in after the next paper cycle.")
if not issues:
    issues.append("No actionable issues detected. Runtime, dashboard, state, and sleeve set look healthy.")
issue_items = ''.join(f"<li>{esc(x)}</li>" for x in issues)
st.markdown(f"<div class='attention'><h3>Attention</h3><ul>{issue_items}</ul></div>", unsafe_allow_html=True)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Portfolio NAV", money(total_nav))
m2.metric("Today", signed_money(today_pnl), signed_pct(today_return))
m3.metric("Since inception", signed_money(since_inception_pnl), signed_pct(since_inception_return))
m4.metric("Exposure", pct(exposure_pct, 1), f"Cash {pct(cash_pct, 1)}")
m5.metric("Last heartbeat", age_text(last_ts))

st.markdown('<div class="section-title">P&L / Exposure</div>', unsafe_allow_html=True)
pnl_html = '<div class="pnl-grid">'
pnl_cards = [
    ("Unrealized P&L", unrealized_pnl_total, "Open mark-to-market P&L against cost basis"),
    ("Realized P&L", realized_pnl, "Closed-trade P&L from paper ledger"),
    ("Cost basis", total_cost_basis, "Current open-position basis"),
    ("Invested value", total_position_value, f"{pct(invested_pct, 1)} of NAV · {open_position_count} open positions"),
    ("Cash", total_cash, f"{pct(cash_pct, 1)} of NAV"),
    ("Fees paid", -fees_total, "Paper commission/fee assumption from runtime config"),
    ("Slippage cost", -slippage_total, "Paper execution/slippage assumption from runtime config"),
    ("Capital base", capital, "Paper starting capital"),
]
for label, value, sub in pnl_cards:
    value_class = pnl_class(float(value)) if label in {"Unrealized P&L", "Realized P&L", "Fees paid", "Slippage cost"} else "muted"
    value_text = signed_money(value) if label in {"Unrealized P&L", "Realized P&L", "Fees paid", "Slippage cost"} else money(value)
    pnl_html += f'<div class="pnl-card"><div class="pnl-label">{esc(label)}</div><div class="pnl-value {value_class}">{esc(value_text)}</div><div class="pnl-sub">{esc(sub)}</div></div>'
pnl_html += '</div>'
st.markdown(pnl_html, unsafe_allow_html=True)

st.markdown('<div class="section-title">Today\'s Attribution</div>', unsafe_allow_html=True)
attribution_rows = sorted(sleeve_rows, key=lambda r: abs(float(r["today_pnl"])), reverse=True)
st.markdown(
    html_table(
        attribution_rows,
        [
            ("display", "Sleeve"), ("position_state", "Position"), ("today_pnl", "Today P&L"), ("contribution", "Contribution"),
            ("unrealized_pnl", "Unrealized"), ("realized_pnl", "Realized"), ("action", "Signal"), ("regime", "Regime"), ("reason", "Reason"),
        ],
        "No attribution data yet.",
    ),
    unsafe_allow_html=True,
)

st.markdown('<div class="section-title">Sleeves</div>', unsafe_allow_html=True)
card_html = '<div class="sleeve-grid">'
for row in sleeve_rows:
    action_css = action_class(row["action"])
    position_css = "position-open" if row["position_open"] else "position-flat"
    card_css = "sleeve-card sleeve-open" if row["position_open"] else "sleeve-card"
    pnl_css = pnl_class(float(row["unrealized_pnl"]))
    changed = " · changed" if row["action_changed"] else ""
    last_fill_text = "—"
    if row.get("last_fill_side"):
        last_fill_text = f"{row['last_fill_side']} {num(row.get('last_fill_qty'), 4)} @ {money(row.get('last_fill_price'))}"
    new_fill_text = "Yes" if row["new_fill_this_cycle"] else "No"
    card_html += f"""
<div class="{card_css}">
  <div class="sleeve-top">
    <div><div class="sleeve-name">{esc(row['display'])}</div><div class="sleeve-meta">{esc(row['sleeve'])} · target {pct(row['target_weight'])}{changed}</div></div>
    <div class="badges"><span class="badge {position_css}">{esc(row['position_state'])}</span><div class="action {action_css}">{esc(row['action'])}</div></div>
  </div>
  <div class="kv">
    <div><div class="k">Regime</div><div class="v">{regime_badge(row['regime'])}</div></div>
    <div><div class="k">Exposure</div><div class="v">{pct(row['exposure'],0)}</div></div>
    <div><div class="k">Drift</div><div class="v">{pct(row['drift'],1)}</div></div>
    <div><div class="k">Qty</div><div class="v">{num(row['qty'], 4) if row['position_open'] else '—'}</div></div>
    <div><div class="k">Avg entry</div><div class="v">{money(row['avg_entry']) if row['avg_entry'] else '—'}</div></div>
    <div><div class="k">Price</div><div class="v">{money(row['price'])}</div></div>
    <div><div class="k">Cost basis</div><div class="v">{money(row['cost_basis']) if row['position_open'] else '—'}</div></div>
    <div><div class="k">Market value</div><div class="v">{money(row['position_value']) if row['position_open'] else '—'}</div></div>
    <div><div class="k">Cash</div><div class="v">{money(row['cash'])}</div></div>
    <div><div class="k">uP&L</div><div class="v {pnl_css}">{signed_money(row['unrealized_pnl'])}</div></div>
    <div><div class="k">uReturn</div><div class="v {pnl_css}">{signed_pct(row['unrealized_return'])}</div></div>
    <div><div class="k">Today</div><div class="v {pnl_class(float(row['today_pnl']))}">{signed_money(row['today_pnl'])}</div></div>
  </div>
  <div class="progress-outer"><div class="progress-inner" style="width:{max(0, min(100, row['exposure']*100)):.1f}%"></div></div>
  <div class="position-line"><span>Last fill: <span class="mono">{esc(last_fill_text)}</span></span><span>New fill this cycle: <span class="mono">{esc(new_fill_text)}</span></span></div>
  <div class="reason">{esc(row['reason'])}</div>
  <div class="small" style="margin-top:8px;">Last bar: <span class="mono">{esc(row['last_bar'])}</span></div>
</div>
"""
card_html += '</div>'
st.markdown(card_html, unsafe_allow_html=True)

left, right = st.columns([1.25, 1])
with left:
    st.markdown('<div class="section-title">Portfolio NAV</div>', unsafe_allow_html=True)
    if events:
        hist = pd.DataFrame([
            {"timestamp": e.get("timestamp"), "nav": e.get("total_nav"), "drawdown": e.get("drawdown_frac"), "today_pnl": e.get("today_pnl")}
            for e in events
        ])
        hist["timestamp"] = pd.to_datetime(hist["timestamp"], utc=True, errors="coerce")
        hist = hist.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()
        if not hist.empty:
            st.line_chart(hist[["nav"]], use_container_width=True)
    else:
        st.info("No NAV history yet.")

with right:
    st.markdown('<div class="section-title">Allocation / Exposure</div>', unsafe_allow_html=True)
    alloc_df = pd.DataFrame(sleeve_rows)[["display", "actual_weight"]].set_index("display") if sleeve_rows else pd.DataFrame()
    if not alloc_df.empty:
        st.bar_chart(alloc_df, use_container_width=True)

st.markdown('<div class="section-title">Signal Changes / Activity</div>', unsafe_allow_html=True)
activity: list[dict[str, Any]] = []
for row in sleeve_rows:
    if row["action_changed"]:
        activity.append({"when": last.get("timestamp") or state.get("last_cycle_at"), "sleeve": row["display"], "event": f"{row['previous_action']} → {row['action']}", "detail": row["reason"]})
for f in fills[-8:][::-1]:
    activity.append({"when": f.get("timestamp"), "sleeve": SLEEVE_NAMES.get(f.get("sleeve"), f.get("sleeve")), "event": f"{f.get('side')} {num(f.get('qty'), 4)} @ {money(f.get('price'))}", "detail": f"notional {money(f.get('notional'))} · fee {money(f.get('fee'))} · slippage {money(f.get('slippage_cost'))}"})
if activity:
    timeline_html = '<div class="timeline">'
    for item in activity[:10]:
        timeline_html += f'<div class="timeline-item"><div><div class="timeline-main"><b>{esc(item["sleeve"])}</b> · {esc(item["event"])}</div><div class="timeline-sub">{esc(item["detail"])}</div></div><div class="timeline-sub mono">{esc(item["when"])}</div></div>'
    timeline_html += '</div>'
    st.markdown(timeline_html, unsafe_allow_html=True)
else:
    st.markdown('<div class="audit-note">No signal changes or recent fills in the latest cycle.</div>', unsafe_allow_html=True)

with st.expander("Audit detail: sleeve table", expanded=False):
    st.markdown('<div class="audit-note">Sanitized read-only view. Internal Streamlit widget objects are intentionally not rendered here.</div>', unsafe_allow_html=True)
    st.markdown(
        html_table(
            sleeve_rows,
            [
                ("display", "Sleeve"), ("position_state", "Position"), ("action", "Signal"), ("previous_action", "Prev"), ("action_changed", "Changed"),
                ("regime", "Regime"), ("target_weight", "Target wt"), ("actual_weight", "Actual wt"), ("drift", "Drift"),
                ("nav", "NAV"), ("today_pnl", "Today"), ("unrealized_pnl", "Unrealized"), ("unrealized_return", "uReturn"), ("realized_pnl", "Realized"),
                ("cost_basis", "Cost basis"), ("avg_entry", "Avg entry"), ("cash", "Cash"), ("position_value", "Market value"),
                ("qty", "Qty"), ("price", "Price"), ("exposure", "Exposure"), ("last_fill_side", "Last fill"), ("last_fill_price", "Last fill px"), ("new_fill_this_cycle", "New fill"), ("last_bar", "Last bar"), ("reason", "Reason"),
            ],
            "No sleeve rows yet.",
        ),
        unsafe_allow_html=True,
    )

with st.expander("Audit detail: latest signals", expanded=False):
    sig_rows = []
    for s in last.get("signals", []):
        sig_rows.append({"sleeve": s.get("sleeve"), "asset": s.get("asset"), "tf": s.get("timeframe"), "previous_action": s.get("previous_action"), "action": s.get("action"), "action_changed": s.get("action_changed"), "target": s.get("target_exposure"), "confidence": s.get("confidence"), "regime": s.get("regime"), "price": s.get("price"), "cost_basis": s.get("cost_basis"), "avg_entry": s.get("avg_entry"), "unrealized_pnl": s.get("unrealized_pnl"), "realized_pnl": s.get("realized_pnl"), "fill": bool(s.get("fill")), "reason": s.get("reason")})
    st.markdown(
        html_table(
            sig_rows,
            [("sleeve", "Sleeve"), ("asset", "Asset"), ("tf", "TF"), ("previous_action", "Prev"), ("action", "Action"), ("action_changed", "Changed"), ("target", "Target"), ("confidence", "Confidence"), ("regime", "Regime"), ("price", "Price"), ("cost_basis", "Cost basis"), ("avg_entry", "Avg entry"), ("unrealized_pnl", "uP&L"), ("realized_pnl", "rP&L"), ("fill", "Fill"), ("reason", "Reason")],
            "No signal records yet.",
        ),
        unsafe_allow_html=True,
    )

with st.expander("Audit detail: fills and errors", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        st.caption("Recent fills")
        st.markdown(
            html_table(
                fills[-50:][::-1],
                [("timestamp", "Timestamp"), ("sleeve", "Sleeve"), ("asset", "Asset"), ("side", "Side"), ("qty", "Qty"), ("price", "Fill price"), ("mid", "Mid"), ("notional", "Notional"), ("fee", "Fee"), ("slippage_cost", "Slippage"), ("realized_pnl", "Realized P&L"), ("cost_basis_after", "Basis after"), ("avg_entry_after", "Avg entry after")],
                "No fills yet.",
            ),
            unsafe_allow_html=True,
        )
    with c2:
        st.caption("Recent errors")
        st.markdown(html_table(errors[-50:][::-1], [("timestamp", "Timestamp"), ("version", "Version"), ("error", "Error")], "No runtime errors logged."), unsafe_allow_html=True)

st.caption(f"State {STATE_PATH} · Signals {SIGNALS_LOG} · Fills {FILLS_LOG} · Generated {datetime.now(UTC).isoformat()}")
