import argparse,hashlib,json,platform,shutil,subprocess,traceback
from datetime import datetime,timezone
from pathlib import Path
import numpy as np,pandas as pd,sklearn,scipy
from research.core_regime_reuse.adapter import verify_source_lock
from research.crypto_reversal.experiment import INPUTS,load_input
from .study import evaluate,HORIZONS,OUTCOMES,STABILITY_HORIZON

def main():
 p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,required=True);p.add_argument('--output-root',type=Path,default=Path('artifacts'));a=p.parse_args();out=a.output_root/('conditional_market_behavior_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'));out.mkdir(parents=True,exist_ok=False);error=None
 try:
  lock=verify_source_lock();sources={};outputs={}
  for asset,(filename,_) in INPUTS.items():
   frame,sources[asset]=load_input(a.data_root/filename,asset)
   for hours in (1,4):
    result=evaluate(frame,asset,hours)
    for k,rows in result.items():outputs.setdefault(k,[]).extend(rows)
  for name,rows in outputs.items():
   if name=='fits':(out/'fits.json').write_text(json.dumps(rows,indent=2)+'\n')
   else:pd.DataFrame(rows).to_csv(out/f'{name}.csv',index=False)
  root=Path(__file__).resolve().parents[2];report=dict(status='observation-only conditional market behavior hypothesis test',source_lock=lock,sources=sources,horizons=list(HORIZONS),outcomes=list(OUTCOMES),primary_instability_horizon=STABILITY_HORIZON,sampling='UTC midnight; yearly 2020-2025 walk-forward; training-only transforms; causal annual OOF stacked instability for behavior-model training',guardrail='No trading rule, P&L, threshold, position, sizing, cost, execution, runtime or portfolio change',versions=dict(python=platform.python_version(),pandas=pd.__version__,numpy=np.__version__,sklearn=sklearn.__version__,scipy=scipy.__version__),git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),study_sha256=hashlib.sha256(Path(__file__).with_name('study.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest());(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('Complete: review scores, within-Core bins, correlations, and fold consistency together.',flush=True)
 except Exception:
  error=traceback.format_exc();(out/'error.txt').write_text(error)
 archive=shutil.make_archive(str(out),'zip',out);print(f'SHARE RESULTS ZIP: {archive}',flush=True)
 if error:raise SystemExit(error)
if __name__=='__main__':main()
