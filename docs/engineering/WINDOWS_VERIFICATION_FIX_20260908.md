# Windows verification follow-up — 2026-09-08

The operator tested exact revision `40e2e08` on Windows with Python 3.12.13:
**813 passed, 10 failed, 8 setup errors, 89 warnings**. These are two root causes,
not 18 independent strategy failures.

1. The packaging inventory used native path strings against Git/ZIP identifiers.
   Windows backslashes made matching files appear missing/new. Use `.as_posix()`
   for repository and wheel inventory keys. No inventory restriction is removed.
2. Python's `%-d` date format failed on Windows. The same expression existed in
   the original `83e4e11` dashboard. Fix the extracted `friendly_ts` and the remaining
   inception label using the integer day and portable month/time/year formatting.
   Plotly hover templates are JavaScript format strings and remain unchanged.

The date correction is a separate behavioral-fix commit. It preserves the existing
Linux display text and enables Windows rendering. Core v1 accounting, parameters,
weights, strategies, research definitions and artifact formats are unchanged.

The packaging containment gate now explicitly applies exactly two reviewed literal
replacements to baseline display expressions before the original byte/AST checks.
Each expected baseline expression must occur exactly once. Other changes in the
same file still fail closed, verified by a corruption test. This is a documented
post-migration correction, not a claim of verbatim extraction for those expressions.
The original I/O baseline boundary and all 193 differential cases remain in place.

Local Linux checks passed: 41 dashboard/packaging tests, including a simulated
Windows-relative-path regression and portable date cases; the refined packaging
canaries passed again (14 tests); the 193-case I/O/containment gate passed.
Native Windows validation is added to CI: full suite on Python 3.12 and actual
installed-wheel verification, alongside the unchanged Linux full-suite/parity jobs.
Final native CI results are recorded in the draft PR; pending runs are not passes.

No skip, xfail, or global path/encoding override is used to hide the reported failures.
Source-byte gates still require appropriate checkout bytes; Git line-ending conversion
is a separate checkout concern. Native Windows CI covers the suite and installed
wheel; Linux CI retains the complete independent-baseline migration gates.

The operator's original local Experiment 012 commit and untracked/private data are
outside this branch and are not modified. No merge or deployment is authorized.
