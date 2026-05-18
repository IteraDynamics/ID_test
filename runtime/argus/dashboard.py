"""Itera Dynamics — Unified Fund v1 Live Dashboard (v2).

Reads RuntimeState JSON files for both sleeves and unified_fund_live_state.json.

Usage:
    streamlit run runtime/argus/dashboard.py

    # Optional env overrides:
    CRYPTO_STATE_PATH=... EQUITY_STATE_PATH=... FUND_ENV=LIVE streamlit run ...
"""

from __future__ import annotations

import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    _PLOTLY = True
except ImportError:
    _PLOTLY = False

# ── Constants & paths ──────────────────────────────────────────────────────────

BTC_STATE_PATH           = os.getenv("BTC_STATE_PATH",           "runtime/argus/state/BTC_live_state.json")
ETH_STATE_PATH           = os.getenv("ETH_STATE_PATH",           "runtime/argus/state/ETH_live_state.json")
EQUITY_STATE_PATH        = os.getenv("EQUITY_STATE_PATH",        "runtime/argus/state/EQUITY_COMPOSITE_live_state.json")
CRYPTO_DETAIL_STATE_PATH = os.getenv("CRYPTO_DETAIL_STATE_PATH", "runtime/argus/state/crypto_detail_state.json")
EQUITY_DETAIL_STATE_PATH = os.getenv("EQUITY_DETAIL_STATE_PATH", "runtime/argus/state/equity_detail_state.json")
FUND_STATE_PATH          = os.getenv("FUND_STATE_PATH",          "runtime/argus/state/unified_fund_live_state.json")
REBALANCE_LOG_PATH       = os.getenv("REBALANCE_LOG_PATH",       "runtime/argus/state/unified_fund_rebalance_log.jsonl")
FILLS_LOG_PATH           = os.getenv("FILLS_LOG_PATH",           "runtime/argus/state/unified_fund_fills.jsonl")
SIGNAL_LOG_PATH          = os.getenv("SIGNAL_LOG_PATH",          "runtime/argus/state/unified_fund_signals.jsonl")

REFRESH_SECS  = int(os.getenv("DASHBOARD_REFRESH_SECS", "30"))
DRIFT_BUFFER  = 0.05
_VERSION      = "2.0.0"
_ENV_LABEL    = os.getenv("FUND_ENV", "PAPER")   # set FUND_ENV=LIVE in production
_STALE_MULT   = 3                                  # warn after this many missed cycles

# ── Page config (must be first Streamlit call) ─────────────────────────────────
st.set_page_config(
    page_title="Itera Dynamics | Unified Fund v1",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
_BADGE_BG = "#b91c1c" if _ENV_LABEL == "LIVE" else "#b45309"

st.markdown(f"""
<style>
/* base */
.stApp {{ background-color: #0f1117; }}
section[data-testid="stSidebar"] {{ background-color: #111827; }}

/* metric typography */
[data-testid="stMetricValue"] {{
    font-family: 'Courier New', Courier, monospace;
    font-size: 1.45rem !important;
    letter-spacing: -0.01em;
}}
[data-testid="stMetricLabel"] {{
    font-size: 0.72rem !important;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: #9ca3af !important;
}}

/* env badge */
.env-badge {{
    display: inline-block;
    background: {_BADGE_BG};
    color: #fff;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    padding: 0.18rem 0.55rem;
    border-radius: 3px;
    vertical-align: middle;
    margin-left: 0.4rem;
}}

/* status badges */
.badge-ok   {{ background:#15803d; color:#fff; padding:2px 9px; border-radius:3px;
               font-size:0.72rem; font-weight:700; display:inline-block; }}
.badge-warn {{ background:#b45309; color:#fff; padding:2px 9px; border-radius:3px;
               font-size:0.72rem; font-weight:700; display:inline-block; }}
.badge-err  {{ background:#b91c1c; color:#fff; padding:2px 9px; border-radius:3px;
               font-size:0.72rem; font-weight:700; display:inline-block; }}

/* footer */
.dash-footer {{
    text-align: center;
    color: #4b5563;
    font-size: 0.68rem;
    padding-top: 1.2rem;
    border-top: 1px solid #1f2937;
    margin-top: 2rem;
}}
</style>
""", unsafe_allow_html=True)


# ── Helpers: I/O ──────────────────────────────────────────────────────────────

def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_jsonl(path: str, n: int = 200) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    try:
        lines = p.read_text(encoding="utf-8").strip().splitlines()
        return [json.loads(ln) for ln in lines[-n:] if ln.strip()]
    except Exception:
        return []


def _derive_event(sl: dict) -> str:
    """Backfill event label for signal entries that pre-date the event field."""
    fill     = sl.get("fill")
    action   = sl.get("action", "HOLD")
    approved = sl.get("approved", False)
    if fill is not None:
        return f"FILL_{fill['side']}"
    if not approved:
        return f"REJECTED_{action}"
    if action == "HOLD":
        return "HOLD"
    return f"NO_FILL_{action}"


def _load_signals(path: str, n_cycles: int = 200) -> pd.DataFrame:
    records = _load_jsonl(path, n_cycles)
    rows = []
    for entry in records:
        ts    = entry.get("timestamp", "")
        cycle = entry.get("cycle", "")
        fund  = entry.get("fund", {})
        for sl in entry.get("sleeves", []):
            fill  = sl.get("fill")
            event = sl.get("event") or _derive_event(sl)
            rows.append({
                "timestamp":   ts,
                "cycle":       cycle,
                "sleeve":      sl.get("asset", ""),
                "event":       event,
                "bar_ts":      sl.get("bar_timestamp", ""),
                "regime":      sl.get("regime", ""),
                "price":       sl.get("price"),
                "nav":         sl.get("nav"),
                "exposure":    sl.get("exposure"),
                "action":      sl.get("action", ""),
                "approved":    sl.get("approved"),
                "reason":      sl.get("reason", ""),
                "fill_side":   fill["side"]  if fill else "",
                "fill_qty":    fill["qty"]   if fill else None,
                "fill_price":  fill["price"] if fill else None,
                "fill_fee":    fill["fee"]   if fill else None,
                "total_nav":   fund.get("total_nav"),
                "crypto_frac": fund.get("crypto_frac"),
                "drawdown":    fund.get("drawdown_frac"),
            })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df.sort_values(["timestamp", "sleeve"], ascending=[False, True]).reset_index(drop=True)


def _load_fills(path: str, n: int = 100) -> pd.DataFrame:
    records = _load_jsonl(path, n)
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df.sort_values("timestamp", ascending=False).reset_index(drop=True)


def _load_rebalance_df(path: str, n: int = 25) -> pd.DataFrame:
    records = [
        r for r in _load_jsonl(path, n)
        if r.get("action") != "skipped_below_1usd_threshold"
    ]
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.sort_values("timestamp", ascending=False)
    return df.reset_index(drop=True)


# ── Helpers: formatting ────────────────────────────────────────────────────────

def _pct(v: float, d: int = 2) -> str:
    return f"{v * 100:.{d}f}%"


def _usd(v: float) -> str:
    return f"${v:,.2f}"


def _delta_usd(v: float, pct: float | None = None) -> str:
    """Format a dollar P&L value for use as a Streamlit metric delta.

    Streamlit detects arrow direction by looking for a leading '-' character.
    The plain _usd() helper formats negatives as '$-X.XX' (dollar sign first),
    which Streamlit misreads as positive.  This helper always puts the sign first.
    """
    sign = "+" if v >= 0 else "-"
    base = f"{sign}${abs(v):,.2f}"
    if pct is not None:
        base += f" ({pct * 100:+.2f}%)"
    return base


def _time_ago(ts_str: str) -> str:
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        secs = int((datetime.now(timezone.utc) - ts).total_seconds())
        if secs < 60:   return f"{secs}s ago"
        if secs < 3600: return f"{secs // 60}m ago"
        if secs < 86400:return f"{secs // 3600}h {(secs % 3600) // 60}m ago"
        return f"{secs // 86400}d ago"
    except Exception:
        return "—"


def _staleness_secs(ts_str: str) -> float:
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - ts).total_seconds())
    except Exception:
        return 0.0


