# Core v1 Episode vs Event-Family Taxonomy

## Scope

Deterministic, replay-safe, research-only, and observation-only comparison.
No runtime, model-training, threshold, order, NAV, exposure, or dashboard behavior changed.

## Governed counts

- Episodes: 122
- Event families: 14
- Deterministic digest: `0c837e746832c64b4a163ab1e968fccccf8ac338c11ce546fd08fa12278dd3b4`

## Counting interpretation

Episode share counts every governed rolling-window episode.
Event-family presence counts each label at most once per family.
Event-family homogeneous share counts only families containing exactly one label.
Mixed families remain mixed; no dominant label is inferred.

## Family composition

- Intrinsic-subtype homogeneous families: 8
- Intrinsic-subtype mixed families: 6
- Recovery-outcome homogeneous families: 9
- Recovery-outcome mixed families: 5

## Intrinsic subtype

- `MAJOR_COLLAPSE__CONCENTRATED_SHIFT__VOLATILITY_NEUTRAL`: episodes 1 (0.008197); family presence 1 (0.071429); homogeneous families 0 (0.000000); amplification 1.000000
- `MAJOR_COLLAPSE__LOW_DISPLACEMENT_COLLAPSE__VOLATILITY_NEUTRAL`: episodes 9 (0.073770); family presence 3 (0.214286); homogeneous families 0 (0.000000); amplification 3.000000
- `MODERATE_COLLAPSE__BROAD_SHIFT__VOLATILITY_EXPANSION`: episodes 2 (0.016393); family presence 1 (0.071429); homogeneous families 0 (0.000000); amplification 2.000000
- `MODERATE_COLLAPSE__CONCENTRATED_SHIFT__VOLATILITY_NEUTRAL`: episodes 1 (0.008197); family presence 1 (0.071429); homogeneous families 0 (0.000000); amplification 1.000000
- `MODERATE_COLLAPSE__LOW_DISPLACEMENT_COLLAPSE__VOLATILITY_EXPANSION`: episodes 1 (0.008197); family presence 1 (0.071429); homogeneous families 0 (0.000000); amplification 1.000000
- `MODERATE_COLLAPSE__LOW_DISPLACEMENT_COLLAPSE__VOLATILITY_NEUTRAL`: episodes 14 (0.114754); family presence 9 (0.642857); homogeneous families 3 (0.214286); amplification 1.555556
- `SEVERE_COLLAPSE__BROAD_SHIFT__VOLATILITY_EXPANSION`: episodes 4 (0.032787); family presence 1 (0.071429); homogeneous families 0 (0.000000); amplification 4.000000
- `SEVERE_COLLAPSE__CONCENTRATED_SHIFT__VOLATILITY_EXPANSION`: episodes 1 (0.008197); family presence 1 (0.071429); homogeneous families 0 (0.000000); amplification 1.000000
- `SEVERE_COLLAPSE__CONCENTRATED_SHIFT__VOLATILITY_NEUTRAL`: episodes 2 (0.016393); family presence 2 (0.142857); homogeneous families 0 (0.000000); amplification 1.000000
- `SEVERE_COLLAPSE__LOW_DISPLACEMENT_COLLAPSE__VOLATILITY_NEUTRAL`: episodes 87 (0.713115); family presence 9 (0.642857); homogeneous families 5 (0.357143); amplification 9.666667

## Recovery outcome

- `DELAYED_RECOVERY`: episodes 45 (0.368852); family presence 6 (0.428571); homogeneous families 1 (0.071429); amplification 7.500000
- `PERSISTENT_COLLAPSE`: episodes 48 (0.393443); family presence 4 (0.285714); homogeneous families 2 (0.142857); amplification 12.000000
- `RAPID_RECOVERY`: episodes 29 (0.237705); family presence 10 (0.714286); homogeneous families 6 (0.428571); amplification 2.900000

## Limits

These are descriptive counts, not predictive estimates or statistical-independence claims.
Only 14 governed event families are available, so the artifact does not assign confidence labels, significance, or alpha conclusions.
