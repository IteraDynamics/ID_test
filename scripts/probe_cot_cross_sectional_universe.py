"""Feasibility probe for the cross-sectional COT redesign -- can we even get the price data?

Campaign #55 (COT positioning -> SPY/QQQ) closed 2026-08-26 as UNDERPOWERED, not as a null, with
Amendment 1's own remedy identified: test the same positioning-contrarian hypothesis across the
broad cross-section of liquid CFTC-tracked futures markets rather than two, which buys real
statistical power per unit of calendar time and naturally supports FDR-controlled discovery with
an untouched holdout subset of markets.

That redesign has a hard prerequisite nobody has checked: **COT reports positions, not prices.**
Every market in the cross-section needs a matching price series to compute forward returns
against. Locally we have SPY, QQQ, GLD and TLT -- four. If a broad price universe cannot actually
be obtained, the redesign is dead no matter how good its statistics would be, and discovering
that AFTER building the analysis is precisely the failure mode CLAUDE.md's "measure the
constraint before doing the work" rule exists to prevent (four feasibility gates have each
already redirected or killed real work here).

So this probe answers one question and builds nothing else: for how many markets can we obtain
BOTH long COT history AND a usable price series?

The candidate COT-market -> ticker mapping below is RECOLLECTION, not verified fact. This session
has been wrong from memory repeatedly (an ETF ticker, a CFTC market name, a venue root filter,
a broker-capability claim), so nothing here is asserted: every COT name is resolved against the
real dataset (by row count and recency, never by guessing which naming variant is current), and
every ticker is validated by actually fetching it. Pairs that fail are reported as failures.

Inclusion criteria, fixed BEFORE running so the universe is not selected on outcomes:
  - at least MIN_COT_REPORTS weekly reports for the market;
  - COT data current to within MAX_COT_STALENESS_DAYS of the dataset's own end;
  - a price series that fetches successfully with at least MIN_PRICE_ROWS daily closes.
No criterion references returns, correlations, or anything downstream. The universe is chosen on
data availability alone.

Read-only. Writes findings to artifacts/ and never raises, matching this repo's probe convention.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

MIN_COT_REPORTS = 500          # ~10 years of weekly reports
MAX_COT_STALENESS_DAYS = 90    # market must still be actively reported
MIN_PRICE_ROWS = 2000          # ~8 years of daily closes
PRICE_START = "2005-01-01"     # generous; actual coverage is measured, not assumed

# Candidate mapping: (search substring for the COT market name, candidate ticker, label).
# BOTH halves are unverified recollection. The COT substring is resolved against the real
# dataset and the ticker is fetched for real; failures on either side are reported, not hidden.
CANDIDATES = [
    ("GOLD - COMMODITY EXCHANGE", "GC=F", "Gold"),
    ("SILVER - COMMODITY EXCHANGE", "SI=F", "Silver"),
    ("COPPER", "HG=F", "Copper"),
    ("PLATINUM", "PL=F", "Platinum"),
    ("CRUDE OIL, LIGHT SWEET", "CL=F", "WTI Crude"),
    ("NATURAL GAS", "NG=F", "Natural Gas"),
    ("GASOLINE", "RB=F", "Gasoline"),
    ("CORN", "ZC=F", "Corn"),
    ("SOYBEANS", "ZS=F", "Soybeans"),
    ("SOYBEAN OIL", "ZL=F", "Soybean Oil"),
    ("WHEAT-SRW", "ZW=F", "Wheat SRW"),
    ("SUGAR NO. 11", "SB=F", "Sugar"),
    ("COFFEE C", "KC=F", "Coffee"),
    ("COCOA", "CC=F", "Cocoa"),
    ("COTTON NO. 2", "CT=F", "Cotton"),
    ("LIVE CATTLE", "LE=F", "Live Cattle"),
    ("LEAN HOGS", "HE=F", "Lean Hogs"),
    ("EURO FX", "6E=F", "Euro FX"),
    ("JAPANESE YEN", "6J=F", "Japanese Yen"),
    ("BRITISH POUND", "6B=F", "British Pound"),
    ("CANADIAN DOLLAR", "6C=F", "Canadian Dollar"),
    ("AUSTRALIAN DOLLAR", "6A=F", "Australian Dollar"),
    ("SWISS FRANC", "6S=F", "Swiss Franc"),
    ("MEXICAN PESO", "6M=F", "Mexican Peso"),
    ("U.S. DOLLAR INDEX", "DX=F", "US Dollar Index"),
    ("10-YEAR U.S. TREASURY NOTES", "ZN=F", "10Y T-Note"),
    ("ULTRA U.S. TREASURY BONDS", "UB=F", "Ultra T-Bond"),
    ("5-YEAR U.S. TREASURY NOTES", "ZF=F", "5Y T-Note"),
    ("2-YEAR U.S. TREASURY NOTES", "ZT=F", "2Y T-Note"),
    ("S&P 500 Consolidated", "ES=F", "S&P 500"),
    ("NASDAQ-100 Consolidated", "NQ=F", "Nasdaq-100"),
    ("DOW JONES INDUSTRIAL AVG", "YM=F", "Dow"),
    ("RUSSELL 2000", "RTY=F", "Russell 2000"),
]


def resolve_cot_market(
    names_df: pd.DataFrame, substring: str, dataset_end: pd.Timestamp | None = None
) -> dict | None:
    """Pick the real, currently-reported market name matching a substring, by row count and
    recency -- never by guessing which naming variant is current. The S&P 500 / Nasdaq-100
    lookups on 2026-08-26 found 15 and 6 competing variants respectively, several long
    discontinued, so this resolution step is doing real work rather than formality.

    dataset_end is the reference point staleness is measured against. It defaults to the passed
    frame's own maximum, which is correct when the FULL dataset is passed (as main() does) but
    silently wrong if a pre-filtered frame is passed -- an already-discontinued market looks
    perfectly current relative to itself. Made explicit rather than left implicit after that
    exact trap caught a test on 2026-08-26."""
    matches = names_df[names_df["Market and Exchange Names"].str.contains(substring, case=False, na=False, regex=False)]
    if matches.empty:
        return None
    if dataset_end is None:
        dataset_end = names_df["report_date"].max()
    best = None
    for name, grp in matches.groupby("Market and Exchange Names"):
        end = grp["report_date"].max()
        staleness = (dataset_end - end).days
        cand = {
            "market_name": name, "reports": len(grp),
            "start": str(grp["report_date"].min().date()), "end": str(end.date()),
            "staleness_days": staleness,
        }
        # Prefer current markets; among those, the one with the most reports.
        key = (staleness <= MAX_COT_STALENESS_DAYS, len(grp))
        if best is None or key > best[0]:
            best = (key, cand)
    return best[1] if best else None


def probe_ticker(ticker: str, start: str) -> dict:
    try:
        import yfinance as yf
    except ImportError:
        return {"ok": False, "error": "yfinance not installed (run: uv sync --extra data)"}
    try:
        raw = yf.download(ticker, start=start, progress=False, auto_adjust=False)
        if raw is None or len(raw) == 0:
            return {"ok": False, "error": "no rows returned"}
        idx = raw.index
        return {
            "ok": True, "rows": int(len(raw)),
            "start": str(idx.min().date()), "end": str(idx.max().date()),
        }
    except Exception as exc:  # noqa: BLE001 -- a probe reports, never raises
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--cot-csv", default="data/cot_legacy_futures_only_1986_present.csv")
    p.add_argument("--price-start", default=PRICE_START)
    p.add_argument("--out-dir", default="artifacts")
    p.add_argument("--out-name", default="cot_cross_sectional_universe_probe.json")
    p.add_argument("--skip-prices", action="store_true",
                   help="Resolve COT names only, without fetching any price data.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print("Loading COT market names and dates...")
    df = pd.read_csv(args.cot_csv, usecols=["Market and Exchange Names", "As of Date in Form YYYY-MM-DD"],
                     low_memory=False)
    df["report_date"] = pd.to_datetime(df["As of Date in Form YYYY-MM-DD"])
    print(f"{len(df):,} rows, {df['Market and Exchange Names'].nunique():,} distinct market names, "
          f"{df['report_date'].min().date()} -> {df['report_date'].max().date()}")

    print(f"\nInclusion criteria (fixed before running, none reference outcomes):")
    print(f"  >= {MIN_COT_REPORTS} weekly COT reports")
    print(f"  COT current to within {MAX_COT_STALENESS_DAYS} days of dataset end")
    print(f"  price series fetches with >= {MIN_PRICE_ROWS} daily closes")

    dataset_end = df["report_date"].max()
    results = []
    print(f"\n{'label':<18} {'COT reports':>11} {'COT end':>12} {'ticker':>7} {'price rows':>11}  verdict")
    print("-" * 84)
    for substring, ticker, label in CANDIDATES:
        cot = resolve_cot_market(df, substring, dataset_end)
        row = {"label": label, "cot_substring": substring, "ticker": ticker, "cot": cot}

        if cot is None:
            row["included"] = False
            row["reason"] = "no COT market matched the substring"
            print(f"{label:<18} {'-':>11} {'-':>12} {ticker:>7} {'-':>11}  EXCLUDED (no COT match)")
            results.append(row)
            continue

        cot_ok = cot["reports"] >= MIN_COT_REPORTS and cot["staleness_days"] <= MAX_COT_STALENESS_DAYS
        if args.skip_prices:
            row["included"] = cot_ok
            row["reason"] = "" if cot_ok else "COT history too short or stale"
            print(f"{label:<18} {cot['reports']:>11} {cot['end']:>12} {ticker:>7} {'skipped':>11}  "
                  f"{'cot-ok' if cot_ok else 'EXCLUDED (cot)'}")
            results.append(row)
            continue

        price = probe_ticker(ticker, args.price_start)
        row["price"] = price
        price_ok = price.get("ok") and price.get("rows", 0) >= MIN_PRICE_ROWS
        included = bool(cot_ok and price_ok)
        row["included"] = included
        if not cot_ok:
            row["reason"] = f"COT: {cot['reports']} reports, {cot['staleness_days']}d stale"
        elif not price_ok:
            row["reason"] = f"price: {price.get('error') or str(price.get('rows')) + ' rows'}"
        else:
            row["reason"] = ""

        verdict = "INCLUDED" if included else f"EXCLUDED ({row['reason']})"
        print(f"{label:<18} {cot['reports']:>11} {cot['end']:>12} {ticker:>7} "
              f"{price.get('rows', 0) if price.get('ok') else 0:>11}  {verdict}")
        results.append(row)

    included = [r for r in results if r.get("included")]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "criteria": {
            "min_cot_reports": MIN_COT_REPORTS,
            "max_cot_staleness_days": MAX_COT_STALENESS_DAYS,
            "min_price_rows": MIN_PRICE_ROWS,
        },
        "candidates_tested": len(CANDIDATES),
        "included_count": len(included),
        "included_labels": [r["label"] for r in included],
        "results": results,
    }
    out_path = out_dir / args.out_name
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    print(f"\n{'='*84}")
    print(f"{len(included)}/{len(CANDIDATES)} candidate markets cleared BOTH gates.")
    print(f"{'='*84}")
    if included:
        print("Included: " + ", ".join(r["label"] for r in included))
    excluded = [r for r in results if not r.get("included")]
    if excluded:
        print("\nExcluded, with reasons (kept visible rather than silently dropped):")
        for r in excluded:
            print(f"  {r['label']}: {r.get('reason', 'unknown')}")

    print(f"\nWrote {out_path}")
    print("\nFEASIBILITY VERDICT for the cross-sectional redesign:")
    if len(included) >= 20:
        print(f"  VIABLE. {len(included)} markets is a real cross-section -- enough to buy the power")
        print("  Campaign #55 lacked, and enough to split into a discovery set and a genuinely")
        print("  untouched holdout subset of markets as Amendment 2 requires.")
    elif len(included) >= 10:
        print(f"  MARGINAL. {len(included)} markets beats the 2 that left Campaign #55 underpowered,")
        print("  but a discovery/holdout split would leave each side thin. Worth proceeding only")
        print("  with the split design stated up front and its limits acknowledged.")
    else:
        print(f"  NOT VIABLE as designed. {len(included)} markets is too few to buy meaningful power")
        print("  or to support a holdout split. The redesign should not proceed on this basis --")
        print("  report the gate failure rather than routing around it.")
    print("\nThis probe computes no returns, no correlations, and no signal. Universe selection")
    print("is on data availability alone, so it cannot be contaminated by outcomes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
