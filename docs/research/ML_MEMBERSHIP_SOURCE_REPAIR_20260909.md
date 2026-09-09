# Free historical membership source repair — 2026-09-09

A dated candidate baseline is now available. Historical prices and terminal
outcomes remain unresolved. This is source engineering, with zero model fits.

## Source and scope

Pinned [fja05680/sp500](https://github.com/fja05680/sp500/tree/a2430f2af0c79ddf0748e91de11bdeb1616ab5a7)
at `a2430f2af0c79ddf0748e91de11bdeb1616ab5a7`. The repository combines older
Trading Evolved companion history with community-maintained changes. It is
not an independently certified index history. Source sizes and SHA-256 values,
the extracted baseline, dated events, reviewed identities and upstream license
are saved under `evidence/ml_membership_source_20260909/`.

The 2018-12-24 original row has 504 ticker strings. The cleaned row has 505:
`SCG-201812` becomes `SCG`, and `LIN` is added. The upstream notebook explicitly
adds LIN after 2018-10-31 and strips every historical `-yyyymm` suffix. We retain
the original identifiers separately. That global stripping rule is unsuitable
for security identity because ticker strings can be reused. LIN's exact index
entry and the rest of the baseline remain community-source evidence.

This establishes a candidate S&P-based population for investigating 2019–2024
data availability. It does not implement or amend the proposed 2010–2024 top-100
nonfinancial operating-company universe. The source is retrieved in 2026 and
may incorporate retrospective corrections. No post-2024 membership rows enter
the extracted event list; a source-file hash still covers the whole source file.

## Concrete repairs

1. Restore the missing January 2, 2019 SCG removal/FRC addition. The local
   change log starts January 18. [S&P's December 27, 2018 announcement](https://press.spglobal.com/2018-12-27-First-Republic-Bank-Set-to-Join-S-P-500)
   confirms the replacement before the January 2 open.
2. Correct HRS removal/LHX addition from June 1 to July 1, 2019. The error also
   exists upstream. [L3Harris's announcement](https://investors.l3harris.com/news/news-details/2019/L3Harris-Technologies-Merger-Successfully-Completed-Board-of-Directors-Leadership-and-Organization-Structure-Announced-07-01-2019/default.aspx)
   identifies July 1 as the first LHX trading day for continuing Harris shares.
   The merger closed June 29. Source and corrected dates are both retained.
3. Record FB/META as a same-Class-A ticker change effective June 9, 2022.
   [Meta's announcement](https://investor.atmeta.com/investor-news/press-release-details/2022/Meta-Platforms-Inc.-to-Change-Ticker-Symbol-to-META-on-June-9/default.aspx)
   confirms the same CUSIP. The existing META acquisition-pilot history is a
   candidate for historical FB observations. The late-start FB file must not
   be substituted for those observations.
4. Keep LLL separate from HRS. LLL stopped trading June 28 and converted into
   1.3 LHX shares per LLL share. This needs merger accounting, including review
   of fractional-share treatment, rather than concatenating ticker histories.

Only the named identity events and four corrected/restored membership action
rows have primary-source verification here. Other membership rows are explicitly
marked community-source unverified. No original local file was overwritten.

## Reconciliation results

| Check | Result |
| --- | ---: |
| Candidate baseline strings | 505 |
| Membership actions through 2024 | 264 |
| Distinct effective change dates after correction | 95 |
| Removals absent from prior membership | 0 |
| Additions already in prior membership | 0 |
| Membership count range after changes | 503–507 |
| Final membership count | 503 |
| Distinct strings encountered across the period | 635 |
| Upstream dated snapshots matched exactly | 98 |
| Snapshots differing only by the corrected HRS/LHX date | 3 |

Actions are grouped by effective date and applied together. All 101 eligible
upstream snapshots were compared with reconstruction from the seed. Only the
three June 2019 snapshots differ, by HRS versus LHX as expected. File hashes
were recomputed after writing. No model or portfolio implementation changed,
so model tests were not rerun. These checks establish internal reconciliation,
not independent historical accuracy. The 635-string union is a coverage count,
never a universe used at earlier dates.

To reproduce source retrieval, clone the linked repository and check out the
pinned commit. Extract the 2018-12-24 row from both historical CSVs. Use
`sp500_changes_since_2019.csv` through 2024-12-31, prepend the January 2
FRC/SCG replacement, and move the HRS/LHX pair to July 1. Compare the sorted
sets with each eligible updated historical row. The committed JSON retains
all inputs to the membership-set reconstruction without needing network access.

## Next useful work and local action

No local rerun or upload is needed for this repair. Existing uploads were enough.
Next, test historical price recovery on a small set of known exits and ticker
changes using free sources. Prioritize APC, NFX, FRC and SBNY for acquisition or
failure outcomes, and HRS/LHX and FB/META for continuing histories. Reuse the
existing META pilot download; do not repeat it. Corporate announcements can
establish identity and conversion terms but cannot supply missing daily prices.

Only after that recovery probe produces usable histories should we expand
downloads against the dated membership list. If the free sources cannot recover
the required exits, close this broad-equity historical design. Further feature
variants do not solve that data limitation. No subscription is proposed.
