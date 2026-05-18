"""IteraDynamics — Paper Trading Dashboard v3."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Config ─────────────────────────────────────────────────────────────────────

BTC_STATE = Path("/root/ID_test/runtime/argus/state/paper_btc_state.json")
ETH_STATE = Path("/root/ID_test/runtime/argus/state/paper_eth_state.json")
SERVICE = "paper-tf-v8.service"
BTC_ALLOC = 60_000.0
ETH_ALLOC = 40_000.0
INITIAL_CAPITAL = BTC_ALLOC + ETH_ALLOC   # derived so sleeve allocations stay in sync
FUND_V1_STATE     = Path("/root/ID_test/runtime/argus/state/fund_v1_state.json")
FUND_V1_BTC_ALLOC = 50_000.0
FUND_V1_ETH_ALLOC = 50_000.0

# ── Page setup ─────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="IteraDynamics Paper Trader",
    page_icon="📈",
    layout="wide",
)

st.markdown("""<style>
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }

    .stMetric label {
        font-size: 0.70rem !important;
        color: #9ca3af !important;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }
    .stMetric [data-testid="stMetricValue"] {
        font-size: 1.25rem !important;
        font-weight: 700 !important;
    }

    .asset-header {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        padding-bottom: 0.45rem;
        margin-bottom: 0.75rem;
        border-bottom: 1px solid #1f2937;
        display: block;
        width: 100%;
    }
    .btc-header { color: #f7931a; }
    .eth-header { color: #627eea; }

    .halted-banner {
        background: rgba(239,68,68,0.12);
        border: 1px solid rgba(239,68,68,0.45);
        color: #fca5a5;
        border-radius: 6px;
        padding: 0.45rem 1rem;
        font-weight: 700;
        margin-bottom: 0.8rem;
        font-size: 0.9rem;
    }

    .exp-label {
        font-size: 0.68rem;
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 0.15rem;
        margin-top: 0.4rem;
    }

    /* ── Log viewer ─────────────────────────── */
    .log-wrap {
        font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
        font-size: 0.755rem;
        line-height: 1.6;
        background: #0e1117;
        border: 1px solid #1f2937;
        border-radius: 6px;
        padding: 0.75rem 1rem;
        max-height: 520px;
        overflow-y: auto;
    }
    .ll { margin: 0; padding: 0 0 1px 0; white-space: pre-wrap; word-break: break-all; }
    .lc  { color: #a78bfa; font-weight: 700; border-top: 1px solid #1e2333;
           margin-top: 4px; padding-top: 3px; }
    .lb  { color: #fb923c; }
    .le  { color: #818cf8; }
    .lbuy  { color: #4ade80; font-weight: 600; }
    .lsel  { color: #f87171; font-weight: 600; }
    .lnav  { color: #e2e8f0; font-weight: 500; }
    .lslp  { color: #2d3748; font-style: italic; }
    .lsys  { color: #374151; font-style: italic; }
    .lwrn  { color: #fbbf24; }
    .lerr  { color: #ef4444; font-weight: 700; }
    .ldef  { color: #6b7280; }

    /* ── Countdown box ──────────────────────── */
    .cd-box {
        background: #111827;
        border: 1px solid #1f2937;
        border-radius: 8px;
        padding: 0.45rem 1rem;
        text-align: center;
    }
    .cd-lbl { font-size: 0.62rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.07em; }
    .cd-val { font-size: 1.3rem; font-weight: 700; color: #a5b4fc;
              font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }
    .cd-sub { font-size: 0.65rem; color: #374151; margin-top: 1px; }

    /* ── Mode banner ────────────────────────── */
    .mode-banner {
        background: rgba(167,139,250,0.08);
        border: 1px solid rgba(167,139,250,0.3);
        color: #c4b5fd;
        border-radius: 6px;
        padding: 0.4rem 1rem;
        font-size: 0.85rem;
        margin-bottom: 0.5rem;
    }

    /* ── Dark base ───────────────────────────── */
    .stApp { background-color: #080c14; }
    [data-testid="stSidebar"] { background-color: #0d1117 !important; }
    [data-testid="stHeader"] { background-color: #080c14; }

    /* ── Fund KPI cards ─────────────────────── */
    .kpi-card {
        background: rgba(17,24,39,0.55);
        border-radius: 8px;
        padding: 1rem 1.25rem;
        border-left: 3px solid #374151;
    }
    .kpi-label {
        font-size: 0.62rem;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.35rem;
    }
    .kpi-value {
        font-size: 1.85rem;
        font-weight: 700;
        color: #f1f5f9;
        letter-spacing: -0.03em;
        line-height: 1.1;
    }
    .kpi-sub {
        font-size: 0.7rem;
        margin-top: 0.25rem;
        color: #6b7280;
    }

    /* ── Allocation bar ─────────────────────── */
    .alloc-section { margin: 0.2rem 0 0.9rem 0; }
    .alloc-lbl {
        font-size: 0.62rem;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.45rem;
    }
    .alloc-bar-wrap {
        display: flex;
        height: 6px;
        border-radius: 3px;
        overflow: hidden;
        background: #1f2937;
    }
    .alloc-seg-btc { background: linear-gradient(90deg,#f7931a,#fb923c); }
    .alloc-seg-eth { background: linear-gradient(90deg,#627eea,#818cf8); }
</style>""", unsafe_allow_html=True)

# ── Helpers ─────────────────────────────────────────────────────────────────────

def load_state(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def service_logs_raw(n: int = 500) -> list[str]:
    """Return cleaned log lines (journalctl prefix stripped)."""
    try:
        result = subprocess.run(
            ["journalctl", "-u", SERVICE, f"-n{n}", "--no-pager", "--output=short-iso"],
            capture_output=True, text=True, timeout=5,
        )
        lines = result.stdout.strip().splitlines()
        last_start = 0
        for i, line in enumerate(lines):
            if "Started paper-tf-v8" in line:
                last_start = i
        lines = lines[last_start:]
        cleaned = []
        for line in lines:
            parts = line.split(": ", 1)
            cleaned.append(parts[-1] if len(parts) == 2 else line)
        return cleaned
    except Exception as exc:
        return [f"(log unavailable: {exc})"]


# ── Log parser (legacy single-sleeve format) ───────────────────────────────────

_RE_CYCLE_HDR   = re.compile(r'── Cycle (\d+)\s+(\S+)')
_RE_ASSET_DATA  = re.compile(r'\b(BTC|ETH)-USD:')
_RE_ASSET_STATE = re.compile(
    r'Cycle \d+ \| ([^|]+?) \| regime=(\w+) \| price=([\d.]+) \| nav=([\d.]+) \| exposure=([\d.]+)'
)
_RE_ALLOC       = re.compile(
    r'Allocation: action=(\w+) target_exp=[\d.]+ approved=(\w+) \| (.+)'
)
_RE_FILL        = re.compile(
    r'Fill: (\w+) ([\d.]+) \w+ @ ([\d.]+) \(mid=([\d.]+)\) fee=([\d.]+) cost=([\d.]+)bps'
)
_RE_PORT_NAV    = re.compile(r'Portfolio NAV=\$?([\d.]+)')
_RE_SLEEP       = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*Sleeping (\d+)s')

# ── fund_v1 cycle parsers ───────────────────────────────────────────────────────
_RE_FV1_1H_BARS   = re.compile(r'(BTC|ETH)-USD: \d+ 1H bars \([^)]*?-> (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\)')
_RE_FV1_SLEEVE1H  = re.compile(r'\[fund_v1\] Sleeve (BTC|ETH)_1H\s+\| regime=(\w+)')
_RE_FV1_GOV       = re.compile(r'\[fund_v1\] (BTC|ETH) governor: action=(\w+) target=([\d.]+) approved=(\w+) \| (.+)')
_RE_FV1_ASSET_DET = re.compile(r'\[fund_v1\] (BTC|ETH): cash=\$[\d.]+ \| pos=[\d.]+@\$([\d.]+).*\| NAV=\$([\d.]+)')
_RE_FV1_PORT      = re.compile(r'\[fund_v1\] Portfolio NAV=\$([\d.]+)')


@dataclass
class FillEvent:
    cycle: int
    asset: str
    side: str
    units: float
    fill_price: float
    mid_price: float
    fee: float
    cost_bps: float


@dataclass
class AssetCycle:
    bar_ts: str = ""
    regime: str = ""
    price: float = 0.0
    nav: float = 0.0
    exposure: float = 0.0
    action: str = ""
    approved: bool = False
    reason: str = ""
    fill: Optional[FillEvent] = None


@dataclass
class CycleRecord:
    num: int = 0
    wall_ts: str = ""
    btc: AssetCycle = dc_field(default_factory=AssetCycle)
    eth: AssetCycle = dc_field(default_factory=AssetCycle)
    portfolio_nav: float = 0.0


def parse_cycles(lines: list[str]) -> list[CycleRecord]:
    cycles: list[CycleRecord] = []
    current: CycleRecord | None = None
    cur_asset: str = ""

    for line in lines:
        m = _RE_CYCLE_HDR.search(line)
        if m:
            if current:
                cycles.append(current)
            current = CycleRecord(num=int(m.group(1)), wall_ts=m.group(2))
            cur_asset = ""
            continue

        if current is None:
            continue

        # ── fund_v1 handlers (checked before legacy patterns) ───────────────
        m = _RE_FV1_1H_BARS.search(line)
        if m:
            asset = m.group(1)
            ac = current.btc if asset == "BTC" else current.eth
            ac.bar_ts = m.group(2)
            cur_asset = asset
            continue

        m = _RE_FV1_SLEEVE1H.search(line)
        if m:
            asset = m.group(1)
            ac = current.btc if asset == "BTC" else current.eth
            ac.regime = m.group(2)
            continue

        m = _RE_FV1_GOV.search(line)
        if m:
            asset = m.group(1)
            ac = current.btc if asset == "BTC" else current.eth
            ac.action   = m.group(2)
            ac.exposure = float(m.group(3))
            ac.approved = m.group(4) == "True"
            ac.reason   = m.group(5)
            continue

        m = _RE_FV1_ASSET_DET.search(line)
        if m:
            asset = m.group(1)
            ac = current.btc if asset == "BTC" else current.eth
            ac.price = float(m.group(2))
            ac.nav   = float(m.group(3))
            continue

        m = _RE_FV1_PORT.search(line)
        if m:
            current.portfolio_nav = float(m.group(1))
            continue

        # ── legacy single-sleeve handlers ───────────────────────────────────
        m = _RE_ASSET_DATA.search(line)
        if m:
            cur_asset = m.group(1)
            continue

        m = _RE_ASSET_STATE.search(line)
        if m and cur_asset:
            ac = current.btc if cur_asset == "BTC" else current.eth
            ac.bar_ts   = m.group(1).strip()
            ac.regime   = m.group(2)
            ac.price    = float(m.group(3))
            ac.nav      = float(m.group(4))
            ac.exposure = float(m.group(5))
            continue

        m = _RE_ALLOC.search(line)
        if m and cur_asset:
            ac = current.btc if cur_asset == "BTC" else current.eth
            ac.action   = m.group(1)
            ac.approved = m.group(2) == "True"
            ac.reason   = m.group(3)
            continue

        m = _RE_FILL.search(line)
        if m and cur_asset:
            ac = current.btc if cur_asset == "BTC" else current.eth
            ac.fill = FillEvent(
                cycle=current.num, asset=cur_asset,
                side=m.group(1), units=float(m.group(2)),
                fill_price=float(m.group(3)), mid_price=float(m.group(4)),
                fee=float(m.group(5)), cost_bps=float(m.group(6)),
            )
            continue

        m2 = re.search(r'\b(BTC|ETH) \| NAV=', line)
        if m2:
            cur_asset = m2.group(1)
            continue

        m = _RE_PORT_NAV.search(line)
        if m:
            current.portfolio_nav = float(m.group(1))
            continue

    if current:
        cycles.append(current)

    return cycles


def _fv1_state_dict(fv1: dict, asset: str) -> dict:
    """Build a per-asset state dict compatible with render_asset from fund_v1_state.json."""
    a = asset.lower()
    sleeves = fv1.get("sleeves", [])
    bar_ts = next(
        (s["bar_timestamp"] for s in sleeves
         if s.get("asset") == asset and s.get("timeframe") == "1H"),
        "—",
    )
    return {
        "asset":                    asset,
        "nav":                      fv1[f"{a}_nav"],
        "cash":                     fv1[f"{a}_cash"],
        "position_units":           fv1[f"{a}_position_units"],
        "exposure_frac":            fv1[f"{a}_exposure"],
        "high_water_mark":          fv1[f"{a}_high_water_mark"],
        "drawdown_governor_halted": fv1[f"{a}_drawdown_halted"],
        "last_bar_timestamp":       bar_ts,
        "last_updated":             fv1["last_updated"],
        "fill_count":               fv1[f"{a}_fill_count"],
        "meta":                     {},
    }


def service_status() -> tuple[str, str]:
    try:
        r = subprocess.run(
            ["systemctl", "is-active", SERVICE],
            capture_output=True, text=True, timeout=3,
        )
        state = r.stdout.strip()
        label = {
            "active": "Running", "inactive": "Stopped",
            "failed": "Failed", "activating": "Starting",
        }.get(state, state.title())
        return state, label
    except Exception:
        return "unknown", "Unknown"


def fmt_usd(v: float) -> str:
    return f"${v:,.2f}"


def fmt_pct(v: float) -> str:
    return f"{'+' if v >= 0 else ''}{v:.2f}%"


def drawdown_pct(state: dict) -> float:
    hwm = state.get("high_water_mark") or state["nav"]
    return (hwm - state["nav"]) / hwm * 100 if hwm > 0 else 0.0


def pnl_pct(nav: float, initial: float) -> float:
    return (nav / initial - 1) * 100 if initial > 0 else 0.0


def last_updated_ago(state: dict) -> str:
    try:
        ts = datetime.fromisoformat(state["last_updated"])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - ts
        mins = int(delta.total_seconds() // 60)
        if mins < 2:
            return "just now"
        if mins < 60:
            return f"{mins}m ago"
        return f"{mins // 60}h {mins % 60}m ago"
    except Exception:
        return state.get("last_updated", "—")


def next_cycle_countdown(lines: list[str]) -> tuple[int, int] | None:
    """Return (seconds_remaining, total_sleep) from last 'Sleeping Xs' line."""
    for line in reversed(lines):
        m = _RE_SLEEP.search(line)
        if m:
            try:
                log_ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                sleep_s = int(m.group(2))
                elapsed = int((datetime.now() - log_ts).total_seconds())
                remaining = max(0, sleep_s - elapsed)
                return remaining, sleep_s
            except Exception:
                pass
    return None


def fmt_countdown(s: int) -> str:
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m {sec:02d}s"


# ── Color-coded log renderer ────────────────────────────────────────────────────

def _log_class(line: str) -> str:
    if "── Cycle" in line:
        return "lc"
    if "Sleeping" in line and "until next" in line:
        return "lslp"
    if "WARNING" in line or " WARN " in line:
        return "lwrn"
    if "ERROR" in line:
        return "lerr"
    if any(k in line for k in ("Started ", "Stopped ", "Stopping ", "Deactivated",
                                "systemd", "Consumed", "DeprecationWarning")):
        return "lsys"
    if "Portfolio NAV=" in line or "Portfolio aggregate" in line:
        return "lnav"
    if "Fill:" in line:
        return "lbuy" if "BUY" in line else "lsel"
    # fund_v1 sleeve lines
    if "[fund_v1]" in line:
        if "BTC" in line:
            return "lbuy" if "BUY" in line else ("lsel" if "SELL" in line else "lb")
        if "ETH" in line:
            return "lbuy" if "BUY" in line else ("lsel" if "SELL" in line else "le")
        return "ldef"
    # legacy single-sleeve lines
    if "BTC" in line:
        if "action=BUY" in line:
            return "lbuy"
        if "action=SELL" in line:
            return "lsel"
        return "lb"
    if "ETH" in line:
        if "action=BUY" in line:
            return "lbuy"
        if "action=SELL" in line:
            return "lsel"
        return "le"
    return "ldef"


def render_log_html(lines: list[str]) -> str:
    parts = ['<div class="log-wrap">']
    for line in lines:
        cls = _log_class(line)
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        parts.append(f'<p class="ll {cls}">{safe}</p>')
    parts.append("</div>")
    return "".join(parts)


# ── NAV history chart ───────────────────────────────────────────────────────────

def build_nav_chart(cycles: list[CycleRecord]) -> go.Figure:
    labels    = [f"#{c.num}" for c in cycles]
    port_navs = [c.portfolio_nav for c in cycles]
    btc_navs  = [c.btc.nav for c in cycles]
    eth_navs  = [c.eth.nav for c in cycles]

    fig = go.Figure()

    fig.add_hline(
        y=INITIAL_CAPITAL, line_dash="dot", line_color="#374151",
        annotation_text="$100k initial", annotation_font_color="#6b7280",
        annotation_font_size=10,
    )

    fig.add_trace(go.Scatter(
        x=labels, y=port_navs, name="Portfolio",
        mode="lines+markers",
        line=dict(color="#a78bfa", width=2),
        marker=dict(size=4),
    ))
    fig.add_trace(go.Scatter(
        x=labels, y=btc_navs, name="BTC Sleeve",
        mode="lines", line=dict(color="#f7931a", width=1.5, dash="dot"),
    ))
    fig.add_trace(go.Scatter(
        x=labels, y=eth_navs, name="ETH Sleeve",
        mode="lines", line=dict(color="#627eea", width=1.5, dash="dot"),
    ))

    # Mark fill events
    buy_x, buy_y, sell_x, sell_y = [], [], [], []
    for c in cycles:
        for ac in (c.btc, c.eth):
            if ac.fill:
                if ac.fill.side == "BUY":
                    buy_x.append(f"#{c.num}"); buy_y.append(c.portfolio_nav)
                else:
                    sell_x.append(f"#{c.num}"); sell_y.append(c.portfolio_nav)

    if buy_x:
        fig.add_trace(go.Scatter(
            x=buy_x, y=buy_y, mode="markers", name="Buy",
            marker=dict(symbol="triangle-up", size=11, color="#4ade80"),
        ))
    if sell_x:
        fig.add_trace(go.Scatter(
            x=sell_x, y=sell_y, mode="markers", name="Sell",
            marker=dict(symbol="triangle-down", size=11, color="#f87171"),
        ))

    fig.update_layout(
        height=210,
        margin=dict(l=0, r=0, t=4, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#9ca3af", size=11),
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=10, color="#6b7280")),
        yaxis=dict(
            showgrid=True, gridcolor="#1a2030", zeroline=False,
            tickprefix="$", tickformat=",.0f",
            tickfont=dict(size=10, color="#6b7280"),
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1, font=dict(size=10),
        ),
        hovermode="x unified",
    )
    return fig


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### Controls")

    if st.button("⟳  Refresh Now", use_container_width=True, type="primary"):
        st.rerun()

    st.divider()

    auto_refresh = st.toggle("Auto-refresh", value=True)
    refresh_interval = st.select_slider(
        "Interval",
        options=[15, 30, 60, 120, 300],
        value=60,
        format_func=lambda s: f"{s}s",
        disabled=not auto_refresh,
    )

    st.divider()
    st.markdown("### Activity Log")
    log_cycles = st.slider("Cycles to show", min_value=5, max_value=100, value=20, step=5)
    show_log = st.checkbox("Show log", value=True)

    st.divider()
    st.caption(
        "**Ports**\n"
        "- :8501 — This dashboard (legacy paper trader)\n"
        "- :8504 — Fund v1 dashboard"
    )


# ── Dashboard (fragment for independent auto-refresh) ──────────────────────────

@st.fragment(run_every=refresh_interval if auto_refresh else None)
def render_dashboard(log_cycles: int, show_log: bool) -> None:
    svc_state, svc_label = service_status()
    raw_lines = service_logs_raw(n=max(log_cycles * 15 + 50, 300))
    is_fund_v1 = any("[fund_v1]" in l for l in raw_lines[-20:])

    if is_fund_v1:
        fv1_raw = load_state(FUND_V1_STATE)
        btc = _fv1_state_dict(fv1_raw, "BTC") if fv1_raw else None
        eth = _fv1_state_dict(fv1_raw, "ETH") if fv1_raw else None
        btc_alloc, eth_alloc = FUND_V1_BTC_ALLOC, FUND_V1_ETH_ALLOC
    else:
        btc = load_state(BTC_STATE)
        eth = load_state(ETH_STATE)
        btc_alloc, eth_alloc = BTC_ALLOC, ETH_ALLOC

    all_cycles = parse_cycles(raw_lines)

    # ── Header ─────────────────────────────────────────────────────────────────
    col_title, col_svc, col_cd = st.columns([5, 1, 1])

    with col_title:
        st.title("IteraDynamics — Paper Trader")
        _alloc_lbl = "BTC 50% / ETH 50%" if is_fund_v1 else "BTC 60% / ETH 40%"
        st.caption(
            "Strategy: `trend_following_v8_ecap60_add80`  ·  "
            f"{_alloc_lbl}  ·  Capital: $100,000"
        )

    with col_svc:
        dot = {"active": "🟢", "failed": "🔴", "inactive": "⚫"}.get(svc_state, "🟡")
        st.metric("Service", f"{dot} {svc_label}")
        st.caption(f"Fetched {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")

    with col_cd:
        cd = next_cycle_countdown(raw_lines)
        if cd and cd[0] > 0:
            remaining, total = cd
            progress_pct = int((1 - remaining / total) * 100) if total else 0
            st.markdown(
                f"<div class='cd-box'>"
                f"<div class='cd-lbl'>Next Cycle</div>"
                f"<div class='cd-val'>{fmt_countdown(remaining)}</div>"
                f"<div class='cd-sub'>{progress_pct}% through wait</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            sub = "sleeping…" if svc_state == "active" else svc_label.lower()
            st.markdown(
                f"<div class='cd-box'><div class='cd-lbl'>Next Cycle</div>"
                f"<div class='cd-val'>—</div>"
                f"<div class='cd-sub'>{sub}</div></div>",
                unsafe_allow_html=True,
            )

    if is_fund_v1:
        st.markdown(
            "<div class='mode-banner'>ℹ️ Running in <b>fund_v1</b> mode — "
            "4-sleeve strategy (BTC 1H+4H, ETH 1H+4H). "
            "Extended sleeve detail available on port <b>:8504</b>.</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Fund KPIs + Allocation ──────────────────────────────────────────────────
    if btc and eth:
        combined_nav   = btc["nav"] + eth["nav"]
        total_pnl_usd  = combined_nav - INITIAL_CAPITAL
        total_pnl_pct  = pnl_pct(combined_nav, INITIAL_CAPITAL)
        total_fills    = btc["fill_count"] + eth["fill_count"]

        # Fund-level drawdown (sum of sleeve HWMs — conservative proxy)
        btc_hwm       = btc.get("high_water_mark", btc["nav"])
        eth_hwm       = eth.get("high_water_mark", eth["nav"])
        portfolio_hwm = btc_hwm + eth_hwm
        fund_dd       = max(0.0, (portfolio_hwm - combined_nav) / portfolio_hwm * 100) if portfolio_hwm > 0 else 0.0

        # Fund net exposure (NAV-weighted average across sleeves)
        fund_net_exp  = (btc["exposure_frac"] * btc["nav"] + eth["exposure_frac"] * eth["nav"]) / combined_nav * 100

        # Allocation split
        btc_alloc_pct = btc["nav"] / combined_nav * 100
        eth_alloc_pct = eth["nav"] / combined_nav * 100
        target_btc    = 50.0 if is_fund_v1 else 60.0
        target_eth    = 50.0 if is_fund_v1 else 40.0
        alloc_drift   = abs(btc_alloc_pct - target_btc)

        # P&L formatting
        pnl_color = "#4ade80" if total_pnl_usd >= 0 else "#f87171"
        if total_pnl_usd >= 0:
            pnl_sub = f"+${total_pnl_usd:,.2f} &nbsp;(+{total_pnl_pct:.2f}%)"
        else:
            pnl_sub = f"-${abs(total_pnl_usd):,.2f} &nbsp;({total_pnl_pct:.2f}%)"

        # Drawdown coloring (red if approaching -20% limit)
        dd_color  = "#f87171" if fund_dd >= 15 else ("#fbbf24" if fund_dd >= 10 else "#a3e635")
        dd_border = "#ef4444" if fund_dd >= 15 else ("#f59e0b" if fund_dd >= 10 else "#374151")
        dd_sub    = "⚠ Approaching −20% limit" if fund_dd >= 15 else ("Elevated" if fund_dd >= 10 else "Within bounds")

        # Allocation drift coloring
        drift_color = "#ef4444" if alloc_drift > 5 else ("#fbbf24" if alloc_drift > 3 else "#4b5563")
        drift_icon  = " ⚠" if alloc_drift > 5 else ""

        # ── KPI row ─────────────────────────────────────────────────────────────
        st.markdown(f"""
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem;margin-bottom:1.1rem;">
  <div class="kpi-card" style="border-left:3px solid #a78bfa;">
    <div class="kpi-label">Total Fund NAV</div>
    <div class="kpi-value">{fmt_usd(combined_nav)}</div>
    <div class="kpi-sub" style="color:{pnl_color};">{pnl_sub}</div>
  </div>
  <div class="kpi-card" style="border-left:3px solid #38bdf8;">
    <div class="kpi-label">Fund Net Exposure</div>
    <div class="kpi-value">{fund_net_exp:.1f}%</div>
    <div class="kpi-sub">{total_fills} fills &nbsp;·&nbsp; Updated {last_updated_ago(btc)}</div>
  </div>
  <div class="kpi-card" style="border-left:3px solid {dd_border};">
    <div class="kpi-label">Fund Max Drawdown</div>
    <div class="kpi-value" style="color:{dd_color};">−{fund_dd:.2f}%</div>
    <div class="kpi-sub">{dd_sub}</div>
  </div>
</div>""", unsafe_allow_html=True)

        # ── Allocation visualizer ────────────────────────────────────────────────
        st.markdown(f"""
<div class="alloc-section">
  <div class="alloc-lbl">Sleeve Allocation</div>
  <div class="alloc-bar-wrap">
    <div class="alloc-seg-btc" style="width:{btc_alloc_pct:.2f}%;"></div>
    <div class="alloc-seg-eth" style="width:{eth_alloc_pct:.2f}%;"></div>
  </div>
  <div style="display:flex;justify-content:space-between;margin-top:0.4rem;font-size:0.8rem;font-weight:600;">
    <span style="color:#f7931a;">₿ BTC &nbsp;{btc_alloc_pct:.1f}%</span>
    <span style="color:#627eea;">Ξ ETH &nbsp;{eth_alloc_pct:.1f}%</span>
  </div>
  <div style="display:flex;justify-content:space-between;margin-top:0.2rem;font-size:0.65rem;">
    <span style="color:#4b5563;">Target {target_btc:.0f} / {target_eth:.0f}</span>
    <span style="color:{drift_color};">Drift {alloc_drift:.1f}%{drift_icon} &nbsp;(threshold ±5%)</span>
  </div>
</div>""", unsafe_allow_html=True)

        # ── NAV chart ────────────────────────────────────────────────────────────
        if len(all_cycles) >= 2:
            fig = build_nav_chart(all_cycles)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.caption("Accumulating cycle data for chart…")

    else:
        st.warning("State files not yet available — waiting for first cycle.")

    st.divider()

    # ── Per-asset cards ─────────────────────────────────────────────────────────
    col_btc, col_eth = st.columns(2)

    def render_asset(col, state: dict | None, asset: str, alloc: float, total_nav: float = 0.0) -> None:
        symbol  = "₿" if asset == "BTC" else "Ξ"
        hdr_cls = "btc-header" if asset == "BTC" else "eth-header"

        with col:
            st.markdown(
                f"<div class='asset-header {hdr_cls}'>{symbol} {asset}</div>",
                unsafe_allow_html=True,
            )

            if state is None:
                st.info("No state file yet.")
                return

            if state.get("drawdown_governor_halted"):
                st.markdown(
                    "<div class='halted-banner'>⛔ DRAWDOWN GOVERNOR HALTED</div>",
                    unsafe_allow_html=True,
                )

            nav            = state["nav"]
            cash           = state["cash"]
            units          = state["position_units"]
            position_value = nav - cash
            exp            = state["exposure_frac"] * 100
            dd             = drawdown_pct(state)
            hwm            = state.get("high_water_mark", nav)
            asset_pnl_usd  = nav - alloc
            asset_pnl_pct  = pnl_pct(nav, alloc)
            fills          = state["fill_count"]
            updated        = last_updated_ago(state)
            last_bar       = state.get("last_bar_timestamp", "—")

            r1a, r1b, r1c = st.columns(3)
            r1a.metric("NAV", fmt_usd(nav),
                       delta=fmt_pct(asset_pnl_pct), delta_color="normal")
            r1b.metric("P&L", fmt_usd(asset_pnl_usd),
                       delta=fmt_pct(asset_pnl_pct), delta_color="normal")
            r1c.metric("HWM", fmt_usd(hwm))

            pos_weight_pct = position_value / total_nav * 100 if total_nav > 0 else 0.0
            r2a, r2b, r2c = st.columns(3)
            r2a.metric("Cash", fmt_usd(cash))
            r2b.metric("Pos. Value", fmt_usd(position_value))
            r2c.metric("Port. Weight", f"{pos_weight_pct:.1f}%")
            st.caption(f"Units held: `{units:.6f} {asset}`")

            st.markdown("<div class='exp-label'>Exposure</div>", unsafe_allow_html=True)
            st.progress(min(exp / 100.0, 1.0), text=f"{exp:.1f}%")

            r3a, r3b, r3c = st.columns(3)
            r3a.metric("Drawdown", f"{dd:.2f}%")
            r3b.metric("Fills", fills)
            r3c.metric("Allocation", fmt_usd(alloc))

            st.caption(f"Last bar: `{last_bar}` · Updated {updated}")

    _total_nav = (btc["nav"] + eth["nav"]) if (btc and eth) else 0.0
    render_asset(col_btc, btc, "BTC", btc_alloc, _total_nav)
    render_asset(col_eth, eth, "ETH", eth_alloc, _total_nav)

    # ── Activity log ────────────────────────────────────────────────────────────
    if show_log:
        st.divider()
        st.markdown("#### Activity Log")

        display_cycles = all_cycles[-log_cycles:]

        ACTION_ICON = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⬜", "": "·"}

        tab_cycles, tab_fills, tab_log = st.tabs(
            [f"Cycles ({len(display_cycles)})", "Fill Events", "Raw Log"]
        )

        # ── Cycles tab ─────────────────────────────────────────────────────────
        with tab_cycles:
            if display_cycles:
                rows = []
                for i, c in enumerate(display_cycles):
                    prev_nav = display_cycles[i - 1].portfolio_nav if i > 0 else c.portfolio_nav
                    delta = c.portfolio_nav - prev_nav if i > 0 else 0.0

                    def _action_cell(ac: AssetCycle) -> str:
                        icon = ACTION_ICON.get(ac.action, "·")
                        if ac.fill:
                            return f"{icon} {ac.action}  @ ${ac.fill.fill_price:,.2f}"
                        return f"{icon} {ac.action}" if ac.action else "·"

                    rows.append({
                        "#":             c.num,
                        "Bar (UTC)":     c.btc.bar_ts[:16] if c.btc.bar_ts else "—",
                        "BTC Action":    _action_cell(c.btc),
                        "BTC Regime":    c.btc.regime,
                        "BTC Exp%":      c.btc.exposure * 100,
                        "BTC Price":     c.btc.price,
                        "BTC NAV":       c.btc.nav,
                        "ETH Action":    _action_cell(c.eth),
                        "ETH Regime":    c.eth.regime,
                        "ETH Exp%":      c.eth.exposure * 100,
                        "ETH Price":     c.eth.price,
                        "ETH NAV":       c.eth.nav,
                        "Portfolio NAV": c.portfolio_nav,
                        "NAV Δ":         delta,
                    })

                df = pd.DataFrame(rows[::-1])  # newest first
                st.dataframe(
                    df,
                    column_config={
                        "#":             st.column_config.NumberColumn("#", width="small"),
                        "Bar (UTC)":     st.column_config.TextColumn("Bar (UTC)", width="medium"),
                        "BTC Action":    st.column_config.TextColumn("BTC Action", width="medium"),
                        "BTC Regime":    st.column_config.TextColumn("BTC Regime", width="medium"),
                        "BTC Exp%":      st.column_config.ProgressColumn(
                                             "BTC Exp%", format="%.1f%%",
                                             min_value=0, max_value=100, width="small"),
                        "BTC Price":     st.column_config.NumberColumn("BTC Price", format="$%.2f", width="medium"),
                        "BTC NAV":       st.column_config.NumberColumn("BTC NAV", format="$%.2f", width="medium"),
                        "ETH Action":    st.column_config.TextColumn("ETH Action", width="medium"),
                        "ETH Regime":    st.column_config.TextColumn("ETH Regime", width="medium"),
                        "ETH Exp%":      st.column_config.ProgressColumn(
                                             "ETH Exp%", format="%.1f%%",
                                             min_value=0, max_value=100, width="small"),
                        "ETH Price":     st.column_config.NumberColumn("ETH Price", format="$%.2f", width="medium"),
                        "ETH NAV":       st.column_config.NumberColumn("ETH NAV", format="$%.2f", width="medium"),
                        "Portfolio NAV": st.column_config.NumberColumn("Portfolio NAV", format="$%.2f", width="medium"),
                        "NAV Δ":         st.column_config.NumberColumn("NAV Δ", format="$+.2f", width="small"),
                    },
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.info("No cycle data in the current log window — increase cycles to show or check service status.")

        # ── Fill Events tab ─────────────────────────────────────────────────────
        with tab_fills:
            fills = [
                (c.num, c.btc.bar_ts, c.btc.fill) for c in all_cycles if c.btc.fill
            ] + [
                (c.num, c.eth.bar_ts, c.eth.fill) for c in all_cycles if c.eth.fill
            ]
            fills.sort(key=lambda x: x[0], reverse=True)

            if fills:
                fill_rows = [
                    {
                        "Cycle":          f.cycle,
                        "Bar":            bar[:16],
                        "Asset":          f.asset,
                        "Side":           f"{'🟢 BUY' if f.side == 'BUY' else '🔴 SELL'}",
                        "Units":          f.units,
                        "Fill $":         f.fill_price,
                        "Mid $":          f.mid_price,
                        "Slippage (bps)": f.cost_bps,
                        "Fee ($)":        f.fee,
                    }
                    for _, bar, f in fills
                ]
                st.dataframe(
                    pd.DataFrame(fill_rows),
                    column_config={
                        "Units":           st.column_config.NumberColumn("Units", format="%.6f"),
                        "Fill $":          st.column_config.NumberColumn("Fill $", format="$%.2f"),
                        "Mid $":           st.column_config.NumberColumn("Mid $", format="$%.2f"),
                        "Slippage (bps)":  st.column_config.NumberColumn("Slippage (bps)", format="%.1f"),
                        "Fee ($)":         st.column_config.NumberColumn("Fee ($)", format="$%.4f"),
                    },
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.info("No fills found in the current log window.")

        # ── Raw Log tab ─────────────────────────────────────────────────────────
        with tab_log:
            filter_col, lines_col = st.columns([3, 1])
            with filter_col:
                log_filter = st.selectbox(
                    "Filter",
                    ["All", "Cycles only", "BTC only", "ETH only",
                     "Fills only", "System events"],
                    label_visibility="collapsed",
                )
            with lines_col:
                log_n = st.number_input(
                    "Lines", min_value=50, max_value=600, value=200, step=50,
                    label_visibility="collapsed",
                )

            display_lines = raw_lines[-int(log_n):]

            if log_filter == "Cycles only":
                display_lines = [l for l in display_lines
                                 if any(k in l for k in ("── Cycle", "Portfolio NAV", "Sleeping"))]
            elif log_filter == "BTC only":
                display_lines = [l for l in display_lines if "BTC" in l]
            elif log_filter == "ETH only":
                display_lines = [l for l in display_lines if "ETH" in l]
            elif log_filter == "Fills only":
                display_lines = [l for l in display_lines if "Fill:" in l]
            elif log_filter == "System events":
                display_lines = [l for l in display_lines
                                 if any(k in l for k in ("Started", "Stopped", "Stopping",
                                                          "Deactivated", "Sleeping", "Consumed"))]

            st.caption(f"Showing {len(display_lines)} lines · newest at bottom")
            st.markdown(render_log_html(display_lines), unsafe_allow_html=True)


render_dashboard(log_cycles, show_log)
