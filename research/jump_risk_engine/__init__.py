"""Research-only Jump Risk Engine / Discontinuity Risk Engine.

This package is intentionally isolated from Core v1 runtime execution. It is
for offline research into whether discontinuous-move risk can be estimated
better than unconditional jump frequency using only prior information.
"""

from .lab import JumpRiskConfig, run_jump_risk_lab

__all__ = ["JumpRiskConfig", "run_jump_risk_lab"]