def _fmt_or_na(v, fmt: str = ".2f") -> str:
    return f"{v:{fmt}}" if v is not None else "—"


def _pct_or_na(v) -> str:
    return f"{v * 100:.2f}%" if v is not None else "—"


# ── Helpers: live equity quotes ───────────────────────────────────────────────

@st.cache_data(ttl=25)
def _fetch_live_equity_quotes() -> dict[str, float] | None:
    import urllib.request as _ur
    out: dict[str, float] = {}
    for ticker in ("SPY", "QQQ"):
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            "?interval=1m&range=1d&includePrePost=false"
        )
        req = _ur.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        try:
            with _ur.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
            price = next((c for c in reversed(closes) if c is not None), None)
            if price is None:
                return None
            out[ticker] = float(price)
        except Exception:
            return None
    return out


def _is_market_open() -> bool:
    from datetime import timedelta
    try:
        import zoneinfo
        _et = datetime.now(zoneinfo.ZoneInfo("America/New_York"))
    except Exception:
        _et = datetime.now(timezone(timedelta(hours=-4)))
    if _et.weekday() >= 5:
        return False
    _mo = _et.replace(hour=9,  minute=30, second=0, microsecond=0)
    _mc = _et.replace(hour=16, minute=0,  second=0, microsecond=0)
    return _mo <= _et < _mc


# ── Helpers: analytics ────────────────────────────────────────────────────────

def _compute_perf(sig_df: pd.DataFrame) -> dict:
    empty = dict(total_return=None, ann_return=None, sharpe=None,
                 max_dd=None, vol=None, n_cycles=0)
    if sig_df.empty or "total_nav" not in sig_df.columns:
        return empty

    nav_df = (
        sig_df.drop_duplicates(subset=["cycle"])
        .sort_values("timestamp")[["timestamp", "total_nav", "drawdown"]]
        .dropna(subset=["total_nav"])
    )
    n = len(nav_df)
    if n < 2:
        return {**empty, "n_cycles": n}

    first_nav = float(nav_df["total_nav"].iloc[0])
    last_nav  = float(nav_df["total_nav"].iloc[-1])
    if first_nav <= 0:
        return {**empty, "n_cycles": n}

    total_return = last_nav / first_nav - 1.0
    t0, t1 = nav_df["timestamp"].iloc[0], nav_df["timestamp"].iloc[-1]
    elapsed = (t1 - t0).total_seconds() if pd.notna(t0) and pd.notna(t1) else 0
    years   = elapsed / (365.25 * 86400) if elapsed > 0 else None

    # Annualized return requires at least 30 days of history; shorter periods
    # produce astronomically large exponents that overflow to nonsense values.
    _MIN_YEARS_ANN = 30 / 365.25
    ann_return = None
    if years and years >= _MIN_YEARS_ANN:
        ann_return = (1 + total_return) ** (1 / years) - 1

    # Vol and Sharpe require ≥30 observations for meaningful statistics.
    returns = nav_df["total_nav"].pct_change().dropna()
    vol_ann, sharpe = None, None
    if len(returns) >= 30 and elapsed > 0:
        cycle_secs      = elapsed / (n - 1)
        cycles_per_year = 365.25 * 86400 / cycle_secs
        vol_ann = float(returns.std() * math.sqrt(cycles_per_year))
        if ann_return is not None and vol_ann > 0:
            sharpe = ann_return / vol_ann

    max_dd = None
    if "drawdown" in nav_df.columns:
        dd = nav_df["drawdown"].dropna()
        if not dd.empty:
            max_dd = float(dd.min())

    return dict(total_return=total_return, ann_return=ann_return, sharpe=sharpe,
                max_dd=max_dd, vol=vol_ann, n_cycles=n)


def _last_trade_per_sleeve(fills_df: pd.DataFrame) -> dict[str, dict]:
    result: dict[str, dict] = {}
    if fills_df.empty or "sleeve" not in fills_df.columns:
        return result
    for sleeve, grp in fills_df.groupby("sleeve"):
        result[sleeve] = grp.sort_values("timestamp", ascending=False).iloc[0].to_dict()
    return result


def _sleeve_health(state: dict) -> dict:
    """Derive live position health from a sleeve RuntimeState dict."""
    units  = float(state.get("position_units", 0.0))
    cash   = float(state.get("cash", 0.0))
    nav    = float(state.get("nav", 0.0))
    avg_ep = float(state.get("average_entry_price", 0.0))
    # A position exists as long as units are held — avg_ep may be stale (0.0)
    # if the orchestrator restarted without rehydrating fill history.
    in_pos = units > 1e-10
    mark   = (nav - cash) / units if in_pos else None
    # Compute PnL from first principles; don't trust the persisted field which
    # is zeroed out whenever avg_entry is stale.
    cost   = avg_ep * units if (in_pos and avg_ep > 0) else 0.0
    unreal = (mark - avg_ep) * units if (in_pos and mark is not None and avg_ep > 0) else 0.0
    avg_ep_stale = in_pos and avg_ep <= 0   # true when runner hasn't rehydrated yet
    return dict(
        units=units, cash=cash, nav=nav, avg_ep=avg_ep, unreal=unreal,
        in_pos=in_pos, mark=mark,
        unreal_pct=unreal / cost if cost > 0 else 0.0,
        regime=state.get("regime", ""),
        avg_ep_stale=avg_ep_stale,
    )


# ── Helpers: rendering ────────────────────────────────────────────────────────

def _render_sleeve_detail(
    state: dict,
    label: str,
    total_nav: float,
    last_trade: dict | None = None,
) -> None:
    if not state:
        st.warning(f"State file not found for {label}")
        return

    sl_nav    = float(state.get("nav", 0.0))
    sl_hwm    = float(state.get("high_water_mark") or sl_nav or 1.0)
    sl_dd     = (sl_nav / sl_hwm - 1.0) if sl_hwm > 0 else 0.0
    sl_exp    = float(state.get("exposure_frac", 0.0))
    sl_fills  = int(state.get("fill_count", 0))
    sl_halted = bool(state.get("drawdown_governor_halted", False))
    sl_cash   = float(state.get("cash", 0.0))
    sl_bar    = state.get("last_bar_timestamp", "—")
    sl_units  = float(state.get("position_units", 0.0))
    sl_avg_ep = float(state.get("average_entry_price", 0.0))
    sl_unreal = float(state.get("unrealized_pnl_usd", 0.0))

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Sleeve NAV",    _usd(sl_nav))
    r2.metric("vs HWM",        _pct(sl_dd),
              delta_color="normal" if sl_dd >= 0 else "inverse",
              help=f"HWM: {_usd(sl_hwm)}")
    r3.metric("Cash",          _usd(sl_cash))
    r4.metric("Total Fills",   sl_fills)

    # Exposure progress bar
    st.caption("**Gross Exposure**")
    st.progress(float(min(max(sl_exp, 0.0), 1.0)), text=f"{sl_exp * 100:.1f}%")

    # DD governor status badge
    if sl_halted:
        st.markdown('<span class="badge-err">⛔ DD GOVERNOR HALTED</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge-ok">✓ DD Governor Active</span>', unsafe_allow_html=True)

    # Position detail
    if sl_units > 1e-10:
        cur_price  = (sl_nav - sl_cash) / sl_units
        if sl_avg_ep > 0:
            cost_basis = sl_avg_ep * sl_units
            sl_unreal  = (cur_price - sl_avg_ep) * sl_units   # recompute; don't trust stale field
            unreal_pct = sl_unreal / cost_basis if cost_basis > 0 else 0.0
            colour     = "green" if sl_unreal >= 0 else "red"
            st.markdown(
                f"**Position:** {sl_units:.6f} units &nbsp;|&nbsp; "
                f"**Avg Entry:** {_usd(sl_avg_ep)} &nbsp;|&nbsp; "
                f"**Mark:** {_usd(cur_price)} &nbsp;|&nbsp; "
                f"**Unrealized PnL:** :{colour}[{_usd(sl_unreal)} ({unreal_pct * 100:+.2f}%)]"
            )
        else:
            st.markdown(
                f"**Position:** {sl_units:.6f} units &nbsp;|&nbsp; "
                f"**Mark:** {_usd(cur_price)} &nbsp;|&nbsp; "
                f"**Avg Entry:** ⚠ stale (restart runner) &nbsp;|&nbsp; "
                f"**Unrealized PnL:** ⚠ stale"
            )
    else:
        st.markdown("**Position:** FLAT")

    # Last trade
    if last_trade:
        lt_side  = last_trade.get("side", "")
        lt_qty   = last_trade.get("qty", 0)
        lt_price = last_trade.get("fill_price", 0)
        lt_ts    = str(last_trade.get("timestamp", ""))
        colour   = "green" if lt_side == "BUY" else "red"
        st.caption(
            f"Last trade: :{colour}[**{lt_side}**] "
            f"{lt_qty:.6f} units @ {_usd(lt_price)} — {_time_ago(lt_ts)}"
        )

    st.caption(f"Last bar: {sl_bar}")


