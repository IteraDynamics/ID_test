"""Compatibility entry point for ML Lab Experiment 005."""
from pathlib import Path
import sys

# Direct-script execution starts with scripts/ on sys.path; package code never
# adjusts import paths. Preserve both historical CLI and import entry points.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.ml_lab.experiments import experiment_005 as _implementation

if __name__ == "__main__":
    _implementation.main()
else:
    # Preserve module identity, including callers that patch module globals.
    sys.modules[__name__] = _implementation
