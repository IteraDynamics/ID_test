#!/usr/bin/env python
"""Run HMM regime analysis (research only)."""

import argparse
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from research.regimes.hmm_regime_v1 import build_hmm_features, fit_hmm_regime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", default="artifacts/hmm_regime_v1")
    args = parser.parse_args()

    df = pd.read_csv(args.data)
    df[df.columns[0]] = pd.to_datetime(df[df.columns[0]])
    df = df.set_index(df.columns[0]).sort_index()

    features = build_hmm_features(df)
    result, probs = fit_hmm_regime(features)

    print("\n=== HMM REGIME ANALYSIS ===")
    print(f"States: {len(result.state_labels)}")
    print(f"Converged: {result.converged}")
    print(f"Iterations: {result.iterations}")

    print("\nState Labels:")
    for k, v in result.state_labels.items():
        print(f"  State {k}: {v}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    probs.to_csv(out_dir / "state_probabilities.csv")

    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
