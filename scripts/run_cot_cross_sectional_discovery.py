"""Cross-sectional COT positioning test across 35 futures markets -- Campaign #55's redesign.

Campaign #55 (COT positioning -> SPY/QQQ) closed 2026-08-26 UNDERPOWERED, not null: its one
surviving combination collapsed from p=0.0004 to p=0.51 once the overlapping-window effective
sample size was respected. Amendment 1's own remedy was named at closure -- go cross-sectional,
because "a cross-section of N instruments buys power that no amount of history buys."

DESIGN, and why it is structured this way
-----------------------------------------
The failure mode to avoid is the one that killed #55: pooling market-weeks would multiply
observations that are not independent, reinflating exactly the autocorrelation problem that
correction exposed. So each market contributes EXACTLY ONE number -- its own Spearman
correlation between positioning percentile and forward return, estimated over its own history.
Within-market overlap is absorbed into that single estimate rather than inflating a sample size.
The primary test then asks whether those per-market numbers are centered below zero, which is a
cross-market question with genuinely (partially) independent units.

"Partially" is doing real work there and is measured, not assumed: grains co-move, metals
co-move, the FX pairs share a dollar factor. Effective breadth is estimated from the realized
cross-market correlation and reported alongside the raw count, because treating 35 correlated
markets as 35 independent tests would overstate this design's own rigor.

PRE-REGISTERED before any result was observed (this section is the specification):
  - primary horizon: 12 weeks (the middle of #55's grid; 4w and 26w are secondary, reported but
    not the basis of any claim);
  - primary statistic: Spearman rank correlation (#55 established it as the more honest one,
    being robust to the magnitude outliers that inflate Pearson);
  - primary test: is the distribution of per-market correlations centered below zero?
    Reported as both a t-test and a Wilcoxon signed-rank test, the latter because 35 values need
    not be normal;
  - direction: NEGATIVE correlation is the contrarian hypothesis (crowded long -> lower forward
    return). A positive result is a failed hypothesis, not a discovery with the sign flipped;
  - multiplicity: Benjamini-Hochberg FDR at q=0.10 across discovery markets;
  - holdout: HOLDOUT_FRACTION of markets, assigned by SPLIT_SEED before any analysis, never
    reported by the default (discovery) stage.

STAGING. The default stage reports discovery markets ONLY. The holdout requires an explicit
--stage confirmation, because a holdout that can be glanced at during discovery is not a
holdout, and Amendment 2 requires the strict standard to sit on untouched data. Run confirmation
once, after the discovery result and decision rule are recorded.

KNOWN LIMITATIONS, stated up front:
  - Continuous futures series carry ROLL GAPS -- price jumps at contract roll that are not real
    returns. This adds noise, which biases toward finding nothing, so it is conservative for a
    discovery test rather than flattering. It is not corrected here.
  - Markets have different history lengths (647 to 1931 reports), so per-market estimates carry
    different precision and span different macro regimes. Treated as noise, not bias.
  - Two pairings are approximate, flagged in the probe: ICE WTI positioning against NYMEX CL
    prices, and VIX futures positioning against the spot VIX index.
  - The Legacy report carries no Treasuries after 2022-02-01, so this cross-section cannot
    address the "no rates or fixed income" deficiency. Confirmed by direct search, not assumed.

Observation/analysis only. No trading signal, no economic claim, no frozen specification.
"""

from __future__ import annotations

# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)


import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parent.parent

from scripts.analyze_cot_positioning_signal import MIN_HISTORY_FOR_PERCENTILE, ROLLING_PERCENTILE_WINDOW_WEEKS, forward_return, load_cot_market, load_price, rolling_percentile

PRIMARY_HORIZON_WEEKS = 12
SECONDARY_HORIZONS_WEEKS = (4, 26)
HOLDOUT_FRACTION = 0.40
SPLIT_SEED = 20260826  # fixed to this session's date; arbitrary but recorded and never re-rolled
FDR_Q = 0.10
MIN_OBSERVATIONS_PER_MARKET = 100


