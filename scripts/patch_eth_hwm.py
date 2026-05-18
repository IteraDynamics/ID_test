"""One-off patch: reset ETH sleeve high-water mark to current NAV to clear
the rebalance-induced DrawdownGovernor halt.

The ETH sleeve was halted because a cross-asset rebalance drained ~$6.1k of
cash from its broker, causing a ~24.7% apparent drawdown from the $12,500 HWM.
No trades were executed (fill_count=0); the NAV drop was purely a capital
transfer. This patch sets high_water_mark = nav and clears the halted flag so
the runner resumes normal operation on the next cycle.

Usage (run from the project root):
    python scripts/patch_eth_hwm.py
"""

from __future__ import annotations

import json
from pathlib import Path

STATE_PATH = Path("runtime/argus/state/ETH_live_state.json")


def main() -> None:
    if not STATE_PATH.exists():
        raise SystemExit(f"State file not found: {STATE_PATH}\n"
                         "Run from the project root directory.")

    raw = STATE_PATH.read_text(encoding="utf-8")
    data = json.loads(raw)

    nav = data.get("nav", 0.0)
    if nav <= 0:
        raise SystemExit(f"NAV is {nav:.6f} — cannot patch a zero-NAV state file.")

    old_hwm     = data.get("high_water_mark")
    old_halted  = data.get("drawdown_governor_halted")

    data["high_water_mark"]          = nav
    data["drawdown_governor_halted"] = False

    STATE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

    print(f"Patched  : {STATE_PATH}")
    print(f"  high_water_mark          : {old_hwm}  →  {nav:.6f}")
    print(f"  drawdown_governor_halted : {old_halted}  →  False")
    print()
    print("The ETH sleeve will resume normal operation on the next runner cycle.")
    print("Apply the structural fix (Phase 2) before restarting the runner to")
    print("prevent future rebalances from triggering the same false halt.")


if __name__ == "__main__":
    main()
