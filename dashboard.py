"""IteraDynamics — Paper Trading Dashboard.

Reads per-asset state JSON files written by paper-tf-v8.service and
tails the service log. Auto-refreshes every 60 seconds.
"""

from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

# ── Config ────────────────────────────────────────────────────────────────────

BTC_STATE  = Path("/root/ID_test/runtime/argus/state/paper_btc_state.json")
ETH_STATE  = Path("/root/ID_test/runtime/argus/state/paper_eth_state.json")
SERVICE    = "paper-tf-v8.service"
INITIAL_CAPITAL = 100_000.0
BTC_ALLOC  = 60_000.0
ETH_ALLOC  = 40_000.0
REFRESH_S  = 60

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_state(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def service_logs(n: int = 200) -> str:
    try:
        result = subprocess.run(
            ["journalctl", "-u", SERVICE, f"-n{n}", "--no-pager", "--output=short-iso"],
            capture_output=True, text=True, timeout=5,
        )
        lines = result.stdout.strip().splitlines()

        # Find the last "Started <service>" line and only show from there
        last_start = 0
        for i, line in enumerate(lines):
            if "Started paper-tf-v8" in line:
                last_start = i
        lines = lines[last_start:]

        # Strip journalctl host/pid prefix — keep timestamp + message
        cleaned = []
        for line in lines:
            parts = line.split(": ", 1)
            cleaned.append(parts[-1] if len(parts) == 2 else line)
        return "\n".join(cleaned)
    except Exception as exc:
        return f"(log unavailable: {exc})"


def service_status() -> tuple[str, str]:
    """Returns (active_state, label) e.g. ('active', 'Running')."""
    try:
        r = subprocess.run(
            ["systemctl", "is-active", SERVICE],
            capture_output=True, text=True, timeout=3,
        )
        state = r.stdout.strip()
        label = {"active": "Running", "inactive": "Stopped",
                 "failed": "Failed", "activating": "Starting"}.get(state, state.title())
        return state, label
    except Exception:
        return "unknown", "Unknown"


def fmt_nav(v: float) -> str:
    return f"${v:,.2f}"


def fmt_pct(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"


def drawdown_pct(state: dict) -> float:
    hwm = state.get("high_water_mark") or state["nav"]
    if hwm <= 0:
        return 0.0
    return (hwm - state["nav"]) / hwm * 100


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


# ── Page setup ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="IteraDynamics Paper Trader",
    page_icon="📈",
    layout="wide",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    .stMetric label { font-size: 0.8rem; color: #888; }
    .asset-header { font-size: 1.1rem; font-weight: 700; margin-bottom: 0.3rem; }
    .dd-warning { color: #e05c5c; font-weight: 600; }
    .halted-banner {
        background: #5c0000; color: #ffcccc; border-radius: 6px;
        padding: 0.5rem 1rem; font-weight: 700; margin-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# ── Load data ─────────────────────────────────────────────────────────────────

btc = load_state(BTC_STATE)
eth = load_state(ETH_STATE)
svc_state, svc_label = service_status()

# ── Header ────────────────────────────────────────────────────────────────────

col_title, col_status = st.columns([4, 1])
with col_title:
    st.title("IteraDynamics — Paper Trader")
    st.caption("Strategy: `trend_following_v8_ecap60_add80`  ·  BTC 60% / ETH 40%")
with col_status:
    colour = {"active": "🟢", "failed": "🔴", "inactive": "⚫"}.get(svc_state, "🟡")
    st.metric("Service", f"{colour} {svc_label}")
    st.caption(f"Auto-refresh {REFRESH_S}s")

st.divider()

# ── Portfolio summary ─────────────────────────────────────────────────────────

if btc and eth:
    combined_nav = btc["nav"] + eth["nav"]
    combined_pnl = pnl_pct(combined_nav, INITIAL_CAPITAL)
    combined_dd  = max(drawdown_pct(btc), drawdown_pct(eth))  # worst sleeve

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Portfolio NAV", fmt_nav(combined_nav),
              delta=fmt_pct(combined_pnl), delta_color="normal")
    c2.metric("Initial Capital", fmt_nav(INITIAL_CAPITAL))
    c3.metric("Total P&L", fmt_pct(combined_pnl),
              delta=fmt_nav(combined_nav - INITIAL_CAPITAL))
    c4.metric("Max Sleeve DD", fmt_pct(-combined_dd) if combined_dd else "—")
else:
    st.warning("State files not yet available — waiting for first cycle.")

st.divider()

# ── Per-asset cards ───────────────────────────────────────────────────────────

col_btc, col_eth = st.columns(2)

def render_asset(col, state: dict | None, asset: str, alloc: float) -> None:
    with col:
        st.markdown(f"<div class='asset-header'>{'₿' if asset == 'BTC' else 'Ξ'} {asset}</div>",
                    unsafe_allow_html=True)

        if state is None:
            st.info("No state file yet.")
            return

        if state.get("drawdown_governor_halted"):
            st.markdown("<div class='halted-banner'>⛔ DRAWDOWN GOVERNOR HALTED</div>",
                        unsafe_allow_html=True)

        nav   = state["nav"]
        cash  = state["cash"]
        units = state["position_units"]
        exp   = state["exposure_frac"] * 100
        dd    = drawdown_pct(state)
        pnl   = pnl_pct(nav, alloc)
        fills = state["fill_count"]
        last_bar = state.get("last_bar_timestamp", "—")
        updated  = last_updated_ago(state)

        r1c1, r1c2, r1c3 = st.columns(3)
        r1c1.metric("NAV", fmt_nav(nav), delta=fmt_pct(pnl), delta_color="normal")
        r1c2.metric("Cash", fmt_nav(cash))
        r1c3.metric("Position", f"{units:.4f} {asset}")

        r2c1, r2c2, r2c3 = st.columns(3)
        r2c1.metric("Exposure", f"{exp:.1f}%")
        r2c2.metric("Drawdown", f"{dd:.2f}%",
                    delta_color="inverse" if dd > 5 else "off")
        r2c3.metric("Fills", fills)

        st.caption(f"Last bar: `{last_bar}` · Updated {updated}")

render_asset(col_btc, btc, "BTC", BTC_ALLOC)
render_asset(col_eth, eth, "ETH", ETH_ALLOC)

st.divider()

# ── Service logs ──────────────────────────────────────────────────────────────

st.subheader("Service Log")
log_lines = service_logs(80)
st.code(log_lines, language=None)

# ── Auto-refresh ──────────────────────────────────────────────────────────────

time.sleep(REFRESH_S)
st.rerun()
