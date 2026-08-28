# Campaign #52 Calendar Amendment and Runtime Optimization Record

## Trigger

The authorized governed development run failed closed during transformation with:

`UNEQUAL_COMPLETE_BLOCK_ROWS:2020:BTC_1H_hedge`

The failure occurred before replay, performance metrics, bootstrap inference, multiplicity adjustment, or a development decision.

## Methodological correction

Commit `969cb63032822b57208c3bbcca173c45b0cc6828` authorizes calendar-compatible stratification of complete 28-day blocks by their ordered full-sleeve row-count signature.

Implementation commit `752242281e1d079b8821a7510cb066e78e3ac4a9`:

- preserves the original fold origins, 28-day wall-clock partition, terminal remainder, 16 controls, and deterministic control seeds;
- groups complete blocks only when all sleeve row counts match;
- derives deterministic group seeds from control, fold, and signature identity;
- applies the same destination-to-source mapping across sleeves;
- leaves singleton signature groups fixed;
- prohibits truncation, padding, interpolation, filling, duplication, or cross-fold movement;
- records signatures, groups, mappings, movable/fixed counts, and per-sleeve equality checks;
- verifies total row-count preservation.

Focused regression commit `addfc084d5408b837af32ccb47d9d96f2acb9f68` covers irregular calendars, fixed incompatible blocks, shared sleeve mappings, terminal preservation, deterministic output, and timezone-aware input handling.

## Runtime optimization

Runner commit `abb3262f008d7d0038352cfa8b2bb4562125de6d`:

- retains the two independent passes and runs them concurrently by default;
- prepares each of the 27 fold/sleeve market-data, state, execution-config, and cash-yield inputs once per pass;
- reuses those immutable inputs across canonical plus all 20 controls;
- retains full sleeve-level artifacts in both passes for deterministic identity;
- retains all 20 controls and 10,000 bootstrap replications per control;
- adds explicit preparation-stage progress messages.

No strategy, source, weight, threshold, cost, fold, order, NAV, exposure, bootstrap, multiplicity, or decision rule changed.

## Required next evidence

Run the focused suite:

`python -m pytest tests/test_campaign52_development.py tests/test_campaign52_development_runner.py -q`

If it passes, rerun:

`python -m scripts.run_campaign52_development`
