# IV versus historical volatility sizing — exploratory economic test

User authorized proceeding after the stated economic-comparison proposal.
This is exploratory, same-session design, not a frozen governed campaign.
No deployment or independent-confirmation implication. Prior limited-power
permission does not establish power for this economic endpoint; report it as
uncalibrated. No tuning after inspecting strategy outcomes.

Before first strategy run: SPY/BIL, no leverage, 10% annual risk target. Three
strategies: constant weight, inverse RV21 volatility, inverse near-IV volatility.
Scales are calibrated to 10% realized volatility on 2013-12--2017 history using
zero-cost simulations; no return objective. Same risk target for all. Search
scale [0,20] by fixed 30-step bisection, flag unattainable target. Scale then
remains fixed throughout 2018--2024. This calibration matches training risk,
not evaluation risk. Report evaluation risk and exposure explicitly.

Use existing every-fifth-session anchor schedule, common IV/RV availability,
and full-session delay. Signals observed t trade at hypothetical close t+1;
new weights earn returns only afterward. Hold both asset quantities between
rebalances. BIL returns on all uninvested allocations. Fractional quantities,
no taxes or leverage. Start training in BIL and carry warm positions into test.
Costs on both ETF legs: 1/5/10 basis points per dollar traded; 5bps primary,
10bps stress. Self-financing rebalance solves fees and weights jointly. Costs
are scenario assumptions, not certified achievable fills. No terminal sale.

Primary criterion: IV beats BOTH historical-vol sizing and constant allocation
by >=0.5 percentage points annual certainty equivalent at 5bps, positive paired
95% block interval, positive in >=4/7 years, realized vol <=110% of comparator,
and drawdown no worse by >2 percentage points. CE = annual arithmetic excess
return minus (3/2)*annual return variance (fixed risk aversion3). BIL cancels
in paired CE differences. Stress requires positive CE differences at10bps.
9,999 circular 65-session paired bootstrap draws, seed20260911. Costs and
thresholds are fixed research choices; show all rather than pick best scenario.

SPY's supplied close is treated conditionally as adjusted total-return proxy;
its adjustment provenance is not independently certified. BIL manifest explicitly
states auto_adjust=true. Source-semantic limitations preclude production claims.
Missing BIL dates fail; no cash forward filling. No use of 2025 data.

## Results and disposition

Evaluation: 2018–2024. Primary cost: 5 basis points on each dollar traded in either ETF.

| Strategy | CAGR | Realized volatility | Maximum drawdown | Excess Sharpe |
|---|---:|---:|---:|---:|
| constant | 12.04% | 16.24% | -28.74% | 0.647 |
| rv | 9.20% | 11.40% | -15.46% | 0.637 |
| iv | 7.83% | 11.86% | -20.17% | 0.511 |

The predefined economic criterion failed. IV sizing had lower return, higher realized volatility, and deeper drawdown than historical-volatility sizing in this sample. IV minus RV annual certainty-equivalent improvement was −1.37 percentage points (paired block 95% interval −3.32 to +0.33 points); only 2 of 7 years were positive. The interval does not establish universal inferiority.

At 1bps, IV CAGR was 8.12% versus RV 9.45%; at 10bps, 7.47% versus 8.90%. Failure therefore persists across the specified cost scenarios. Constant allocation had materially higher evaluation volatility, so its higher CAGR is not an equal-risk comparison.

Disposition: this implementation of IV-based SPY sizing does not earn promotion. Close this hypothesis without post-result parameter searching. The prior forecast-loss improvement did not translate into an economic benefit under these rules. Core, runtime, and portfolio remain unchanged. This is a conditional exploratory simulation, not a verified executable total-return record.

Machine-readable evidence: `ML_IV_SIZING_RESULTS_20260911.json`, including source, runner, and daily-output hashes. The daily CSV can be reproduced with the command below; use a new output directory.

```powershell
python scripts/run_ml_iv_sizing.py --options-zip "<path-to-ml_options_variance_20260910_160826.zip>" --cash-zip "<path-to-ml_cash_proxy_20260910_085630.zip>" --output-dir artifacts/ml_iv_sizing_replay
```

Validation: 12 targeted tests passed. A second complete run reproduced both daily CSV and report JSON byte-for-byte.