# ── Data loading ───────────────────────────────────────────────────────────────

btc_state      = _load_json(BTC_STATE_PATH)
eth_state      = _load_json(ETH_STATE_PATH)
equity_state   = _load_json(EQUITY_STATE_PATH)
crypto_detail  = _load_json(CRYPTO_DETAIL_STATE_PATH)
equity_detail  = _load_json(EQUITY_DETAIL_STATE_PATH)
fund_state     = _load_json(FUND_STATE_PATH)

_missing = [
    name for name, path, data in [
        ("BTC sleeve",    BTC_STATE_PATH,    btc_state),
        ("ETH sleeve",    ETH_STATE_PATH,    eth_state),
        ("Equity sleeve", EQUITY_STATE_PATH, equity_state),
        ("Fund state",    FUND_STATE_PATH,   fund_state),
    ]
    if data is None
]
if _missing:
    st.warning(
        f"⚠️  State file(s) missing: **{', '.join(_missing)}**. "
        "NAV for these sleeves is shown as $0. "
        "Start the runner to generate state."
    )

# Combined crypto NAV = BTC NAV + ETH NAV (fund_state is authoritative if present)
_btc_nav_raw  = float(btc_state.get("nav",  0.0)) if btc_state  else 0.0
_eth_nav_raw  = float(eth_state.get("nav",  0.0)) if eth_state  else 0.0
crypto_nav    = float(fund_state.get("crypto_nav",  _btc_nav_raw + _eth_nav_raw))
equity_nav    = float(fund_state.get("equity_nav",  equity_state.get("nav", 0.0) if equity_state else 0.0))
total_nav     = float(fund_state.get("total_nav",   crypto_nav + equity_nav))
fund_hwm      = float(fund_state.get("high_water_mark", total_nav or 1.0))
drawdown_frac = float(fund_state.get("drawdown_frac",
    (total_nav / fund_hwm - 1.0) if fund_hwm > 0 else 0.0))
crypto_frac   = float(fund_state.get("crypto_frac",
    (crypto_nav / total_nav) if total_nav > 0 else 0.5))
equity_frac   = float(fund_state.get("equity_frac",
    (equity_nav / total_nav) if total_nav > 0 else 0.5))
fund_cycle    = int(fund_state.get("cycle", 0))
last_updated  = fund_state.get("timestamp", "")

sig_df    = _load_signals(SIGNAL_LOG_PATH, n_cycles=200)
fills_df  = _load_fills(FILLS_LOG_PATH, n=100)
rebal_df  = _load_rebalance_df(REBALANCE_LOG_PATH, n=25)
perf      = _compute_perf(sig_df)
last_trades = _last_trade_per_sleeve(fills_df)

btc_health    = _sleeve_health(btc_state)  if btc_state  else {}
eth_health    = _sleeve_health(eth_state)  if eth_state  else {}
equity_health = _sleeve_health(equity_state) if equity_state else {}

# Crypto sleeve combined health (used for KPI row)
_crypto_unreal = btc_health.get("unreal", 0.0) + eth_health.get("unreal", 0.0)
_crypto_cost   = (
    btc_health.get("avg_ep", 0.0) * btc_health.get("units", 0.0)
    + eth_health.get("avg_ep", 0.0) * eth_health.get("units", 0.0)
)
total_unrealized = _crypto_unreal + equity_health.get("unreal", 0.0)
_total_cost = (
    _crypto_cost
    + equity_health.get("avg_ep", 0.0) * equity_health.get("units", 0.0)
)
total_unreal_pct = total_unrealized / _total_cost if _total_cost > 0 else None

# cycle-over-cycle NAV delta
_prev_nav: float | None = None
if not sig_df.empty and "total_nav" in sig_df.columns:
    _navs = (
        sig_df.drop_duplicates(subset=["cycle"])
        .sort_values("timestamp")["total_nav"].dropna()
    )
    if len(_navs) >= 2:
        _prev_nav = float(_navs.iloc[-2])

# ── Auto-refresh: session state init ──────────────────────────────────────────
if "next_refresh" not in st.session_state:
    st.session_state.next_refresh = time.time() + REFRESH_SECS

# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
h_left, h_right = st.columns([4, 1])
with h_left:
    st.markdown(
        f"## Itera Dynamics — Unified Fund v1 "
        f'<span class="env-badge">{_ENV_LABEL}</span>',
        unsafe_allow_html=True,
    )
    age = _time_ago(last_updated) if last_updated else "no data"
    st.caption(
        f"Cycle {fund_cycle}  ·  Updated {age}  ·  "
        f"Auto-refresh {REFRESH_SECS}s  ·  v{_VERSION}"
    )
with h_right:
    if st.button("⟳  Refresh now", use_container_width=True):
        st.session_state.next_refresh = time.time() + REFRESH_SECS
        st.rerun()

# ── Staleness warning ──────────────────────────────────────────────────────────
if last_updated:
    stale = _staleness_secs(last_updated)
    # estimate cycle period from signal log
    est_cycle = 3600.0
    if not sig_df.empty:
        _ts_sorted = (
            sig_df.drop_duplicates(subset=["cycle"])
            .sort_values("timestamp")["timestamp"]
        )
        if len(_ts_sorted) > 1:
            _diffs = _ts_sorted.diff().dropna().dt.total_seconds()
            _med   = _diffs.median()
            if _med > 0:
                est_cycle = _med
    if stale > est_cycle * _STALE_MULT:
        st.warning(
            f"⚠️  Data may be stale — last update **{_time_ago(last_updated)}**. "
            "Check that the runner process is active."
        )

# ══════════════════════════════════════════════════════════════════════════════
# KPI BANNER
# ══════════════════════════════════════════════════════════════════════════════
k1, k2, k3, k4, k5, k6 = st.columns(6)

k1.metric(
    "Total Fund NAV",
    _usd(total_nav),
    delta=_usd(total_nav - _prev_nav) if _prev_nav is not None else None,
    help="Crypto sleeve NAV + Equity sleeve NAV",
)
k2.metric(
    "Fund Drawdown",
    _pct(drawdown_frac),
    delta_color="inverse",
    help=f"High-Water Mark: {_usd(fund_hwm)}",
)
k3.metric("High-Water Mark", _usd(fund_hwm))
k4.metric(
    "Crypto Allocation",
    f"{crypto_frac * 100:.1f}%",
    delta=f"{(crypto_frac - 0.50) * 100:+.1f} pp",
    delta_color="off",
    help=f"Target 50% ± {DRIFT_BUFFER * 100:.0f}%",
)
k5.metric(
    "Equity Allocation",
    f"{equity_frac * 100:.1f}%",
    delta=f"{(equity_frac - 0.50) * 100:+.1f} pp",
    delta_color="off",
    help=f"Target 50% ± {DRIFT_BUFFER * 100:.0f}%",
)
k6.metric(
    "Unrealized PnL",
    _usd(total_unrealized),
    delta=f"{total_unreal_pct * 100:+.2f}%" if total_unreal_pct is not None else None,
    delta_color="normal",
    help="Total unrealized PnL across both sleeves vs. cost basis",
)

