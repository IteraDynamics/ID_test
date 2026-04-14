"""Argus — the runtime execution engine for IteraDynamics.

Argus is the name for the Layer 3 runtime.  It:
- Polls for new closed bars.
- Calls Layer 1 and Layer 2.
- Applies governors and portfolio rules.
- Routes execution to the broker abstraction.
- Persists live state.
"""