def assign_split(labels: list[str]) -> tuple[list[str], list[str]]:
    """Deterministic discovery/holdout split, fixed by SPLIT_SEED and computed from the SORTED
    label list so it cannot drift with dict or file ordering. Assigned before any statistic is
    computed, so holdout membership cannot be influenced by results."""
    ordered = sorted(labels)
    rng = np.random.RandomState(SPLIT_SEED)
    shuffled = [str(x) for x in rng.permutation(ordered)]  # str() -- permutation yields np.str_
    n_holdout = int(round(len(ordered) * HOLDOUT_FRACTION))
    holdout = sorted(shuffled[:n_holdout])
    discovery = sorted(shuffled[n_holdout:])
    return discovery, holdout


def benjamini_hochberg(p_values: list[float], q: float) -> list[bool]:
    """BH step-up procedure. Returns a rejection mask aligned with the input order."""
    n = len(p_values)
    if n == 0:
        return []
    order = np.argsort(p_values)
    sorted_p = np.array(p_values)[order]
    thresholds = q * (np.arange(1, n + 1) / n)
    passing = sorted_p <= thresholds
    k = np.max(np.where(passing)[0]) + 1 if passing.any() else 0
    rejected_sorted = np.zeros(n, dtype=bool)
    rejected_sorted[:k] = True
    out = np.zeros(n, dtype=bool)
    out[order] = rejected_sorted
    return list(out)


def analyze_market(cot_csv: str, market_name: str, price_csv: str, horizons: tuple[int, ...]) -> dict | None:
    """One market -> one correlation per horizon, plus the forward-return series needed later to
    measure cross-market dependence. Returns None if the market cannot be evaluated at all."""
    try:
        cot = load_cot_market(cot_csv, market_name)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"COT load failed: {type(exc).__name__}: {exc}"}
    if len(cot) < MIN_HISTORY_FOR_PERCENTILE + MIN_OBSERVATIONS_PER_MARKET:
        return {"error": f"only {len(cot)} COT reports"}

    cot["percentile"] = rolling_percentile(
        cot["noncomm_net_pct_oi"], ROLLING_PERCENTILE_WINDOW_WEEKS, MIN_HISTORY_FOR_PERCENTILE
    )
    cot = cot.dropna(subset=["percentile"]).reset_index(drop=True)

    try:
        price = load_price(price_csv)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"price load failed: {type(exc).__name__}: {exc}"}

    out: dict = {"cot_reports": int(len(cot)),
                 "cot_start": str(cot["report_date"].min().date()),
                 "cot_end": str(cot["report_date"].max().date())}
    for weeks in horizons:
        col = f"fwd_{weeks}w"
        cot[col] = cot["usable_date"].apply(lambda d: forward_return(price, d, weeks))
        valid = cot.dropna(subset=[col])
        if len(valid) < MIN_OBSERVATIONS_PER_MARKET:
            out[f"spearman_{weeks}w"] = None
            out[f"p_{weeks}w"] = None
            out[f"n_{weeks}w"] = int(len(valid))
            continue
        rho, p = stats.spearmanr(valid["percentile"], valid[col])
        out[f"spearman_{weeks}w"] = float(rho)
        out[f"p_{weeks}w"] = float(p)
        out[f"n_{weeks}w"] = int(len(valid))
        if weeks == PRIMARY_HORIZON_WEEKS:
            out["_fwd_series"] = pd.Series(valid[col].values, index=valid["usable_date"].values)
    return out


