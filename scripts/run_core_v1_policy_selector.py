from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class SelectorResult:
    name: str
    nav: pd.Series
    audit: pd.DataFrame
    metrics: dict
    annual_returns: dict[str, float]


def load_nav(path: str | Path, name: str) -> pd.Series:
    path = Path(path)
    df = pd.read_csv(path)
    if df.shape[1] < 2:
        raise ValueError(f"{path}: expected timestamp + nav columns")
    ts_col = df.columns[0]
    val_col = df.columns[1]
    idx = pd.to_datetime(df[ts_col])
    nav = pd.to_numeric(df[val_col], errors="coerce")
    out = pd.Series(nav.values, index=idx, name=name).dropna().sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out


def load_ohlcv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    ts_col = None
    for candidate in ["timestamp", "time", "date", "datetime", "Date", "Timestamp", "Unnamed: 0"]:
        if candidate in df.columns:
            ts_col = candidate
            break
    if ts_col is None:
        raise ValueError(f"{path}: no timestamp column found; columns={list(df.columns)}")
    rename = {c: c.lower() for c in df.columns if c != ts_col}
    df = df.rename(columns=rename)
    df["timestamp"] = pd.to_datetime(df[ts_col], errors="coerce")
    if getattr(df["timestamp"].dt, "tz", None) is not None:
        df["timestamp"] = df["timestamp"].dt.tz_convert(None)
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["timestamp", "close"]).sort_values("timestamp")
    df = df.drop_duplicates("timestamp", keep="last")
    return df.set_index("timestamp")


def daily_close(path: str | Path, name: str) -> pd.Series:
    df = load_ohlcv(path)
    out = df["close"].resample("D").last().dropna()
    out.name = name
    return out


def compute_metrics(nav: pd.Series) -> dict:
    nav = nav.dropna().sort_index()
    if nav.empty:
        raise ValueError("empty NAV series")
    daily = nav.resample("D").last().dropna()
    if len(daily) < 2:
        raise ValueError("not enough daily NAV observations")
    total_return = float(daily.iloc[-1] / daily.iloc[0] - 1.0)
    years = max((daily.index[-1] - daily.index[0]).days / 365.25, 1e-9)
    cagr = (1.0 + total_return) ** (1.0 / years) - 1.0
    returns = daily.pct_change().dropna()
    vol = float(returns.std(ddof=0) * (252 ** 0.5)) if len(returns) else 0.0
    sharpe = float((returns.mean() / returns.std(ddof=0)) * (252 ** 0.5)) if len(returns) and returns.std(ddof=0) > 0 else 0.0
    running_max = daily.cummax()
    dd = daily / running_max - 1.0
    maxdd = float(dd.min())
    calmar = float(cagr / abs(maxdd)) if maxdd < 0 else 0.0
    return {
        "cagr_pct": round(cagr * 100.0, 2),
        "total_return_pct": round(total_return * 100.0, 2),
        "max_drawdown_pct": round(maxdd * 100.0, 2),
        "sharpe": round(sharpe, 3),
        "calmar": round(calmar, 3),
        "volatility_ann_pct": round(vol * 100.0, 2),
        "initial_equity": round(float(daily.iloc[0]), 2),
        "final_equity": round(float(daily.iloc[-1]), 2),
    }


def annual_returns(nav: pd.Series) -> dict[str, float]:
    daily = nav.resample("D").last().dropna()
    out: dict[str, float] = {}
    for yr, grp in daily.groupby(daily.index.year):
        if len(grp) >= 5:
            out[str(yr)] = round((float(grp.iloc[-1]) / float(grp.iloc[0]) - 1.0) * 100.0, 2)
    return out


def build_signals(btc_close: pd.Series, spy_close: pd.Series) -> pd.DataFrame:
    signals = pd.DataFrame(index=btc_close.index.union(spy_close.index).sort_values())
    signals["btc_close"] = btc_close.reindex(signals.index).ffill()
    signals["spy_close"] = spy_close.reindex(signals.index).ffill()
    signals["btc_sma175"] = signals["btc_close"].rolling(175).mean()
    signals["btc_sma365"] = signals["btc_close"].rolling(365).mean()
    signals["spy_sma175"] = signals["spy_close"].rolling(175).mean()
    signals["btc_above_sma175"] = signals["btc_close"] > signals["btc_sma175"]
    signals["btc_above_sma365"] = signals["btc_close"] > signals["btc_sma365"]
    signals["spy_above_sma175"] = signals["spy_close"] > signals["spy_sma175"]
    return signals


