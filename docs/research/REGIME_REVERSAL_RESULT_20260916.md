# Initial controlled regime result

Decision: do not advance this reversal/filter family to OOS or Monte Carlo on
these results. No filter or threshold was revised after viewing the output.
This is not a rejection of the classifier's usefulness for other mechanisms.

Frozen design published as c2dd512c740d7d949ee73a6379d829c8c86e8749.
17 tests passed. All 128 individual asset simulations completed with accounting
and independent fill replay checks. All 980 protected original tracked files
remain byte-identical. The unfiltered primary reproduces the prior run across
all scenarios/assets/periods for CAGR, Sharpe, drawdown, terminal multiple and
exposure (1e-12 tolerance).

Combined BTC/ETH, original gap treatment, 30 bps each way:

| Entry filter | CAGR | Zero-cash Sharpe | Max drawdown | Trades |
|---|---:|---:|---:|---:|
| Unfiltered | 1.43% | 0.172 | -26.04% | 115 |
| TREND_DOWN | 1.84% | 0.477 | -7.44% | 29 |
| RANGE | 0.85% | 0.304 | -4.35% | 4 |

All seven labels, including negative and empty groups, appear in the evidence
CSVs. Downtrend-only cost stress produces -0.34% CAGR and -9.71% drawdown;
delay stress produces 2.97% CAGR and -6.59% drawdown. These are full-period
capital returns, with substantial idle cash, not returns on deployed capital.

The downtrend bucket's base-case BTC CAGR is only 0.18% versus ETH 3.38%.
Its combined 2020–2022 CAGR is 2.57%, versus 1.12% for 2023–end; these are both
exposed development periods. Removing the five largest winning trade returns
reduces its combined terminal multiple to 0.9518. This is a sensitivity
calculation, not a causal estimate or an implementable trading rule.
The RANGE bucket has only four trades; its positive return cannot support a
reliability claim. All seven state-only filters were inspected, so selecting
the best observed one would add selection bias.

The causal 240-hour missing-data screen produces identical portfolio metrics.
It does not establish that older gaps have no EWM influence. Future missing
exits were never screened out. The classifier itself is unchanged.

Evidence is stored under `docs/research/evidence/regime_reversal_20260916/`.
The runner produces full trade/fill ledgers and daily NAV in the local ZIP.
PowerShell wrapper was not executed on Linux; its Python entrypoint completed.
