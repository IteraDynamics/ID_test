import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import traceback

import numpy as np
import pandas as pd
import sklearn

from research.core_regime_reuse.adapter import verify_source_lock
from research.crypto_reversal.experiment import INPUTS, load_input
from .study import evaluate, panel_from_hourly, KS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, default=Path('artifacts'))
    args = parser.parse_args()
    out = args.output_root / ('regime_state_compression_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir(parents=True, exist_ok=False)
    error = None
    try:
        lock = verify_source_lock()
        sources, outputs = {}, {}
        for asset, (filename, _) in INPUTS.items():
            frame, sources[asset] = load_input(args.data_root / filename, asset)
            for hours in (1, 4):
                result = evaluate(panel_from_hourly(frame, hours), asset, hours)
                for key, rows in result.items():
                    outputs.setdefault(key, []).extend(rows)
        for name, rows in outputs.items():
            if name == 'fits':
                (out / 'fits.json').write_text(json.dumps(rows, indent=2) + '\n')
            else:
                pd.DataFrame(rows).to_csv(out / f'{name}.csv', index=False)
        root = Path(__file__).resolve().parents[2]
        report = dict(
            status='observation-only state compression research; no strategy or runtime changes',
            sources=sources,
            source_lock=lock,
            seed=1729,
            cluster_counts=list(KS),
            pca_components='1 through 5, training-only fit',
            sampling='UTC midnight; states use 1H/4H inputs; yearly 2020-2025 walk-forward folds',
            uncertainty='Descriptive research; no promotion, validation, or trading claim',
            versions=dict(python=platform.python_version(), pandas=pd.__version__, numpy=np.__version__, sklearn=sklearn.__version__),
            git_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
            study_sha256=hashlib.sha256(Path(__file__).with_name('study.py').read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
        )
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print('Complete: review score, occupancy, persistence, Core cross-tabs, outcomes, and PCA fits together.')
    except Exception:
        error = traceback.format_exc()
        (out / 'error.txt').write_text(error)
    archive = shutil.make_archive(str(out), 'zip', out)
    print(f'SHARE RESULTS ZIP: {archive}', flush=True)
    if error:
        raise SystemExit(error)


if __name__ == '__main__':
    main()