# ── Position Health Strip ─────────────────────────────────────────────────────

# Helper: sniper status → badge html
_SNIPER_BADGE = {
    "ARMED":   ('<span style="background:#b45309;color:#fff;padding:2px 8px;'
                'border-radius:3px;font-size:0.72rem;font-weight:700">⚡ ARMED</span>'),
    "ACTIVE":  ('<span style="background:#15803d;color:#fff;padding:2px 8px;'
                'border-radius:3px;font-size:0.72rem;font-weight:700">● ACTIVE</span>'),
    "POLLING": ('<span style="background:#1e3a5f;color:#93c5fd;padding:2px 8px;'
                'border-radius:3px;font-size:0.72rem;font-weight:700">◎ POLLING</span>'),
    "WARMUP":  ('<span style="background:#374151;color:#9ca3af;padding:2px 8px;'
                'border-radius:3px;font-size:0.72rem;font-weight:700">… WARMUP</span>'),
}

if btc_health or eth_health or equity_health:
    _phc1, _phc2 = st.columns(2)

    # ── Crypto card (BTC + ETH sub-sleeves) ──────────────────────────────────
    with _phc1:
        with st.container(border=True):
            _cd = crypto_detail
            # Regime label: prefer btc (primary) regime
            _cd_btc_regime = (_cd.get("btc_regime") if _cd else None) or ""
            _cr_regime_tag = f" · `{_cd_btc_regime}`" if _cd_btc_regime else ""
            st.caption(f"**CRYPTO SLEEVE** (BTC + ETH){_cr_regime_tag}")

            # ── Price row: live mark when in position, last bar close when flat ─
            _btc_close = _cd.get("btc_close") if _cd else None
            _eth_close = _cd.get("eth_close") if _cd else None
            # NAV-derived mark is always current; bar-close is only updated each cycle.
            _btc_price = btc_health.get("mark") if btc_health.get("in_pos") else _btc_close
            _eth_price = eth_health.get("mark") if eth_health.get("in_pos") else _eth_close
            if _btc_price is not None or _eth_price is not None:
                _cp1, _cp2 = st.columns(2)
                if _btc_price is not None:
                    _btc_help = ("Live mark — (NAV − cash) ÷ units."
                                 if btc_health.get("in_pos")
                                 else "Last bar close — updates each runner cycle.")
                    _cp1.metric("BTC-USD", _usd(_btc_price), help=_btc_help)
                if _eth_price is not None:
                    _eth_help = ("Live mark — (NAV − cash) ÷ units."
                                 if eth_health.get("in_pos")
                                 else "Last bar close — updates each runner cycle.")
                    _cp2.metric("ETH-USD", _usd(_eth_price), help=_eth_help)
            else:
                st.caption(
                    ":gray[BTC/ETH prices pending — runner restart required]"
                    if _cd else ":gray[Prices unavailable — runner not started]"
                )

            # ── BTC sub-sleeve position ───────────────────────────────────
            _btc = btc_health
            if _btc.get("in_pos"):
                _btc_stale = _btc.get("avg_ep_stale", False)
                _bm1, _bm2, _bm3, _bm4 = st.columns(4)
                _bm1.metric("BTC Mark",  _usd(_btc["mark"]))
                _bm2.metric(
                    "BTC Entry",
                    "⚠ stale" if _btc_stale else _usd(_btc["avg_ep"]),
                    help="Restart runner to restore avg entry." if _btc_stale else None,
                )
                _bm3.metric("BTC Units", f"{_btc['units']:.6f}")
                if _btc_stale:
                    _bm4.metric("BTC PnL", "⚠ stale",
                                help="Cannot compute without valid avg entry.")
                else:
                    _bm4.metric(
                        "BTC PnL",
                        _usd(_btc["unreal"]),
                        delta=f"{_btc['unreal_pct'] * 100:+.2f}%",
                        delta_color="normal",
                    )
            else:
                _bc1, _bc2 = st.columns([1, 3])
                _bc1.metric("BTC Cash", _usd(_btc.get("cash", 0.0)))
                _bc2.markdown(
                    "<br><span style='color:#6b7280'>BTC — FLAT</span>",
                    unsafe_allow_html=True,
                )

            # ── ETH sub-sleeve position ───────────────────────────────────
            _eth = eth_health
            if _eth.get("in_pos"):
                _eth_stale = _eth.get("avg_ep_stale", False)
                _em1, _em2, _em3, _em4 = st.columns(4)
                _em1.metric("ETH Mark",  _usd(_eth["mark"]))
                _em2.metric(
                    "ETH Entry",
                    "⚠ stale" if _eth_stale else _usd(_eth["avg_ep"]),
                    help="Restart runner to restore avg entry." if _eth_stale else None,
                )
                _em3.metric("ETH Units", f"{_eth['units']:.6f}")
                if _eth_stale:
                    _em4.metric("ETH PnL", "⚠ stale",
                                help="Cannot compute without valid avg entry.")
                else:
                    _em4.metric(
                        "ETH PnL",
                        _usd(_eth["unreal"]),
                        delta=f"{_eth['unreal_pct'] * 100:+.2f}%",
                        delta_color="normal",
                    )
            else:
                _ec1, _ec2 = st.columns([1, 3])
                _ec1.metric("ETH Cash", _usd(_eth.get("cash", 0.0)))
                _ec2.markdown(
                    "<br><span style='color:#6b7280'>ETH — FLAT</span>",
                    unsafe_allow_html=True,
                )

    # ── Equity card ──────────────────────────────────────────────────────────
    with _phc2:
        with st.container(border=True):
            _eq = equity_health
            _ed = equity_detail
            _eq_regime = _ed.get("regime") or _eq.get("regime", "")
            _eq_regime_tag = f" · `{_eq_regime}`" if _eq_regime else ""
            st.caption(f"**{equity_state.get('asset', 'EQUITY_COMPOSITE')}**{_eq_regime_tag}")

            # Per-asset price + position breakdown (SPY / QQQ)
            _ed_live   = _ed and _ed.get("spy_close") is not None
            _eq_in_pos = _eq.get("in_pos", False)
            _eq_stale  = _eq.get("avg_ep_stale", False)
            if _ed_live:
                _spy_close  = float(_ed["spy_close"])
                _qqq_close  = float(_ed["qqq_close"])
                _spy_active = _ed.get("spy_active", False)
                _qqq_active = _ed.get("qqq_active", False)
                _spy_sma    = _ed.get("spy_sma")
                _qqq_sma    = _ed.get("qqq_sma")
                _spy_wt     = float(_ed.get("spy_weight", 0.5))
                _qqq_wt     = float(_ed.get("qqq_weight", 0.5))

                # Bar-date staleness badge
                _eq_bar_ts   = equity_state.get("last_bar_timestamp", "")
                _eq_bar_date = _eq_bar_ts[:10] if _eq_bar_ts else ""
                _eq_bar_age  = 0
                if _eq_bar_date:
                    try:
                        _bar_d      = datetime.strptime(_eq_bar_date, "%Y-%m-%d")
                        _today_d    = datetime.now(timezone.utc).replace(tzinfo=None)
                        _eq_bar_age = max(0, (_today_d - _bar_d).days)
                    except Exception:
                        pass
                # Fetch live quotes (cached 25 s); resolve display prices
                _live_quotes = _fetch_live_equity_quotes()
                _mkt_open    = _is_market_open()
                if _live_quotes:
                    _disp_spy  = _live_quotes["SPY"]
                    _disp_qqq  = _live_quotes["QQQ"]
                    _price_tag = "LIVE" if _mkt_open else "QUOTE"
                else:
                    _disp_spy  = _spy_close
                    _disp_qqq  = _qqq_close
                    _price_tag = None

                _bar_colour = "#f59e0b" if _eq_bar_age >= 1 else "#6b7280"
                _bar_badge  = f"⚠ {_eq_bar_age}d stale" if _eq_bar_age >= 1 else "current"
                if _live_quotes and not _eq_bar_age:
                    _live_badge = (
                        '<span style="color:#22c55e;font-size:0.72rem;margin-left:6px;">'
                        "⚡ LIVE</span>" if _mkt_open else
                        '<span style="color:#6b7280;font-size:0.72rem;margin-left:6px;">'
                        "QUOTE</span>"
                    )
                else:
                    _live_badge = ""
                st.markdown(
                    f'<span style="color:{_bar_colour};font-size:0.72rem;">'
                    f"Prices as of {_eq_bar_date or '—'} ({_bar_badge})</span>"
                    f"{_live_badge}",
                    unsafe_allow_html=True,
                )

                if _eq_in_pos and not _eq_stale and _eq.get("mark"):
                    _disp_comp   = _spy_wt * _disp_spy + _qqq_wt * _disp_qqq
                    _eq_notional = _eq["units"] * _disp_comp
                    _total_cost  = _eq["avg_ep"] * _eq["units"]
                    _total_pnl   = _eq_notional - _total_cost
                    _total_pnl_pct = _total_pnl / _total_cost if _total_cost > 0 else 0.0
                    _pnl_label   = "Live PnL" if _live_quotes else "PnL"
                    _tag_sfx     = f"  [{_price_tag}]" if _price_tag else ""

                    # ── Composite-level P&L ──────────────────────────────────
                    _ep1, _ep2, _ep3, _ep4 = st.columns(4)
                    _ep1.metric(
                        f"Composite{_tag_sfx}",
                        _usd(_disp_comp),
                        help=f"1 unit = SPY×{_spy_wt:.0%} + QQQ×{_qqq_wt:.0%}",
                    )
                    _ep2.metric("Avg Entry", _usd(_eq["avg_ep"]))
                    _ep3.metric("Units", f"{_eq['units']:.4f}")
                    _ep4.metric(
                        _pnl_label,
                        _usd(_total_pnl),
                        delta=_delta_usd(_total_pnl, _total_pnl_pct),
                        delta_color="normal",
                    )
                    st.caption(
                        f"1 unit = SPY×{_spy_wt:.0%} + QQQ×{_qqq_wt:.0%}  ·  "
                        f"Cost basis: {_usd(_total_cost)}  ·  Notional: {_usd(_eq_notional)}"
                    )
                    st.divider()

                    # ── SPY / QQQ as signal references (no fake split P&L) ──
                    _ea1, _ea2 = st.columns(2)
                    with _ea1:
                        _spy_icon    = "✅" if _spy_active else "⬜"
                        _spy_sma_str = f"SMA {_usd(_spy_sma)}" if _spy_sma else "SMA —"
                        st.metric(
                            f"{_spy_icon} SPY{_tag_sfx}",
                            _usd(_disp_spy),
                            delta="above SMA" if _spy_active else "below SMA",
                            delta_color="normal" if _spy_active else "off",
                            help=(
                                f"Signal: {'above' if _spy_active else 'below'} {_spy_sma_str} "
                                f"→ {'allocated' if _spy_active else 'cash'}."
                                + (f"  Last bar: {_usd(_spy_close)}" if _live_quotes else "")
                            ),
                        )
                    with _ea2:
                        _qqq_icon    = "✅" if _qqq_active else "⬜"
                        _qqq_sma_str = f"SMA {_usd(_qqq_sma)}" if _qqq_sma else "SMA —"
                        st.metric(
                            f"{_qqq_icon} QQQ{_tag_sfx}",
                            _usd(_disp_qqq),
                            delta="above SMA" if _qqq_active else "below SMA",
                            delta_color="normal" if _qqq_active else "off",
                            help=(
                                f"Signal: {'above' if _qqq_active else 'below'} {_qqq_sma_str} "
                                f"→ {'allocated' if _qqq_active else 'cash'}."
                                + (f"  Last bar: {_usd(_qqq_close)}" if _live_quotes else "")
                            ),
                        )
                else:
                    # Flat or stale avg_entry: show signal status only, no PnL
                    _ea1, _ea2 = st.columns(2)
                    with _ea1:
                        _spy_icon = "✅" if _spy_active else "⬜"
                        _spy_vs   = f"  vs SMA {_usd(_spy_sma)}" if _spy_sma else ""
                        st.metric(
                            f"{_spy_icon} SPY",
                            _usd(_spy_close),
                            delta="above SMA" if _spy_active else "below SMA",
                            delta_color="normal" if _spy_active else "off",
                            help=f"Last bar close. SPY above SMA = allocated, below = cash.{_spy_vs}",
                        )
                    with _ea2:
                        _qqq_icon = "✅" if _qqq_active else "⬜"
                        _qqq_vs   = f"  vs SMA {_usd(_qqq_sma)}" if _qqq_sma else ""
                        st.metric(
                            f"{_qqq_icon} QQQ",
                            _usd(_qqq_close),
                            delta="above SMA" if _qqq_active else "below SMA",
                            delta_color="normal" if _qqq_active else "off",
                            help=f"Last bar close. QQQ above SMA = allocated, below = cash.{_qqq_vs}",
                        )
                    if _eq_in_pos and _eq_stale:
                        st.markdown(
                            f"**Position:** {_eq.get('units', 0.0):.6f} composite units &nbsp;|&nbsp; "
                            f"**Avg Entry:** ⚠ stale (restart runner) &nbsp;|&nbsp; "
                            f"**Unrealized PnL:** ⚠ stale"
                        )
                    elif not _eq_in_pos:
                        _ec1, _ec2 = st.columns([1, 3])
                        _ec1.metric("Cash", _usd(_eq.get("cash", 0.0)))
                        _ec2.markdown(
                            "<br><span style='color:#6b7280'>FLAT — no open position</span>",
                            unsafe_allow_html=True,
                        )
            else:
                st.caption(
                    ":gray[SPY/QQQ prices pending — runner restart required to populate live data]"
                    if _ed else ":gray[Asset detail unavailable — runner not yet started]"
                )
                if _eq_in_pos:
                    _em1, _em2, _em3 = st.columns(3)
                    _em1.metric("Mark Price", _usd(_eq["mark"]))
                    _em2.metric(
                        "Avg Entry",
                        "⚠ stale" if _eq_stale else _usd(_eq["avg_ep"]),
                        help="Restart runner to restore avg entry." if _eq_stale else None,
                    )
                    if _eq_stale:
                        _em3.metric("Unrealized PnL", "⚠ stale",
                                    help="Cannot compute without valid avg entry. Restart runner.")
                    else:
                        _em3.metric(
                            "Unrealized PnL",
                            _usd(_eq["unreal"]),
                            delta=f"{_eq['unreal_pct'] * 100:+.2f}%",
                            delta_color="normal",
                        )
                else:
                    _ec1, _ec2 = st.columns([1, 3])
                    _ec1.metric("Cash", _usd(_eq.get("cash", 0.0)))
                    _ec2.markdown(
                        "<br><span style='color:#6b7280'>FLAT — no open position</span>",
                        unsafe_allow_html=True,
                    )

            # Overlay status row
            if _ed:
                st.divider()
                _active_assets = " + ".join(
                    a for a, flag in [("SPY", _ed.get("spy_active")), ("QQQ", _ed.get("qqq_active"))]
                    if flag
                ) or "CASH"
                _sniper_status = _ed.get("sniper_status", "POLLING")
                _sniper_badge  = _SNIPER_BADGE.get(_sniper_status, _SNIPER_BADGE["POLLING"])
                _sniper_mom    = _ed.get("sniper_long_momentum")
                _sniper_mom_str = f" · mom {_sniper_mom:+.2%}" if _sniper_mom is not None else ""
                st.markdown(
                    f"**Core Beta:** `{_eq_regime}` → **{_active_assets}**"
                    f"&nbsp;&nbsp;|&nbsp;&nbsp;"
                    f"**Sniper Overlay:** {_sniper_badge}{_sniper_mom_str}",
                    unsafe_allow_html=True,
                )
                if _ed.get("sniper_reason"):
                    st.caption(f"Sniper: {_ed['sniper_reason']}")

