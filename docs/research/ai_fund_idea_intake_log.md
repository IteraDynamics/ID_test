# AI-Fund Idea Intake Log

## Purpose

This log records AI-fund-generated ideas after Itera triage.

These entries are not trade instructions. They are research idea inputs that may be translated into deterministic ID_test tasks.

---

## Intake Cycle: 2026-05-20

Source:

```text
AI-fund MVP desktop run
```

Context:

The AI-fund system produced plausible PM-style trade ideas. These ideas are useful as examples of agentic idea generation, but must be converted into Itera research candidates before they can affect the research radar.

---

### Intake 1 — TLT Macro Long

Original idea:

```text
LONG TLT
Notional: $400,000
Size: 4.0% NAV
PM: pm_macro
Confidence: 65%
Expected return: 5.0%
Stop loss: 4.0%
Take profit: 8.0%
Horizon: 30 days
Submitted: 2026-05-20T12:51:42.635843
```

Original rationale summary:

```text
Potential June cut, 10Y rally toward 4.40% to 4.50%, and late-cycle easing could support duration upside via TLT.
```

Triage status:

```text
TRANSLATE -> QUEUE
```

Research lane:

```text
Macro / Cross-Asset
```

Portfolio role:

```text
Defensive destination / duration-sensitive diversifier
```

Itera translation:

```text
Duration-filtered bond destination.
```

Deterministic research candidate:

```text
During state-confirmed crypto risk-off, test TLT and IEF as destinations only when duration trend is favorable.
Candidate filter: TLT close > TLT SMA200 or IEF close > IEF SMA200.
Benchmark against 50/50 GLD/BIL, GLD-only, BIL-only, and cash.
```

Required data:

```text
TLT_1D.csv
IEF_1D.csv
baseline Fund v1 equity curve
BTC daily close
GLD_1D.csv
BIL_1D.csv
```

Expected failure mode:

```text
Duration assets may fail during inflation / rising-rate regimes, especially if the filter is too slow or too permissive.
```

Priority:

```text
Medium
```

Notes:

This should not be treated as a current TLT trade. It is useful because it points to a conditional-duration destination test.

---

### Intake 2 — ASML Long

Original idea:

```text
LONG ASML
Notional: $300,000
Size: 3.0% NAV
PM: pm_longshort
Confidence: 70%
Expected return: 15.0%
Stop loss: 5.0%
Take profit: 20.0%
Horizon: 30 days
Submitted: 2026-05-20T12:51:29.526888
```

Original rationale summary:

```text
ASML fundamentals, margins, FCF, DCF upside, and forward P/E compression may support upside despite geopolitical and cyclical risks.
```

Triage status:

```text
TRANSLATE -> QUEUE
```

Research lane:

```text
Sector / Equity
```

Portfolio role:

```text
Risk-on enhancer
```

Itera translation:

```text
AI infrastructure / semiconductor ETF risk-on basket.
```

Deterministic research candidate:

```text
During crypto-friendly regimes, test SMH / SOXX / XLK / IGV / QQQ as risk-on complements or allocation destinations.
Do not test ASML as a single-name discretionary trade unless Itera explicitly opens a single-name equity sleeve.
```

Required data:

```text
SMH_1D.csv
SOXX_1D.csv if added
XLK_1D.csv
IGV_1D.csv
QQQ_1D.csv
baseline Fund v1 equity curve
BTC daily close
```

Expected failure mode:

```text
AI infrastructure exposure may simply duplicate high-beta tech / QQQ exposure, increase drawdown, or fail to diversify the existing crypto risk profile.
```

Priority:

```text
Low-medium until defensive allocator research stabilizes.
```

Notes:

This is a useful research theme, but not an immediate Itera trade.

---

### Intake 3 — Stale / Duplicate TLT Macro Long

Original idea:

```text
LONG TLT
Notional: $300,000
Size: 3.0% NAV
PM: pm_macro
Confidence: 70%
Expected return: 15.0%
Stop loss: 5.0%
Take profit: 20.0%
Horizon: 30 days
Submitted: 2026-05-07T16:06:17.073572
```

Original rationale summary:

```text
US GDP slowing to 2.8% QoQ annualized in Q3 2024 and CPI at 2.4% YoY in September 2024 support a Fed easing thesis and duration upside.
```

Triage status:

```text
ARCHIVE
```

Reason:

```text
The idea is stale / duplicate for Itera purposes. It uses old macro data as support for a current trade and overlaps with the fresher duration-filtered bond destination idea.
```

Retained research value:

```text
The duration-filtered bond destination remains in the backlog, but this stale rationale is not accepted as current evidence.
```

---

## Intake Summary

Accepted into radar:

```text
Duration-filtered bond destination
AI infrastructure / semiconductor ETF risk-on basket
```

Archived:

```text
Stale duplicate TLT macro long
```

Next action:

```text
Update docs/research/itera_research_radar.md with AI-fund intake section and backlog entries.
```
