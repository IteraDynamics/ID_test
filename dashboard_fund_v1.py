"""IteraDynamics — Fund v1 Operator Dashboard v4."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ── Config ────────────────────────────────────────────────────────────────────

# Fund v1 (current / default)
FUND_V1_STATE   = Path("runtime/argus/state/fund_v1_state.json")
FUND_V1_FILLS   = Path("runtime/argus/state/fund_v1_fills.jsonl")
FUND_V1_LOG     = Path("logs/fund_v1_live.out")
FUND_V1_SCRIPT  = "run_fund_v1_live.py"

# Fund v2 (research/paper candidate — separate files, never mixed with v1)
FUND_V2_STATE   = Path("runtime/argus/state/fund_v2_state.json")
FUND_V2_FILLS   = Path("runtime/argus/state/fund_v2_fills.jsonl")
FUND_V2_LOG     = Path("logs/fund_v2_live.out")
FUND_V2_SCRIPT  = "run_fund_v2_live.py"

# Backward-compat aliases (existing code below still references these names)
FUND_STATE      = FUND_V1_STATE
FUND_FILLS      = FUND_V1_FILLS
FUND_LOG        = FUND_V1_LOG
RUNNER_SCRIPT   = FUND_V1_SCRIPT

SERVICE         = "paper-tf-v8.service"
INITIAL_CAPITAL = 100_000.0
BTC_ALLOC       = 50_000.0
ETH_ALLOC       = 50_000.0

# ── Page setup ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="IteraDynamics — Fund v1",
    page_icon="📊",
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
        font-size: 1.20rem !important;
        font-weight: 700 !important;
    }

    .asset-header {
        font-size: 1rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.1em; padding-bottom: 0.5rem; margin-bottom: 0.6rem;
        border-bottom: 2px solid; display: inline-block; width: 100%;
    }
    .btc-header { color: #f7931a; border-color: #f7931a44; }
    .eth-header { color: #627eea; border-color: #627eea44; }

    .halted-banner {
        background: rgba(239,68,68,0.12); border: 1px solid rgba(239,68,68,0.45);
        color: #fca5a5; border-radius: 6px; padding: 0.45rem 1rem;
        font-weight: 700; margin-bottom: 0.8rem; font-size: 0.9rem;
    }

    .exp-label {
        font-size: 0.68rem; color: #9ca3af; text-transform: uppercase;
        letter-spacing: 0.06em; margin-bottom: 0.15rem; margin-top: 0.4rem;
    }

    /* ── Status panel ─── */
    .status-panel {
        background: #111827; border: 1px solid #1f2937;
        border-radius: 8px; padding: 0.8rem 1.2rem; margin-bottom: 0.5rem;
    }
    .status-row { display: flex; flex-wrap: wrap; gap: 1.4rem; align-items: center; }
    .status-kv  { display: flex; flex-direction: column; }
    .status-k   { font-size: 0.60rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.07em; }
    .status-v   { font-size: 0.88rem; font-weight: 600; color: #e2e8f0; }

    /* ── Why Now panel ─── */
    .why-panel {
        border-radius: 0 8px 8px 0; padding: 0.55rem 1rem;
        margin-bottom: 0.6rem; display: flex; gap: 1rem; align-items: center;
    }
    .why-ok   { background: rgba(74,222,128,0.07);  border-left: 4px solid #4ade80; }
    .why-warn { background: rgba(251,191,36,0.09);  border-left: 4px solid #fbbf24; }
    .why-err  { background: rgba(239,68,68,0.10);   border-left: 4px solid #ef4444; }
    .why-badge {
        font-size: 0.62rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.09em; white-space: nowrap; padding: 0.15rem 0.5rem;
        border-radius: 4px; background: rgba(255,255,255,0.07);
    }
    .why-ok   .why-badge { color: #4ade80; }
    .why-warn .why-badge { color: #fbbf24; }
    .why-err  .why-badge { color: #f87171; }
    .why-msg { font-size: 0.88rem; font-weight: 600; color: #e2e8f0; }

    /* ── Governor panel ─── */
    .gov-panel {
        background: #0f172a; border: 1px solid #1e293b;
        border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 0.5rem;
    }
    .gov-asset { font-size: 0.73rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.3rem; }
    .gov-btc   { color: #f7931a; }
    .gov-eth   { color: #627eea; }
    .gov-action-line { display: flex; gap: 0.6rem; align-items: baseline; flex-wrap: wrap; margin-bottom: 0.25rem; }
    .gov-action { font-size: 0.95rem; font-weight: 700; }
    .gov-hold   { color: #9ca3af; }
    .gov-buy    { color: #4ade80; }
    .gov-sell   { color: #f87171; }
    .gov-badge  { font-size: 0.62rem; font-weight: 700; padding: 0.1rem 0.45rem; border-radius: 3px; }
    .gov-approved   { background: rgba(74,222,128,0.15); color: #4ade80; }
    .gov-unapproved { background: rgba(156,163,175,0.12); color: #9ca3af; }
    .gov-meta   { font-size: 0.73rem; color: #6b7280; display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 0.2rem; }
    .gov-reason { font-size: 0.73rem; color: #6b7280; font-style: italic; margin-top: 0.1rem; }
    .gov-blocked { font-size: 0.65rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
                   padding: 0.1rem 0.4rem; border-radius: 3px;
                   background: rgba(239,68,68,0.10); color: #f87171; }

    /* ── Fill Audit ─── */
    .fill-armed {
        background: #111827; border: 1px dashed #374151;
        border-radius: 8px; padding: 0.6rem 1rem;
        font-size: 0.82rem; color: #6b7280; text-align: center;
    }
    .fill-panel {
        background: #0d1f35; border: 1px solid #1e3a5f;
        border-radius: 8px; padding: 0.8rem 1.2rem; margin-bottom: 0.6rem;
    }
    .fill-header {
        font-size: 0.75rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.08em; margin-bottom: 0.5rem;
    }
    .fill-buy  { color: #4ade80; }
    .fill-sell { color: #f87171; }

    /* ── Cal effect ─── */
    .cal-effect-bar {
        background: #111827; border: 1px solid #1f2937;
        border-radius: 6px; padding: 0.45rem 0.9rem;
        font-size: 0.80rem; color: #9ca3af; margin-bottom: 0.5rem;
        display: flex; gap: 1rem; flex-wrap: wrap; align-items: center;
    }
    .cal-active { color: #a78bfa; font-weight: 600; }
    .cal-none   { color: #4b5563; }

    /* ── Drift ─── */
    .drift-ok   { color: #4ade80; font-weight: 700; }
    .drift-warn { color: #fbbf24; font-weight: 700; }

    /* ── Log viewer ─── */
    .log-wrap {
        font-family: 'JetBrains Mono', 'Fira Code', monospace;
        font-size: 0.755rem; line-height: 1.6;
        background: #0e1117; border: 1px solid #1f2937;
        border-radius: 6px; padding: 0.75rem 1rem;
        max-height: 520px; overflow-y: auto;
    }
    .ll { margin: 0; padding: 0 0 1px 0; white-space: pre-wrap; word-break: break-all; }
    .lc   { color: #a78bfa; font-weight: 700; border-top: 1px solid #1e2333; margin-top: 4px; padding-top: 3px; }
    .lb   { color: #fb923c; }
    .le   { color: #818cf8; }
    .lbuy { color: #4ade80; font-weight: 600; }
    .lsel { color: #f87171; font-weight: 600; }
    .lnav { color: #e2e8f0; font-weight: 500; }
    .lslp { color: #2d3748; font-style: italic; }
    .lsys { color: #374151; font-style: italic; }
    .lwrn { color: #fbbf24; }
    .lerr { color: #ef4444; font-weight: 700; }
    .ldef { color: #6b7280; }

    /* ── Countdown ─── */
    .cd-box {
        background: #111827; border: 1px solid #1f2937;
        border-radius: 8px; padding: 0.45rem 1rem; text-align: center;
    }
    .cd-lbl { font-size: 0.62rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.07em; }
    .cd-val { font-size: 1.3rem; font-weight: 700; color: #a5b4fc;
              font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }
    .cd-sub { font-size: 0.65rem; color: #374151; margin-top: 1px; }
</style>""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_state(state_path: Path = FUND_V1_STATE) -> dict | None:
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_fills(fills_path: Path = FUND_V1_FILLS) -> list[dict]:
    """Read all fills from the JSONL audit log, newest first."""
    try:
        if not fills_path.exists():
            return []
        lines = fills_path.read_text(encoding="utf-8", errors="replace").splitlines()
        fills = []
        for ln in lines:
            ln = ln.strip()
            if ln:
                try:
                    fills.append(json.loads(ln))
                except Exception:
                    pass
        return fills[::-1]
    except Exception:
        return []


def runner_status(script: str = FUND_V1_SCRIPT) -> tuple[str, str]:
    try:
        r = subprocess.run(["pgrep", "-f", script],
                           capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and r.stdout.strip():
            return "running", "Running"
        return "stopped", "Stopped"
    except Exception:
        return "unknown", "Unknown"


def fund_logs_raw(n: int = 600, log_path: Path = FUND_V1_LOG) -> list[str]:
    """Return cleaned log lines from journalctl (v1) or log file fallback."""
    # For Fund v1, try journalctl first (registered service).
    # For Fund v2 (standalone process), go straight to log file fallback.
    if log_path == FUND_V1_LOG:
        try:
            result = subprocess.run(
                ["journalctl", "-u", SERVICE, f"-n{n}", "--no-pager", "--output=short-iso"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().splitlines()
                cleaned = []
                for line in lines:
                    parts = line.split(": ", 1)
                    cleaned.append(parts[-1] if len(parts) == 2 else line)
                return cleaned
        except Exception:
            pass
    # fallback to log file (always used for Fund v2)
    try:
        if log_path.exists():
            return log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except Exception as exc:
        return [f"(log unavailable: {exc})"]
    return [f"(log unavailable: journalctl failed and {log_path} not found)"]


def _usd(v) -> str:
    if v is None:
        return "—"
    try:
        return f"${v:,.2f}"
    except Exception:
        return "—"


def _bps(v) -> str:
    if v is None:
        return "—"
    try:
        return f"{v:.2f} bps"
    except Exception:
        return "—"


def fmt_pct(v: float) -> str:
    return f"{'+' if v >= 0 else ''}{v:.2f}%"


def pnl_pct(nav: float, initial: float) -> float:
    return (nav / initial - 1) * 100 if initial > 0 else 0.0


def drawdown_pct(nav: float, hwm: float) -> float:
    return (hwm - nav) / hwm * 100 if hwm > 0 else 0.0


def last_updated_ago(ts_str: str) -> tuple[str, int]:
    """Returns (human label, staleness_minutes)."""
    try:
        ts = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - ts
        mins  = int(delta.total_seconds() // 60)
        if mins < 2:
            return "just now", mins
        if mins < 60:
            return f"{mins}m ago", mins
        return f"{mins // 60}h {mins % 60}m ago", mins
    except Exception:
        return (ts_str or "—"), 9999


_RE_SLEEP = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*Sleeping (\d+)s')


def next_cycle_countdown(lines: list[str]) -> tuple[int, int] | None:
    for line in reversed(lines):
        m = _RE_SLEEP.search(line)
        if m:
            try:
                log_ts  = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                sleep_s = int(m.group(2))
                elapsed = int((datetime.now() - log_ts).total_seconds())
                return max(0, sleep_s - elapsed), sleep_s
            except Exception:
                pass
    return None


def fmt_countdown(s: int) -> str:
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {sec:02d}s"


# ── State interpretation ──────────────────────────────────────────────────────

def interpret_state(state: dict | None, run_state: str, staleness_mins: int) -> tuple[str, str, str]:
    """Return (badge_label, message, severity) where severity in ok|warn|err."""
    if state is None:
        return "INITIALIZING", "State file not found — waiting for first cycle.", "err"
    if run_state == "stopped":
        return "STOPPED", "Runner is not running — no new cycles will execute.", "err"
    if run_state == "unknown":
        return "UNKNOWN", "Runner status could not be determined — check process.", "warn"

    btc_halted = state.get("btc_drawdown_halted", False)
    eth_halted = state.get("eth_drawdown_halted", False)
    if btc_halted and eth_halted:
        return "HALTED", "Both BTC and ETH drawdown governors have halted trading.", "err"
    if btc_halted:
        return "HALTED", "BTC drawdown governor halted — BTC trading suspended.", "err"
    if eth_halted:
        return "HALTED", "ETH drawdown governor halted — ETH trading suspended.", "err"

    port_nav  = state.get("portfolio_nav", 0.0)
    btc_nav_s = state.get("btc_nav", 0.0)
    eth_nav_s = state.get("eth_nav", 0.0)
    nav_drift = abs(port_nav - (btc_nav_s + eth_nav_s))
    if nav_drift > 1.0:
        return "ACCT ALERT", f"NAV conservation drift ${nav_drift:.2f} — accounting mismatch detected.", "err"

    if not state.get("calibrator_loaded", False):
        return "CAL WARN", "Calibrator not loaded — signals running uncalibrated.", "warn"

    if staleness_mins > 120:
        return "STALE", f"State last updated {staleness_mins}m ago — runner may be stuck.", "warn"

    sleeves    = state.get("sleeves", [])
    port_tgt   = state.get("portfolio_target_exposure", 0.0)
    btc_exp    = state.get("btc_exposure", 0.0)
    eth_exp    = state.get("eth_exposure", 0.0)

    if not sleeves:
        return "WAITING", "No sleeve data — waiting for first completed cycle.", "warn"

    active_sl  = [s for s in sleeves if s.get("desired_exposure", 0) > 0]
    regimes    = list({s.get("regime", "") for s in sleeves if s.get("regime")})
    regime_str = regimes[0] if len(regimes) == 1 else " / ".join(regimes[:2])

    if btc_exp > 0 or eth_exp > 0:
        parts = []
        if btc_exp > 0:
            parts.append(f"BTC {btc_exp:.0%}")
        if eth_exp > 0:
            parts.append(f"ETH {eth_exp:.0%}")
        driver = ""
        if active_sl:
            best = max(active_sl, key=lambda s: s.get("desired_exposure", 0))
            driver = f" — driven by {best.get('label', '')}"
        return "ACTIVE", f"Exposure live: {', '.join(parts)}{driver}.", "ok"

    if port_tgt > 0:
        last_btc = state.get("last_btc_decision", "") or ""
        last_eth = state.get("last_eth_decision", "") or ""
        btc_approved = "approved=True" in last_btc
        eth_approved = "approved=True" in last_eth
        if not btc_approved and not eth_approved:
            best_label = ""
            if active_sl:
                best = max(active_sl, key=lambda s: s.get("desired_exposure", 0))
                best_label = best.get("label", "")
            held_why = (last_btc or last_eth)[:80]
            return "SIGNAL/HELD", (
                f"{best_label + ' ' if best_label else ''}sleeve targeting {port_tgt:.0%}"
                f" — governor holding: {held_why}."
            ), "warn"
        driver = ""
        if active_sl:
            best = max(active_sl, key=lambda s: s.get("desired_exposure", 0))
            driver = f" — driven by {best.get('label', '')}"
        return "ENTERING", f"Target exposure {port_tgt:.0%} set — fills pending next cycle{driver}.", "ok"

    if active_sl and port_tgt == 0:
        return "SIGNAL/HELD", "Sleeve signals exist but portfolio target is 0 — governors holding.", "warn"

    return "FLAT", f"No active signals — all sleeves FLAT in {regime_str}.", "ok"


# ── Calibration effect ────────────────────────────────────────────────────────

def cal_effect_label(delta: float) -> str:
    if abs(delta) < 0.005:
        return "NONE"
    if abs(delta) < 0.02:
        return "LOW"
    return "ACTIVE"


def cal_effect_summary(sleeves: list[dict]) -> str:
    if not sleeves:
        return ""
    deltas = [s.get("calibrated_confidence", 0) - s.get("raw_confidence", 0) for s in sleeves]
    active = [d for d in deltas if abs(d) >= 0.02]
    if not active:
        return "Calibration effect: NONE across all sleeves"
    pos = [d for d in active if d > 0]
    neg = [d for d in active if d < 0]
    n   = len(sleeves)
    if pos and not neg:
        return f"Calibration amplifying exposure — active on {len(pos)}/{n} sleeves"
    if neg and not pos:
        return f"Calibration suppressing exposure — active on {len(neg)}/{n} sleeves"
    return f"Calibration active (mixed) on {len(active)}/{n} sleeves"


# ── Governor parsing ──────────────────────────────────────────────────────────

_RE_GOV_FULL   = re.compile(
    r'\[fund_v[12]\] (BTC|ETH) governor: action=(\w+) target=([\d.]+) approved=(\w+)\s*\|?\s*(.*)'
)
_RE_GOV_REASON = re.compile(r'\[fund_v[12]\] (BTC|ETH) governor:.*\|\s*(.*)')


def infer_blocked_by(reason: str, approved: bool) -> str:
    if approved:
        return ""
    r = reason.lower()
    if "already flat" in r or "all sleeves exit" in r:
        return "already_flat"
    if "rebalance" in r or "threshold" in r:
        return "rebalance_threshold"
    if "drawdown" in r:
        return "drawdown_halt"
    if "no signal" in r or "no_signal" in r:
        return "no_signal"
    if "no change" in r:
        return "no_change"
    return "unknown"


def parse_gov_from_log(raw_lines: list[str]) -> dict[str, dict]:
    """Parse most-recent BTC and ETH governor decisions from the live log."""
    result: dict[str, dict] = {"BTC": {}, "ETH": {}}
    for line in reversed(raw_lines):
        if result["BTC"] and result["ETH"]:
            break
        m = _RE_GOV_FULL.search(line)
        if m:
            asset, action, target, approved_s, reason = m.groups()
            approved = approved_s.lower() == "true"
            if asset in result and not result[asset]:
                result[asset] = {
                    "action":     action,
                    "target":     float(target),
                    "approved":   approved,
                    "reason":     reason.strip(),
                    "blocked_by": infer_blocked_by(reason, approved),
                }
    return result


# ── Structured event parser ───────────────────────────────────────────────────

_RE_LOG_TS   = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')
_RE_CYCLE_EV = re.compile(r'── Cycle (\d+)\s+(\S+).*mode=fund_v')
_RE_GOV_EV   = re.compile(
    r'\[fund_v[12]\] (BTC|ETH) governor: action=(\w+) target=([\d.]+) approved=(\w+)\s*\|?\s*(.*)'
)
_RE_FILL_EV  = re.compile(r'Fill:\s*(.*)')
_RE_CAL_EV   = re.compile(r'calibrator loaded.*?method=(\S+).*?n_samples=(\d+)', re.IGNORECASE)
_RE_SAVE_EV  = re.compile(r'State saved\s*->\s*(\S+)')
_RE_NAV_EV   = re.compile(r'\[fund_v[12]\] Portfolio NAV=\$?([\d.]+)\s+BTC NAV=\$?([\d.]+).*ETH NAV=\$?([\d.]+)')
_RE_NAVWRN   = re.compile(r'NAV.*(?:drift|mismatch|conservation|warning)', re.IGNORECASE)


def parse_structured_events(lines: list[str], max_events: int = 100) -> list[dict]:
    events: list[dict] = []
    for line in lines:
        ts_m = _RE_LOG_TS.match(line)
        ts   = ts_m.group(1) if ts_m else ""

        if m := _RE_CYCLE_EV.search(line):
            events.append({"ts": ts, "type": "CYCLE", "icon": "🔄",
                           "summary": f"Cycle {m.group(1)} started", "detail": ""})

        elif m := _RE_GOV_EV.search(line):
            asset, action, target, approved_s, reason = m.groups()
            approved = approved_s.lower() == "true"
            ev_type  = "GOV_ACTIVE" if (approved or action not in ("HOLD",)) else "GOV_HOLD"
            icon_map = {"BUY": "🟢", "ENTER": "🟢", "SELL": "🔴", "EXIT": "🔴"}
            icon     = icon_map.get(action, "⬜" if approved else "·")
            events.append({"ts": ts, "type": ev_type, "icon": icon,
                           "summary": f"{asset} gov → {action}  tgt={float(target):.3f}  approved={approved_s}",
                           "detail": reason.strip()[:80]})

        elif m := _RE_FILL_EV.search(line):
            icon = "🟢" if "BUY" in line else "🔴"
            events.append({"ts": ts, "type": "FILL", "icon": icon,
                           "summary": f"Fill: {m.group(1)[:100]}", "detail": ""})

        elif m := _RE_CAL_EV.search(line):
            events.append({"ts": ts, "type": "CAL", "icon": "✅",
                           "summary": f"Calibrator loaded — method={m.group(1)}  n={m.group(2)}", "detail": ""})

        elif m := _RE_SAVE_EV.search(line):
            events.append({"ts": ts, "type": "SAVE", "icon": "💾",
                           "summary": f"State saved → {m.group(1)}", "detail": ""})

        elif m := _RE_NAV_EV.search(line):
            events.append({"ts": ts, "type": "NAV", "icon": "📊",
                           "summary": (
                               f"NAV  Port=${float(m.group(1)):,.0f}"
                               f"  BTC=${float(m.group(2)):,.0f}"
                               f"  ETH=${float(m.group(3)):,.0f}"
                           ), "detail": ""})

        elif _RE_NAVWRN.search(line):
            events.append({"ts": ts, "type": "WARN", "icon": "⚠️",
                           "summary": line[-120:], "detail": ""})

        elif "ERROR" in line:
            events.append({"ts": ts, "type": "ERROR", "icon": "🔴",
                           "summary": line[-120:], "detail": ""})

    return events[-max_events:][::-1]


# ── Cycle parser ──────────────────────────────────────────────────────────────

_RE_FUND_CYCLE = re.compile(r'── Cycle (\d+)\s+(\S+).*mode=fund_v')
_RE_SLEEVE     = re.compile(
    r'\[fund_v[12]\] Sleeve (\w+)\s+[\[\w\]]*\s*\| regime=(\w+)\s+action=(\w+)\s+'
    r'raw=([\d.]+)\s+cal=([\d.]+)\s+desired_exp=([\d.]+)\s+\|\s+(.*)'
)
_RE_GOV        = re.compile(
    r'\[fund_v[12]\] (BTC|ETH) governor: action=(\w+) target=([\d.]+) approved=(\w+)'
)
_RE_FUND_NAV   = re.compile(
    r'\[fund_v[12]\] Portfolio NAV=\$?([\d.]+)\s+BTC NAV=\$?([\d.]+)\s+exp=([\d.]+)'
    r'\s+ETH NAV=\$?([\d.]+)\s+exp=([\d.]+)'
)
_RE_PORT_EXP   = re.compile(
    r'\[fund_v[12]\] Portfolio aggregate target exposure:\s*([\d.]+)'
)

_SLEEVE_MAP = {"BTC_1H": "btc_1h", "BTC_4H": "btc_4h",
               "ETH_1H": "eth_1h", "ETH_4H": "eth_4h"}


@dataclass
class SleeveSnap:
    regime:     str   = ""
    action:     str   = ""
    raw_conf:   float = 0.0
    cal_conf:   float = 0.0
    desired_exp: float = 0.0
    reason:     str   = ""


@dataclass
class FundCycle:
    num:            int   = 0
    wall_ts:        str   = ""
    btc_1h:         SleeveSnap = dc_field(default_factory=SleeveSnap)
    btc_4h:         SleeveSnap = dc_field(default_factory=SleeveSnap)
    eth_1h:         SleeveSnap = dc_field(default_factory=SleeveSnap)
    eth_4h:         SleeveSnap = dc_field(default_factory=SleeveSnap)
    btc_gov:        str   = ""
    eth_gov:        str   = ""
    portfolio_nav:  float = 0.0
    btc_nav:        float = 0.0
    eth_nav:        float = 0.0
    port_target_exp: float = 0.0
    btc_exp:        float = 0.0
    eth_exp:        float = 0.0


def parse_fund_cycles(lines: list[str]) -> list[FundCycle]:
    cycles: list[FundCycle] = []
    current: FundCycle | None = None

    for line in lines:
        m = _RE_FUND_CYCLE.search(line)
        if m:
            if current:
                cycles.append(current)
            current = FundCycle(num=int(m.group(1)), wall_ts=m.group(2))
            continue

        if current is None:
            continue

        m = _RE_SLEEVE.search(line)
        if m:
            label, regime, action, raw, cal, desired_exp, reason = m.groups()
            attr = _SLEEVE_MAP.get(label)
            if attr:
                setattr(current, attr, SleeveSnap(
                    regime=regime, action=action,
                    raw_conf=float(raw), cal_conf=float(cal),
                    desired_exp=float(desired_exp), reason=reason.strip(),
                ))
            continue

        m = _RE_GOV.search(line)
        if m:
            asset, action, target, approved = m.groups()
            val = f"{action}  target={float(target):.3f}  ok={approved}"
            if asset == "BTC":
                current.btc_gov = val
            else:
                current.eth_gov = val
            continue

        m = _RE_FUND_NAV.search(line)
        if m:
            current.portfolio_nav = float(m.group(1))
            current.btc_nav       = float(m.group(2))
            current.btc_exp       = float(m.group(3))
            current.eth_nav       = float(m.group(4))
            current.eth_exp       = float(m.group(5))
            continue

        m = _RE_PORT_EXP.search(line)
        if m:
            current.port_target_exp = float(m.group(1))

    if current:
        cycles.append(current)
    return cycles


# ── Charts ────────────────────────────────────────────────────────────────────

def build_nav_exp_chart(cycles: list[FundCycle]) -> go.Figure:
    """NAV history (top) + Exposure history (bottom) as a 2-panel chart."""
    labels = [f"#{c.num}" for c in cycles]

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.58, 0.42],
        vertical_spacing=0.07,
        subplot_titles=("NAV", "Exposure"),
    )

    # NAV panel
    fig.add_hline(y=INITIAL_CAPITAL, line_dash="dot", line_color="#374151",
                  annotation_text="$100k", annotation_font_color="#6b7280",
                  annotation_font_size=9, row=1, col=1)
    fig.add_trace(go.Scatter(
        x=labels, y=[c.portfolio_nav for c in cycles], name="Portfolio",
        mode="lines+markers", line=dict(color="#a78bfa", width=2), marker=dict(size=4),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=labels, y=[c.btc_nav for c in cycles], name="BTC NAV",
        mode="lines", line=dict(color="#f7931a", width=1.5, dash="dot"),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=labels, y=[c.eth_nav for c in cycles], name="ETH NAV",
        mode="lines", line=dict(color="#627eea", width=1.5, dash="dot"),
    ), row=1, col=1)

    # Exposure panel
    fig.add_trace(go.Scatter(
        x=labels, y=[c.port_target_exp for c in cycles], name="Port Target Exp",
        mode="lines+markers", line=dict(color="#a78bfa", width=2), marker=dict(size=3),
        fill="tozeroy", fillcolor="rgba(167,139,250,0.07)",
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=labels, y=[c.btc_exp for c in cycles], name="BTC Exp",
        mode="lines", line=dict(color="#f7931a", width=1.5, dash="dot"),
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=labels, y=[c.eth_exp for c in cycles], name="ETH Exp",
        mode="lines", line=dict(color="#627eea", width=1.5, dash="dot"),
    ), row=2, col=1)

    fig.update_layout(
        height=340,
        margin=dict(l=0, r=0, t=26, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#9ca3af", size=11),
        legend=dict(orientation="h", yanchor="bottom", y=1.07,
                    xanchor="right", x=1, font=dict(size=10)),
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=False, zeroline=False, tickfont=dict(size=9, color="#6b7280"))
    fig.update_yaxes(showgrid=True, gridcolor="#1a2030", zeroline=False,
                     tickfont=dict(size=9, color="#6b7280"))
    fig.update_yaxes(tickprefix="$", tickformat=",.0f", row=1, col=1)
    fig.update_yaxes(tickformat=".0%", row=2, col=1)
    for ann in fig.layout.annotations:
        ann.font.size = 10
        ann.font.color = "#6b7280"
    return fig


# ── Color-coded raw log renderer ──────────────────────────────────────────────

def _log_class(line: str) -> str:
    if "── Cycle" in line:           return "lc"
    if "Sleeping" in line:           return "lslp"
    if "WARNING" in line:            return "lwrn"
    if "ERROR" in line:              return "lerr"
    if "DeprecationWarning" in line or "self.last_updated" in line: return "lsys"
    if "Portfolio NAV=" in line:     return "lnav"
    if "Fill:" in line:              return "lbuy" if "BUY" in line else "lsel"
    if "governor:" in line:
        if "action=BUY" in line or "action=ENTER" in line: return "lbuy"
        if "action=SELL" in line or "action=EXIT" in line: return "lsel"
        return "lnav"
    if "BTC" in line:
        if "action=BUY" in line or "action=ENTER" in line: return "lbuy"
        if "action=SELL" in line or "action=EXIT" in line: return "lsel"
        return "lb"
    if "ETH" in line:
        if "action=BUY" in line or "action=ENTER" in line: return "lbuy"
        if "action=SELL" in line or "action=EXIT" in line: return "lsel"
        return "le"
    return "ldef"


def render_log_html(lines: list[str]) -> str:
    parts = ['<div class="log-wrap">']
    for line in lines:
        cls  = _log_class(line)
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        parts.append(f'<p class="ll {cls}">{safe}</p>')
    parts.append("</div>")
    return "".join(parts)


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### Fund")
    selected_fund = st.radio(
        "Select fund",
        options=["fund_v1_current", "fund_v2_crypto_hybrid_eth4h_cap75"],
        format_func=lambda x: (
            "Fund v1 — current" if x == "fund_v1_current"
            else "Fund v2 — paper candidate"
        ),
        label_visibility="collapsed",
        key="fund_selector",
    )
    if selected_fund == "fund_v2_crypto_hybrid_eth4h_cap75":
        st.caption(
            "⚠ Fund v2 is a research/paper candidate.\n"
            "Paper only — not live."
        )
    st.divider()
    st.markdown("### Controls")
    if st.button("⟳  Refresh Now", use_container_width=True, type="primary"):
        st.rerun()
    st.divider()
    auto_refresh     = st.toggle("Auto-refresh", value=True)
    refresh_interval = st.select_slider(
        "Interval", options=[15, 30, 60, 120, 300], value=60,
        format_func=lambda s: f"{s}s", disabled=not auto_refresh,
    )
    st.divider()
    st.markdown("### Activity Log")
    log_cycles = st.slider("Cycles to show", min_value=5, max_value=50, value=20, step=5)
    show_log   = st.checkbox("Show log", value=True)
    st.divider()
    st.caption("**dashboard.iteradynamics.com**\nFund v1/v2 · Port 8504")


# ── Dashboard fragment ────────────────────────────────────────────────────────

@st.fragment(run_every=refresh_interval if auto_refresh else None)
def render_dashboard(log_cycles: int, show_log: bool, selected_fund: str) -> None:
    # ── Select data sources based on fund choice ───────────────────────────────
    is_v2 = selected_fund == "fund_v2_crypto_hybrid_eth4h_cap75"
    active_state_path = FUND_V2_STATE  if is_v2 else FUND_V1_STATE
    active_fills_path = FUND_V2_FILLS  if is_v2 else FUND_V1_FILLS
    active_log_path   = FUND_V2_LOG    if is_v2 else FUND_V1_LOG
    active_script     = FUND_V2_SCRIPT if is_v2 else FUND_V1_SCRIPT

    state      = load_state(active_state_path)
    fills      = load_fills(active_fills_path)
    run_state, run_label = runner_status(active_script)
    raw_lines  = fund_logs_raw(n=max(log_cycles * 15 + 50, 600), log_path=active_log_path)
    all_cycles = parse_fund_cycles(raw_lines)

    # ════════════════════════════════════════════════════════════════════════
    # 1 ▸ HEADER
    # ════════════════════════════════════════════════════════════════════════
    col_title, col_svc, col_cd = st.columns([5, 1, 1])

    with col_title:
        fund_label = "Fund v2 (paper)" if is_v2 else "Fund v1"
        st.title(f"IteraDynamics — {fund_label}")
        if is_v2:
            st.markdown(
                "<div style='background:rgba(251,191,36,0.08);border:1px solid "
                "rgba(251,191,36,0.35);color:#fde68a;border-radius:6px;"
                "padding:0.3rem 0.8rem;font-size:0.82rem;margin-bottom:0.3rem'>"
                "⚠ <b>fund_v2_crypto_hybrid_eth4h_cap75</b> — research/paper candidate. "
                "Read-only view. Not live.</div>",
                unsafe_allow_html=True,
            )

    with col_svc:
        dot = {"running": "🟢", "stopped": "⚫"}.get(run_state, "🟡")
        st.metric("Runner", f"{dot} {run_label}")
        st.caption(f"Fetched {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")

    with col_cd:
        cd = next_cycle_countdown(raw_lines)
        if cd and cd[0] > 0:
            remaining, total = cd
            pct = int((1 - remaining / total) * 100) if total else 0
            st.markdown(
                f"<div class='cd-box'><div class='cd-lbl'>Next Cycle</div>"
                f"<div class='cd-val'>{fmt_countdown(remaining)}</div>"
                f"<div class='cd-sub'>{pct}% through wait</div></div>",
                unsafe_allow_html=True,
            )
        else:
            sub = "sleeping…" if run_state == "running" else run_label.lower()
            st.markdown(
                f"<div class='cd-box'><div class='cd-lbl'>Next Cycle</div>"
                f"<div class='cd-val'>—</div><div class='cd-sub'>{sub}</div></div>",
                unsafe_allow_html=True,
            )

    # ── Status strip ────────────────────────────────────────────────────────
    s           = state or {}
    mode        = s.get("mode", "—")
    strategy    = s.get("strategy", "—")
    cycle_n     = s.get("cycle", "—")
    last_upd_s  = s.get("last_updated", "")
    last_upd_label, staleness_mins = last_updated_ago(last_upd_s)
    port_nav_s  = s.get("portfolio_nav", 0.0)
    port_tgt_s  = s.get("portfolio_target_exposure", 0.0)
    cal_loaded  = s.get("calibrator_loaded", False)
    cal_method  = s.get("calibrator_method", "—")
    cal_n       = s.get("calibrator_n_samples", 0)
    cal_source  = s.get("calibrator_source", "—")
    cal_color   = "#4ade80" if cal_loaded else "#fbbf24"
    cal_str     = "✓ Yes" if cal_loaded else "⚠ No"

    st.markdown(
        f"""<div class="status-panel"><div class="status-row">
  <div class="status-kv"><div class="status-k">Mode</div><div class="status-v">{mode}</div></div>
  <div class="status-kv"><div class="status-k">Strategy</div><div class="status-v" style="font-size:0.76rem">{strategy}</div></div>
  <div class="status-kv"><div class="status-k">Cycle</div><div class="status-v">{cycle_n}</div></div>
  <div class="status-kv"><div class="status-k">Last Update</div><div class="status-v">{last_upd_label}</div></div>
  <div class="status-kv"><div class="status-k">Portfolio NAV</div><div class="status-v">{_usd(port_nav_s)}</div></div>
  <div class="status-kv"><div class="status-k">Target Exposure</div><div class="status-v">{port_tgt_s:.1%}</div></div>
  <div class="status-kv"><div class="status-k">Calibrator</div><div class="status-v" style="color:{cal_color}">{cal_str}</div></div>
  <div class="status-kv"><div class="status-k">Cal Method</div><div class="status-v" style="font-size:0.74rem">{cal_method}</div></div>
  <div class="status-kv"><div class="status-k">Cal Samples</div><div class="status-v">{cal_n:,}</div></div>
  <div class="status-kv"><div class="status-k">Cal Source</div><div class="status-v">{cal_source}</div></div>
