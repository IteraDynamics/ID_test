# ML Lab Experiment 010 — Results

## Status

**EXPLORATORY_DIAGNOSTIC_NONCONFIRMATORY**

No Core v1, Core v2, runtime, threshold, order, NAV, exposure, portfolio, paper, live, or capital implication is authorized.

## Purpose

Experiment 010 audited the stability and mechanism of the macro-conditioned cross-sectional structure observed in Experiment 009. It performed no model refit and no tuning. It used the saved Experiment 009 OOS predictions, macro-state series, and feature-importance artifacts, with feature geometry restricted to anchors that actually had Experiment 009 OOS predictions.

The audit asked whether the macro GBM increment:

1. recurred across rate, curve, and VIX regimes;
2. depended primarily on the zero-rate era;
3. used similar interaction families before and after 2022;
4. was broadly distributed across ETFs rather than concentrated in a few names.

## Frozen audit dimensions

Rate regimes:

- `rate2_low`: DGS2 trailing percentile < 1/3
- `rate2_mid`: 1/3 <= percentile < 2/3
- `rate2_high`: percentile >= 2/3

Curve regimes:

- `curve_inverted`: DGS10-DGS2 < 0
- `curve_flat`: 0 <= DGS10-DGS2 < 1 percentage point
- `curve_steep`: DGS10-DGS2 >= 1 percentage point

VIX regimes:

- `vix_low`: trailing percentile <= 0.5
- `vix_high`: trailing percentile > 0.5

Zero-rate diagnostic:

- `zirp_like`: DGS2 < 0.5%
- `non_zirp`: DGS2 >= 0.5%

## Main result

The Experiment 009 macro-GBM increment was **not limited to one macro regime and was not a zero-rate-era artifact**.

### Expanding memory

Macro GBM minus price GBM was positive in:

- all three curve regimes;
- both VIX regimes;
- low and high relative 2-year-rate regimes;
- both ZIRP-like and non-ZIRP periods.

The only negative rate-state cell was the middle relative-rate regime.

Curve recurrence was especially clean:

| Regime | IC increment | Tail-spread increment | Anchors |
|---|---:|---:|---:|
| Flat | +0.01743 | +0.01968 | 293 |
| Inverted | +0.01005 | +0.02257 | 121 |
| Steep | +0.01035 | +0.01486 | 488 |

VIX recurrence:

| Regime | IC increment | Tail-spread increment | Anchors |
|---|---:|---:|---:|
| High VIX | +0.01446 | +0.00684 | 415 |
| Low VIX | +0.01103 | +0.02651 | 487 |

Zero-rate diagnostic:

| Regime | IC increment | Tail-spread increment | Anchors |
|---|---:|---:|---:|
| Non-ZIRP | +0.01331 | +0.01653 | 644 |
| ZIRP-like | +0.01086 | +0.01979 | 258 |

The expanding macro GBM therefore does not owe its incremental result to old near-zero-rate history alone.

### Trailing 3-year memory

The shorter-memory model remained more regime-sensitive.

Positive macro-GBM increments appeared in:

- flat and steep curves;
- low and high relative-rate regimes;
- high VIX;
- non-ZIRP periods.

Important failures:

- inverted curve: IC increment -0.05612, spread increment -0.09431;
- low VIX: IC increment -0.00407, spread increment -0.00735;
- ZIRP-like: IC increment -0.00361, though spread remained +0.01529;
- middle relative-rate regime: IC increment -0.00937, spread increment -0.01303.

This supports the Experiment 009 interpretation that short memory and explicit macro state can partly substitute for one another and can become brittle in some states.

## Interaction-family stability

Macro/interaction features remained a large share of macro-GBM importance both before and after 2022:

- expanding pre-2022: ~0.683 total mean importance;
- expanding post-2022: ~0.701;
- trailing 3y pre-2022: ~0.717;
- trailing 3y post-2022: ~0.814.

Recurring high-importance interaction families included:

- curve state × 60-day volatility rank;
- VIX state × 60-day volatility rank;
- 2-year-rate state × 60-day volatility rank;
- rate change × 120-day return rank;
- curve/rate state × 120-day return rank.

The exact ordering changed across periods, but the same families repeatedly reappeared. No single macro interaction dominated the full macro block: the top three macro/interaction features generally represented roughly 28%-32% of that block for macro GBM.

## Ridge comparison

The mechanism continued to look nonlinear rather than like a universally additive macro factor.

In the non-ZIRP sample:

- expanding macro GBM minus price GBM: +0.01331 IC;
- expanding macro Ridge minus price Ridge: -0.02938 IC;
- expanding macro GBM minus macro Ridge: +0.03479 IC.

Trailing 3y non-ZIRP:

- macro GBM minus price GBM: +0.02379 IC;
- macro Ridge minus price Ridge: -0.02490 IC;
- macro GBM minus macro Ridge: +0.01434 IC.

The macro representation therefore does not behave like a simple linear augmentation that helps both model classes uniformly.

## Asset concentration

Asset concentration remains the main weakness.

Positive centered-improvement concentration:

- expanding pre-2022: top three = 52.2% of positive improvement;
- expanding post-2022: top three = 70.7%;
- trailing 3y pre-2022: top three = 66.2%;
- trailing 3y post-2022: top three = 87.2%.

The most concentrated cell was trailing-3y post-2022, where only five ETFs had positive centered improvement and XLY, XLE, and IWD accounted for most of it.

This prevents treating the current U.S.-ETF result as a general cross-sectional mechanism without transfer evidence.

## Interpretation

Experiment 010 strengthens Experiment 009.

The supported exploratory statement is:

> Macro-conditioned nonlinear cross-sectional structure is a credible recurring phenomenon in the original U.S. ETF universe, particularly under expanding training memory. The increment recurs across multiple rate, curve, VIX, and non-ZIRP states and uses repeated macro × asset-state interaction families.

The unsupported stronger statement is:

> The mechanism is already general, portable, or suitable for production.

That claim remains blocked by asset concentration and by the fact that all evidence so far comes from one domestic-equity cross-section.

## Next research question

The next justified test is cross-universe transfer without changing the learned representation:

> If annual models are trained on the original U.S. ETF universe, does the same frozen price/macro feature geometry rank a distinct international country-ETF universe when applied unchanged?

A transfer failure would materially weaken the general-mechanism interpretation. A successful transfer would be substantially stronger evidence than another fit on the same U.S. universe.
