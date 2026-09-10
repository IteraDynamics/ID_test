# Energy source feasibility — 2026-09-10

Status: SOURCE_SAMPLE_PASS; PRICE_INPUT_PENDING. Exploratory feasibility only.
No model fits, outcome selection, campaign freeze, or production change.

## Question and bounded choice

Does unusually low U.S. commercial crude inventory, relative to its own causal seasonal history, add information about USO's next 21 trading-session return over BIL, beyond training-only historical mean and price-only controls?

Select USO and 21 sessions now, before examining USO outcomes. USO is an oil-futures fund, not spot crude. Its realized share returns include its changing futures exposure, collateral and expenses; these are part of the instrument. Do not substitute CL=F or XLE outcomes after seeing results. This is a development choice, not a frozen campaign charter. Broker access, power, and horizon feasibility remain prerequisites for a campaign.

## Actual source checks

Four archived EIA Table 1 CSVs retrieved and parsed: 2014-01-08, 2018-01-04, 2022 June-17 data released June-29, and 2024-01-04. Hashes and sample rows are in ML_ENERGY_SOURCE_PROBE_20260910.json. All contain an exact Commercial (Excluding SPR) stock row. They require Windows-1252 decoding; UTF-8 fails. Tables contain multiple sections and unequal row widths. The 2024 file has 59 rows versus 55 in the other samples and changed supply-section line numbers. Parse by section, label and dated column, never fixed row number. Full historical coverage and unit verification remain outstanding; four examples do not establish complete vintage integrity.

The EIA archive and the June-2022 issue explicitly distinguish observation ending June 17 from release June 29. Preserve both. For multiple reports on a release date, use the newest observation for a single decision, retain older releases in the historical information set, and never backdate a trade.

Local CL=F manifest: yfinance, auto_adjust=false, 5,445 rows, 2005-01-03 through 2026-08-26; six OHLCV columns, no contract identifier, expiry or roll ledger. Uploaded sample ZIP contains its manifest but no CL price CSV. This does not establish executable futures returns. Do not use it as the tradable target. No post-2024 return observations were inspected in this audit.

USO sponsor documents a 1-for-8 reverse split on April 28, 2020 and futures-based exposure. Validate adjusted prices around this date and assess historical exposure changes before modeling. Current fund roll rules must not be assumed constant historically.

## Causal construction to implement after acquisition

- Acquire archived issues from 2009 through 2024 with release-page provenance, hashes, observation dates, units and explicit missingness. Do not silently replace unavailable issues with today's revised API history.
- Start with commercial crude inventory only. Use first-published observations from prior releases for historical seasonal comparisons: five prior calendar years, same seasonal week plus/minus two weeks; require all five years represented. Define week-53 handling and minimum counts before feature generation. No full-sample normalization or claims of consensus surprise.
- Separate level tightness from inventory-change anomaly. Inspect revisions and definition changes before adding other petroleum fields. Preserve source values and parsing diagnostics.
- Earliest entry is the opening after one complete exchange session strictly after the release date. This deliberately permits a slow signal, not a release-time trading claim. Exit 21 sessions after entry. No label may extend into 2025.
- Compare the incremental feature against training-only mean and the same price-only model with identical execution and costs. Purge overlapping labels at folds; overlapping weekly 21-session returns are not independent observations.
- Before any fitting, estimate attainable power/effective sample size for a stated economically useful effect. If insufficient, report feasibility failure, not an underpowered negative model result.
- Freeze the model shortlist, portfolio rule, cost assumptions and decision criteria in a later review; preserve all attempts. Reserved 2025 remains untouched.

## Next required input

Run DOWNLOAD_ML_ENERGY_PRICES.ps1 using the existing repository downloader. It creates a new dated folder with adjusted USO and BIL through 2024 plus manifests, then a ZIP. No subscription or EIA key is needed. Review these price inputs and complete archived-table coverage before fitting.

## Sources

- https://www.eia.gov/petroleum/supply/weekly/archive/
- https://www.eia.gov/petroleum/supply/weekly/archive/2022/2022_06_17_data/wpsr_2022_06_17_data.php
- https://www.eia.gov/petroleum/supply/weekly/archive/2024/2024_01_04/wpsr_2024_01_04.php
- https://www.uscfinvestments.com/uso
