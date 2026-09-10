"""Read-only candidate selection; bounded learning-size and seed diagnostics.

Never changes a selection or the original forecast artifacts. Learning-size
comparisons use the most recent 25%/50% of training dates: size and recency are
confounded, so these are sensitivity diagnostics, not causal sample-size effects.
"""
import argparse
import hashlib
import json
from pathlib import Path
import warnings
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from .run import build_panel,split,estimator,SUMMARY,SEQUENCE
from scripts.run_ml_etf_risk_screen import load_inputs


def run(inputs,original,output):
    report=json.loads((original/'report.json').read_text())
    frames,sources=load_inputs(inputs)
    assert sources==report['sources']
    for filename,h in report['artifacts'].items():assert hashlib.sha256((original/filename).read_bytes()).hexdigest()==h
    if output.exists():raise FileExistsError(output)
    p=build_panel(frames);rows=[]
    for selection in report['selections']:
        year,name=selection['outer_year'],selection['candidate']
        train,val=split(p,year)
        columns=SEQUENCE if name.startswith('sequence') else SUMMARY
        experiments=[('recent25',.25,17),('recent50',.5,17)]
        if not name.startswith('ridge'):experiments += [('seed29',1.,29),('seed43',1.,43)]
        for diagnostic,fraction,seed in experiments:
            dates=np.sort(train.date.unique());keep=dates[-max(1,int(len(dates)*fraction)):]
            sub=train.loc[train.date.isin(keep)]
            model=estimator(name)
            params={k:seed for k in model.get_params() if k.endswith('random_state')}
            model.set_params(**params)
            with threadpool_limits(limits=1),warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                model.fit(sub[columns],100*sub.target)
                pr=model.predict(val[columns])/100
            rows.append({'outer_year':year,'candidate':name,'diagnostic':diagnostic,'seed':seed,
                'training_dates':len(keep),'validation_mse':float(np.mean((pr-val.target.to_numpy())**2)),
                'warnings':' | '.join(str(w.message) for w in caught)})
        print(f'{year}: fixed selection diagnostics complete',flush=True)
    output.mkdir(parents=True)
    path=output/'sensitivities.csv';pd.DataFrame(rows).to_csv(path,index=False,lineterminator='\n')
    (output/'report.json').write_text(json.dumps({'status':'DIAGNOSTICS_NO_RESELECTION','fits':len(rows),
        'source_report_sha256':hashlib.sha256((original/'report.json').read_bytes()).hexdigest(),
        'artifact_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'limitations':__doc__},indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-root',type=Path,required=True)
    p.add_argument('--original',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();run(a.input_root,a.original,a.output_dir)
