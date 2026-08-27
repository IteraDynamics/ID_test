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

COT market names in the mapping below are copied VERBATIM from a real enumeration of the live
universe, not written from memory -- an earlier substring-based version paired sterling's ticker
with a EUR/GBP cross-rate contract and reported it as INCLUDED, so matching is now exact (see
the CANDIDATES comment for the full account). Tickers remain recollection and are validated by
actually fetching them. Pairs that fail on either side are reported as failures, never dropped
silently.

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

# Candidate mapping: (EXACT COT market name, candidate ticker, label).
#
# Rebuilt 2026-08-26 from a real enumeration of the live universe
# (`list_cot_market_names.py --current-within-days 90 --min-reports 500`), replacing an earlier
# substring-based list written from memory. Two things forced the rewrite:
#
#   1. Substring matching produced a silently WRONG pair. "BRITISH POUND" matched
#      'EURO FX/BRITISH POUND XRATE' -- a cross-rate contract -- which was then paired with
#      6B=F, the actual sterling future. Positioning in one instrument tested against prices of
#      another, and it cleared both gates reporting INCLUDED. Exact names make that class of
#      error impossible, which is why matching is now exact rather than substring.
#   2. CFTC retired a large batch of market names on 2022-02-01. Names written from memory
#      matched the RETIRED variants, wrongly excluding live markets.
#
# Names below are copied verbatim from the real enumeration. Tickers remain recollection and are
# still validated by actually fetching them; failures are reported rather than hidden.
#
# NOT AVAILABLE, confirmed by direct search rather than assumed: the entire Treasury complex
# (10Y/5Y/2Y notes, bonds, Ultra) ends 2022-02-01 with no successor under any Treasury name, so
# the Legacy Futures-Only report cannot supply rates at all. Recovering them needs a different
# CFTC report series and is out of scope here. Consequence recorded in the campaign board: this
# cross-section cannot address the "no rates or fixed income" named deficiency.
CANDIDATES = [
    # Metals
    ("GOLD - COMMODITY EXCHANGE INC.", "GC=F", "Gold"),
    ("SILVER - COMMODITY EXCHANGE INC.", "SI=F", "Silver"),
    ("PLATINUM - NEW YORK MERCANTILE EXCHANGE", "PL=F", "Platinum"),
    ("PALLADIUM - NEW YORK MERCANTILE EXCHANGE", "PA=F", "Palladium"),
    # Energy -- NYMEX WTI retired 2022-02-01; the live ICE WTI contract tracks the same
    # underlying, so pairing it with CL=F is defensible but is a cross-venue link, weaker than
    # same-contract. Flagged rather than hidden.
    ("CRUDE OIL, LIGHT SWEET-WTI - ICE FUTURES EUROPE", "CL=F", "WTI Crude (ICE)"),
    ("HENRY HUB LAST DAY FIN - NEW YORK MERCANTILE EXCHANGE", "NG=F", "Natural Gas"),
    # Grains and oilseeds
    ("CORN - CHICAGO BOARD OF TRADE", "ZC=F", "Corn"),
    ("SOYBEANS - CHICAGO BOARD OF TRADE", "ZS=F", "Soybeans"),
    ("SOYBEAN OIL - CHICAGO BOARD OF TRADE", "ZL=F", "Soybean Oil"),
    ("SOYBEAN MEAL - CHICAGO BOARD OF TRADE", "ZM=F", "Soybean Meal"),
    ("WHEAT-SRW - CHICAGO BOARD OF TRADE", "ZW=F", "Wheat SRW"),
    ("WHEAT-HRW - CHICAGO BOARD OF TRADE", "KE=F", "Wheat HRW"),
    ("OATS - CHICAGO BOARD OF TRADE", "ZO=F", "Oats"),
    ("ROUGH RICE - CHICAGO BOARD OF TRADE", "ZR=F", "Rough Rice"),
    # Livestock
    ("LIVE CATTLE - CHICAGO MERCANTILE EXCHANGE", "LE=F", "Live Cattle"),
    ("FEEDER CATTLE - CHICAGO MERCANTILE EXCHANGE", "GF=F", "Feeder Cattle"),
    ("LEAN HOGS - CHICAGO MERCANTILE EXCHANGE", "HE=F", "Lean Hogs"),
    # Softs
    ("SUGAR NO. 11 - ICE FUTURES U.S.", "SB=F", "Sugar"),
    ("COFFEE C - ICE FUTURES U.S.", "KC=F", "Coffee"),
    ("COCOA - ICE FUTURES U.S.", "CC=F", "Cocoa"),
    ("COTTON NO. 2 - ICE FUTURES U.S.", "CT=F", "Cotton"),
    ("FRZN CONCENTRATED ORANGE JUICE - ICE FUTURES U.S.", "OJ=F", "Orange Juice"),
    # FX
    ("EURO FX - CHICAGO MERCANTILE EXCHANGE", "6E=F", "Euro FX"),
    ("JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE", "6J=F", "Japanese Yen"),
    ("CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE", "6C=F", "Canadian Dollar"),
    ("AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE", "6A=F", "Australian Dollar"),
    ("SWISS FRANC - CHICAGO MERCANTILE EXCHANGE", "6S=F", "Swiss Franc"),
    ("MEXICAN PESO - CHICAGO MERCANTILE EXCHANGE", "6M=F", "Mexican Peso"),
    ("BRAZILIAN REAL - CHICAGO MERCANTILE EXCHANGE", "6L=F", "Brazilian Real"),
    # Equity indices and volatility
    ("S&P 500 Consolidated - CHICAGO MERCANTILE EXCHANGE", "ES=F", "S&P 500"),
    ("NASDAQ-100 Consolidated - CHICAGO MERCANTILE EXCHANGE", "NQ=F", "Nasdaq-100"),
    ("DJIA Consolidated - CHICAGO BOARD OF TRADE", "YM=F", "Dow"),
    ("E-MINI S&P 400 STOCK INDEX - CHICAGO MERCANTILE EXCHANGE", "^SP400", "S&P 400 Midcap"),
    ("NIKKEI STOCK AVERAGE YEN DENOM - CHICAGO MERCANTILE EXCHANGE", "^N225", "Nikkei 225"),
    # VIX futures positioning against the VIX index itself -- correlated but NOT the same
    # instrument (futures carry a term structure the spot index does not). Included because it
    # is directly relevant to the VRP work, flagged because the pairing is approximate.
    ("VIX FUTURES - CBOE FUTURES EXCHANGE", "^VIX", "VIX (approximate pairing)"),
    # Unverified names -- included so the probe reports whether they exist rather than being
    # dropped on an assumption. Sterling and copper did not appear in the live enumeration.
    ("BRITISH POUND STERLING - CHICAGO MERCANTILE EXCHANGE", "6B=F", "British Pound"),
    ("COPPER-GRADE #1 - COMMODITY EXCHANGE INC.", "HG=F", "Copper"),
]