# ── Drift banner + ruler ───────────────────────────────────────────────────────
_lo_pct  = (0.50 - DRIFT_BUFFER) * 100
_hi_pct  = (0.50 + DRIFT_BUFFER) * 100
_cur_pct = crypto_frac * 100
_in_band = abs(crypto_frac - 0.50) <= DRIFT_BUFFER

if total_nav == 0:
    st.info("No fund state found. Has the runner been started?")
elif not _in_band:
    st.error(
        f"⚡ DRIFT BUFFER BREACHED — Crypto at {_cur_pct:.1f}% "
        f"(band: {_lo_pct:.0f}%–{_hi_pct:.0f}%). Rebalance may be pending."
    )

if total_nav > 0:
    if _PLOTLY:
        _marker_col = "#22c55e" if _in_band else "#ef4444"
        _fig_drift = go.Figure()
        _fig_drift.add_shape(
            type="rect", x0=_lo_pct, x1=_hi_pct, y0=0, y1=1,
            fillcolor="rgba(34,197,94,0.12)", line_width=0, layer="below",
        )
        _fig_drift.add_vline(x=50.0, line_color="#4b5563", line_dash="dot", line_width=1)
        _fig_drift.add_vline(x=_cur_pct, line_color=_marker_col, line_width=3)
        _fig_drift.add_annotation(
            x=_cur_pct, y=0.85, text=f"<b>{_cur_pct:.1f}%</b>",
            showarrow=False, font=dict(color=_marker_col, size=13),
        )
        _fig_drift.add_annotation(
            x=50.0, y=0.15, text="50% target",
            showarrow=False, font=dict(color="#6b7280", size=10),
        )
        _fig_drift.update_layout(
            height=72, margin=dict(l=10, r=10, t=4, b=4),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(range=[35, 65], showgrid=False, ticksuffix="%",
                       color="#6b7280", showticklabels=True),
            yaxis=dict(visible=False),
            showlegend=False,
        )
        st.plotly_chart(_fig_drift, use_container_width=True,
                        config={"displayModeBar": False})
    else:
        _norm = (_cur_pct - 35) / 30
        st.progress(
            float(min(max(_norm, 0.0), 1.0)),
            text=f"Crypto allocation: {_cur_pct:.1f}%  (band {_lo_pct:.0f}%–{_hi_pct:.0f}%)",
        )

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab_overview, tab_positions, tab_blotter, tab_signals, tab_rebalances = st.tabs([
    "📈  Overview",
    "📊  Positions & Risk",
    "🔄  Trade Blotter",
    "📋  Signals",
    "⚖️  Rebalances",
])

