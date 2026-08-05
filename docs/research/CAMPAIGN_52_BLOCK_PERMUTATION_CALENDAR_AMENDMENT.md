# Campaign #52 Block-Permutation Calendar Compatibility Amendment

## Status

Authorized methodological correction for Campaign #52 development-only controls. This amendment was required after the governed development runner failed closed before replay with `UNEQUAL_COMPLETE_BLOCK_ROWS:2020:BTC_1H_hedge`.

No governed control was replayed, no metric or inference was calculated, and no development conclusion was produced before this amendment.

## Reason

The frozen 28-day wall-clock block design assumed that every complete block would contain an identical native-row count for every sleeve. Governed development targets disproved that assumption. Missing bars and calendar irregularities can produce different row counts across otherwise complete 28-day intervals.

Silently truncating, padding, interpolating, filling, or duplicating observations would change the target process and is prohibited.

## Amended deterministic rule

For each development fold independently:

1. retain the same fold origin and consecutive 28-day wall-clock partition;
2. retain the incomplete terminal interval in its original terminal position;
3. for every complete block, calculate a calendar signature consisting of the ordered native-row counts across the full frozen sleeve set;
4. group complete blocks only when their full sleeve-count signatures are identical;
5. derive a deterministic group seed from the frozen permutation seed plus fold and signature identity;
6. apply seeded Fisher-Yates only within each compatible group;
7. use the same destination-to-source block mapping for every sleeve;
8. leave singleton groups fixed;
9. preserve native row order within every moved block;
10. require exact source/destination row-count equality for every sleeve and mapped block;
11. preserve every destination identifier, timestamp, sequence number, and metadata field while replacing only signed target exposure;
12. do not truncate, pad, interpolate, resample, fill, duplicate, or cross folds or stages.

## Manifest requirements

For each fold and permutation control, record:

- complete-block count;
- terminal-day count;
- ordered sleeve set;
- each block's full calendar signature;
- compatible groups and their deterministic seeds;
- destination-to-source block mapping;
- movable-block count;
- fixed-block count;
- per-sleeve source/destination equality checks.

## Interpretation

This amendment preserves the intended chronology-destruction control wherever the observed calendar permits an exact replay-safe mapping. Irregular singleton signatures remain fixed rather than being altered by an unverifiable mapping.

The control family remains exactly sixteen deterministic 28-day block permutations. Seeds, development window, endpoints, bootstrap, multiplicity, decision rules, execution semantics, and all Core behavior remain unchanged.
