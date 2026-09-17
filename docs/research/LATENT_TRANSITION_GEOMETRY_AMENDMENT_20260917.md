# Latent Transition Geometry — Methodological Amendment — 2026-09-17

The first frozen run exposed a specification limitation before a destination conclusion can be made: the multiclass target combines `NO_TRANSITION` with destination labels. Therefore its score can establish information about the joint occurrence+destination problem, but cannot by itself establish that trajectory predicts destination conditional on a transition.

This amendment does not change features, horizons, support thresholds, data, Core logic, or any runtime behavior. It adds the missing conditional destination test required by the already-frozen primary hypothesis.

For each frozen horizon, evaluate a second multiclass task restricted to observations whose first Core transition occurs within that horizon. The target is the first destination Core label. Fit and score using the same training-only representations and deterministic logistic model. Report event counts/classes and refuse interpretation when fewer than two destination classes are available.

The original joint occurrence+destination results remain intact and must be reported separately. The conditional test may not replace or overwrite them.