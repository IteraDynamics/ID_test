#!/usr/bin/env python
"""Streamlit dashboard for the clean Core v1 paper runtime."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

STATE_PATH = Path(os.getenv("CORE_V1_STATE_PATH", "/opt/itera/runtime/core_v1/state.json"))
SIGNALS_LOG = Path(os.getenv("CORE_V1_SIGNALS_LOG", "/opt/itera/logs/core_v1_signals.jsonl"))
FILLS_LOG = Path(os.getenv("CORE_V1_FILLS_LOG", "/opt/itera/logs/core_v1_fills.jsonl"))
REFRESH_SECONDS = int(os.getenv("CORE_V1_DASHBOARD_REFRESH_SECONDS", "30"))

st.set_page_config(page_title="Itera Core v1 Paper", page_icon="📈", layout="wide")
st.title("Itera Core v1 — Investigative Paper Trading")
st.caption("Selected allocation: candidate_btc1h_hedges_to_btc4h_gld_qqq")


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_jsonl(path: Path, n: int = 200) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines()[-n:]:
        if line.strip():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


state = read_json(STATE_PATH)
events = read_jsonl(SIGNALS_LOG, 500)
fills = read_jsonl(FILLS_LOG, 500)
last = events[-1] if events else {}

c1, c2, c3, c4 = st.columns(4)
c1.metric("NAV", f"${float(state.get('last_total_nav', 0.0)):,.2f}")
c2.metric("Cycle", state.get("cycle", 0))
c3.metric("Drawdown", f"{float(state.get('drawdown_frac', 0.0)):.2%}")
c4.metric("Last cycle", state.get("last_cycle_at", "—"))

if not state:
    st.warning(f"No state found at {STATE_PATH}")

st.subheader("Sleeves")
sleeves = state.get("sleeves", {})
sleeve_navs = state.get("sleeve_navs", {})
if sleeves:
    rows = []
    for label, payload in sleeves.items():
        price = float(payload.get("last_price") or 0.0)
        qty = float(payload.get("qty") or 0.0)
        cash = float(payload.get("cash") or 0.0)
        nav = float(sleeve_navs.get(label) or cash + qty * price)
        exposure = 0.0 if nav <= 0 else qty * price / nav
        rows.append({
            "sleeve": label,
            "nav": nav,
            "cash": cash,
            "qty": qty,
            "price": price,
            "exposure": exposure,
            "target_exposure": float(payload.get("last_target_exposure") or 0.0),
            "last_bar": payload.get("last_timestamp"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

st.subheader("Latest signals")
if last.get("signals"):
    sig_rows = []
    for s in last["signals"]:
        sig_rows.append({
            "sleeve": s.get("sleeve"),
            "asset": s.get("asset"),
            "tf": s.get("timeframe"),
            "action": s.get("action"),
            "target": s.get("target_exposure"),
            "confidence": s.get("confidence"),
            "regime": s.get("regime"),
            "price": s.get("price"),
            "reason": s.get("reason"),
            "fill": bool(s.get("fill")),
        })
    st.dataframe(pd.DataFrame(sig_rows), use_container_width=True)
else:
    st.info("No signal records yet.")

st.subheader("NAV history")
if events:
    hist = pd.DataFrame([
        {"timestamp": e.get("timestamp"), "nav": e.get("total_nav"), "drawdown": e.get("drawdown_frac"), "fills": len(e.get("fills", []))}
        for e in events
    ])
    hist["timestamp"] = pd.to_datetime(hist["timestamp"], errors="coerce")
    st.line_chart(hist.dropna(subset=["timestamp"]).set_index("timestamp")[["nav"]])
else:
    st.info("No NAV history yet.")

st.subheader("Fills")
if fills:
    st.dataframe(pd.DataFrame(fills[::-1]), use_container_width=True)
else:
    st.info("No fills yet.")

st.caption(f"State: {STATE_PATH} | Signals: {SIGNALS_LOG} | Refresh manually or set browser auto-refresh. Suggested cadence: {REFRESH_SECONDS}s.")
