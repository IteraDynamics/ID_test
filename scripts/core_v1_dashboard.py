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
import streamlit.components.v1 as components
from plotly.subplots import make_subplots

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from runtime.core_v1.dashboard.charts import nav_chart, DRAWDOWN_AXIS_FLOOR

from runtime.core_v1.dashboard.formatting import (
    age_seconds, format_duration, age_text, money, signed_money, pct, signed_pct,
    num, esc, css_class_for_value, status_badge, sleeve_status, friendly_ts, strategy_display,
)

from runtime.core_v1.dashboard.snapshots import (
    read_json, read_jsonl, parse_ts, intraday_nav_baseline, latest_same_day_navs,
)

from runtime.core_v1.allocation import SELECTED_CORE_V1_SCENARIO, SELECTED_CORE_V1_SLEEVES
from scripts.core_v1_dashboard_health import (
    LARGEST_DRIFT_CAVEAT,
    audit_failure_lines,
    derive_audit_trust,
    nav_history,
    runtime_identity_view,
)

STATE_PATH = Path(os.getenv("CORE_V1_STATE_PATH", "/opt/itera/runtime/core_v1/state.json"))
SIGNALS_LOG = Path(os.getenv("CORE_V1_SIGNALS_LOG", "/opt/itera/logs/core_v1_signals.jsonl"))
FILLS_LOG = Path(os.getenv("CORE_V1_FILLS_LOG", "/opt/itera/logs/core_v1_fills.jsonl"))
MARKET_DATA_LOG = Path(os.getenv("CORE_V1_MARKET_DATA_LOG", "/opt/itera/logs/core_v1_market_data.jsonl"))
ERROR_LOG = SIGNALS_LOG.with_name("core_v1_errors.jsonl")
AUDIT_REPORT_PATH = Path(os.getenv("CORE_V1_AUDIT_REPORT_PATH", str(STATE_PATH.with_name("core_v1_audit_report.json"))))
RUNTIME_IDENTITY_PATH = Path(os.getenv("CORE_V1_RUNTIME_IDENTITY_PATH", str(STATE_PATH.with_name("core_v1_runtime_identity.json"))))
PAPER_EXPORT_DIR = Path(os.getenv("CORE_V1_PAPER_EXPORT_DIR", str(REPO_ROOT / "artifacts" / "core_v1_paper_export")))
EXPECTED_POLL_SECONDS = int(os.getenv("CORE_V1_POLL_SECONDS", "3600"))
STALE_AFTER_SECONDS = int(os.getenv("CORE_V1_STALE_AFTER_SECONDS", str(EXPECTED_POLL_SECONDS * 2 + 300)))
STALE_AUDIT_AFTER_SECONDS = int(os.getenv("CORE_V1_STALE_AUDIT_AFTER_SECONDS", str(EXPECTED_POLL_SECONDS * 6)))
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
# One-word regime read for the Market Regime hero card — same underlying
# regime taxonomy as REGIME_DISPLAY, phrased for a plain-English summary.
REGIME_WORD = {
    "TREND_UP": ("Bullish", "good"),
    "TREND_DOWN": ("Bearish", "bad"),
    "RANGE": ("Range-bound", "muted"),
    "VOL_COMPRESSION": ("Compressing", "muted"),
    "VOL_EXPANSION": ("Expanding", "muted"),
    "HIGH_VOL": ("Volatile", "muted"),
    "UNKNOWN": ("Unknown", "muted"),
    "MIXED": ("Mixed", "muted"),
}
POSTURE_NARRATIVE = {
    "RISK ON": "Growth Exposure",
    "BALANCED": "Balanced Exposure",
    "DEFENSIVE": "Capital Preservation",
}

def inject_scroll_and_expander_persistence() -> None:
    """Keep scroll position and expander state stable across Streamlit reruns.

    There is deliberately no timer and no hard browser navigation of any
    kind here — that always resets scroll to the top and collapses
    expanders, which is exactly what we're avoiding. The dashboard only
    updates when the operator clicks "Refresh now" (a native st.button,
    which reruns the script over the existing websocket connection instead
    of navigating the page). Even so, Streamlit's own rerun zeroes out the
    scroll container's scrollTop (sometimes more than once as content keeps
    settling), so this continuously tracks the last known-good scroll
    position and snaps back to it the instant the container unexpectedly
    reads 0, rather than reacting to reruns directly — which would otherwise
    fight the operator's own fresh scrolling if a correction was still in
    flight when they moved. Expander open/closed state is saved to
    sessionStorage on toggle and restored the same way.
    """
    components.html(
        """
<script>
(function() {
  const win = window.parent;
  const doc = win.document;
  const EXPANDER_KEY = "core_v1_dashboard_expanders";

  // Streamlit scrolls an internal container (historically
  // [data-testid="stMain"] / [data-testid="stAppViewContainer"]), not the
  // window itself, so find whichever element is actually scrollable.
  function getScrollContainer() {
    // Prefer the known container by existence alone: gating on
    // scrollHeight > clientHeight is unreliable mid-rerun, when content is
    // briefly shorter than the viewport before the rest of the page paints,
    // and would otherwise make this fall through to scanning the whole page
    // and grabbing the wrong (non-scrolling) element for that moment.
    const known = doc.querySelector('[data-testid="stMain"]') || doc.querySelector('[data-testid="stAppViewContainer"]');
    if (known) { return known; }
    let best = null;
    let bestOverflow = 0;
    doc.querySelectorAll("*").forEach(function(el) {
      const overflow = el.scrollHeight - el.clientHeight;
      if (overflow > bestOverflow) { bestOverflow = overflow; best = el; }
    });
    return best || win.document.scrollingElement || doc.documentElement;
  }

  // The expander summary also contains a material-icon ligature span
  // (e.g. "keyboard_arrow_right"/"keyboard_arrow_down") whose text changes
  // with open/closed state, so pull the label from Streamlit's markdown
  // container rather than the summary's full textContent.
  function detailsLabel(d, i) {
    const summary = d.querySelector("summary");
    if (!summary) return "idx:" + i;
    const markdown = summary.querySelector('[data-testid="stMarkdownContainer"]');
    if (markdown) return markdown.textContent.trim();
    return summary.textContent.trim();
  }

  function saveExpanderState() {
    try {
      const map = {};
      doc.querySelectorAll("details").forEach(function(d, i) {
        map[detailsLabel(d, i)] = d.open;
      });
      win.sessionStorage.setItem(EXPANDER_KEY, JSON.stringify(map));
    } catch (e) {}
  }

  function restoreExpanders() {
    try {
      const raw = win.sessionStorage.getItem(EXPANDER_KEY);
      if (!raw) return;
      const map = JSON.parse(raw);
      doc.querySelectorAll("details").forEach(function(d, i) {
        const label = detailsLabel(d, i);
        if (Object.prototype.hasOwnProperty.call(map, label)) { d.open = map[label]; }
      });
    } catch (e) {}
  }

  // Opening/closing an expander is purely client-side, but save the
  // operator's choice immediately (capture phase so this fires even where
  // "toggle" doesn't bubble) so it's already correct if a rerun happens
  // shortly after for an unrelated reason.
  doc.addEventListener("toggle", function() { saveExpanderState(); }, true);
  win.setInterval(saveExpanderState, 1000);

  // A Streamlit rerun (triggered by the refresh button or any other widget)
  // resets the scroll container's scrollTop to 0, sometimes more than once
  // over the following couple of seconds as content keeps settling — even
  // though nothing else about the page changes size. Continuously track the
  // last known-good (nonzero) scrollTop, and step in when the container
  // suddenly reads exactly 0 while we know the operator wasn't already at
  // the top — which is what Streamlit's reset looks like — restoring the
  // last known-good value in that instant. This is scoped to a short window
  // after a DOM mutation (a rerun repainting the page, or an expander
  // revealing content) rather than running unconditionally forever, so it
  // never overrides the operator's own deliberate scroll back to the top
  // once things have been quiet for a couple of seconds.
  let lastKnownGoodScroll = 0;
  let correctUntil = 0;
  const CORRECTION_WINDOW_MS = 2500;
  new win.MutationObserver(function() {
    correctUntil = performance.now() + CORRECTION_WINDOW_MS;
  }).observe(doc.body, { childList: true, subtree: true });
  correctUntil = performance.now() + CORRECTION_WINDOW_MS; // covers the very first page load

  win.setInterval(function() {
    const container = getScrollContainer();
    if (container.scrollTop === 0 && lastKnownGoodScroll > 40 && performance.now() < correctUntil) {
      container.scrollTop = lastKnownGoodScroll;
      restoreExpanders();
    } else {
      lastKnownGoodScroll = container.scrollTop;
    }
  }, 100);
})();
</script>
""",
        height=0,
        width=0,
    )