def effective_breadth(series_by_label: dict[str, pd.Series]) -> tuple[float, float, int]:
    """Estimate how many INDEPENDENT markets 35 correlated markets are worth.

    Uses the mean pairwise correlation of the per-market forward-return series on their shared
    dates, via the standard effective-sample-size deflation N_eff = N / (1 + (N-1) * rho_bar).
    Reported because claiming 35 independent tests across grains that co-move, metals that
    co-move, and FX pairs sharing a dollar factor would overstate this design's own rigor."""
    labels = [k for k, v in series_by_label.items() if v is not None and len(v) > 20]
    n = len(labels)
    if n < 2:
        return float("nan"), float("nan"), n
    frame = pd.DataFrame({k: series_by_label[k] for k in labels})
    corr = frame.corr(min_periods=20)
    vals = corr.values[np.triu_indices_from(corr.values, k=1)]
    vals = vals[~np.isnan(vals)]
    if len(vals) == 0:
        return float("nan"), float("nan"), n
    rho_bar = float(np.mean(vals))
    denom = 1.0 + (n - 1) * rho_bar
    n_eff = n / denom if denom > 0 else float(n)
    # Cap at the raw count. When mean pairwise correlation comes out slightly NEGATIVE (possible
    # by chance, and seen on synthetic data), the formula returns more "independent" markets than
    # there are markets -- arithmetically what it says, but nonsense as a statement about
    # breadth. Deflation is the only direction this quantity can honestly move.
    n_eff = min(float(n_eff), float(n))
    return rho_bar, n_eff, n


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--cot-csv", default="data/cot_legacy_futures_only_1986_present.csv")
    p.add_argument("--probe-json", default="artifacts/cot_cross_sectional_universe_probe.json")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--stage", choices=("discovery", "confirmation"), default="discovery",
                   help="discovery reports the discovery markets only. confirmation opens the "
                        "untouched holdout -- run it once, after the discovery result and "
                        "decision rule are recorded.")
    p.add_argument("--out-dir", default="artifacts")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    probe = json.loads(Path(args.probe_json).read_text(encoding="utf-8"))
    included = [r for r in probe.get("results", []) if r.get("included")]
    if not included:
        print("No included markets in the probe artifact.")
        return 1

    labels = [r["label"] for r in included]
    discovery, holdout = assign_split(labels)
    horizons = (PRIMARY_HORIZON_WEEKS, *SECONDARY_HORIZONS_WEEKS)

    print(f"{len(labels)} markets from {args.probe_json}")
    print(f"Split (seed {SPLIT_SEED}, fixed before any statistic): "
          f"{len(discovery)} discovery / {len(holdout)} holdout")
    print(f"Stage: {args.stage.upper()}")
    if args.stage == "discovery":
        print("Holdout markets are NOT evaluated or named in this stage.")
    else:
        print("\n*** CONFIRMATION STAGE -- this opens the untouched holdout. It is meaningful")
        print("*** exactly once. If the discovery result and decision rule are not already")
        print("*** recorded, stop and do that first.")
    active = set(discovery) if args.stage == "discovery" else set(holdout)

    print(f"\nPre-registered: primary horizon {PRIMARY_HORIZON_WEEKS}w, primary statistic "
          f"Spearman, FDR q={FDR_Q}, contrarian direction = NEGATIVE correlation.")

    rows, fwd_series, failures = [], {}, []
    for r in included:
        if r["label"] not in active:
            continue
        market_name = r["cot_market_name"]
        price_csv = str(Path(args.data_dir) / f"{r['ticker'].upper()}_1D.csv")
        res = analyze_market(args.cot_csv, market_name, price_csv, horizons)
        if res is None or "error" in res:
            failures.append((r["label"], res.get("error") if res else "unknown"))
            continue
        fwd_series[r["label"]] = res.pop("_fwd_series", None)
        res["label"] = r["label"]
        res["ticker"] = r["ticker"]
        rows.append(res)

    if failures:
        print(f"\n{len(failures)} market(s) could not be evaluated:")
        for label, err in failures:
            print(f"  {label}: {err}")

    df = pd.DataFrame(rows)
    primary_col = f"spearman_{PRIMARY_HORIZON_WEEKS}w"
    usable = df.dropna(subset=[primary_col]).reset_index(drop=True)
    if len(usable) < 5:
        print(f"\nOnly {len(usable)} markets produced a usable primary estimate. Too few.")
        return 1

    print(f"\n{'='*78}")
    print(f"PER-MARKET, primary horizon {PRIMARY_HORIZON_WEEKS}w (Spearman; negative = contrarian)")
    print(f"{'='*78}")
    print(f"{'market':<24} {'n':>5} {'spearman':>10} {'p':>9}")
    print("-" * 78)
    for _, r in usable.sort_values(primary_col).iterrows():
        print(f"{r['label']:<24} {int(r[f'n_{PRIMARY_HORIZON_WEEKS}w']):>5} "
              f"{r[primary_col]:>+10.4f} {r[f'p_{PRIMARY_HORIZON_WEEKS}w']:>9.5f}")

    rhos = usable[primary_col].to_numpy()
    print(f"\n{'='*78}")
    print("PRIMARY TEST: are per-market correlations centered below zero?")
    print(f"{'='*78}")
    t_stat, t_p = stats.ttest_1samp(rhos, 0.0)
    try:
        w_stat, w_p = stats.wilcoxon(rhos)
    except ValueError:
        w_stat, w_p = float("nan"), float("nan")
    print(f"markets: {len(rhos)}   mean rho: {rhos.mean():+.4f}   median: {np.median(rhos):+.4f}")
    print(f"negative in {(rhos < 0).sum()}/{len(rhos)} markets")
    print(f"t-test:            t={t_stat:+.3f}  two-tailed p={t_p:.5f}")
    print(f"Wilcoxon signed-rank:          two-tailed p={w_p:.5f}")

    rho_bar, n_eff, n_used = effective_breadth(fwd_series)
    print(f"\nEFFECTIVE BREADTH (measured, not assumed):")
    print(f"  mean pairwise forward-return correlation across markets: {rho_bar:+.4f}")
    print(f"  {n_used} markets are worth roughly {n_eff:.1f} independent ones")
    if not np.isnan(n_eff) and n_eff < len(rhos) * 0.5:
        print("  NOTE: effective breadth is well below the raw count -- the markets co-move")
        print("  substantially, so p-values above are optimistic and the honest reading is that")
        print("  this design has less independent evidence than 'N markets' suggests.")

    print(f"\n{'='*78}")
    print(f"MULTIPLICITY: Benjamini-Hochberg FDR at q={FDR_Q}")
    print(f"{'='*78}")
    p_col = f"p_{PRIMARY_HORIZON_WEEKS}w"
    rejected = benjamini_hochberg(usable[p_col].tolist(), FDR_Q)
    survivors = usable[pd.Series(rejected, index=usable.index)]
    print(f"{len(survivors)}/{len(usable)} markets survive FDR")
    if len(survivors):
        for _, r in survivors.sort_values(primary_col).iterrows():
            direction = "contrarian" if r[primary_col] < 0 else "WRONG SIGN (momentum)"
            print(f"  {r['label']:<24} rho={r[primary_col]:+.4f}  p={r[p_col]:.5f}  {direction}")
    else:
        print("  none")

    print(f"\n{'='*78}")
    print("SECONDARY HORIZONS (reported, not a basis for any claim)")
    print(f"{'='*78}")
    for weeks in SECONDARY_HORIZONS_WEEKS:
        col = f"spearman_{weeks}w"
        sub = df.dropna(subset=[col])
        if len(sub) < 5:
            continue
        v = sub[col].to_numpy()
        _, p_sec = stats.ttest_1samp(v, 0.0)
        print(f"  {weeks:>2}w: markets={len(v)}  mean rho={v.mean():+.4f}  "
              f"negative in {(v < 0).sum()}/{len(v)}  t-test p={p_sec:.5f}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"cot_cross_sectional_{args.stage}_{stamp}.json"
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": args.stage,
        "split_seed": SPLIT_SEED,
        "holdout_fraction": HOLDOUT_FRACTION,
        "primary_horizon_weeks": PRIMARY_HORIZON_WEEKS,
        "fdr_q": FDR_Q,
        "markets_evaluated": int(len(usable)),
        "mean_rho": float(rhos.mean()),
        "median_rho": float(np.median(rhos)),
        "negative_count": int((rhos < 0).sum()),
        "t_p": float(t_p),
        "wilcoxon_p": float(w_p),
        "mean_pairwise_correlation": None if np.isnan(rho_bar) else rho_bar,
        "effective_markets": None if np.isnan(n_eff) else n_eff,
        "fdr_survivors": survivors["label"].tolist(),
        "per_market": usable.drop(columns=[c for c in usable.columns if c.startswith("_")]).to_dict("records"),
        "failures": failures,
    }
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(f"\nWrote {out_path}")

    print("\nDiscovery-stage observation only. Roll gaps in continuous futures are uncorrected")
    print("(noise, biasing toward the null). No trading signal, no economic claim, nothing frozen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
