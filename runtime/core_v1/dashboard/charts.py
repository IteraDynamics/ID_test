"""Existing NAV chart specification, separated from Streamlit rendering."""
from __future__ import annotations
from typing import Any
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Fixed display scale, not a strategy or risk-policy parameter.
DRAWDOWN_AXIS_FLOOR = -0.40

def nav_chart(history: list[dict[str, Any]], fills: list[dict[str, Any]]) -> go.Figure | None:
    """Row 1: % return vs. the $100k inception baseline. Row 2: worst-of-day
    drawdown on a fixed scale. `history` is the daily series from
    core_v1_dashboard_health.nav_history()."""
    if not history:
        return None
    hist = pd.DataFrame(history)
    hist["timestamp"] = pd.to_datetime(hist["timestamp"], utc=True, errors="coerce")
    hist = hist.dropna(subset=["timestamp"]).sort_values("timestamp")
    if hist.empty:
        return None

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.72, 0.28], vertical_spacing=0.05)

    # Row 1 — return since inception, baseline ($100k) = 0%. Anchoring the
    # fill at 0 keeps every move proportional and keeps 0 in frame, so a
    # future flat stretch reads flat rather than as autoranged noise.
    fig.add_trace(
        go.Scatter(
            x=hist["timestamp"], y=hist["ret"], mode="lines", name="Return",
            line=dict(color="#38bdf8", width=2.2), fill="tozeroy", fillcolor="rgba(56,189,248,0.10)",
            customdata=hist["nav"],
            hovertemplate="%{x|%b %-d}<br>%{y:+.2%} · $%{customdata:,.0f}<extra></extra>",
        ),
        row=1, col=1,
    )

    fill_df = pd.DataFrame(fills)
    if not fill_df.empty and "timestamp" in fill_df:
        fill_df["timestamp"] = pd.to_datetime(fill_df["timestamp"], utc=True, errors="coerce")
        fill_df = fill_df.dropna(subset=["timestamp"]).sort_values("timestamp")
        fill_df = fill_df[fill_df["timestamp"] >= hist["timestamp"].min()]
        if not fill_df.empty:
            merged = pd.merge_asof(fill_df, hist[["timestamp", "ret"]], on="timestamp", direction="nearest")
            for side, color, symbol in (("BUY", "#22c55e", "triangle-up"), ("SELL", "#ef4444", "triangle-down")):
                side_rows = merged[merged["side"].astype(str).str.upper() == side]
                if side_rows.empty:
                    continue
                has_meta = {"sleeve", "qty", "price"}.issubset(side_rows.columns)
                fig.add_trace(
                    go.Scatter(
                        x=side_rows["timestamp"], y=side_rows["ret"], mode="markers", name=side,
                        marker=dict(color=color, size=9, symbol=symbol, line=dict(color="#05070c", width=1)),
                        customdata=side_rows[["sleeve", "qty", "price"]].to_numpy() if has_meta else None,
                        hovertemplate=(f"{side} %{{customdata[0]}}<br>qty %{{customdata[1]:.4f}} @ $%{{customdata[2]:,.2f}}<extra></extra>" if has_meta else f"{side}<extra></extra>"),
                    ),
                    row=1, col=1,
                )

    fig.add_trace(
        go.Scatter(
            x=hist["timestamp"], y=hist["drawdown"], mode="lines", name="Drawdown",
            line=dict(color="#ef4444", width=1.4), fill="tozeroy", fillcolor="rgba(239,68,68,0.16)",
            hovertemplate="%{x|%b %-d}<br>Drawdown %{y:.2%}<extra></extra>",
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
    fig.update_yaxes(showgrid=True, gridcolor="#182235", zeroline=True, zerolinecolor="#475569", tickformat="+.0%", row=1, col=1)
    fig.update_yaxes(showgrid=True, gridcolor="#182235", tickformat=".0%", range=[DRAWDOWN_AXIS_FLOOR, 0.02], dtick=0.1, row=2, col=1)
    return fig

