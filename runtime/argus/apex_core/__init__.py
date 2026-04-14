"""Apex Core — signal generation and runtime orchestration."""

from runtime.argus.apex_core.signal_generator import generate_signals
from runtime.argus.apex_core.orchestrator import Orchestrator

__all__ = ["generate_signals", "Orchestrator"]
