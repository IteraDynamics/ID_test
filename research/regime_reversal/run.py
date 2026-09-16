"""Local runner for the frozen 4H/24H reversal regime experiment."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import platform
import shutil
import subprocess
import traceback
import pandas as pd
import numpy as np
from research.crypto_reversal.experiment import INPUTS, load_input
from .experiment import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, default=Path('artifacts'))
    args = parser.parse_args()
    out = args.output_root / ('regime_reversal_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir(parents=True, exist_ok=False)
    error = None
    try:
        frames, sources = {}, {}
        for asset, (filename, _) in INPUTS.items():
            frames[asset], sources[asset] = load_input(args.data_root/filename, asset)
        report = execute(frames, out)
        report['sources'] = sources
        report['versions'] = {'python': platform.python_version(), 'pandas': pd.__version__, 'numpy': np.__version__}
        root = Path(__file__).resolve().parents[2]
        report['git_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
        report['execution_source_sha256'] = sha256((root/'research/crypto_reversal/experiment.py').read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        (out/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        summary = pd.read_csv(out/'summary.csv')
        print(summary.loc[(summary.scenario=='base') & (summary.gap_mode=='original') &
              (summary.asset=='MIX') & (summary.period=='full'),
              ['regime_filter','cagr','zero_cash_sharpe','max_drawdown']].to_string(index=False))
    except Exception:
        error = traceback.format_exc()
        (out/'error.txt').write_text(error, encoding='utf-8')
    archive = shutil.make_archive(str(out), 'zip', out)
    print(f'SHARE RESULTS ZIP: {archive}', flush=True)
    if error:
        raise SystemExit(error)


if __name__ == '__main__':
    main()