def resolve_cot_market(
    names_df: pd.DataFrame, exact_name: str, dataset_end: pd.Timestamp | None = None
) -> dict | None:
    """Look up one market by its EXACT name and report its span and staleness.

    Matching is exact, not substring, deliberately. The substring version of this probe paired
    'EURO FX/BRITISH POUND XRATE' (a cross-rate contract) with 6B=F (the sterling future) and
    reported it as INCLUDED -- positioning in one instrument tested against prices of another,
    with nothing flagging it. Exact names make that class of error impossible. Substrings also
    silently matched names retired in CFTC's 2022-02-01 renaming. Names in CANDIDATES are now
    copied verbatim from a real enumeration of the live universe.

    dataset_end is the reference staleness is measured against. It defaults to the passed
    frame's own maximum, which is correct when the FULL dataset is passed (as main() does) but
    silently wrong for a pre-filtered frame -- a discontinued market looks current relative to
    itself. Made explicit after that trap caught a test on 2026-08-26."""
    matches = names_df[names_df["Market and Exchange Names"] == exact_name]
    if matches.empty:
        return None
    if dataset_end is None:
        dataset_end = names_df["report_date"].max()
    end = matches["report_date"].max()
    return {
        "market_name": exact_name,
        "reports": len(matches),
        "start": str(matches["report_date"].min().date()),
        "end": str(end.date()),
        "staleness_days": (dataset_end - end).days,
    }


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
    print(f"\n{'label':<22} {'COT reports':>11} {'COT end':>12} {'ticker':>7} {'price rows':>11}  verdict")
    print("-" * 84)
    for exact_name, ticker, label in CANDIDATES:
        cot = resolve_cot_market(df, exact_name, dataset_end)
        row = {"label": label, "cot_market_name": exact_name, "ticker": ticker, "cot": cot}

        if cot is None:
            row["included"] = False
            row["reason"] = "no COT market with that exact name"
            print(f"{label:<22} {'-':>11} {'-':>12} {ticker:>7} {'-':>11}  EXCLUDED (no exact COT name)")
            results.append(row)
            continue

        cot_ok = cot["reports"] >= MIN_COT_REPORTS and cot["staleness_days"] <= MAX_COT_STALENESS_DAYS
        if args.skip_prices:
            row["included"] = cot_ok
            row["reason"] = "" if cot_ok else "COT history too short or stale"
            print(f"{label:<22} {cot['reports']:>11} {cot['end']:>12} {ticker:>7} {'skipped':>11}  "
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
        print(f"{label:<22} {cot['reports']:>11} {cot['end']:>12} {ticker:>7} "
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
