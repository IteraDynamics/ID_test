import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import platform
import shutil
import subprocess
import traceback
import pandas as pd
import numpy as np
import sklearn
from research.crypto_reversal.experiment import INPUTS,load_input
from research.core_regime_reuse.adapter import verify_source_lock
from .study import FEATURES,MODELS,build_panel,add_benchmarks,annual,scores,compare


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-root',type=Path,required=True)
    parser.add_argument('--output-root',type=Path,default=Path('artifacts'))
    args=parser.parse_args()
    out=args.output_root/('volatility_incremental_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir(parents=True,exist_ok=False);error=None
    try:
        lock=verify_source_lock();sources={};results=[]
        for asset,(filename,_) in INPUTS.items():
            frame,sources[asset]=load_input(args.data_root/filename,asset)
            for hours in (1,4):
                panel=add_benchmarks(frame,build_panel(frame,hours))
                results.append(annual(panel,asset,hours))
        forecasts=pd.concat(results,ignore_index=True)
        forecasts.to_csv(out/'forecasts.csv',index=False)
        summary=scores(forecasts);summary.to_csv(out/'scores.csv',index=False)
        differences=compare(summary);differences.to_csv(out/'comparisons.csv',index=False)
        root=Path(__file__).resolve().parents[2]
        report=dict(state='forecast-only chronological development replay; not pristine OOS',
            source_lock=lock,sources=sources,features=FEATURES,models=MODELS,
            git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
            versions=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,sklearn=sklearn.__version__),
            selection='No tuning, model selection, trading simulation or automatic promotion',
            timing='UTC midnight; 24h outcome; annual expanding fits; label_end strictly before fit time')
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(differences[(differences.year=='all')&(differences.candidate=='boosted_augmented')].to_string(index=False))
    except Exception:
        error=traceback.format_exc();(out/'error.txt').write_text(error)
    archive=shutil.make_archive(str(out),'zip',out)
    print(f'SHARE RESULTS ZIP: {archive}',flush=True)
    if error:raise SystemExit(error)


if __name__=='__main__':main()