def selector_mask(name: str, signals: pd.DataFrame) -> pd.Series:
    if name == "dual_confirmed_risk_on":
        return signals["btc_above_sma175"] & signals["spy_above_sma175"]
    if name == "btc_led_risk_on":
        return signals["btc_above_sma175"]
    if name == "btc_long_horizon_risk_on":
        return signals["btc_above_sma365"]
    if name == "equity_confirmed_or_btc_long":
        return signals["btc_above_sma365"] | (signals["btc_above_sma175"] & signals["spy_above_sma175"])
    raise ValueError(f"unknown selector: {name}")


def run_selector(
    name: str,
    baseline_nav: pd.Series,
    gold20_nav: pd.Series,
    signals: pd.DataFrame,
    start: str,
    end: str,
) -> SelectorResult:
    base_daily = baseline_nav.resample("D").last().dropna()
    gold_daily = gold20_nav.resample("D").last().dropna()
    idx = base_daily.index.intersection(gold_daily.index)
    base_daily = base_daily.loc[idx]
    gold_daily = gold_daily.loc[idx]

    base_ret = base_daily.pct_change().fillna(0.0)
    gold_ret = gold_daily.pct_change().fillna(0.0)

    signal_daily = signals.reindex(idx).ffill()
    # Use yesterday's regime signal to choose today's template. This avoids same-day close lookahead.
    use_baseline = selector_mask(name, signal_daily).shift(1).fillna(False).astype(bool)
    chosen_ret = pd.Series(index=idx, dtype=float, name=name)
    chosen_ret.loc[use_baseline] = base_ret.loc[use_baseline]
    chosen_ret.loc[~use_baseline] = gold_ret.loc[~use_baseline]

    nav = (1.0 + chosen_ret).cumprod() * 100_000.0
    nav.name = f"{name}_nav"
    nav = nav.loc[start:end]

    audit = pd.DataFrame(
        {
            "timestamp": idx,
            "selector": name,
            "use_template": ["baseline_40_35_15_10" if x else "gold20_35_35_20_10" for x in use_baseline],
            "use_baseline": use_baseline.values,
            "btc_above_sma175": signal_daily["btc_above_sma175"].values,
            "btc_above_sma365": signal_daily["btc_above_sma365"].values,
            "spy_above_sma175": signal_daily["spy_above_sma175"].values,
            "baseline_return": base_ret.values,
            "gold20_return": gold_ret.values,
            "chosen_return": chosen_ret.values,
        }
    ).set_index("timestamp")
    audit = audit.loc[start:end]

    return SelectorResult(
        name=name,
        nav=nav,
        audit=audit,
        metrics=compute_metrics(nav),
        annual_returns=annual_returns(nav),
    )


