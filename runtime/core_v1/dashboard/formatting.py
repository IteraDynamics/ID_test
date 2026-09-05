"""Existing dashboard presentation helpers; no file writes or app startup."""
from __future__ import annotations
import html
from typing import Any
import pandas as pd
from .snapshots import parse_ts

def age_seconds(ts: pd.Timestamp | None) -> int | None:
    if ts is None:
        return None
    return max(0, int((pd.Timestamp.now(tz="UTC") - ts).total_seconds()))


def format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "unknown"
    seconds = abs(seconds)
    if seconds < 90:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 90:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h"
    return f"{hours // 24}d"


def age_text(ts: pd.Timestamp | None) -> str:
    seconds = age_seconds(ts)
    if seconds is None:
        return "unknown"
    return f"{format_duration(seconds)} ago"


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


def friendly_ts(value: Any) -> str:
    ts = parse_ts(value)
    if ts is None:
        return "—"
    return ts.strftime("%b %-d, %H:%M UTC")


def strategy_display(name: str | None) -> str:
    if not name:
        return "—"
    return name.replace("_", " ").title()

