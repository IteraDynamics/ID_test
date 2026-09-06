"""Compatibility entry point for ML Lab Experiment 009."""

# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)

from pathlib import Path
import sys

# Direct-script execution starts with scripts/ on sys.path; package code never
# adjusts import paths. Preserve both historical CLI and import entry points.

from research.ml_lab.experiments import experiment_009 as _implementation

if __name__ == "__main__":
    _implementation.main()
else:
    # Preserve module identity, including callers that patch module globals.
    sys.modules[__name__] = _implementation
