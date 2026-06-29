from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


TIMESTAMP_ALIASES = ["timestamp", "time", "date", "datetime", "Date", "Timestamp", "Unnamed: 0", ""]
REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]


def find_timestamp_column(df: pd.DataFrame) -> str:
    for col in TIMESTAMP_ALIASES:
        if col in df.columns:
            return col
    raise ValueError(f"no timestamp column found; columns={list(df.columns)}")


def load_ohlcv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    ts_col = find_timestamp_column(df)
    rename_map = {c: c.lower() for c in df.columns if c != ts_col}
    df = df.rename(columns=rename_map)

    ts = df[ts_col]
    if pd.api.types.is_numeric_dtype(ts):
        unit = "ms" if ts.dropna().median() > 1e12 else "s"
        parsed = pd.to_datetime(ts, unit=unit, utc=True).dt.tz_localize(None)
    else:
        parsed = pd.to_datetime(ts, errors="coerce", utc=False)
        if getattr(parsed.dt, "tz", None) is not None:
            parsed = parsed.dt.tz_convert(None)

    df["timestamp"] = parsed
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing required columns {missing}; columns={list(df.columns)}")

    out = df[["timestamp", *REQUIRED_COLUMNS]].copy()
    for col in REQUIRED_COLUMNS:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["timestamp"])
    out = out.sort_values("timestamp").drop_duplicates("timestamp", keep="last")
    return out.set_index("timestamp")


def gap_report(df: pd.DataFrame, max_rows: int) -> None:
    gaps = df.index.to_series().diff().dropna()
    gaps = gaps[gaps > pd.Timedelta(hours=1)]
    print(f"gaps > 1h: {len(gaps)}")
    for ts, delta in gaps.head(max_rows).items():
        pos = df.index.get_loc(ts)
        prev = df.index[pos - 1] if isinstance(pos, int) and pos > 0 else None
        print(f"  {prev} -> {ts} gap={delta}")


def compare(asset: str, old_path: str, new_path: str, threshold_pct: float, max_rows: int) -> None:
    old = load_ohlcv(old_path)
    new = load_ohlcv(new_path)
    common = old.index.intersection(new.index)
    old_c = old.loc[common]
    new_c = new.loc[common]

    close_abs = (old_c["close"] - new_c["close"]).abs()
    close_pct = close_abs / old_c["close"].replace(0, pd.NA)

    print(f"\n=== {asset} OVERLAP CHECK ===")
    print(f"old: {old_path}")
    print(f"new: {new_path}")
    print(f"old rows:      {len(old)}")
    print(f"new rows:      {len(new)}")
    print(f"common rows:   {len(common)}")
    print(f"old start/end: {old.index.min()} -> {old.index.max()}")
    print(f"new start/end: {new.index.min()} -> {new.index.max()}")
    if len(common):
        print(f"common:        {common.min()} -> {common.max()}")
        print(f"max close abs diff:    {close_abs.max():.8f}")
        print(f"mean close abs diff:   {close_abs.mean():.8f}")
        print(f"median close abs diff: {close_abs.median():.8f}")
        print(f"max close pct diff:    {float(close_pct.max() * 100):.6f}%")
        print(f"mean close pct diff:   {float(close_pct.mean() * 100):.6f}%")

        big = close_pct[close_pct > threshold_pct / 100.0]
        print(f"rows > {threshold_pct:.4f}% close diff: {len(big)}")
        if len(big):
            print(f"first {max_rows} big diffs:")
            for ts in big.index[:max_rows]:
                print(
                    f"  {ts} old_close={old_c.loc[ts, 'close']} "
                    f"new_close={new_c.loc[ts, 'close']} "
                    f"pct={float(close_pct.loc[ts] * 100):.6f}%"
                )
    print("new file gap report:")
    gap_report(new, max_rows=max_rows)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Compare overlapping OHLCV CSVs with flexible timestamp columns.")
    ap.add_argument("--asset", required=True)
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--threshold-pct", type=float, default=0.10)
    ap.add_argument("--max-rows", type=int, default=10)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    compare(args.asset, args.old, args.new, args.threshold_pct, args.max_rows)


if __name__ == "__main__":
    main()
