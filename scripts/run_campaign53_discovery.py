"""Campaign #53 real discovery-stage computation -- FDR-controlled ranking of the funding-carry
candidates against real acquired Deribit data.

Authorized 2026-08-24 (docs/ITERA_CAMPAIGN_BOARD.md correction): the operator explicitly
authorized real predictor/outcome computation for Campaign #53's discovery/confirmation decision,
after the power analysis (scripts/run_campaign53_power_analysis.py) cleared Amendment 1's 50%
floor at 56.0% average power on the corrected {24h,72h}-window, top-2-confirmation family
(charter §4, "Corrected family re-run, 2026-08-24").

This computes the DISCOVERY half of the charter's frozen §3d decision rule for real:

- the real observed correlation between each candidate and its forward net carry target (no
  synthetic effect injection -- this is the actual data, not a power simulation);
- an empirical p-value for each, measured against a block-bootstrapped null reference
  distribution built with the same, already-tested machinery the power analysis validated
  (build_null_reference, imported directly rather than reimplemented);
- Benjamini-Hochberg FDR control at q=0.10 across the three-hypothesis family (§3c's
  2026-08-21 window-narrowing correction -- funding level and funding persistence, each at
  {24h, 72h} -- AND its 2026-08-24 exclusion of funding_level_24h, EXCLUDED_HYPOTHESES,
  imported directly rather than reimplemented);
- a top-2 shortlist by |correlation| among FDR-discovered hypotheses (§3d's 2026-08-21
  confirmation-k correction).

**2026-08-24 correction, found by this script's own first real run:** the initial four-hypothesis
version of this script put `funding_level_24h` (r=0.7075) at the top of the shortlist. That
result is a near-tautology, not a discovery: funding_level's 24h window, 24h target horizon, and
the 24h daily rebalance interval are all numerically identical, so a candidate's trailing-mean
window at day t+1 is EXACTLY the target's forward-sum window at day t -- corr(candidate,target)
is pinned to candidate's own lag-1 autocorrelation regardless of any real relationship (proven
under synthetic noise and AR(1) input independent of this script, real-data r matched candidate's
own real lag-1 autocorrelation to 4 decimals). funding_level_24h is now excluded
(EXCLUDED_HYPOTHESES in the power analysis module) rather than silently left in a shortlist slot
a real candidate should occupy.

What this script deliberately does NOT do:

- It does not compute confirmation. Per charter §3a-iii, confirmation is against CDE's
  live-forward-accumulated funding rate -- a holdout that is not backfillable. The logging script
  (scripts/log_cde_live_funding_rate.py) was written 2026-08-21 but not actually scheduled until
  2026-08-24 (root crontab, hourly) -- the holdout's true accumulation start is 2026-08-24, not
  the 2026-08-21 authorship date. A discovery result from this script is not a trading
  decision, authorizes no economic or runtime action, and must not be treated as validated until
  it separately clears that untouched holdout.
- It does not implement §3d's "rank candidates cross-sectionally at each rebalance by expected
  net carry" trading-construction language -- that describes how a live position would be sized
  and chosen day to day, which is execution-adjacent and belongs to confirmation/execution, not
  to the discovery statistical test. Building that now, before any holdout exists to confirm
  against, would drift toward producing a trading signal, which remains explicitly unauthorized.
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
from typing import Any

import numpy as np
import pandas as pd


from scripts.run_campaign53_power_analysis import (
    CONFIRMATION_TOP_K,
    EXCLUDED_HYPOTHESES,
    FDR_Q,
    REBALANCE,
    WINDOWS_HOURS,
    benjamini_hochberg,
    build_hypothesis_frame,
    build_null_reference,
    empirical_pvalue,
    funding_level,
    funding_persistence,
    hourly_reindex,
    lag1_autocorr,
    load_funding_series,
)

BLOCK_DAYS_DEFAULT = 30
N_NULL_DEFAULT = 300


def compute_discovery(
    hypotheses: list[dict[str, Any]],
    block_size: int,
    n_null: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    """Real (non-simulated) discovery step on real data: observed correlation, empirical
    p-value against a block-bootstrapped null, BH FDR at q=0.10, and a top-CONFIRMATION_TOP_K
    shortlist by |correlation| among FDR-discovered hypotheses only."""
    per_hyp: list[dict[str, Any]] = []
    for hyp in hypotheses:
        candidate = hyp["candidate"]
        target = hyp["target"]
        observed_r = float(np.corrcoef(candidate, target)[0, 1])
        null_reference = build_null_reference(candidate, target, block_size, n_null, rng)
        pvalue = empirical_pvalue(abs(observed_r), null_reference)
        per_hyp.append({
            "name": hyp["name"],
            "observed_correlation": observed_r,
            "empirical_pvalue": pvalue,
            "null_reference_median_abs_r": float(np.median(null_reference)),
        })

    pvals = np.array([h["empirical_pvalue"] for h in per_hyp])
    rejected = benjamini_hochberg(pvals, FDR_Q)
    for h, r in zip(per_hyp, rejected):
        h["fdr_discovered"] = bool(r)

    discovered_idx = [i for i, h in enumerate(per_hyp) if h["fdr_discovered"]]
    ranked = sorted(discovered_idx, key=lambda i: -abs(per_hyp[i]["observed_correlation"]))
    shortlist_idx = set(ranked[: CONFIRMATION_TOP_K])
    for i, h in enumerate(per_hyp):
        h["confirmation_shortlist"] = i in shortlist_idx

    return {
        "hypotheses": per_hyp,
        "fdr_q": FDR_Q,
        "confirmation_top_k": CONFIRMATION_TOP_K,
        "n_discovered": len(discovered_idx),
        "n_shortlisted": len(shortlist_idx),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--btc-funding-csv", required=True)
    p.add_argument("--eth-funding-csv", required=True)
    p.add_argument("--n-null", type=int, default=N_NULL_DEFAULT, help="Null reference resamples per hypothesis.")
    p.add_argument("--block-days", type=int, default=BLOCK_DAYS_DEFAULT, help="Block bootstrap block size, in rebalance periods (days).")
    p.add_argument("--seed", type=int, default=20260824)
    p.add_argument("--out-dir", default="artifacts/campaign53_discovery")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rng = np.random.default_rng(args.seed)

    print("Loading and pooling BTC/ETH funding series...")
    btc = hourly_reindex(load_funding_series(args.btc_funding_csv))
    eth = hourly_reindex(load_funding_series(args.eth_funding_csv))

    candidate_fns = {"funding_level": funding_level, "funding_persistence": funding_persistence}
    hypotheses: list[dict[str, Any]] = []
    for cand_name, cand_fn in candidate_fns.items():
        for window in WINDOWS_HOURS:
            if (cand_name, window) in EXCLUDED_HYPOTHESES:
                print(f"  {cand_name}_{window}h: excluded -- see EXCLUDED_HYPOTHESES "
                      f"(near-tautological candidate/target identity, 2026-08-24)")
                continue
            btc_frame = build_hypothesis_frame(btc, cand_fn, window, REBALANCE)
            eth_frame = build_hypothesis_frame(eth, cand_fn, window, REBALANCE)
            pooled = pd.concat([btc_frame, eth_frame], ignore_index=True)
            name = f"{cand_name}_{window}h"
            print(f"  {name}: {len(pooled)} pooled (candidate, target) observations")
            hypotheses.append({
                "name": name,
                "candidate": pooled["candidate"].to_numpy(),
                "target": pooled["target"].to_numpy(),
            })

    print("\nBlock-width sanity check (lag-1 autocorrelation of each pooled series):")
    for hyp in hypotheses:
        print(f"  {hyp['name']}: candidate lag-1 r={lag1_autocorr(hyp['candidate']):.4f}, "
              f"target lag-1 r={lag1_autocorr(hyp['target']):.4f}")

    block_size = min(args.block_days, min(len(h["candidate"]) for h in hypotheses) - 1)
    print(f"\nRunning real discovery (block size {block_size}, {args.n_null} null resamples per hypothesis)...")
    discovery = compute_discovery(hypotheses, block_size, args.n_null, rng)

    print(f"\n{'hypothesis':<28}{'r':>10}{'p-value':>12}{'FDR disc.':>12}{'shortlist':>12}")
    for h in discovery["hypotheses"]:
        print(f"{h['name']:<28}{h['observed_correlation']:>10.4f}{h['empirical_pvalue']:>12.4f}"
              f"{str(h['fdr_discovered']):>12}{str(h['confirmation_shortlist']):>12}")

    print(f"\n{discovery['n_discovered']} of {len(hypotheses)} hypotheses cleared FDR discovery "
          f"(q={FDR_Q}); {discovery['n_shortlisted']} shortlisted for confirmation "
          f"(top-{CONFIRMATION_TOP_K}).")

    report = {
        "audit": "campaign53_discovery_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "caveats": [
            "DISCOVERY ONLY. No confirmation was run or is possible yet: the untouched CDE "
            "live-forward holdout (charter §3a-iii) is not backfillable, and accumulation only "
            "actually started 2026-08-24 when the logging script was scheduled via cron -- it "
            "was written 2026-08-21 but not running until then.",
            "A shortlisted hypothesis here is not a validated finding and is not a trading "
            "signal -- it is a candidate that has cleared FDR discovery and is eligible for "
            "confirmation once the holdout has enough accumulated data to test against.",
            "Effect-size grid used for the earlier power analysis was a reasoned estimate, not "
            "literature-cited; this discovery step does not depend on that grid (it measures the "
            "real correlation directly), but the campaign's overall evidentiary standard still "
            "carries that caveat.",
            "funding_level_24h is excluded from this family (EXCLUDED_HYPOTHESES, 2026-08-24): "
            "its 24h candidate window, 24h target horizon, and 24h daily rebalance interval are "
            "numerically identical, making corr(candidate,target) a near-tautological restatement "
            "of the candidate's own lag-1 autocorrelation rather than a distinct predictive "
            "relationship. Proven independent of this script's data; see charter §3c.",
        ],
        "block_size_days": block_size,
        "discovery": discovery,
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"discovery_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\nArtifact: {out_path}")
    print("\nReminder: this is DISCOVERY ONLY. No candidate here is confirmed, validated, or a")
    print("trading signal until it clears the untouched CDE live-forward holdout separately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