st.set_page_config(page_title="Itera Mission Control", page_icon="◎", layout="wide", initial_sidebar_state="collapsed")
inject_scroll_and_expander_persistence()

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
.refresh-status { color:#64748b; font-size:.74rem; margin:2px 0 14px 0; }
div[data-testid="stButton"] button { background:#0d1422; border:1px solid #1f2a3d; color:#e5e7eb; border-radius:10px; font-weight:750; font-size:.78rem; padding:4px 10px; }
div[data-testid="stButton"] button:hover { border-color:#38bdf8; color:#38bdf8; }
.badges { display:flex; gap:8px; align-items:center; justify-content:flex-end; flex-wrap:wrap; }
.badge { display:inline-flex; align-items:center; gap:6px; border-radius:999px; padding:6px 11px; font-size:.66rem; letter-spacing:.07em; font-weight:900; text-transform:uppercase; white-space:nowrap; }
.ok { background:#052e26; color:#99f6e4; border:1px solid #0f766e; }
.warn { background:#3b2505; color:#fde68a; border:1px solid #b45309; }
.err { background:#3f0a0a; color:#fecaca; border:1px solid #dc2626; }
.neutral { background:#111827; color:#cbd5e1; border:1px solid #334155; }
.info { background:#0c1e33; color:#bfdbfe; border:1px solid #1d4ed8; }
.unverified { background:#3a1d02; color:#fed7aa; border:1px solid #ea580c; }
.identity-strip { display:flex; flex-wrap:wrap; align-items:center; gap:8px 16px; background:#0d1422; border:1px solid #1f2a3d; border-radius:12px; padding:8px 13px; margin:0 0 12px 0; font-size:.72rem; color:#94a3b8; }
.identity-strip.unknown { background:#3a1d02; border-color:#ea580c; color:#fed7aa; }
.identity-strip .id-k { color:#64748b; text-transform:uppercase; letter-spacing:.07em; font-weight:850; font-size:.62rem; margin-right:5px; }
.identity-strip .id-v { color:#dbe4f0; font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; }
.identity-strip.unknown .id-v { color:#fed7aa; }
.identity-warn { color:#fdba74; font-size:.70rem; margin:-6px 0 12px 2px; display:flex; flex-direction:column; gap:2px; }
.deck-flag { display:flex; align-items:center; gap:9px; background:#3a1d02; border:1px solid #ea580c; color:#fed7aa; border-radius:12px; padding:9px 13px; margin:10px 0 0 0; font-size:.80rem; font-weight:800; letter-spacing:.01em; }
.deck-flag::before { content:"⚠"; font-size:1rem; }
.unverified-banner { display:flex; align-items:center; gap:16px; border-radius:16px; padding:14px 18px; margin:10px 0 16px 0; background:linear-gradient(145deg,#3a1d02 0%, #2a1401 100%); border:1px solid #ea580c; box-shadow:0 18px 40px rgba(0,0,0,.24); }
.unverified-banner .healthy-icon { font-size:1.6rem; color:#fb923c; flex:none; }
.unverified-banner .healthy-title { color:#ffedd5; font-size:1.02rem; font-weight:900; letter-spacing:-.02em; }
.unverified-banner .healthy-sub { color:#fed7aa; font-size:.78rem; margin-top:4px; display:flex; gap:14px; flex-wrap:wrap; }
.banner-failures { color:#fecaca; font-size:.74rem; margin-top:7px; display:flex; flex-direction:column; gap:3px; }
.banner-failures.amber { color:#fed7aa; }
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
.healthy-banner { display:flex; align-items:center; gap:16px; border-radius:16px; padding:14px 18px; margin:10px 0 16px 0; background:linear-gradient(145deg,#06281f 0%, #052018 100%); border:1px solid #0f766e; box-shadow:0 18px 40px rgba(0,0,0,.24); }
.healthy-banner .healthy-icon { font-size:1.6rem; color:#4ade80; flex:none; }
.healthy-title { color:#f0fdf4; font-size:1.02rem; font-weight:900; letter-spacing:-.02em; }
.healthy-sub { color:#a7f3d0; font-size:.78rem; margin-top:4px; display:flex; gap:14px; flex-wrap:wrap; }
.attention-banner { display:flex; align-items:center; gap:16px; border-radius:16px; padding:14px 18px; margin:10px 0 16px 0; background:linear-gradient(145deg,#3f0a0a 0%, #2a0505 100%); border:1px solid #dc2626; box-shadow:0 18px 40px rgba(0,0,0,.24); }
.attention-banner .healthy-icon { font-size:1.6rem; color:#f87171; flex:none; }
.attention-banner .healthy-title { color:#fef2f2; }
.attention-banner .healthy-sub { color:#fecaca; }
.section-head { display:flex; justify-content:space-between; align-items:end; gap:12px; margin:22px 0 10px 0; }
.section-title { color:#f8fafc; font-size:1.08rem; font-weight:850; letter-spacing:-.025em; }
.live-pill { display:inline-flex; align-items:center; vertical-align:middle; margin-left:9px; background:#052e26; color:#6ee7b7; border:1px solid #0f766e; border-radius:999px; padding:3px 9px; font-size:.58rem; font-weight:900; letter-spacing:.1em; text-transform:uppercase; }
.chart-caption { color:#94a3b8; font-size:.74rem; margin:6px 2px 2px 2px; }
.chart-caption b { color:#e2e8f0; font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; font-weight:800; }
.chart-caption .live-pill { margin-left:6px; padding:2px 7px; }
.section-sub { color:#64748b; font-size:.76rem; margin-top:2px; }
div[data-testid="stElementContainer"]:has(> div[data-testid="stFullScreenFrame"]) { background:linear-gradient(180deg,#111827 0%, #0b1220 100%); border:1px solid #1f2a3d; border-radius:18px; padding:10px 12px 4px 12px; box-shadow:0 18px 40px rgba(0,0,0,.24); }
.posture-row { display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:12px; }
.posture-card { background:linear-gradient(180deg,#111827 0%, #0b1220 100%); border:1px solid #1f2a3d; border-radius:18px; padding:16px; box-shadow:0 18px 40px rgba(0,0,0,.24); }
.regime-hero { background:linear-gradient(145deg,#132033 0%, #0b1220 62%, #07101d 100%); border:1px solid #334155; border-radius:18px; padding:18px 20px; box-shadow:0 18px 40px rgba(0,0,0,.24); margin:10px 0 12px 0; }
.regime-hero-top { display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; }
.regime-hero-kicker { color:#64748b; font-size:.68rem; letter-spacing:.2em; font-weight:900; text-transform:uppercase; }
.regime-hero-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-top:14px; }
.regime-cell { background:#0d1422; border:1px solid #1f2a3d; border-radius:14px; padding:10px 12px; }
.regime-cell-label { color:#94a3b8; font-size:.64rem; letter-spacing:.08em; text-transform:uppercase; font-weight:900; }
.regime-cell-value { font-size:1.05rem; font-weight:900; margin-top:6px; }
.regime-posture { display:flex; justify-content:space-between; align-items:center; gap:12px; margin-top:14px; padding-top:12px; border-top:1px solid #1f2a3d; }
.regime-posture-label { color:#94a3b8; font-size:.72rem; letter-spacing:.04em; text-transform:uppercase; font-weight:850; }
.regime-posture-value { color:#f8fafc; font-size:1.0rem; font-weight:900; }
.thesis-card { background:linear-gradient(180deg,#111827 0%, #0b1220 100%); border:1px solid #1f2a3d; border-radius:18px; padding:18px 20px; box-shadow:0 18px 40px rgba(0,0,0,.24); margin:10px 0 12px 0; }
.thesis-line { color:#e2e8f0; font-size:.94rem; line-height:1.6; margin-top:8px; }
.thesis-line:first-child { margin-top:0; }
.thesis-closing { color:#f8fafc; font-size:.94rem; font-weight:900; margin-top:14px; padding-top:12px; border-top:1px solid #1f2a3d; }
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
.regime { display:inline-flex; align-items:center; border-radius:999px; padding:5px 9px; font-size:.64rem; font-weight:900; letter-spacing:.04em; white-space:nowrap; line-height:1; }
.regime-up { background:#052e26; color:#99f6e4; border:1px solid #0f766e; }
.regime-down { background:#3f0a0a; color:#fecaca; border:1px solid #dc2626; }
.regime-vol { background:#162033; color:#bfdbfe; border:1px solid #334155; }
.regime-neutral { background:#111827; color:#cbd5e1; border:1px solid #334155; }
.state-chip { display:inline-flex; align-items:center; font-size:.66rem; font-weight:950; letter-spacing:.06em; padding:5px 9px; border-radius:8px; text-transform:uppercase; line-height:1; }
.state-holding { background:#052e26; color:#99f6e4; border:1px solid #0f766e; }
.state-flat { background:#1e293b; color:#cbd5e1; border:1px solid #334155; }
.state-entering { background:#0c1e33; color:#bfdbfe; border:1px solid #1d4ed8; }
.state-exiting { background:#3b2505; color:#fde68a; border:1px solid #b45309; }
.health-grid { display:grid; grid-template-columns:repeat(4,1fr); align-items:start; gap:10px; }
@media (max-width:1100px) { .health-grid { grid-template-columns:repeat(2,1fr); } }
.health-card { background:#0d1422; border:1px solid #1f2a3d; border-radius:14px; padding:11px 12px; min-height:72px; box-shadow:0 12px 28px rgba(0,0,0,.20); }
.health-bar { display:flex; flex-wrap:wrap; gap:8px; margin:12px 0 2px 0; }
.hchip { display:inline-flex; align-items:center; gap:8px; background:#0d1422; border:1px solid #1f2a3d; border-radius:10px; padding:7px 12px; font-size:.72rem; white-space:nowrap; }
.hchip .hdot { width:8px; height:8px; border-radius:50%; flex:none; }
.hchip .hk { color:#8b98ab; text-transform:uppercase; letter-spacing:.06em; font-weight:850; font-size:.62rem; }
.hchip .hv { color:#f1f5f9; font-weight:800; }
.hchip.attn { border-color:#ea580c; }
.hdot.ok { background:#4ade80; } .hdot.warn { background:#fbbf24; } .hdot.err { background:#f87171; } .hdot.unverified { background:#fb923c; } .hdot.neutral { background:#64748b; }
.health-bar-note { color:#64748b; font-size:.7rem; margin:6px 0 2px 2px; }
.health-label { color:#94a3b8; font-size:.64rem; letter-spacing:.08em; text-transform:uppercase; font-weight:900; }
.health-value { color:#f8fafc; font-size:.98rem; font-weight:850; margin-top:6px; }
.health-sub { color:#64748b; font-size:.72rem; margin-top:2px; }
.health-detail { color:#94a3b8; font-size:.72rem; margin-top:6px; display:flex; flex-direction:column; gap:5px; border-top:1px solid #1f2a3d; padding-top:6px; }
.health-detail-row { display:flex; justify-content:space-between; gap:10px; }
.health-detail-row span:last-child { color:#cbd5e1; font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; text-align:right; }
.health-detail-row.stacked { flex-direction:column; gap:2px; }
.health-detail-row.stacked span:last-child { color:#dbe4f0; text-align:left; white-space:normal; line-height:1.35; }
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
@media (max-width:760px) { .command-deck,.position-grid { grid-template-columns:1fr; } .brand-row { flex-direction:column; align-items:flex-start; } .stat-grid { grid-template-columns:repeat(2,1fr); } .primary .command-value { font-size:1.72rem; } .comp-legend { gap:12px; } .comp-item { min-width:42%; } .regime-hero-grid { grid-template-columns:repeat(2,1fr); } }
</style>
""",
    unsafe_allow_html=True,
)






























def regime_badge(regime: str) -> str:
    label, klass = REGIME_DISPLAY.get(regime or "UNKNOWN", (regime or "Unknown", "regime-neutral"))
    return f'<span class="regime {klass}">{esc(label)}</span>'








def weighted_regime(rows: list[dict[str, Any]]) -> str:
    """Weighted-majority regime label for a group of sleeves.

    Weights each sleeve's regime vote by its target allocation so a larger
    sleeve's regime dominates the class-level read. Ties/no-data fall back
    to MIXED/UNKNOWN rather than guessing.
    """
    weights: dict[str, float] = {}
    for row in rows:
        regime = row.get("regime") or "UNKNOWN"
        weights[regime] = weights.get(regime, 0.0) + float(row.get("target_weight") or 0.0)
    if not weights:
        return "UNKNOWN"
    best_regime = max(weights, key=lambda k: weights[k])
    tied = [r for r, w in weights.items() if abs(w - weights[best_regime]) < 1e-12]
    if len(tied) > 1:
        return "MIXED"
    return best_regime


def join_names(names: list[str]) -> tuple[str, str]:
    """Join sleeve display names into a natural phrase; returns (phrase, verb)."""
    if not names:
        return "", "is"
    if len(names) == 1:
        return names[0], "is"
    if len(names) == 2:
        return f"{names[0]} and {names[1]}", "are"
    return f"{', '.join(names[:-1])}, and {names[-1]}", "are"


def class_narrative(cls: str, rows: list[dict[str, Any]], regime: str) -> str | None:
    """Plain-English read of one asset class, built only from real position
    state and the class's own weighted regime — no invented specifics."""
    class_rows = [r for r in rows if r["asset_class"] == cls]
    if not class_rows:
        return None
    open_rows = [r for r in class_rows if r["position_open"]]
    flat_rows = [r for r in class_rows if not r["position_open"]]
    regime_word = REGIME_WORD.get(regime, ("unclear", "muted"))[0].lower()
    open_phrase, open_verb = join_names([r["display"] for r in open_rows])
    flat_phrase, flat_verb = join_names([r["display"] for r in flat_rows])

    if open_rows and not flat_rows:
        return f"{cls} remains {regime_word} — {open_phrase} {open_verb} actively held."
    if flat_rows and not open_rows:
        return f"{cls} is sitting defensively in cash — {flat_phrase} {flat_verb} flat while the regime reads {regime_word}."
    if open_rows and flat_rows:
        return f"{cls} is split: {open_phrase} {open_verb} held while {flat_phrase} {flat_verb} flat, as the broader regime reads {regime_word}."
    return None


def display_cell(key: str, value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    money_keys = {"nav", "today_pnl", "unrealized_pnl", "realized_pnl", "cost_basis", "avg_entry", "cash", "position_value", "price", "last_fill_price", "fee", "slippage_cost", "notional", "market_value", "strategy_bar_price", "verified_bar_price", "live_price"}
    pct_keys = {"target_weight", "actual_weight", "drift", "contribution", "unrealized_return", "exposure", "target_exposure", "confidence", "bar_price_diff_pct", "live_drift_pct"}
    if key in money_keys:
        return signed_money(value) if key in {"today_pnl", "unrealized_pnl", "realized_pnl"} else money(value)
    if key in pct_keys:
        return signed_pct(value) if key in {"drift", "contribution", "unrealized_return", "bar_price_diff_pct", "live_drift_pct"} else pct(value)
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






# Drawdown panel is drawn on a fixed scale so today's calm and a future real
# drawdown both render truthfully. The pre-committed -26% / -35% planning
# band as drawn reference *lines* is Phase 2 item 11 (from the governed
# degradation-band artifact, not hardcoded here) — the numbers below are
# only quoted as caption text.
# Pre-registered planning drawdown assumption. Source of truth:
# docs/research/CORE_V1_LIVE_EXPECTATION_AND_DEGRADATION_BAND.md ("roughly
# -26% to -35%"). Quoted as text only; keep in sync with that doc.
DRAWDOWN_PLANNING_BAND = (-0.26, -0.35)




state = read_json(STATE_PATH)
events = read_jsonl(SIGNALS_LOG)
# Full since-inception cycle history for the equity curve — the recent
# window `events` (used for intraday/activity) truncates the record.
nav_events = read_jsonl(SIGNALS_LOG, n=200_000)
fills = read_jsonl(FILLS_LOG)
errors = read_jsonl(ERROR_LOG, 100)
audit_report = read_json(AUDIT_REPORT_PATH)
last = events[-1] if events else {}
last_ts = parse_ts(state.get("last_cycle_at") or last.get("timestamp"))
last_age_seconds = age_seconds(last_ts)
is_stale = last_age_seconds is None or last_age_seconds > STALE_AFTER_SECONDS
missing_sleeves = sorted(set(EXPECTED_WEIGHTS) - set(state.get("sleeves", {})))
state_is_v2 = state.get("version") == "core_v1_paper_runtime_v2"
seconds_until_next_cycle = None if last_age_seconds is None else EXPECTED_POLL_SECONDS - last_age_seconds
poll_minutes = max(1, round(EXPECTED_POLL_SECONDS / 60))

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
        "strategy": meta.strategy if meta else "—",
        "last_fill_side": last_fill.get("side"),
        "last_fill_ts": last_fill.get("timestamp"),
        "last_fill_price": last_fill.get("price"),
        "last_fill_qty": last_fill.get("qty"),
        "last_fill_notional": last_fill.get("notional"),
        "last_fill_fee": last_fill.get("fee"),
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
posture_narrative = POSTURE_NARRATIVE[posture_label]

# Market Regime hero card: weighted-majority regime per asset class, derived
# entirely from each sleeve's own regime signal (no synthesized data).
class_regime = {
    cls: weighted_regime([r for r in sleeve_rows if r["asset_class"] == cls])
    for cls in ("Crypto", "Equities", "Gold")
}

# Portfolio Thesis: a plain-English narrative generated from the same
# real position/regime data as the rest of the dashboard — never hardcoded.
if total_nav <= 0:
    thesis_lines = ["Core v1 has not yet completed a trading cycle — no positions to report."]
    thesis_closing = "Overall posture: Awaiting first cycle."
else:
    leading_class, leading_value = max(
        (("Crypto", class_value.get("Crypto", 0.0)), ("Equities", class_value.get("Equities", 0.0)), ("Gold", class_value.get("Gold", 0.0))),
        key=lambda x: x[1],
    )
    if leading_value / total_nav >= 0.25:
        thesis_opening = f"Core v1 currently favors {leading_class}."
    else:
        thesis_opening = f"Core v1 is currently positioned defensively, holding {pct(cash_pct, 0)} in cash."
    thesis_lines = [thesis_opening]
    for cls in ("Equities", "Gold", "Crypto"):
        line = class_narrative(cls, sleeve_rows, class_regime.get(cls, "UNKNOWN"))
        if line:
            thesis_lines.append(line)
    thesis_closing = f"Overall posture: {posture_narrative}."

audit_ts = parse_ts(audit_report.get("timestamp")) if audit_report else None
audit_age = age_seconds(audit_ts)
audit_available = bool(audit_report)
audit_ok = bool(audit_report.get("ok")) if audit_available else None
audit_stale = audit_available and audit_age is not None and audit_age > STALE_AUDIT_AFTER_SECONDS
audit_rows = audit_report.get("rows", []) if audit_available else []
audit_failures = audit_failure_lines(audit_report)
# Single verdict on whether the NAV / P&L numbers on this page can be
# trusted: only "verified" (an independent audit ran recently and passed)
# clears them. "No audit" and "stale audit" both read as UNVERIFIED, never
# as a silent pass. Phase 0 items 2-4 of the dashboard redesign.
audit_trust = derive_audit_trust(
    audit_available=audit_available,
    audit_ok=audit_ok,
    audit_stale=audit_stale,
)
# "Largest drift" surfaces live market movement since each sleeve's last
# completed bar — informational context, not a pass/fail signal. Pass/fail
# comes from bar_price_ok, which compares the runtime's stored bar price
# against an independently reconstructed completed bar, not the live tick.
largest_drift_row = max(audit_rows, key=lambda r: abs(float(r.get("live_drift_pct") or 0.0)), default=None)
failed_audit_rows = [r for r in audit_rows if not r.get("bar_price_ok", True) or r.get("bar_completed") is False or not r.get("position_value_ok", True) or not r.get("unrealized_ok", True) or not r.get("avg_entry_ok", True)]

bar_ages = [age_seconds(parse_ts(r["last_bar"])) for r in sleeve_rows if parse_ts(r["last_bar"]) is not None]
oldest_bar_age = max(bar_ages) if bar_ages else None
newest_bar_age = min(bar_ages) if bar_ages else None

last_fill_overall = fills[-1] if fills else None

# Attach each historical fill's strategy reason via the signals log nearest in
# time — real per-cycle reasons, not fabricated commentary.
reason_frames = []
for event in events:
    for sig_row in event.get("signals", []):
        if sig_row.get("fill"):
            reason_frames.append({"sleeve": sig_row.get("sleeve"), "timestamp": event.get("timestamp"), "reason": sig_row.get("reason", "")})
reason_lookup_df = pd.DataFrame(reason_frames)
if not reason_lookup_df.empty:
    reason_lookup_df["timestamp"] = pd.to_datetime(reason_lookup_df["timestamp"], utc=True, errors="coerce")
    reason_lookup_df = reason_lookup_df.dropna(subset=["timestamp"]).sort_values("timestamp")


def lookup_fill_reason(sleeve: str, ts_value: Any) -> str:
    if reason_lookup_df.empty:
        return ""
    ts = parse_ts(ts_value)
    if ts is None:
        return ""
    subset = reason_lookup_df[reason_lookup_df["sleeve"] == sleeve]
    if subset.empty:
        return ""
    diffs = (subset["timestamp"] - ts).abs()
    idx = diffs.idxmin()
    if diffs.loc[idx] > pd.Timedelta(minutes=10):
        return ""
    return str(subset.loc[idx, "reason"] or "")

latest_error = errors[-1] if errors else None
latest_error_ts = parse_ts(latest_error.get("timestamp")) if latest_error else None
latest_success_ts = last_ts
active_error = latest_error is not None and (
    latest_success_ts is None or latest_error_ts is None or latest_error_ts >= latest_success_ts
)
resolved_error = latest_error is not None and not active_error

issues: list[str] = []
if is_stale:
    issues.append(f"Runtime stale: last cycle {age_text(last_ts)}; expected every {EXPECTED_POLL_SECONDS}s.")
if missing_sleeves:
    issues.append(f"Missing sleeves in state: {', '.join(missing_sleeves)}.")
if active_error:
    issues.append(f"Latest runtime error: {errors[-1].get('error', 'unknown error')}")
if not state_is_v2:
    issues.append("Runtime has not completed a v2 telemetry cycle yet.")
if audit_available and not audit_ok:
    issues.append(
        "Price/accounting audit failing: "
        + ("; ".join(audit_failures) if audit_failures else "unknown")
    )
if not audit_available:
    issues.append(
        "Independent price audit has never run against this state — NAV/P&L figures are UNVERIFIED."
    )
if audit_stale:
    issues.append(f"Audit report stale: last run {age_text(audit_ts)} — NAV/P&L figures are UNVERIFIED.")
# An unavailable or stale audit is at least a "warn" (it was previously
# possible for a missing audit to fall through to "ok" / green).
health_status = (
    "err"
    if is_stale or missing_sleeves or (audit_available and not audit_ok)
    else "warn"
    if active_error or not state_is_v2 or not audit_trust.numbers_trustworthy
    else "ok"
)
health_label = "ALERT" if health_status == "err" else "CHECK" if health_status == "warn" else "VERIFIED"

# Issues not related to the price audit — the audit gets its own dedicated,
# visually distinct banner treatment, so it must not be double-reported as a
# generic issue line beneath it.
non_audit_issues = [i for i in issues if "audit" not in i.lower() and "unverified" not in i.lower()]

runtime_ident = runtime_identity_view(
    read_json(RUNTIME_IDENTITY_PATH) or state.get("runtime_identity"),
    dashboard_state_path=str(STATE_PATH),
    audit_state_path=audit_report.get("state_path") if audit_available else None,
)


def render_identity_strip() -> None:
    """Phase 0 item 1 — which git branch / commit / host produced the
    state.json being rendered. Renders as a warning strip when the runtime
    did not record its identity (the branch-blind-spot the redesign exists
    to surface), rather than silently omitting it."""
    # Under Option B a clean, known identity is shown only as a chip in the
    # health bar + a tile in the System Health grid. The loud strip is
    # reserved for the case that actually matters: unknown or mismatched
    # provenance.
    if runtime_ident.known and not runtime_ident.warnings:
        return
    if not runtime_ident.known:
        msg = "UNKNOWN — the git branch / commit that produced these numbers is not recorded"
    else:
        msg = "MISMATCH — " + "; ".join(runtime_ident.warnings)
    st.markdown(
        f'<div class="identity-strip unknown"><span><span class="id-k">Provenance</span>'
        f'<span class="id-v">{esc(msg)}</span></span></div>',
        unsafe_allow_html=True,
    )


def render_top_banner() -> None:
    """Phase 0 items 2-4 — the trust verdict on this page's numbers, rendered
    above the NAV/PnL command deck. An unavailable or stale price audit gets
    its own visually distinct 'Numbers Unverified' treatment and can never
    render inside the green 'System Healthy' banner."""
    t = audit_trust
    if t.level == "failing":
        bullets = ["Review audit details", *non_audit_issues]
        bullets_html = "".join(f"<span>{esc(b)}</span>" for b in bullets)
        failures_html = (
            '<div class="banner-failures">' + "".join(f"<span>• {esc(f)}</span>" for f in audit_failures) + "</div>"
            if audit_failures
            else ""
        )
        st.markdown(
            f"""
<div class="attention-banner">
  <div class="healthy-icon">✕</div>
  <div>
    <div class="healthy-title">{esc(t.headline)}</div>
    <div class="healthy-sub"><span>{esc(t.detail)}</span>{bullets_html}</div>
    {failures_html}
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
        return
    if t.level in ("unverified", "stale"):
        bullets_html = "".join(f"<span>{esc(b)}</span>" for b in non_audit_issues)
        extra = ""
        if t.level == "stale" and audit_ts is not None:
            extra = f"<span>Last audit {age_text(audit_ts)}</span>"
        st.markdown(
            f"""
<div class="unverified-banner">
  <div class="healthy-icon">◐</div>
  <div>
    <div class="healthy-title">{esc(t.headline)}</div>
    <div class="healthy-sub"><span>{esc(t.detail)}</span>{extra}{bullets_html}</div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
        return
    if non_audit_issues:
        alert_class = "alert-err" if health_status == "err" else "alert-warn"
        alert_right = "Action required" if health_status == "err" else "Review"
        st.markdown(
            f'<div class="alert-line {alert_class}"><span>{esc(" · ".join(non_audit_issues))}</span><span class="mono">{esc(alert_right)}</span></div>',
            unsafe_allow_html=True,
        )
        return
    # Provenance is a separate axis from health: the runtime can be fully
    # healthy while we still can't verify which branch/commit built it. Say
    # so on the banner rather than letting a bare "System Healthy" imply the
    # numbers are fully vouched for.
    provenance_ok = runtime_ident.known and not runtime_ident.warnings
    title = "System Healthy" if provenance_ok else "System Healthy · provenance unverified"
    third_bullet = "Provenance Verified" if provenance_ok else "Provenance Unverified"
    st.markdown(
        f"""
<div class="healthy-banner">
  <div class="healthy-icon">✓</div>
  <div>
    <div class="healthy-title">{esc(title)}</div>
    <div class="healthy-sub"><span>Runtime Active</span><span>Pricing Verified</span><span>Market Data Fresh</span><span>{esc(third_bullet)}</span></div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def compute_health_checks() -> list[tuple[str, str, str, str, list[tuple[str, str]]]]:
    """Every operational check as (label, value, css_klass, sub, detail_rows).
    Shared by the compact health bar (above the deck) and the full System
    Health grid (further down the page)."""
    next_cycle_text = (
        "unknown"
        if seconds_until_next_cycle is None
        else (
            f"in {format_duration(seconds_until_next_cycle)}"
            if seconds_until_next_cycle > 0
            else f"overdue {format_duration(seconds_until_next_cycle)}"
        )
    )
    sleeves_checked = f"{len(audit_rows)}/{len(EXPECTED_WEIGHTS)}"
    largest_drift_text = (
        f"{signed_pct(largest_drift_row.get('live_drift_pct'), 2)} "
        f"({largest_drift_row.get('sleeve') or largest_drift_row.get('asset') or '—'})"
        if largest_drift_row is not None
        else "—"
    )
    # Phase 0 item 6: surface every failure, not just failures[0].
    failure_rows = [(f"Failure {i + 1}", f) for i, f in enumerate(audit_failures)] or [("Failure Reason", "—")]

    if not audit_available:
        audit_value, audit_klass, audit_sub = "UNVERIFIED", "unverified", "No independent audit has run"
        audit_detail = [
            ("Meaning", "NAV / P&L on this page are the runtime's own numbers, un-cross-checked."),
            ("To populate", f"schedule scripts/audit_core_v1_prices.py --output {AUDIT_REPORT_PATH}"),
        ]
    elif not audit_ok:
        audit_value, audit_klass, audit_sub = "FAIL", "err", "Pricing verification failed"
        affected = (
            ", ".join(sorted({r.get("sleeve") or r.get("asset") or "—" for r in failed_audit_rows}))
            if failed_audit_rows
            else "—"
        )
        audit_detail = [
            ("Largest Drift", largest_drift_text),
            ("Drift note", LARGEST_DRIFT_CAVEAT),
            ("Affected Sleeves", affected),
            *failure_rows,
            ("Audit Timestamp", friendly_ts(audit_report.get("timestamp"))),
        ]
    elif audit_stale:
        audit_value, audit_klass, audit_sub = "STALE", "warn", f"last run {age_text(audit_ts)} — unverified"
        audit_detail = [
            ("Largest Drift", largest_drift_text),
            ("Drift note", LARGEST_DRIFT_CAVEAT),
            ("Sleeves Checked", sleeves_checked),
            ("Audit Timestamp", friendly_ts(audit_report.get("timestamp"))),
        ]
    else:
        audit_value, audit_klass, audit_sub = "PASS", "ok", "Verified"
        audit_detail = [
            ("Last Audit", friendly_ts(audit_report.get("timestamp"))),
            ("Largest Drift", largest_drift_text),
            ("Drift note", LARGEST_DRIFT_CAVEAT),
            ("Sleeves Checked", sleeves_checked),
        ]

    runtime_detail = [
        ("Cycle #", str(state.get("cycle", last.get("cycle", 0)))),
        ("Last cycle", age_text(last_ts)),
    ]
    market_data_detail = [
        ("Oldest bar", format_duration(oldest_bar_age) if oldest_bar_age is not None else "—"),
        ("Newest bar", format_duration(newest_bar_age) if newest_bar_age is not None else "—"),
    ]
    scheduler_detail = [("Next cycle", next_cycle_text)]

    last_fill_sub = "No fills recorded"
    last_fill_value = "—"
    last_fill_klass = "neutral"
    if last_fill_overall:
        side = str(last_fill_overall.get("side") or "—").upper()
        last_fill_value = side
        last_fill_klass = "ok" if side == "BUY" else "warn" if side == "SELL" else "neutral"
        fill_sleeve_name = SLEEVE_NAMES.get(last_fill_overall.get("sleeve"), last_fill_overall.get("sleeve"))
        last_fill_sub = f"{fill_sleeve_name} · {age_text(parse_ts(last_fill_overall.get('timestamp')))}"

    if active_error:
        errors_value, errors_klass = "CHECK", "warn"
        errors_sub = f"active {age_text(latest_error_ts)}"
    elif resolved_error:
        errors_value, errors_klass = "RESOLVED", "ok"
        errors_sub = f"last error {age_text(latest_error_ts)} · recovered {friendly_ts(latest_success_ts)}"
    else:
        errors_value, errors_klass = "CLEAR", "ok"
        errors_sub = "0 logged"

    identity_value = "REPORTED" if runtime_ident.known else "UNKNOWN"
    identity_klass = "unverified" if not runtime_ident.known else ("warn" if runtime_ident.warnings else "ok")
    if runtime_ident.known:
        identity_sub = f"{runtime_ident.branch or '—'} @ {runtime_ident.commit_display}"
        identity_detail = [("Host", runtime_ident.hostname or "—")]
        if runtime_ident.recorded_at:
            identity_detail.append(("Recorded", friendly_ts(runtime_ident.recorded_at)))
    else:
        identity_sub = "branch / commit not recorded"
        identity_detail = []
    identity_detail += [("Warning", w) for w in runtime_ident.warnings]

    return [
        ("Runtime Identity", identity_value, identity_klass, identity_sub, identity_detail),
        ("Runtime", "RUNNING" if not is_stale else "STALE", "ok" if not is_stale else "err", f"poll every {poll_minutes}m", runtime_detail),
        ("Market Data", "FRESH" if not missing_sleeves else "MISSING", "ok" if not missing_sleeves else "err", f"{len(EXPECTED_WEIGHTS) - len(missing_sleeves)}/{len(EXPECTED_WEIGHTS)} sleeves", market_data_detail),
        ("Price Audit", audit_value, audit_klass, audit_sub, audit_detail),
        ("Scheduler", "ON", "ok", f"every {poll_minutes}m", scheduler_detail),
        ("Last Fill", last_fill_value, last_fill_klass, last_fill_sub, []),
        ("Errors", errors_value, errors_klass, errors_sub, []),
        ("State Persistence", "V2" if state_is_v2 else "V1", "ok" if state_is_v2 else "warn", STATE_PATH.name, []),
        ("Cost & Fees", money(fees_total + slippage_total), "neutral", "fees + slippage to date", []),
    ]


# Which checks ride in the compact bar above the command deck. The rest
# (Scheduler, Last Fill, Cost & Fees) are pure operational trivia and stay
# in the full grid lower down.
HEALTH_BAR_CHECKS = ("Runtime Identity", "Runtime", "Market Data", "Price Audit", "Errors", "State Persistence")


def render_health_bar(checks: list[tuple[str, str, str, str, list[tuple[str, str]]]]) -> None:
    """Compact one-row health readout directly above the NAV/PnL deck
    (Phase 0 item 2 + the four-seat 'too much on the page' finding). One
    chip per trust-relevant check; full detail is in the System Health
    section further down."""
    chosen = [c for c in checks if c[0] in HEALTH_BAR_CHECKS]
    chosen.sort(key=lambda c: HEALTH_BAR_CHECKS.index(c[0]))
    bar = '<div class="health-bar">'
    for label, value, klass, sub, detail_rows in chosen:
        tip = " · ".join([sub, *[f"{k}: {v}" for k, v in detail_rows]])
        attn = " attn" if klass in ("err", "unverified") else ""
        bar += (
            f'<span class="hchip{attn}" title="{esc(tip)}">'
            f'<span class="hdot {klass}"></span>'
            f'<span class="hk">{esc(label)}</span><span class="hv">{esc(value)}</span></span>'
        )
    bar += "</div>"
    st.markdown(bar, unsafe_allow_html=True)
    st.markdown('<div class="health-bar-note">Full System Health &amp; audit detail below.</div>', unsafe_allow_html=True)


def render_system_health(checks: list[tuple[str, str, str, str, list[tuple[str, str]]]]) -> None:
    """Full operational status grid (lower on the page under Option B)."""
    st.markdown(
        '<div class="section-head"><div><div class="section-title">System Health</div>'
        '<div class="section-sub">Full detail behind the status bar at the top of the page.</div></div></div>',
        unsafe_allow_html=True,
    )
    health_html = '<div class="health-grid">'
    for label, value, klass, sub, detail_rows in checks:
        detail_html = ""
        if detail_rows:
            detail_html = '<div class="health-detail">' + "".join(
                f'<div class="health-detail-row{" stacked" if len(str(v)) > 18 else ""}">'
                f"<span>{esc(k)}</span><span>{esc(v)}</span></div>"
                for k, v in detail_rows
            ) + "</div>"
        health_html += (
            f'<div class="health-card"><div class="health-label">{esc(label)}</div>'
            f'<div class="health-value">{status_badge(value, klass)}</div>'
            f'<div class="health-sub">{esc(sub)}</div>{detail_html}</div>'
        )
    health_html += "</div>"
    st.markdown(health_html, unsafe_allow_html=True)


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

# Auto-refresh is intentionally off: a timer-driven reload/rerun would always
# fire mid-read and disrupt whatever the operator is inspecting. Updating is
# a deliberate operator action instead.
refresh_status_col, refresh_button_col = st.columns([5, 1])
with refresh_status_col:
    st.markdown(
        f'<div class="refresh-status">Auto-refresh paused while inspecting · last updated {datetime.now(UTC).strftime("%H:%M:%S UTC")}</div>',
        unsafe_allow_html=True,
    )
with refresh_button_col:
    st.button("Refresh now", use_container_width=True)

# ---------------------------------------------------------------------------
# 0. Can I trust this page? — provenance + health gate, always above the deck
# ---------------------------------------------------------------------------
health_checks = compute_health_checks()
render_identity_strip()
render_top_banner()
render_health_bar(health_checks)

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
    ("Portfolio NAV", money(total_nav), f"{open_position_count} open · {money(total_cash)} cash", "primary", "white"),
    ("Intraday P&L", today_value, today_sub, "", today_class),
    ("Since Inception", signed_money(since_inception_pnl), signed_pct(since_inception_return), "", since_class),
    ("Drawdown", drawdown_value, drawdown_sub, "", drawdown_class if total_nav > 0 else "muted"),
    ("Unrealized", signed_money(unrealized_pnl_total), f"Basis {money(total_cost_basis)}", "", unrealized_class),
]
# Phase 0 item 4: an unavailable / stale / failing price audit stamps an
# explicit "numbers unverified" flag on the command deck itself, not just a
# buried tile lower down the page.
command_html = ""
if not audit_trust.numbers_trustworthy and audit_trust.deck_flag:
    command_html += f'<div class="deck-flag">{esc(audit_trust.deck_flag)}</div>'
command_html += '<div class="command-deck">'
for label, value, sub, extra, value_class in command_cards:
    command_html += f'<div class="command-card {extra}"><div class="command-label">{esc(label)}</div><div class="command-value {value_class}">{value}</div><div class="command-sub">{sub}</div></div>'
command_html += "</div>"
st.markdown(command_html, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Market Regime — plain-English read of what each asset class is doing and
# why the portfolio is positioned the way it is.
# ---------------------------------------------------------------------------
regime_cells = ""
for cls in ("Crypto", "Equities", "Gold"):
    word, word_cls = REGIME_WORD.get(class_regime[cls], ("Unknown", "muted"))
    regime_cells += f'<div class="regime-cell"><div class="regime-cell-label">{esc(cls)}</div><div class="regime-cell-value {word_cls}">{esc(word)}</div></div>'
regime_cells += f'<div class="regime-cell"><div class="regime-cell-label">Cash</div><div class="regime-cell-value white">{pct(cash_pct, 1)}</div></div>'
st.markdown(
    f"""
<div class="regime-hero">
  <div class="regime-hero-top">
    <div class="regime-hero-kicker">Market Regime</div>
    {status_badge(f'Overall: {posture_label}', posture_status)}
  </div>
  <div class="regime-hero-grid">{regime_cells}</div>
  <div class="regime-posture"><span class="regime-posture-label">Portfolio Posture</span><span class="regime-posture-value">{esc(posture_narrative)}</span></div>
</div>
""",
    unsafe_allow_html=True,
)

_inception_ts = parse_ts(state.get("started_at"))
inception_label = _inception_ts.strftime("%b %-d, %Y") if _inception_ts is not None else "inception"
st.markdown(
    f'<div class="section-head"><div><div class="section-title">Portfolio NAV '
    f'<span class="live-pill">LIVE · PAPER</span></div>'
    f'<div class="section-sub">Equity curve as % return vs. $100k inception, with worst-of-day drawdown. '
    f'Full record since {esc(inception_label)}.</div></div></div>',
    unsafe_allow_html=True,
)
nav_daily = nav_history(nav_events, capital)
fig = nav_chart(nav_daily, fills)
if fig is not None:
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    worst_dd = min((d["drawdown"] for d in nav_daily), default=0.0)
    lo, hi = DRAWDOWN_PLANNING_BAND
    st.markdown(
        f'<div class="chart-caption">Drawdown from high-water · now '
        f'<b>{signed_pct(min(drawdown_frac, 0.0), 1)}</b> · worst <b>{signed_pct(worst_dd, 1)}</b> · '
        f'planning band <b>{lo:.0%} / {hi:.0%}</b> '
        f'<span class="live-pill">LIVE</span></div>',
        unsafe_allow_html=True,
    )
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
    last_fill = "—"
    if row.get("last_fill_side"):
        last_fill = f"{row['last_fill_side']} {num(row.get('last_fill_qty'), 4)} @ {money(row.get('last_fill_price'))}"
    actual_pct = max(0.0, min(100.0, float(row["actual_weight"]) * 100.0))
    target_pct = max(0.0, min(100.0, float(row["target_weight"]) * 100.0))

    if is_open:
        headline = signed_money(row["unrealized_pnl"])
        headline_cls = css_class_for_value(float(row["unrealized_pnl"]))
        headline_sub = f"Unrealized · {signed_pct(row['unrealized_return'])}"
        stats = f"""
    <div class="stat"><div class="stat-label">Current Price</div><div class="stat-value">{money(row['price'])}</div></div>
    <div class="stat"><div class="stat-label">Position value</div><div class="stat-value">{money(row['position_value'])}</div></div>
    <div class="stat"><div class="stat-label">Avg entry</div><div class="stat-value">{money(row['avg_entry']) if row['avg_entry'] else '—'}</div></div>
    <div class="stat"><div class="stat-label">Intraday</div><div class="stat-value {css_class_for_value(float(row['today_pnl']))}">{signed_money(row['today_pnl'])}</div></div>
    <div class="stat"><div class="stat-label">Qty</div><div class="stat-value">{num(row['qty'], 4)}</div></div>
    <div class="stat"><div class="stat-label">Realized</div><div class="stat-value {css_class_for_value(float(row['realized_pnl']))}">{signed_money(row['realized_pnl'])}</div></div>
"""
    else:
        headline = "FLAT"
        headline_cls = "muted"
        exit_ts = parse_ts(row.get("last_fill_ts")) if row.get("last_fill_side") == "SELL" else None
        if exit_ts is not None:
            exited_today = exit_ts.date() == pd.Timestamp.now(tz="UTC").date()
            exit_label = "Exited today" if exited_today else f"Last exit {age_text(exit_ts)}"
            cash_returned = row.get("last_fill_notional")
            fee = row.get("last_fill_fee") or 0.0
            cash_returned_value = money(float(cash_returned) - float(fee)) if cash_returned is not None else "—"
            exit_stat_value = friendly_ts(row.get("last_fill_ts"))
        else:
            exit_label = "No exits yet"
            cash_returned_value = "—"
            exit_stat_value = "—"
        headline_sub = exit_label
        stats = f"""
    <div class="stat"><div class="stat-label">Current Price</div><div class="stat-value">{money(row['price'])}</div></div>
    <div class="stat"><div class="stat-label">Cash</div><div class="stat-value">{money(row['cash'])}</div></div>
    <div class="stat"><div class="stat-label">Realized P&amp;L</div><div class="stat-value {css_class_for_value(float(row['realized_pnl']))}">{signed_money(row['realized_pnl'])}</div></div>
    <div class="stat"><div class="stat-label">Last exit</div><div class="stat-value">{exit_stat_value}</div></div>
    <div class="stat"><div class="stat-label">Cash returned</div><div class="stat-value">{cash_returned_value}</div></div>
    <div class="stat"><div class="stat-label">Last signal</div><div class="stat-value">{friendly_ts(row['last_bar'])}</div></div>
"""
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
  <div class="position-pnl {headline_cls}">{headline}</div>
  <div class="position-pnl-sub">{esc(headline_sub)}</div>
  <div class="alloc-wrap">
    <div class="alloc-top"><span>Allocation {pct(row['actual_weight'], 1)}</span><span>Target {pct(row['target_weight'], 1)}</span></div>
    <div class="alloc-meter"><div class="alloc-fill" style="width:{actual_pct:.1f}%"></div><div class="target-pin" style="left:{target_pct:.1f}%"></div></div>
  </div>
  <div class="stat-grid">{stats}</div>
  <div class="position-line"><span>Last fill: <span class="mono">{esc(last_fill)}</span></span><span>Drift: <span class="mono">{signed_pct(row['drift'], 1)}</span></span></div>
  <div class="small" style="margin-top:8px;">Last bar: <span class="mono">{esc(friendly_ts(row['last_bar']))}</span></div>
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
        tooltip = f"{strategy_display(row['strategy'])} — {row['reason']}"
        activity.append({"kind": "signal", "when": last.get("timestamp") or state.get("last_cycle_at"), "sleeve": row["display"], "event": f"{row['previous_action']} → {row['action']}", "detail": row["reason"], "tooltip": tooltip})
for f in fills[-12:][::-1]:
    side = str(f.get("side") or "").upper()
    kind = "buy" if side == "BUY" else "sell" if side == "SELL" else "signal"
    sleeve_key = f.get("sleeve")
    strategy = SLEEVE_META[sleeve_key].strategy if sleeve_key in SLEEVE_META else None
    reason = lookup_fill_reason(sleeve_key, f.get("timestamp"))
    execution_cost = float(f.get("fee") or 0.0) + float(f.get("slippage_cost") or 0.0)
    detail = f"notional {money(f.get('notional'))} · execution cost {money(execution_cost)} · realized {signed_money(f.get('realized_pnl', 0.0))}"
    tooltip = f"{strategy_display(strategy)}" + (f" — {reason}" if reason else "")
    activity.append({"kind": kind, "when": f.get("timestamp"), "sleeve": SLEEVE_NAMES.get(sleeve_key, sleeve_key), "event": f"{num(f.get('qty'), 4)} @ {money(f.get('price'))}", "detail": detail, "tooltip": tooltip})
if activity:
    timeline_html = '<div class="timeline">'
    for item in activity[:12]:
        tag = item["kind"].upper() if item["kind"] in ("buy", "sell") else "SIGNAL"
        timeline_html += (
            f'<div class="timeline-item {esc(item["kind"])}" title="{esc(item["tooltip"])}"><div class="timeline-left">'
            f'<span class="timeline-tag {esc(item["kind"])}">{esc(tag)}</span>'
            f'<div><div class="timeline-main"><b>{esc(item["sleeve"])}</b> · {esc(item["event"])}</div><div class="timeline-sub">{esc(item["detail"])}</div></div>'
            f'</div><div class="timeline-sub mono">{esc(friendly_ts(item["when"]))}</div></div>'
        )
    timeline_html += "</div>"
    st.markdown(timeline_html, unsafe_allow_html=True)
else:
    st.markdown('<div class="audit-note">No signal changes or fills in the latest activity window.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 5. Is everything healthy? — full operational status grid. The compact
# health bar above the command deck (Phase 0 item 2) is the at-a-glance
# version; this is the drill-down.
# ---------------------------------------------------------------------------
render_system_health(health_checks)

# ---------------------------------------------------------------------------
# Portfolio Thesis — the executive-level "why" behind the current portfolio.
# ---------------------------------------------------------------------------
st.markdown('<div class="section-head"><div><div class="section-title">Portfolio Thesis</div><div class="section-sub">Why the portfolio currently looks the way it does.</div></div></div>', unsafe_allow_html=True)
thesis_html = '<div class="thesis-card">'
thesis_html += "".join(f'<div class="thesis-line">{esc(line)}</div>' for line in thesis_lines)
thesis_html += f'<div class="thesis-closing">{esc(thesis_closing)}</div>'
thesis_html += "</div>"
st.markdown(thesis_html, unsafe_allow_html=True)

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
        st.markdown(f'<div class="audit-note">No audit report found at {esc(str(AUDIT_REPORT_PATH))}. Run <span class="mono">scripts/audit_core_v1_prices.py --output {esc(str(AUDIT_REPORT_PATH))}</span> on a schedule to populate this.</div>', unsafe_allow_html=True)
    else:
        st.markdown(html_table(audit_report.get("rows", []), [("sleeve", "Sleeve"), ("asset", "Asset"), ("strategy_bar_price", "Bar price"), ("verified_bar_price", "Verified price"), ("bar_price_diff_pct", "Bar diff"), ("bar_price_ok", "Bar OK"), ("bar_completed", "Bar completed"), ("live_price", "Live price"), ("live_drift_pct", "Live drift"), ("bar_age_hours", "Bar age (h)"), ("position_value_ok", "Value OK"), ("unrealized_ok", "uPnL OK"), ("avg_entry_ok", "Avg OK")], "No audit rows recorded."), unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Paper Data Export — low-priority operator diagnostic, not part of the main
# Mission Control narrative. Shows whether market-data capture is running
# and points at the most recent local export, if any.
# ---------------------------------------------------------------------------
with st.expander("Paper Data Export", expanded=False):
    market_data_rows = read_jsonl(MARKET_DATA_LOG)
    latest_market_data_ts = None
    for row in reversed(market_data_rows):
        candidate_ts = parse_ts(row.get("timestamp"))
        if candidate_ts is not None:
            latest_market_data_ts = candidate_ts
            break
    capture_age = age_seconds(latest_market_data_ts)
    capture_active = MARKET_DATA_LOG.exists() and capture_age is not None and capture_age <= STALE_AFTER_SECONDS

    latest_export_dir = None
    if PAPER_EXPORT_DIR.exists():
        export_subdirs = [d for d in PAPER_EXPORT_DIR.iterdir() if d.is_dir()]
        if export_subdirs:
            latest_export_dir = max(export_subdirs, key=lambda d: d.stat().st_mtime)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"**Market data capture active:** {'Yes' if capture_active else 'No'}")
        st.markdown(f"**Latest market-data row:** {friendly_ts(str(latest_market_data_ts)) if latest_market_data_ts is not None else 'None captured yet'}")
    with col_b:
        st.markdown(f"**Captured rows:** {len(market_data_rows):,}")
        st.markdown(f"**Latest export:** {esc(str(latest_export_dir)) if latest_export_dir is not None else 'No exports found'}")
    st.caption(f"Log: {MARKET_DATA_LOG} · Run scripts/export_core_v1_paper_data.py for a local replay-ready export (raw JSONL + normalized CSVs + manifest).")

st.caption(f"State {STATE_PATH} · Signals {SIGNALS_LOG} · Fills {FILLS_LOG} · Generated {datetime.now(UTC).isoformat()}")
