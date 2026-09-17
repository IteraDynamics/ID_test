import argparse,hashlib,json,platform,shutil,subprocess,traceback
from datetime import datetime,timezone
from pathlib import Path
import numpy as np,pandas as pd,sklearn
from research.core_regime_reuse.adapter import verify_source_lock
from research.crypto_reversal.experiment import INPUTS,load_input
from .study import evaluate,summarize_gate,COST_BPS,RISK_HORIZON_DAYS,RIDGE_ALPHA,MULTIPLIER_BOUNDS

def main():
 p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,required=True);p.add_argument('--output-root',type=Path,default=Path('artifacts'));a=p.parse_args();out=a.output_root/('core_pca4_economic_comparison_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'));out.mkdir(parents=True,exist_ok=False);error=None
 try:
  lock=verify_source_lock();sources={};outputs={'metrics':[],'pairs':[],'fits':[]}
  for asset,(filename,_) in INPUTS.items():
   frame,sources[asset]=load_input(a.data_root/filename,asset)
   for hours in (1,4):
    result=evaluate(frame,asset,hours)
    for k,rows in result.items():outputs[k].extend(rows)
  metrics=pd.DataFrame(outputs['metrics']);pairs=pd.DataFrame(outputs['pairs']);metrics.to_csv(out/'metrics.csv',index=False);pairs.to_csv(out/'pairs.csv',index=False);(out/'fits.json').write_text(json.dumps(outputs['fits'],indent=2)+'\n')
  gate=summarize_gate(pairs,metrics);(out/'gate.json').write_text(json.dumps(gate,indent=2)+'\n')
  root=Path(__file__).resolve().parents[2];report=dict(status='research-only controlled economic comparison',classification=gate['status'],source_lock=lock,sources=sources,risk_horizon_days=RISK_HORIZON_DAYS,ridge_alpha=RIDGE_ALPHA,multiplier_bounds=list(MULTIPLIER_BOUNDS),cost_bps=list(COST_BPS),sampling='UTC midnight; yearly 2020-2025 walk-forward; training-only PCA and risk decoder',direction='TREND_UP=+1; TREND_DOWN=-1; all other Core labels=0',guardrail='No production, paper-trading, runtime, strategy, portfolio, order, NAV, exposure, execution, threshold, or Core-label change authorized',versions=dict(python=platform.python_version(),pandas=pd.__version__,numpy=np.__version__,sklearn=sklearn.__version__),git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),study_sha256=hashlib.sha256(Path(__file__).with_name('study.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest());(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(f"Frozen economic gate: {gate['status']}",flush=True)
 except Exception:
  error=traceback.format_exc();(out/'error.txt').write_text(error)
 archive=shutil.make_archive(str(out),'zip',out);print(f'SHARE RESULTS ZIP: {archive}',flush=True)
 if error:raise SystemExit(error)
if __name__=='__main__':main()