</div></div>""",
        unsafe_allow_html=True,
    )

    # ── Why Now? interpretation panel ────────────────────────────────────────
    badge, msg, sev = interpret_state(state, run_state, staleness_mins)
    sev_cls = {"ok": "why-ok", "warn": "why-warn", "err": "why-err"}.get(sev, "why-warn")
    st.markdown(
        f"<div class='why-panel {sev_cls}'>"
        f"<span class='why-badge'>{badge}</span>"
        f"<span class='why-msg'>{msg}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    if state is None:
        return

    st.divider()

    # ════════════════════════════════════════════════════════════════════════
    # 2 ▸ FILL AUDIT PANEL (always visible — armed or active)
    # ════════════════════════════════════════════════════════════════════════
    total_fills = s.get("btc_fill_count", 0) + s.get("eth_fill_count", 0)

    if fills:
        st.markdown("#### Latest Fill Audit")
        latest = fills[0]
        asset  = latest.get("asset", "?")
        side   = latest.get("side", "?")
        side_color = "fill-buy" if side == "BUY" else "fill-sell"

        st.markdown(
            f"<div class='fill-panel'>"
            f"<div class='fill-header {side_color}'>"
            f"{'🟢' if side == 'BUY' else '🔴'} {asset} {side} — "
            f"{latest.get('timestamp', '')[:19]} UTC"
            f"</div>",
            unsafe_allow_html=True,
        )
        fa1, fa2, fa3, fa4 = st.columns(4)
        fa1.metric("Qty",        f"{latest.get('qty', 0):.6f} {asset}")
        fa2.metric("Mid Price",  _usd(latest.get("mid_price")))
        fa3.metric("Fill Price", _usd(latest.get("fill_price")))
        fa4.metric("Slippage",   _usd(latest.get("slippage_cost")))

        fb1, fb2, fb3, fb4 = st.columns(4)
        fb1.metric("Fee",            _usd(latest.get("fee")))
        fb2.metric("Cost (bps)",     _bps(latest.get("cost_bps")))
        fb3.metric("Cash After",     _usd(latest.get("cash_after")))
        fb4.metric("NAV After",      _usd(latest.get("nav_after")))

        fc1, fc2, fc3, fc4 = st.columns(4)
        fc1.metric("Position After", f"{latest.get('position_after', 0):.6f}")
        fc2.metric("Avg Entry",      _usd(latest.get("avg_entry_price")))
        fc3.metric("Realized PnL",   _usd(latest.get("realized_pnl")))
        fc4.metric("Total Fills",    total_fills)

        st.markdown("</div>", unsafe_allow_html=True)

        if len(fills) > 1:
            with st.expander(f"All fills ({len(fills)} total)", expanded=False):
                fill_rows = []
                for f in fills[:30]:
                    side_f = f.get("side", "")
                    fill_rows.append({
                        "Time":     (f.get("timestamp") or "")[:16],
                        "Asset":    f.get("asset", ""),
                        "Side":     f.get("side", ""),
                        "Qty":      f.get("qty", 0),
                        "Fill $":   f.get("fill_price", 0),
                        "Slip $":   f.get("slippage_cost", 0),
                        "Fee $":    f.get("fee", 0),
                        "Bps":      f.get("cost_bps", 0),
                        "NAV Aft":  f.get("nav_after", 0),
                        "R.PnL":    f.get("realized_pnl", 0),
                    })
                st.dataframe(
                    pd.DataFrame(fill_rows),
                    column_config={
                        "Time":    st.column_config.TextColumn("Time",    width="medium"),
                        "Asset":   st.column_config.TextColumn("Asset",   width="small"),
                        "Side":    st.column_config.TextColumn("Side",    width="small"),
                        "Qty":     st.column_config.NumberColumn("Qty",   format="%.6f", width="medium"),
                        "Fill $":  st.column_config.NumberColumn("Fill $", format="$%.2f", width="medium"),
                        "Slip $":  st.column_config.NumberColumn("Slip $", format="$%.4f", width="small"),
                        "Fee $":   st.column_config.NumberColumn("Fee $",  format="$%.4f", width="small"),
                        "Bps":     st.column_config.NumberColumn("Bps",    format="%.2f",  width="small"),
                        "NAV Aft": st.column_config.NumberColumn("NAV Aft", format="$%.2f", width="medium"),
                        "R.PnL":   st.column_config.NumberColumn("R.PnL",   format="$%.4f", width="medium"),
                    },
                    hide_index=True,
                    use_container_width=True,
                )
    else:
        st.markdown(
            "<div class='fill-armed'>⚡ First Fill Audit — armed and waiting for first fill.</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ════════════════════════════════════════════════════════════════════════
    # 3 ▸ PORTFOLIO ACCOUNTING
    # ════════════════════════════════════════════════════════════════════════
    st.markdown("#### Portfolio Accounting")

    port_nav       = state.get("portfolio_nav", 0.0)
    btc_cash       = state.get("btc_cash", 0.0)
    eth_cash       = state.get("eth_cash", 0.0)
    total_cash     = btc_cash + eth_cash
    total_pos_val  = port_nav - total_cash
    total_rpnl     = state.get("total_realized_pnl")
    total_upnl     = state.get("total_unrealized_pnl")
    total_fees     = state.get("total_fees")
    total_slippage = state.get("total_slippage")
    total_pnl      = (total_rpnl + total_upnl) if (total_rpnl is not None and total_upnl is not None) else None
    port_pnl_usd   = port_nav - INITIAL_CAPITAL
    port_pnl_pct   = pnl_pct(port_nav, INITIAL_CAPITAL)

    btc_nav_s  = state.get("btc_nav", 0.0)
    eth_nav_s  = state.get("eth_nav", 0.0)
    nav_drift  = port_nav - (btc_nav_s + eth_nav_s)
    drift_cls  = "drift-warn" if abs(nav_drift) > 0.01 else "drift-ok"
    drift_label = f"{nav_drift:+.4f}" if abs(nav_drift) > 0.001 else "✓ balanced"

    ca1, ca2, ca3, ca4 = st.columns(4)
    ca1.metric("Portfolio NAV",  _usd(port_nav),
               delta=fmt_pct(port_pnl_pct), delta_color="normal")
    ca2.metric("Total Cash",     _usd(total_cash))
    ca3.metric("Position Value", _usd(total_pos_val))
    ca4.metric("NAV P&L",        _usd(port_pnl_usd),
               delta=fmt_pct(port_pnl_pct), delta_color="normal")

    cb1, cb2, cb3, cb4, cb5 = st.columns(5)
    cb1.metric("Realized PnL",   _usd(total_rpnl))
    cb2.metric("Unrealized PnL", _usd(total_upnl))
    cb3.metric("Total PnL",      _usd(total_pnl))
    cb4.metric("Cumul Fees",     _usd(total_fees))
    cb5.metric("Cumul Slippage", _usd(total_slippage))

    # Per-broker NAV drift from state (authoritative) or computed fallback
    btc_drift_state = state.get("btc_nav_drift")
    eth_drift_state = state.get("eth_nav_drift")
    drift_detail = ""
    if btc_drift_state is not None and eth_drift_state is not None:
        drift_detail = (
            f"  btc_drift={btc_drift_state:+.6f}  eth_drift={eth_drift_state:+.6f}"
        )

    st.markdown(
        f"<div style='font-size:0.77rem;margin-top:0.2rem;margin-bottom:0.3rem'>"
        f"NAV conservation drift: <span class='{drift_cls}'>{drift_label}</span>"
        f"<span style='color:#4b5563;margin-left:0.5em'>(portfolio_nav − btc_nav − eth_nav)"
        f"{drift_detail}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    if len(all_cycles) >= 2:
        st.plotly_chart(build_nav_exp_chart(all_cycles), use_container_width=True,
                        config={"displayModeBar": False})
    else:
        st.caption("Accumulating cycle data for NAV + Exposure chart…")

    st.divider()

    # ════════════════════════════════════════════════════════════════════════
    # 4 ▸ PER-ASSET ACCOUNTING
    # ════════════════════════════════════════════════════════════════════════
    st.markdown("#### Per-Asset Accounting")
    col_btc, col_eth = st.columns(2)

    def render_asset(col, prefix: str, asset: str, alloc: float) -> None:
        hdr_cls = "btc-header" if asset == "BTC" else "eth-header"
        symbol  = "₿" if asset == "BTC" else "Ξ"
        key     = prefix.lower()

        with col:
            st.markdown(
                f"<div class='asset-header {hdr_cls}'>{symbol} {asset} "
                f"<span style='font-weight:400;font-size:0.78rem'>"
                f"({prefix}_1H 25% + {prefix}_4H 25%)</span></div>",
                unsafe_allow_html=True,
            )

            nav       = state.get(f"{key}_nav", 0.0)
            exp       = state.get(f"{key}_exposure", 0.0)
            units     = state.get(f"{key}_position_units", 0.0)
            cash      = state.get(f"{key}_cash", 0.0)
            fills_n   = state.get(f"{key}_fill_count", 0)
            hwm       = state.get(f"{key}_high_water_mark", nav) or nav
            halted    = state.get(f"{key}_drawdown_halted", False)
            dd        = drawdown_pct(nav, hwm)
            avg_entry = state.get(f"{key}_avg_entry_price")
            rpnl      = state.get(f"{key}_realized_pnl")
            upnl      = state.get(f"{key}_unrealized_pnl")
            cum_fees  = state.get(f"{key}_cumulative_fees")
            cum_slip  = state.get(f"{key}_cumulative_slippage")

            if halted:
                st.markdown(
                    "<div class='halted-banner'>⛔ DRAWDOWN GOVERNOR HALTED</div>",
                    unsafe_allow_html=True,
                )

            r1, r2, r3 = st.columns(3)
            r1.metric("NAV",  _usd(nav),       delta=fmt_pct(pnl_pct(nav, alloc)), delta_color="normal")
            r2.metric("P&L",  _usd(nav-alloc), delta=fmt_pct(pnl_pct(nav, alloc)), delta_color="normal")
            r3.metric("HWM",  _usd(hwm))

            r4, r5, r6 = st.columns(3)
            r4.metric("Cash",             _usd(cash))
            r5.metric(f"Units ({asset})", f"{units:.6f}")
            r6.metric("Fills",            fills_n)

            r7, r8, r9 = st.columns(3)
            r7.metric("Avg Entry",      _usd(avg_entry) if avg_entry else "—")
            r8.metric("Realized PnL",   _usd(rpnl))
            r9.metric("Unrealized PnL", _usd(upnl))

            r10, r11, r12 = st.columns(3)
            r10.metric("Cumul Fees",     _usd(cum_fees))
            r11.metric("Cumul Slippage", _usd(cum_slip))
            r12.metric("Drawdown",       f"{dd:.2f}%",
                       delta="HALTED" if halted else None,
                       delta_color="inverse" if halted else "off")

            st.markdown("<div class='exp-label'>Exposure</div>", unsafe_allow_html=True)
            st.progress(min(exp, 1.0), text=f"{exp:.1%}")

    render_asset(col_btc, "BTC", "BTC", BTC_ALLOC)
    render_asset(col_eth, "ETH", "ETH", ETH_ALLOC)

    st.divider()

    # ════════════════════════════════════════════════════════════════════════
    # 5 ▸ CALIBRATION EFFECT + SLEEVE INTENT
    # ════════════════════════════════════════════════════════════════════════
    st.markdown("#### Sleeve Intent")
    sleeves = state.get("sleeves", [])

    if sleeves:
        # Calibration effect summary
        cal_sum = cal_effect_summary(sleeves)
        has_active = "active" in cal_sum.lower() or "amplify" in cal_sum.lower() or "suppress" in cal_sum.lower()
        cal_cls = "cal-active" if has_active else "cal-none"
        st.markdown(
            f"<div class='cal-effect-bar'>"
            f"<span style='color:#6b7280;font-size:0.70rem;text-transform:uppercase;letter-spacing:0.07em'>Cal Effect</span>"
            f"<span class='{cal_cls}'>{cal_sum}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        _ACTION_ICON = {
            "BUY": "🟢", "ENTER": "🟢", "SELL": "🔴", "EXIT": "🔴",
            "HOLD": "⬜", "FLAT": "·",
        }
        rows = []
        for sv in sleeves:
            action    = sv.get("action", "")
            icon      = _ACTION_ICON.get(action, "·")
            raw_c     = sv.get("raw_confidence", 0.0)
            cal_c     = sv.get("calibrated_confidence", 0.0)
            delta     = cal_c - raw_c
            bar_age   = sv.get("bar_age_seconds")
            age_label = "—"
            if bar_age is not None and bar_age >= 0:
                if bar_age < 3600:
                    age_label = f"{bar_age // 60}m"
                elif bar_age < 86400:
                    age_label = f"{bar_age // 3600}h {(bar_age % 3600) // 60}m"
                else:
                    age_label = f"{bar_age // 86400}d"
            rows.append({
                "Sleeve":      sv.get("label", ""),
                "Asset":       sv.get("asset", ""),
                "TF":          sv.get("timeframe", ""),
                "Regime":      sv.get("regime", ""),
                "Action":      f"{icon} {action}",
                "Raw":         raw_c,
                "Cal":         cal_c,
                "Cal Δ":       delta,
                "Effect":      cal_effect_label(delta),
                "Desired Exp": sv.get("desired_exposure", 0.0),
                "Wtd Contrib": sv.get("weighted_contribution", 0.0),
                "Bar Age":     age_label,
                "Bar (UTC)":   (sv.get("bar_timestamp") or "")[:16],
                "Reason":      (sv.get("reason") or "")[:70],
            })

        st.dataframe(
            pd.DataFrame(rows),
            column_config={
                "Sleeve":      st.column_config.TextColumn("Sleeve",      width="small"),
                "Asset":       st.column_config.TextColumn("Asset",       width="small"),
                "TF":          st.column_config.TextColumn("TF",          width="small"),
                "Regime":      st.column_config.TextColumn("Regime",      width="medium"),
                "Action":      st.column_config.TextColumn("Action",      width="medium"),
                "Raw":         st.column_config.NumberColumn("Raw",       format="%.3f", width="small"),
                "Cal":         st.column_config.NumberColumn("Cal",       format="%.3f", width="small"),
                "Cal Δ":       st.column_config.NumberColumn("Cal Δ",     format="%+.3f", width="small"),
                "Effect":      st.column_config.TextColumn("Effect",      width="small"),
                "Desired Exp": st.column_config.NumberColumn("Desired Exp", format="%.3f", width="small"),
                "Wtd Contrib": st.column_config.NumberColumn("Wtd Contrib", format="%.3f", width="small"),
                "Bar Age":     st.column_config.TextColumn("Bar Age",     width="small"),
                "Bar (UTC)":   st.column_config.TextColumn("Bar (UTC)",   width="medium"),
                "Reason":      st.column_config.TextColumn("Reason",      width="large"),
            },
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("No sleeve data yet — waiting for first cycle.")

    # ════════════════════════════════════════════════════════════════════════
    # 6 ▸ GOVERNOR / DECISION PANEL (enhanced)
    # ════════════════════════════════════════════════════════════════════════
    st.markdown("#### Governor / Last Decision")

    gov_detail          = parse_gov_from_log(raw_lines)
    rebalance_threshold = state.get("rebalance_threshold")

    def _gov_css(action: str) -> str:
        if action in ("BUY", "ENTER"):  return "gov-buy"
        if action in ("SELL", "EXIT"):  return "gov-sell"
        return "gov-hold"

    def render_gov_panel(col, asset: str, asset_css: str, symbol: str) -> None:
        gd          = gov_detail.get(asset, {})
        action      = gd.get("action", state.get(f"last_{asset.lower()}_decision", "—") or "—")
        approved    = gd.get("approved", False)
        target_exp  = gd.get("target", 0.0)
        reason      = gd.get("reason", "")
        blocked_by  = gd.get("blocked_by", "")
        current_exp = state.get(f"{asset.lower()}_exposure", 0.0)
        delta_exp   = target_exp - current_exp

        # If we only have the state string (no log parse), extract action
        if not gd and isinstance(action, str):
            m = re.search(r'(\w+)\s+approved=(\w+)', action)
            if m:
                action   = m.group(1)
                approved = m.group(2).lower() == "true"

        act_css      = _gov_css(action)
        appr_badge   = "gov-approved" if approved else "gov-unapproved"
        appr_text    = "✓ approved" if approved else "✗ not approved"
        blocked_html = (f"<span class='gov-blocked'>blocked: {blocked_by}</span>"
                        if blocked_by else "")

        thr_html = (
            f"<span style='color:#4b5563'>threshold {rebalance_threshold:.2f}</span>"
            if rebalance_threshold is not None else ""
        )
        with col:
            st.markdown(
                f"<div class='gov-panel'>"
                f"<div class='gov-asset {asset_css}'>{symbol} {asset} Governor</div>"
                f"<div class='gov-action-line'>"
                f"<span class='gov-action {act_css}'>{action}</span>"
                f"<span class='gov-badge {appr_badge}'>{appr_text}</span>"
                f"{blocked_html}"
                f"</div>"
                f"<div class='gov-meta'>"
                f"<span>target {target_exp:.1%}</span>"
                f"<span>current {current_exp:.1%}</span>"
                f"<span>Δ {delta_exp:+.1%}</span>"
                f"{thr_html}"
                f"</div>"
                f"<div class='gov-reason'>{reason[:100] if reason else '—'}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    gc1, gc2 = st.columns(2)
    render_gov_panel(gc1, "BTC", "gov-btc", "₿")
    render_gov_panel(gc2, "ETH", "gov-eth", "Ξ")

    # ════════════════════════════════════════════════════════════════════════
    # 7 ▸ EVENT LOG
    # ════════════════════════════════════════════════════════════════════════
    if show_log:
        st.divider()
        st.markdown("#### Event Log")

        events   = parse_structured_events(raw_lines, max_events=100)
        n_cycles = min(len(all_cycles), log_cycles)

        tab_events, tab_cycles, tab_raw = st.tabs(
            [f"Events ({len(events)})", f"Cycles ({n_cycles})", "Raw Log"]
        )

        # ── Events tab ──────────────────────────────────────────────────────
        with tab_events:
            if events:
                ALL_TYPES      = ["FILL", "GOV_ACTIVE", "GOV_HOLD", "CAL",
                                  "CYCLE", "NAV", "SAVE", "ERROR", "WARN"]
                DEFAULT_TYPES  = ["FILL", "GOV_ACTIVE", "CAL", "ERROR", "WARN", "CYCLE"]
                present_types  = sorted({e["type"] for e in events},
                                        key=lambda t: ALL_TYPES.index(t) if t in ALL_TYPES else 99)
                default_sel    = [t for t in present_types if t in DEFAULT_TYPES]

                type_filter = st.multiselect(
                    "Filter event types",
                    options=present_types,
                    default=default_sel,
                    label_visibility="collapsed",
                )
                shown = [e for e in events if e["type"] in type_filter] if type_filter else events
                ev_rows = [
                    {"Time": e["ts"], "": e["icon"], "Type": e["type"],
                     "Event": e["summary"], "Detail": e["detail"]}
                    for e in shown
                ]
                st.dataframe(
                    pd.DataFrame(ev_rows),
                    column_config={
                        "Time":   st.column_config.TextColumn("Time",   width="medium"),
                        "":       st.column_config.TextColumn("",       width="small"),
                        "Type":   st.column_config.TextColumn("Type",   width="small"),
                        "Event":  st.column_config.TextColumn("Event",  width="large"),
                        "Detail": st.column_config.TextColumn("Detail", width="large"),
                    },
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.info("No structured events found in current log window.")

        # ── Cycles tab ──────────────────────────────────────────────────────
        with tab_cycles:
            display_cycles = all_cycles[-log_cycles:]
            if display_cycles:
                _AICO = {"BUY": "🟢", "ENTER": "🟢", "SELL": "🔴", "EXIT": "🔴",
                         "HOLD": "⬜", "FLAT": "·", "": "·"}

                def _fmt_sl(sv: SleeveSnap) -> str:
                    icon    = _AICO.get(sv.action, "·")
                    exp_str = f"{sv.desired_exp:.0%}" if sv.desired_exp else "0%"
                    return f"{icon} {sv.action or '·'}  [{sv.regime or '—'}]  {exp_str}"

                rows = []
                for i, c in enumerate(display_cycles):
                    prev  = display_cycles[i-1].portfolio_nav if i > 0 else c.portfolio_nav
                    delta = c.portfolio_nav - prev if i > 0 else 0.0
                    rows.append({
                        "#":    c.num,
                        "B1H":  _fmt_sl(c.btc_1h),
                        "B4H":  _fmt_sl(c.btc_4h),
                        "E1H":  _fmt_sl(c.eth_1h),
                        "E4H":  _fmt_sl(c.eth_4h),
                        "BTC NAV": c.btc_nav,
                        "ETH NAV": c.eth_nav,
                        "Port NAV": c.portfolio_nav,
                        "NAV Δ":   delta,
                        "Exp":     c.port_target_exp,
                    })

                st.dataframe(
                    pd.DataFrame(rows[::-1]),
                    column_config={
                        "#":       st.column_config.NumberColumn("#",        width="small"),
                        "B1H":     st.column_config.TextColumn("B1H",        width="large"),
                        "B4H":     st.column_config.TextColumn("B4H",        width="large"),
                        "E1H":     st.column_config.TextColumn("E1H",        width="large"),
                        "E4H":     st.column_config.TextColumn("E4H",        width="large"),
                        "BTC NAV": st.column_config.NumberColumn("BTC NAV",  format="$%.0f", width="small"),
                        "ETH NAV": st.column_config.NumberColumn("ETH NAV",  format="$%.0f", width="small"),
                        "Port NAV":st.column_config.NumberColumn("Port NAV", format="$%.0f", width="small"),
                        "NAV Δ":   st.column_config.NumberColumn("NAV Δ",    format="$+.2f", width="small"),
                        "Exp":     st.column_config.NumberColumn("Exp",      format="%.1%",  width="small"),
                    },
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.info("No fund_v1 cycle data in the current log window.")

        # ── Raw Log tab ──────────────────────────────────────────────────────
        with tab_raw:
            with st.expander("Raw log (debugging)", expanded=False):
                fc, lc = st.columns([3, 1])
                with fc:
                    log_filter = st.selectbox(
                        "Filter",
                        ["All", "Fund v1 only", "BTC only", "ETH only",
                         "Sleeves only", "Governor only"],
                        label_visibility="collapsed",
                    )
                with lc:
                    log_n = st.number_input(
                        "Lines", min_value=50, max_value=600, value=200, step=50,
                        label_visibility="collapsed",
                    )

                display_lines = raw_lines[-int(log_n):]
                if log_filter == "Fund v1 only":
                    display_lines = [ln for ln in display_lines if "[fund_v1]" in ln]
                elif log_filter == "BTC only":
                    display_lines = [ln for ln in display_lines if "BTC" in ln]
                elif log_filter == "ETH only":
                    display_lines = [ln for ln in display_lines if "ETH" in ln]
                elif log_filter == "Sleeves only":
                    display_lines = [ln for ln in display_lines if "Sleeve" in ln]
                elif log_filter == "Governor only":
                    display_lines = [ln for ln in display_lines if "governor" in ln]

                st.caption(f"Showing {len(display_lines)} lines · newest at bottom")
                st.markdown(render_log_html(display_lines), unsafe_allow_html=True)


render_dashboard(log_cycles, show_log, selected_fund)
