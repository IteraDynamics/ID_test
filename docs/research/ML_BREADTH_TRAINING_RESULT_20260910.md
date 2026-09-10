# Eight-ETF development results — 2026-09-10

The adjusted upload passes manifest and matching-calendar checks. All eight ETFs
supply 2,789 usable sessions, 2013-12-02 through 2024-12-31. No reserved2025 data
enters features or outcomes. Source hashes are in the report. No raw inputs are
committed to GitHub. The earlier unadjusted TLT file is not used.

Completed168 candidate evaluations /252 optimizer fits, no failed real fits.
84 neural stopping runs plus84 refits. No neural stopping run reached the200-epoch
cap; selected epochs5–85, median5. Absence of warnings is not proof of global
optimization or a well-specified model: partial_fit uses explicit stopping rather
than the version1 convergence-warning convention. Five is the earliest inspected
epoch, so many minima sit on that boundary. No further search was conducted.

364 weekly signal dates,2,912 ETF forecasts. Relative MSE reductions:

| Procedure | Versus zero | Versus historical mean |
|---|---:|---:|
| Inner-selected candidate |0.7501%|0.4425%|
| Ridge100 |1.3265%|1.0206%|
| Summary MLP16 |0.6827%|0.3749%|
| Historical mean |0.3090%|0%|

These are forecast-error improvements, not investment returns. Ridge100 is an
ex-post descriptive comparison, not a replacement for the recorded selector.
Selected candidates:2018 GBM2;2019 sequence32;2020 ridge100;2021/2022 MLP32;
2023 GBM2;2024 sequence32. Neither a stable neural winner nor a profitability claim.

A cached-forecast concentration diagnostic, declared after the main results,
excludes2020 without refitting/reselection. Selected procedure then has1.8952%
MORE error than historical mean; Ridge1001.0102% more; MLP162.6281% more.
The pooled positive result is therefore fragile and strongly influenced by2020.
This diagnostic is descriptive and cannot alter the candidate-selection record.

Validation:22 targeted tests passed. Real source/forecast hashes verified; metrics
recomputed from saved forecasts byte-for-byte; all training/stopping boundaries
checked. Tests demonstrate future outcomes cannot change selected neural epochs,
eight-asset identity encoding and chronological purging. No additional real fits.

The breadth and training changes occur together; improvements over the initial
three-ETF run cannot be attributed solely to either one. Summary and lagged-input
models also differ in volume information. Eight correlated ETFs are not eight
independent markets, and overlapping daily labels do not increase independence.

Next design decision: choose the economic objective before implementing portfolio
construction. Proposed default is a standalone long-only allocator that may hold
cash and targets smoother returns through explicit risk limits. An alternative is
fully invested relative allocation against a passive eight-ETF basket. These need
different benchmarks and success criteria. Neither changes frozen Core.
Do not convert the small forecast improvements into a capital recommendation.