def write_report(out_dir: Path, static_metrics: dict, results: list[SelectorResult]) -> None:
    lines = ["# Core v1 Policy Selector Harness Report", ""]
    lines += ["## Static Reference", ""]
    lines.append("| Config | CAGR | MaxDD | Sharpe | Calmar | Final Equity |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for name, m in static_metrics.items():
        lines.append(f"| {name} | {m['cagr_pct']} | {m['max_drawdown_pct']} | {m['sharpe']} | {m['calmar']} | {m['final_equity']} |")
    lines += ["", "## Selector Results", ""]
    lines.append("| Selector | CAGR | MaxDD | Sharpe | Calmar | Final Equity | Baseline Active | Transitions |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in results:
        active = float(r.audit["use_baseline"].mean() * 100.0) if len(r.audit) else 0.0
        transitions = int(r.audit["use_baseline"].astype(int).diff().abs().fillna(0).sum()) if len(r.audit) else 0
        m = r.metrics
        lines.append(f"| {r.name} | {m['cagr_pct']} | {m['max_drawdown_pct']} | {m['sharpe']} | {m['calmar']} | {m['final_equity']} | {active:.2f}% | {transitions} |")
    lines += ["", "## Annual Returns", ""]
    years = sorted({yr for r in results for yr in r.annual_returns.keys()})
    lines.append("| Selector | " + " | ".join(years) + " |")
    lines.append("|---|" + "|".join(["---:"] * len(years)) + "|")
    for r in results:
        vals = [f"{r.annual_returns.get(yr, float('nan')):+.2f}%" for yr in years]
        lines.append("| " + r.name + " | " + " | ".join(vals) + " |")
    lines += ["", "## Methodology", ""]
    lines.append("This harness combines the daily returns of two completed static portfolio NAV streams.")
    lines.append("The selector uses yesterday's regime signal to choose today's template return, avoiding same-day close lookahead.")
    lines.append("This is a first-pass policy test, not a replacement for a full sleeve-level rerun.")
    lines.append("")
    lines.append("_Research only. Not financial advice._")
    (out_dir / "policy_selector_report.md").write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Test deterministic policy selectors between Core v1 baseline and gold20 NAV streams.")
    ap.add_argument("--baseline-nav", required=True)
    ap.add_argument("--gold20-nav", required=True)
    ap.add_argument("--btc-data", required=True)
    ap.add_argument("--spy-data", required=True)
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--out-dir", default="artifacts/core_v1_policy_selector")
    ap.add_argument(
        "--selectors",
        nargs="+",
        default=[
            "dual_confirmed_risk_on",
            "btc_led_risk_on",
            "btc_long_horizon_risk_on",
            "equity_confirmed_or_btc_long",
        ],
    )
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    baseline = load_nav(args.baseline_nav, "baseline")
    gold20 = load_nav(args.gold20_nav, "gold20")
    btc = daily_close(args.btc_data, "btc_close")
    spy = daily_close(args.spy_data, "spy_close")
    signals = build_signals(btc, spy)

    static_metrics = {
        "baseline_40_35_15_10": compute_metrics(baseline.loc[args.start : args.end]),
        "gold20_35_35_20_10": compute_metrics(gold20.loc[args.start : args.end]),
    }

    results: list[SelectorResult] = []
    for selector in args.selectors:
        result = run_selector(selector, baseline, gold20, signals, args.start, args.end)
        results.append(result)
        result.nav.to_csv(out_dir / f"{selector}_nav.csv", header=True)
        result.audit.to_csv(out_dir / f"{selector}_audit.csv")

    summary = {
        "static_reference": static_metrics,
        "selectors": {
            r.name: {
                "metrics": r.metrics,
                "annual_returns": r.annual_returns,
                "baseline_active_pct": round(float(r.audit["use_baseline"].mean() * 100.0), 2) if len(r.audit) else 0.0,
                "transitions": int(r.audit["use_baseline"].astype(int).diff().abs().fillna(0).sum()) if len(r.audit) else 0,
            }
            for r in results
        },
        "config": vars(args),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_report(out_dir, static_metrics, results)

    print("=== STATIC REFERENCE ===")
    for name, m in static_metrics.items():
        print(f"{name}: CAGR {m['cagr_pct']:.2f}% MaxDD {m['max_drawdown_pct']:.2f}% Sharpe {m['sharpe']:.3f} Calmar {m['calmar']:.3f}")
    print("\n=== SELECTORS ===")
    for r in results:
        m = r.metrics
        active = float(r.audit["use_baseline"].mean() * 100.0) if len(r.audit) else 0.0
        transitions = int(r.audit["use_baseline"].astype(int).diff().abs().fillna(0).sum()) if len(r.audit) else 0
        print(f"{r.name}: CAGR {m['cagr_pct']:.2f}% MaxDD {m['max_drawdown_pct']:.2f}% Sharpe {m['sharpe']:.3f} Calmar {m['calmar']:.3f} baseline_active {active:.2f}% transitions {transitions}")
    print(f"\nWrote artifacts to {out_dir}")


if __name__ == "__main__":
    main()
