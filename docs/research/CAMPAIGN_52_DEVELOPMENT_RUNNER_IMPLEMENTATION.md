# Campaign #52 Governed Development Runner Implementation

## Status

The user's explicit `Proceed` authorized implementation of the complete development-only hypothesis runner and one compact integration test gate.

Implementation commits:

- governed development hypothesis runner: `4443496290bdde5762edd8fe0deaf7a523be0c41`
- importer/runner integration tests: `06a750a051883f85df579aa662e0a563be389b48`

## Runner boundary

The runner:

- verifies the six frozen source hashes;
- requires the governed equivalence PASS manifest and identical pass-1/pass-2 artifact hash maps;
- imports exactly 27 development target streams from 2020-2022;
- structurally rejects validation target paths;
- verifies every imported target file against its recorded SHA-256;
- never invokes a canonical strategy;
- constructs exactly the frozen static, three lagged, and sixteen 28-day block-permutation controls;
- preserves transformed signed target exposure exactly while normalizing non-economic action metadata to replay-safe `HOLD` records;
- replays canonical plus all 20 controls through unchanged execution mechanics;
- calculates the frozen primary and secondary development metrics;
- performs 10,000-replication paired 21-day moving-block inference for each control;
- applies Holm adjustment across exactly 20 controls;
- applies the frozen development support decision;
- repeats the complete process independently twice and requires identical artifact maps and decisions;
- writes to a temporary root and atomically promotes only after completion.

The runner does not open validation target files, produce validation outcomes, alter Core behavior, or modify runtime, strategy, weights, thresholds, costs, orders, NAV mechanics, or exposure mechanics.

## Focused gate

Before the governed development run, execute:

`python -m pytest tests/test_campaign52_development.py tests/test_campaign52_development_runner.py -q`

This is the final focused implementation gate. If it passes, the next command is the actual Campaign #52 development hypothesis test:

`python -m scripts.run_campaign52_development`

No additional procedure or micro-gate is planned between those commands.
