"""One compatibility path adjustment for direct-file execution from a checkout.

Package imports do not invoke this helper. Installed commands resolve through
normal package discovery; bare checkout commands retain their historical paths.
"""
from pathlib import Path
import sys


def bootstrap(script_file: str) -> None:
    root = str(Path(script_file).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)
