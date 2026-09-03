"""Campaign #58 residualization leakage canary -- proof it can fail, on synthetic data only.

Per the charter's Red Team condition 3: "Residualization must be strictly expanding/walk-forward
... with a pre-registered leakage canary that is proven capable of failing -- inject a synthetic
leak, confirm the census's own detector catches it -- before any real residual is computed."

This script does exactly that, on fabricated data only (no real Itera market data, per CLAUDE.md's
own two-habits lesson: "A check that cannot fail is not evidence" -- the Jump Risk timing audit
passed for months because both sides of its comparison were derived from the same value; this
canary must be shown capable of catching a real leak before it is trusted on real data).

MECHANISM UNDER TEST

"Residualizing against known Itera signals" means: fit a model of Y_t on a known signal K_t
(e.g. momentum, vol, regime state), then hand the residual R_t = Y_t - fitted(K_t) to the
simple-vs-ML horse race. If that first-stage fit is NOT computed strictly causally (expanding
window, using only rows < t to predict row t), the residual can quietly encode information the
model shouldn't have had yet -- exactly the leakage risk this canary exists to catch before any
real residual is trusted.

SYNTHETIC CONSTRUCTION

K_t ~ N(0,1) i.i.d. ("known signal"). Y_t has a REGIME SHIFT in its true dependence on K_t:
  Y_t = 1.0 * K_t + noise_t   for t in the first half
  Y_t = 3.0 * K_t + noise_t   for t in the second half
(noise_t ~ N(0,1) i.i.d., independent of K_t). This is a deliberately simple, fully-known ground
truth -- the true first-stage beta differs by regime, and only the SECOND half's data reveals the
later beta.

TWO RESIDUALIZATION PIPELINES, same data:

  CLEAN (expanding/walk-forward): at each t, fit Y ~ K by OLS using only rows < t (a minimum
  warmup applies). This can only ever see the beta that has already been observed, so first-half
  residuals should be clean noise -- the causal fit correctly tracks the (only) beta it has seen.

  LEAKY (full-sample): fit Y ~ K by OLS ONCE using ALL rows (both regimes), then apply that single
  blended coefficient to every row, including the first half. The blended beta is pulled toward
  the second-regime's higher beta, systematically MISPRICING first-half rows -- their residual
  is no longer pure noise, it retains a K_t-shaped signature, because the "known signal" model
  applied to the first half secretly reflects a beta that had not been observed yet at that point
  in history.

CANARY METRIC: |correlation(residual, K_t)| within the FIRST HALF ONLY (the period whose true beta
the leaky pipeline could not have legitimately known). A canary "capable of failing" is one that:
  (a) reports near-zero first-half residual-vs-K correlation under the CLEAN pipeline (no false
      positive on an honest pipeline), AND
  (b) reports a materially larger, clearly detectable first-half residual-vs-K correlation under
      the LEAKY pipeline (catches the injected leak).

If (a) and (b) both hold, the canary is proven capable of failing (b) while not crying wolf on a
clean pipeline (a), and Campaign #58's real residualization step may adopt the same expanding-
window-only pipeline with this canary as a standing pre-flight check.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

N = 2_000
WARMUP = 50  # minimum rows before an expanding-window fit is attempted
SEED = 20260903
BETA_FIRST_HALF = 1.0
BETA_SECOND_HALF = 3.0
DETECTION_THRESHOLD = 0.05  # a first-half |corr(residual, K)| above this counts as "detected"


def simulate(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    k = rng.normal(size=N)
    noise = rng.normal(size=N)
    half = N // 2
    beta = np.where(np.arange(N) < half, BETA_FIRST_HALF, BETA_SECOND_HALF)
    y = beta * k + noise
    return k, y


def clean_expanding_residuals(k: np.ndarray, y: np.ndarray, warmup: int) -> np.ndarray:
    """Strictly causal: row t's fitted value uses only an OLS fit on rows [0, t)."""
    resid = np.full(N, np.nan)
    for t in range(warmup, N):
        k_train = k[:t]
        y_train = y[:t]
        beta_hat = float(np.dot(k_train, y_train) / np.dot(k_train, k_train))
        resid[t] = y[t] - beta_hat * k[t]
    return resid


def leaky_full_sample_residuals(k: np.ndarray, y: np.ndarray, warmup: int) -> np.ndarray:
    """Leaky: ONE OLS fit using ALL rows (including future ones), applied to every row."""
    beta_hat_full = float(np.dot(k, y) / np.dot(k, k))
    resid = np.full(N, np.nan)
    resid[warmup:] = y[warmup:] - beta_hat_full * k[warmup:]
    return resid


def first_half_abs_corr(resid: np.ndarray, k: np.ndarray, warmup: int) -> float:
    half = N // 2
    valid = slice(warmup, half)
    r = resid[valid]
    kk = k[valid]
    mask = ~np.isnan(r)
    return float(abs(np.corrcoef(r[mask], kk[mask])[0, 1]))


def main() -> int:
    rng = np.random.default_rng(SEED)
    k, y = simulate(rng)

    clean_resid = clean_expanding_residuals(k, y, WARMUP)
    leaky_resid = leaky_full_sample_residuals(k, y, WARMUP)

    clean_corr = first_half_abs_corr(clean_resid, k, WARMUP)
    leaky_corr = first_half_abs_corr(leaky_resid, k, WARMUP)

    clean_detected = clean_corr > DETECTION_THRESHOLD
    leaky_detected = leaky_corr > DETECTION_THRESHOLD

    canary_proven = (not clean_detected) and leaky_detected

    print(f"First-half |corr(residual, K)| -- CLEAN (expanding) pipeline: {clean_corr:.4f} "
          f"({'FALSE POSITIVE -- bad' if clean_detected else 'no false positive -- good'})")
    print(f"First-half |corr(residual, K)| -- LEAKY (full-sample) pipeline: {leaky_corr:.4f} "
          f"({'leak DETECTED -- good' if leaky_detected else 'leak MISSED -- bad'})")
    print(f"\nCanary proven capable of failing (catches the leak, no false positive on clean): "
          f"{'YES' if canary_proven else 'NO'}")

    report = {
        "audit": "campaign58_residualization_leakage_canary_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "note": "Synthetic data only -- no real Itera market data used. Proves the canary can "
                "fail (per Red Team condition 3) before any real residualization is trusted.",
        "n_rows": N,
        "warmup_rows": WARMUP,
        "true_beta_first_half": BETA_FIRST_HALF,
        "true_beta_second_half": BETA_SECOND_HALF,
        "detection_threshold_abs_corr": DETECTION_THRESHOLD,
        "seed": SEED,
        "clean_pipeline_first_half_abs_corr": clean_corr,
        "leaky_pipeline_first_half_abs_corr": leaky_corr,
        "clean_pipeline_false_positive": clean_detected,
        "leaky_pipeline_leak_detected": leaky_detected,
        "canary_proven_capable_of_failing": canary_proven,
    }
    out_dir = Path("artifacts/campaign58_leakage_canary_proof")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"canary_proof_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\nArtifact: {out_path}")

    return 0 if canary_proven else 1


if __name__ == "__main__":
    raise SystemExit(main())
