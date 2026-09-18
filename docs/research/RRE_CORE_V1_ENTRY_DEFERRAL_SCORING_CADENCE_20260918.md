# RRE Core v1 Entry Deferral — Scoring-Cadence Clarification — 2026-09-18

This is a pre-outcome methodological clarification to the frozen specification. No economic result has been computed.

The frozen Core-regime-stability experiment was trained and evaluated on UTC-midnight daily snapshots produced by \`panel_from_hourly\`. Its trajectory features are daily differences between those snapshots. Recomputing those features at every 1H/4H native bar would silently define a different model.

Therefore the economic experiment MUST preserve the validated model cadence:

- fit and score the frozen 7-day instability model only on the original UTC-midnight daily panel;
- derive q80 only from the model's matured daily training predictions;
- at a native Core decision timestamp, use the most recent causally available daily instability score at or before that timestamp;
- never interpolate or use a later daily score;
- if no prior valid daily score exists, fail closed to canonical Core behavior;
- the daily score remains in force until superseded by the next causally available UTC-midnight score.

This clarification changes no model feature, horizon, coefficient regularization, threshold rule, Core rule, allocation, action eligibility, or economic gate. It prevents an unvalidated intraday reinterpretation of the frozen stability model.