# ─────────────────────────────────────────────────────
# TAB 1 — Overview
# ─────────────────────────────────────────────────────
with tab_overview:

    st.subheader("Performance Summary")
    p1, p2, p3, p4, p5 = st.columns(5)
    p1.metric("Total Return",    _pct_or_na(perf["total_return"]))
    p2.metric("Ann. Return",     _pct_or_na(perf["ann_return"]))
    p3.metric("Sharpe (ann.)",   _fmt_or_na(perf["sharpe"]))
    p4.metric("Ann. Volatility", _pct_or_na(perf["vol"]))
    p5.metric("Max Drawdown",    _pct_or_na(perf["max_dd"]))

    if perf["n_cycles"] < 5:
        st.caption("_Performance metrics stabilise after ≥ 5 cycles of data._")

    st.divider()

    if not sig_df.empty and "total_nav" in sig_df.columns:
        _chart_df = (
            sig_df.drop_duplicates(subset=["cycle"])
            .sort_values("timestamp")
            .dropna(subset=["total_nav"])
        )

        # NAV chart
        st.subheader("Fund NAV")
        if _PLOTLY and len(_chart_df) > 1:
            _fig_nav = go.Figure()
            _fig_nav.add_trace(go.Scatter(
                x=_chart_df["timestamp"], y=_chart_df["total_nav"],
                mode="lines",
                line=dict(color="#38bdf8", width=2),
                fill="tozeroy", fillcolor="rgba(56,189,248,0.08)",
                hovertemplate="<b>%{x|%Y-%m-%d %H:%M}</b><br>NAV: $%{y:,.2f}<extra></extra>",
            ))
            _fig_nav.update_layout(
                height=220, margin=dict(l=0, r=0, t=8, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(17,24,39,0.6)",
                xaxis=dict(showgrid=False, color="#6b7280"),
                yaxis=dict(gridcolor="#1f2937", color="#6b7280",
                           tickprefix="$", tickformat=",.0f"),
                showlegend=False,
            )
            st.plotly_chart(_fig_nav, use_container_width=True,
                            config={"displayModeBar": False})
        else:
            st.line_chart(_chart_df.set_index("timestamp")[["total_nav"]])

        # Drawdown chart
        if "drawdown" in _chart_df.columns:
            st.subheader("Drawdown")
            if _PLOTLY and len(_chart_df) > 1:
                _dd_vals = _chart_df["drawdown"].fillna(0) * 100
                _fig_dd  = go.Figure()
                _fig_dd.add_trace(go.Scatter(
                    x=_chart_df["timestamp"], y=_dd_vals,
                    mode="lines",
                    line=dict(color="#ef4444", width=2),
                    fill="tozeroy", fillcolor="rgba(239,68,68,0.08)",
                    hovertemplate="<b>%{x|%Y-%m-%d %H:%M}</b><br>DD: %{y:.3f}%<extra></extra>",
                ))
                _fig_dd.update_layout(
                    height=160, margin=dict(l=0, r=0, t=8, b=0),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(17,24,39,0.6)",
                    xaxis=dict(showgrid=False, color="#6b7280"),
                    yaxis=dict(gridcolor="#1f2937", color="#6b7280",
                               ticksuffix="%", autorange="reversed"),
                    showlegend=False,
                )
                st.plotly_chart(_fig_dd, use_container_width=True,
                                config={"displayModeBar": False})
            else:
                st.line_chart(_chart_df.set_index("timestamp")[["drawdown"]])

        # Allocation drift chart
        if "crypto_frac" in _chart_df.columns:
            st.subheader("Crypto Allocation Over Time")
            if _PLOTLY and len(_chart_df) > 1:
                _cf_vals  = _chart_df["crypto_frac"].fillna(0.5) * 100
                _fig_alloc = go.Figure()
                _fig_alloc.add_hrect(
                    y0=_lo_pct, y1=_hi_pct,
                    fillcolor="rgba(34,197,94,0.10)", line_width=0,
                )
                _fig_alloc.add_hline(
                    y=50.0, line_dash="dot",
                    line_color="#4b5563", line_width=1,
                )
                _fig_alloc.add_trace(go.Scatter(
                    x=_chart_df["timestamp"], y=_cf_vals,
                    mode="lines",
                    line=dict(color="#a78bfa", width=2),
                    hovertemplate="<b>%{x|%Y-%m-%d %H:%M}</b><br>Crypto: %{y:.1f}%<extra></extra>",
                ))
                _fig_alloc.update_layout(
                    height=160, margin=dict(l=0, r=0, t=8, b=0),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(17,24,39,0.6)",
                    xaxis=dict(showgrid=False, color="#6b7280"),
                    yaxis=dict(gridcolor="#1f2937", color="#6b7280",
                               ticksuffix="%", range=[30, 70]),
                    showlegend=False,
                )
                st.plotly_chart(_fig_alloc, use_container_width=True,
                                config={"displayModeBar": False})
            else:
                st.line_chart(_chart_df.set_index("timestamp")[["crypto_frac"]])
    else:
        st.info("No signal history yet — charts will appear after the first cycle.")


# ─────────────────────────────────────────────────────
# TAB 2 — Positions & Risk
# ─────────────────────────────────────────────────────
with tab_positions:

    st.subheader("Live Positions")

    _pos_rows = []
    for _sl_state, _sl_label in [
        (btc_state,    btc_state.get("asset",    "BTC")            if btc_state    else "BTC"),
        (eth_state,    eth_state.get("asset",    "ETH")            if eth_state    else "ETH"),
        (equity_state, equity_state.get("asset", "EQUITY_COMPOSITE") if equity_state else "EQUITY_COMPOSITE"),
    ]:
        if not _sl_state:
            continue
        _units    = float(_sl_state.get("position_units", 0.0))
        _cash_sl  = float(_sl_state.get("cash", 0.0))
        _nav_sl   = float(_sl_state.get("nav", 0.0))
        _avg_ep   = float(_sl_state.get("average_entry_price", 0.0))
        _unreal   = float(_sl_state.get("unrealized_pnl_usd", 0.0))
        _hwm_sl   = float(_sl_state.get("high_water_mark") or _nav_sl or 1.0)
        _sl_dd    = (_nav_sl / _hwm_sl - 1.0) if _hwm_sl > 0 else 0.0

        if _units > 1e-10:
            _cur_price  = (_nav_sl - _cash_sl) / _units
            _weight_pct = (_units * _cur_price) / total_nav * 100 if total_nav > 0 else 0.0
            if _avg_ep > 0:
                _cost_basis = _avg_ep * _units
                _unreal     = (_cur_price - _avg_ep) * _units   # derive; don't trust stale field
                _unreal_pct = _unreal / _cost_basis if _cost_basis > 0 else 0.0
            else:
                _unreal = _unreal_pct = 0.0
        else:
            _cur_price = _unreal = _unreal_pct = _weight_pct = 0.0

        _pos_rows.append({
            "Asset":            _sl_label,
            "Units":            round(_units, 6),
            "Avg Entry":        round(_avg_ep, 4) if _avg_ep > 0 else float("nan"),
            "Mark Price":       round(_cur_price, 4) if _cur_price > 0 else 0.0,
            "Unreal PnL $":     round(_unreal, 2),
            "Unreal PnL %":     round(_unreal_pct * 100, 3),
            "Sleeve NAV":       round(_nav_sl, 2),
            "Sleeve HWM":       round(_hwm_sl, 2),
            "Sleeve DD %":      round(_sl_dd * 100, 3),
            "Weight %":         round(_weight_pct, 2),
        })

    if _pos_rows:
        def _col_signed(v: float) -> str:
            if v > 0:  return "color: #22c55e; font-weight: 600"
            if v < 0:  return "color: #ef4444; font-weight: 600"
            return "color: #6b7280"

        _pos_df = pd.DataFrame(_pos_rows)
        _styled = (
            _pos_df.style
            .map(_col_signed, subset=["Unreal PnL $", "Unreal PnL %", "Sleeve DD %"])
            .format({
                "Units":       "{:.6f}",
                "Avg Entry":   "${:,.4f}",
                "Mark Price":  "${:,.4f}",
                "Unreal PnL $": "${:+,.2f}",
                "Unreal PnL %": "{:+.3f}%",
                "Sleeve NAV":  "${:,.2f}",
                "Sleeve HWM":  "${:,.2f}",
                "Sleeve DD %": "{:+.3f}%",
                "Weight %":    "{:.2f}%",
            })
        )
        st.dataframe(_styled, use_container_width=True, hide_index=True)

        _all_flat   = all(r["Units"] == 0.0 for r in _pos_rows)
        _wt_sum     = sum(r["Weight %"] for r in _pos_rows)
        pc1, pc2    = st.columns(2)
        pc1.caption(
            "All positions: **FLAT**" if _all_flat
            else f"Total position weight: **{_wt_sum:.2f}%** of fund NAV"
        )
        if not _all_flat and total_nav > 0:
            _cash_rem = total_nav * (1 - _wt_sum / 100)
            pc2.caption(f"Cash across sleeves (approx.): **{_usd(_cash_rem)}**")
    else:
        st.info("No sleeve state available.")

    st.divider()
    st.subheader("Sleeve Detail")

    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.markdown("**BTC Sub-Sleeve**")
        _render_sleeve_detail(
            btc_state, "BTC", total_nav,
            last_trade=last_trades.get("BTC"),
        )
    with sc2:
        st.markdown("**ETH Sub-Sleeve**")
        _render_sleeve_detail(
            eth_state, "ETH", total_nav,
            last_trade=last_trades.get("ETH"),
        )
    with sc3:
        st.markdown("**Equity Sleeve — EQUITY_COMPOSITE**")
        _render_sleeve_detail(
            equity_state, "EQUITY_COMPOSITE", total_nav,
            last_trade=last_trades.get("EQUITY_COMPOSITE"),
        )
        _ed2      = equity_detail
        _eh2      = equity_health
        _ed2_live = _ed2 and _ed2.get("spy_close") is not None
        if _ed2_live and _eh2.get("in_pos") and not _eh2.get("avg_ep_stale") and _eh2.get("mark"):
            st.caption("**Component Reference**")
            _sw2 = float(_ed2.get("spy_weight", 0.5))
            _qw2 = float(_ed2.get("qqq_weight", 0.5))
            _sc2 = float(_ed2["spy_close"])
            _qc2 = float(_ed2["qqq_close"])
            _ss2 = _ed2.get("spy_sma")
            _qs2 = _ed2.get("qqq_sma")
            _sa2 = bool(_ed2.get("spy_active", False))
            _qa2 = bool(_ed2.get("qqq_active", False))
            _ref_df = pd.DataFrame([
                {
                    "Asset":      "SPY",
                    "Weight":     f"{_sw2:.0%}",
                    "Last Bar $": round(_sc2, 2),
                    "SMA $":      round(float(_ss2), 2) if _ss2 else None,
                    "Signal":     "above SMA" if _sa2 else "below SMA",
                },
                {
                    "Asset":      "QQQ",
                    "Weight":     f"{_qw2:.0%}",
                    "Last Bar $": round(_qc2, 2),
                    "SMA $":      round(float(_qs2), 2) if _qs2 else None,
                    "Signal":     "above SMA" if _qa2 else "below SMA",
                },
            ])
            st.dataframe(
                _ref_df.style.format({
                    "Last Bar $": "${:,.2f}",
                    "SMA $":      "${:,.2f}",
                }),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                f"1 unit = SPY×{_sw2:.0%} + QQQ×{_qw2:.0%}. "
                "P&L tracked at composite level — see sleeve overview above."
            )


# ─────────────────────────────────────────────────────
# TAB 3 — Trade Blotter
# ─────────────────────────────────────────────────────
with tab_blotter:

    st.subheader("Orders & Fills — last 100 executed trades")

    if not fills_df.empty:
        bf1, bf2, _ = st.columns([1, 1, 4])
        _sl_opts   = ["All"] + sorted(fills_df["sleeve"].dropna().unique().tolist()) \
                     if "sleeve" in fills_df.columns else ["All"]
        _side_opts = ["All", "BUY", "SELL"]
        _sel_sl    = bf1.selectbox("Sleeve", _sl_opts,   key="blotter_sl")
        _sel_side  = bf2.selectbox("Side",   _side_opts, key="blotter_side")

        _bview = fills_df.copy()
        if _sel_sl   != "All" and "sleeve" in _bview.columns:
            _bview = _bview[_bview["sleeve"] == _sel_sl]
        if _sel_side != "All" and "side"   in _bview.columns:
            _bview = _bview[_bview["side"] == _sel_side]

        _bcols = {
            "timestamp":      "Time (UTC)",
            "sleeve":         "Sleeve",
            "side":           "Side",
            "qty":            "Qty",
            "fill_price":     "Fill Price",
            "mid_price":      "Mid Price",
            "slippage_usd":   "Slippage $",
            "fee":            "Fee $",
            "cost_bps":       "Cost bps",
            "nav_after":      "NAV After",
            "exposure_after": "Exposure",
            "regime":         "Regime",
            "reason":         "Reason",
        }
        _bp = [c for c in _bcols if c in _bview.columns]
        _bview = _bview[_bp].rename(columns=_bcols)

        def _col_side(v: str) -> str:
            return ("color: #22c55e; font-weight: 600" if v == "BUY"
                    else "color: #ef4444; font-weight: 600")

        _bstyled = _bview.style.map(_col_side, subset=["Side"]) \
                   if "Side" in _bview.columns else _bview.style
        st.dataframe(_bstyled, use_container_width=True, hide_index=True)

        # Summary
        n_buys     = int((fills_df["side"] == "BUY").sum())  if "side"         in fills_df.columns else 0
        n_sells    = int((fills_df["side"] == "SELL").sum()) if "side"         in fills_df.columns else 0
        total_fees = fills_df["fee"].sum()                   if "fee"          in fills_df.columns else 0.0
        total_slip = fills_df["slippage_usd"].sum()          if "slippage_usd" in fills_df.columns else 0.0
        avg_bps    = fills_df["cost_bps"].mean()             if "cost_bps"     in fills_df.columns else 0.0

        bs1, bs2, bs3, bs4, bs5 = st.columns(5)
        bs1.metric("Total Fills",     len(fills_df))
        bs2.metric("Buys",            n_buys)
        bs3.metric("Sells",           n_sells)
        bs4.metric("Total Fees",      f"${total_fees:.2f}")
        bs5.metric("Avg Cost (bps)",  f"{avg_bps:.1f}")
        st.caption(f"Total slippage: {_usd(total_slip)}")
    else:
        st.info("No fills recorded yet. Fills appear here as trades execute.")


# ─────────────────────────────────────────────────────
# TAB 4 — Signals
# ─────────────────────────────────────────────────────
with tab_signals:

    st.subheader("Signal History — all decisions (last 200 cycles)")

    if not sig_df.empty:
        sf1, sf2, _ = st.columns([1, 1, 4])
        _ssl_opts = ["All"] + sorted(sig_df["sleeve"].dropna().unique().tolist())
        _sev_opts = ["All"] + sorted(sig_df["event"].dropna().unique().tolist())
        _sel_ssl  = sf1.selectbox("Sleeve", _ssl_opts, key="sig_sl")
        _sel_sev  = sf2.selectbox("Event",  _sev_opts, key="sig_ev")

        _sview = sig_df.copy()
        if _sel_ssl != "All":
            _sview = _sview[_sview["sleeve"] == _sel_ssl]
        if _sel_sev != "All":
            _sview = _sview[_sview["event"] == _sel_sev]

        _EV_COL = {
            "FILL_BUY":      "#22c55e",
            "FILL_SELL":     "#ef4444",
            "HOLD":          "#6b7280",
            "REJECTED_SELL": "#f59e0b",
            "REJECTED_BUY":  "#f59e0b",
            "REJECTED_HOLD": "#f59e0b",
        }

        def _col_event(v: str) -> str:
            return f"color: {_EV_COL.get(v, '#9ca3af')}; font-weight: 600"

        def _col_approved(v: object) -> str:
            if v is True:  return "color: #22c55e"
            if v is False: return "color: #ef4444"
            return ""

        _scols = {
            "timestamp":  "Time (UTC)",
            "cycle":      "Cycle",
            "sleeve":     "Sleeve",
            "event":      "Event",
            "regime":     "Regime",
            "exposure":   "Exposure",
            "nav":        "NAV",
            "fill_side":  "Fill Side",
            "fill_qty":   "Fill Qty",
            "fill_price": "Fill Price",
            "fill_fee":   "Fill Fee $",
            "approved":   "Approved",
            "reason":     "Reason",
        }
        _sp = [c for c in _scols if c in _sview.columns]
        _sview = _sview[_sp].rename(columns=_scols)

        _sstyled = (
            _sview.style
            .map(_col_event,    subset=["Event"])
            .map(_col_approved, subset=["Approved"])
        )
        st.dataframe(_sstyled, use_container_width=True, hide_index=True)

        _total_cyc    = sig_df["cycle"].nunique()
        _fill_rows    = sig_df[sig_df["event"].str.startswith("FILL_",     na=False)]
        _reject_rows  = sig_df[sig_df["event"].str.startswith("REJECTED_", na=False)]
        _hold_rows    = sig_df[sig_df["event"] == "HOLD"]

        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Cycles logged", _total_cyc)
        sc2.metric("Fills",         len(_fill_rows),   help="FILL_BUY + FILL_SELL")
        sc3.metric("Holds",         len(_hold_rows))
        sc4.metric("Rejections",    len(_reject_rows), help="Blocked by a governor")
    else:
        st.info("No signal history yet. Entries appear each cycle.")


# ─────────────────────────────────────────────────────
# TAB 5 — Rebalances
# ─────────────────────────────────────────────────────
with tab_rebalances:

    st.subheader("Cross-Asset Rebalance Events")

    if not rebal_df.empty:
        _rcols = {
            "timestamp":           "Time (UTC)",
            "direction":           "Direction",
            "transfer_usd":        "Transfer $",
            "crypto_nav_before":   "Crypto NAV Before",
            "equity_nav_before":   "Equity NAV Before",
            "total_nav_before":    "Total NAV Before",
            "crypto_split_before": "Crypto % Before",
            "equity_split_before": "Equity % Before",
            "crypto_split_after":  "Crypto % After",
            "equity_split_after":  "Equity % After",
        }
        _rp     = [c for c in _rcols if c in rebal_df.columns]
        _rview  = rebal_df[_rp].rename(columns=_rcols)

        _rfmt: dict[str, str] = {}
        for _col in ["Transfer $", "Crypto NAV Before", "Equity NAV Before", "Total NAV Before"]:
            if _col in _rview.columns:
                _rfmt[_col] = "${:,.2f}"
        for _col in ["Crypto % Before", "Equity % Before", "Crypto % After", "Equity % After"]:
            if _col in _rview.columns:
                _rfmt[_col] = "{:.2%}"

        def _col_direction(v: str) -> str:
            if v == "crypto_to_equity": return "color: #a78bfa; font-weight: 600"
            if v == "equity_to_crypto": return "color: #38bdf8; font-weight: 600"
            return ""

        _rstyled = _rview.style.format(_rfmt)
        if "Direction" in _rview.columns:
            _rstyled = _rstyled.map(_col_direction, subset=["Direction"])
        st.dataframe(_rstyled, use_container_width=True, hide_index=True)
        st.caption(f"{len(rebal_df)} rebalance event(s) shown (sub-$1 skipped events excluded).")
    else:
        st.info("No rebalance events recorded yet.")


# ══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(
    f'<div class="dash-footer">'
    f"Itera Dynamics · Unified Fund v1 · Dashboard v{_VERSION} · "
    f"Environment: <b>{_ENV_LABEL}</b> · "
    f"Cycle {fund_cycle} · "
    f"Auto-refresh every {REFRESH_SECS}s"
    f"</div>",
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════════════════════════════════════
# AUTO-REFRESH
# Each render sleeps ≤5 s then checks whether the interval has elapsed.
# Install streamlit-autorefresh for a non-blocking alternative:
#   pip install streamlit-autorefresh
#   from streamlit_autorefresh import st_autorefresh
#   st_autorefresh(interval=REFRESH_SECS * 1000, key="auto")
# ══════════════════════════════════════════════════════════════════════════════
_remaining = st.session_state.next_refresh - time.time()
if _remaining <= 0:
    st.session_state.next_refresh = time.time() + REFRESH_SECS
    st.rerun()
else:
    time.sleep(min(5.0, _remaining))
    st.rerun()
