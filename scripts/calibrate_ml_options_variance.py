"""Synthetic linear-signal power probe on the prepared options panel.
Not a real-outcome forecast comparison or general bound on ML learnability.
"""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler


def run(path, repetitions=200):
    with zipfile.ZipFile(path) as z:
        report = json.loads(z.read('options_variance_preparation.json'))
        for name, sha in report['artifact_sha256'].items():
            if hashlib.sha256(z.read(name)).hexdigest() != sha:
                raise ValueError('Input hash mismatch')
        f = pd.read_csv(z.open('options_variance_anchors.csv'))
    f = f.sort_values('source_date').reset_index(drop=True)
    initial = (f.source_date < '2018-01-01').to_numpy()
    base = np.column_stack([np.log(f.rv_5), np.log(f.rv_21), np.log(f.rv_63),
                            f.return_21, np.log(f.iv_near)])
    extra = f[['iv_far','put_call_skew','iv_term_slope','gamma_strike_concentration',
               'front_gamma_share','log_gamma_z252']].to_numpy()
    # Construct one fixed synthetic linear alternative from geometry only.
    # Residualization and calibration use pre-2018 observations exclusively.
    scaler = StandardScaler().fit(base[initial])
    x = scaler.transform(base)
    sx = StandardScaler().fit(extra[initial])
    e = sx.transform(extra)
    geometry = e[:,3] + e[:,4] + e[:,5]
    residualizer = Ridge(alpha=10).fit(x[initial], geometry[initial])
    signal = geometry-residualizer.predict(x)
    signal /= signal[initial].std()
    ylog = np.log(f.future_variance_5.to_numpy())
    pilot = Ridge(alpha=10).fit(x[initial], ylog[initial])
    mean = pilot.predict(x)
    residuals = ylog[initial]-mean[initial]
    residuals -= residuals.mean()
    # Residual block resampling keeps some observed weekly noise dependence.
    sigma = float(residuals.std())
    folds = []
    for year in range(2018,2025):
        tr = (f.target_end < f'{year}-01-01').to_numpy()
        te = (f.source_date.str[:4] == str(year)).to_numpy()
        if tr.sum() < 100 or te.sum() < 20:
            raise ValueError('Insufficient annual fold')
        designs = []
        for features in [base, np.column_stack([base,extra])]:
            s = StandardScaler().fit(features[tr])
            a = np.column_stack([np.ones(tr.sum()),s.transform(features[tr])])
            b = np.column_stack([np.ones(te.sum()),s.transform(features[te])])
            penalty=np.diag([0]+[10]*(a.shape[1]-1))
            # Fixed Ridge linear operator, identical to refitting each label draw.
            operator=np.linalg.solve(a.T@a+penalty,a.T)
            designs.append((a,b,operator))
        folds.append((tr,te,designs))
    test_indices=np.flatnonzero(~initial)
    rng=np.random.default_rng(20260910)
    n=len(test_indices)
    # Fixed moving-block bootstrap of paired OOS loss differences (13 anchors).
    starts=rng.integers(0,n,size=(999,int(np.ceil(n/13))))
    boot=((starts[:,:,None]+np.arange(13))%n).reshape(999,-1)[:,:n]
    output=[]
    for strength in [0,.25,.5,1.0]:
        wins=0; improvements=[]; coverages=[]
        for rep in range(repetitions):
            starts=rng.integers(0,len(residuals),size=int(np.ceil(len(f)/13)))
            noise=residuals[((starts[:,None]+np.arange(13))%len(residuals)).ravel()[:len(f)]]
            synthetic_log=mean+strength*sigma*signal+noise
            prediction=np.full((len(f),2),np.nan)
            for tr,te,designs in folds:
                for j,(a,b,op) in enumerate(designs):
                    coef=op@synthetic_log[tr]
                    # Training-only log-to-level smearing correction.
                    smear=np.log(np.exp(synthetic_log[tr]-a@coef).mean())
                    prediction[te,j]=b@coef+smear
            log_ratio=synthetic_log[test_indices,None]-prediction[test_indices]
            loss=np.exp(log_ratio)-log_ratio-1
            diff=loss[:,0]-loss[:,1]
            reduction=float(diff.mean()/loss[:,0].mean())
            lower=float(np.quantile(diff[boot].mean(axis=1),.025))
            yearly=[float(diff[f.source_date.iloc[test_indices].str[:4].to_numpy()==str(y)].mean()) for y in range(2018,2025)]
            passes=reduction>=.05 and lower>0 and sum(v>0 for v in yearly)>=4
            wins+=passes;improvements.append(reduction);coverages.append(lower)
        output.append(dict(signal_sd_in_training_noise_units=strength,repetitions=repetitions,
                           gate_passes=wins,gate_pass_fraction=wins/repetitions,
                           monte_carlo_standard_error=float(np.sqrt((wins/repetitions)*(1-wins/repetitions)/repetitions)),
                           median_relative_qlike_improvement=float(np.median(improvements))))
    return dict(status='SYNTHETIC_LINEAR_ALTERNATIVE_CALIBRATION_ONLY',
                input_zip_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                training_anchors=int(initial.sum()),evaluation_anchors=n,
                evaluation_years=list(range(2018,2025)),training_log_residual_sd=sigma,
                real_oos_target_values_used_for_calibration=False,
                real_outcome_model_comparison_performed=False,
                seed=20260910,block_length_anchors=13,bootstrap_repetitions=999,
                gate='>=5% QLIKE reduction, positive in >=4/7 years, paired block 95% lower bound >0',
                limitations=['Only a constructed linear geometry alternative; not a nonlinear learning-power claim',
                             'Effect sizes are scenarios, not empirically established plausible effects',
                             'Noise assumes pre-2018 residual blocks represent future uncertainty',
                             'Missing feature dates limit the inference to complete anchors',
                             'Does not establish a campaign power gate without a justified central effect'],
                scenarios=output)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-zip',type=Path,required=True)
    p.add_argument('--output-json',type=Path,required=True)
    a=p.parse_args()
    if a.output_json.exists():raise ValueError('Refusing overwrite')
    result=run(a.input_zip)
    a.output_json.parent.mkdir(parents=True,exist_ok=True)
    a.output_json.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
