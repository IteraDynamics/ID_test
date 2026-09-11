"""Bounded, exploratory decision-layer diagnostic; no production integration."""
import argparse
import json
import platform
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import sklearn
from scipy.optimize import minimize

from research.ml_development import incremental as inc
from research.ml_development import portfolio as port

SPEC = Path('docs/research/ML_DECISION_ALIGNMENT_SPEC_20260911.md')
REFERENCE = Path('docs/research/evidence/ml_incremental_information_20260910/report.json')
POLICIES = [f'{kind}:{v}' for kind in ('opt', 'gate') for v in inc.VARIANTS] + ['equal', 'bil', 'hold']


def aligned_panel(frames):
    q = inc.panel(frames)
    dates = frames['SPY'].index
    origin = dates.get_loc(q.date.min())
    q['weekly'] = (dates.get_indexer(q.date) - origin) % 5 == 0
    active = q[q.weekly]
    offsets = dates.get_indexer(active.label_end) - dates.get_indexer(active.date)
    if not (offsets == 6).all():
        raise ValueError('Label must mature six sessions after signal')
    return q


def feasible(w, cov, tol=1e-8):
    return (np.isfinite(w).all() and abs(w.sum()-1) <= tol and w.min() >= -tol
            and w[:8].max() <= .25+tol and w[:8].sum() <= .75+tol
            and w@cov@w <= .01+tol)


def utility(w, mu, cov, current, cost):
    return float(mu@w - 1.5*(5/252)*(w@cov@w) - cost*np.abs(w-current).sum())


def optimize(mu, cov, current, cost):
    """Convex quadratic/L1 program. Current weights include BIL, exclude cash."""
    mu, cov, current = map(np.asarray, (mu, cov, current))
    if mu.shape != (9,) or current.shape != (9,) or cov.shape != (9,9):
        raise ValueError('Optimizer dimensions')
    if not all(np.isfinite(x).all() for x in (mu,cov,current)) or cost < 0:
        raise ValueError('Nonfinite optimizer inputs')
    if not np.allclose(cov,cov.T) or np.linalg.eigvalsh(cov).min() < -1e-10:
        raise ValueError('Covariance is not positive semidefinite')
    start = current.copy() if feasible(current,cov) else np.r_[np.zeros(8),1.]
    if not feasible(start,cov):
        raise ValueError('No feasible cash-proxy start')
    scale = 100.
    def fun(x):
        w=x[:9]
        return scale*(-mu@w + 1.5*(5/252)*(w@cov@w) + cost*x[9:].sum())
    def jac(x):
        return scale*np.r_[-mu+3*(5/252)*cov@x[:9],np.full(9,cost)]
    # Slack variables bound absolute asset trades, including changes in BIL.
    a = np.block([[-np.eye(9),np.eye(9)],[np.eye(9),np.eye(9)]])
    offset = np.r_[current,-current]
    constraints = [
        {'type':'eq','fun':lambda x:x[:9].sum()-1,'jac':lambda x:np.r_[np.ones(9),np.zeros(9)]},
        {'type':'ineq','fun':lambda x:a@x+offset,'jac':lambda x:a},
        {'type':'ineq','fun':lambda x:1.-(x[:9]@cov@x[:9])/.01,
         'jac':lambda x:np.r_[-2*cov@x[:9]/.01,np.zeros(9)]},
    ]
    result = minimize(fun,np.r_[start,np.abs(start-current)],jac=jac,method='SLSQP',
                      bounds=[(0,.25)]*8+[(.25,1)]+[(0,None)]*9,
                      constraints=constraints,options={'maxiter':300,'ftol':1e-8})
    w=result.x[:9]
    if not result.success or not feasible(w,cov) or (a@result.x+offset).min() < -1e-8:
        raise ValueError(f'Optimizer failure: {result.message}; variance={w@cov@w}')
    baseline = utility(start,mu,cov,current,cost)
    gain = utility(w,mu,cov,current,cost)-baseline
    if gain < -1e-8:
        raise ValueError('Optimizer worse than feasible starting candidate')
    hold = feasible(current,cov) and utility(w,mu,cov,current,cost) <= utility(current,mu,cov,current,cost)+1e-10
    if hold:
        w=current.copy()
    return w, bool(hold), dict(iterations=int(result.nit),gain_vs_start=max(0.,gain),
                              variance=float(w@cov@w),weight_sum=float(w.sum()))


def simulate(frames, forecasts, policy, cost, replay=None):
    """Close decisions -> next-open orders -> self-financing daily ledger."""
    dates=frames['SPY'].index
    opens=np.column_stack([frames[a].open for a in port.ALL_ASSETS])
    closes=np.column_stack([frames[a].close for a in port.ALL_ASSETS])
    grouped={dates.get_loc(d):g.set_index('asset').loc[list(inc.b.ASSETS)] for d,g in forecasts.groupby('date')}
    signals=sorted(grouped)
    if len(signals)>1 and not (np.diff(signals)==5).all():
        raise ValueError('Noncontiguous five-session grid')
    start=signals[0]+1
    end=dates.get_loc(forecasts.label_end.max())
    if end != signals[-1]+6 or end >= len(dates):
        raise ValueError('Exit does not match final forecast')
    h=np.zeros(9); cash=nav=1.; last=opens[start]
    rows=[]; decisions=[]; orders={}
    def choose(s):
        nonlocal orders
        if replay is not None:
            if s+1 in replay:orders[s+1]=replay[s+1].copy()
            return
        current=h*closes[s]/(cash+(h*closes[s]).sum())
        cov=port.covariance(closes,s)
        hold=False;info={}
        if policy.startswith('opt:'):
            v=policy.split(':',1)[1];mu=np.r_[grouped[s][v].to_numpy(),0.]
            w,hold,info=optimize(mu,cov,current,cost)
        elif policy.startswith('gate:'):
            v=policy.split(':',1)[1]
            w=port.limit_risk(inc.gated(grouped[s][v].to_numpy(),cost),cov)
        elif policy=='bil':
            w=np.r_[np.zeros(8),1.]
            hold=bool(h[8]>0)
        elif policy in ('equal','hold'):
            w=port.limit_risk(np.full(8,.75/8),cov)
            hold=policy=='hold' and s!=signals[0]
        else:
            raise ValueError(policy)
        if hold:w=current.copy()
        elif not feasible(w,cov):raise ValueError('Infeasible target')
        if not hold:orders[s+1]=w.copy()
        decisions.append(dict(date=dates[s],no_trade=hold,forecast_volatility=float(np.sqrt(w@cov@w)),
                              incumbent_feasible=feasible(current,cov),**info,**dict(zip(port.ALL_ASSETS,w))))
    choose(signals[0])
    for i in range(start,end+1):
        fees=np.zeros(9);traded=np.zeros(9);before=cash+(h*opens[i]).sum()
        contribution=h*(opens[i]-last)
        if i==end:
            target=np.zeros(9)
        else:
            target=orders.get(i)
        if target is not None:
            h,cash,fees,traded,before=port.rebalance(h,cash,opens[i],target,cost)
        contribution+=h*(closes[i]-opens[i])-fees
        values=h*closes[i];new=cash+values.sum();ret=new/nav-1
        if cash < -1e-12 or new <= 0 or abs(contribution.sum()/nav-ret)>1e-10:
            raise ValueError('Daily accounting failure')
        row=dict(date=dates[i],nav=new,return_value=ret,turnover=traded.sum()/before,cost=fees.sum(),
                 exposure=values[:8].sum()/new,cash_fraction=(values[8]+cash)/new,
                 bil_fraction=values[8]/new,settlement_cash=cash)
        row.update({a+'_contribution':contribution[j]/nav for j,a in enumerate(port.ALL_ASSETS)})
        rows.append(row);nav=new;last=closes[i]
        if i in grouped:choose(i)
    if np.abs(h).sum()>1e-12:raise ValueError('Terminal liquidation')
    return pd.DataFrame(rows).rename(columns={'return_value':'return'}),pd.DataFrame(decisions),orders


def judge(fm, em):
    mse=fm[fm.asset=='pooled'].pivot(index='scope',columns='variant',values='mse')
    years=[str(y) for y in range(2018,2025)];result={}
    for model in inc.MODELS:
        name='cal_'+model;static='static_'+model
        checks={f'mse_{t}':bool(mse.loc[t,name]<min(mse.loc[t,'mean'],mse.loc[t,static])) for t in ['all','excluding_2020']}
        checks['mse_year_majority']=bool((mse.loc[years,name]<mse.loc[years,'mean']).sum()>=4)
        for scenario in ['cost10','cost25','fixed_cost25']:
            e=em[em.scenario==scenario].pivot(index='period',columns='policy',values='ce')
            for t in ['all','excluding_2020']:
                checks[f'ce_{scenario}_{t}']=bool(e.loc[t,'opt:'+name]>e.loc[t,['opt:mean','equal','bil','hold']].max())
            if scenario=='cost10':checks['ce_year_majority']=bool((e.loc[years,'opt:'+name]>e.loc[years,'opt:mean']).sum()>=4)
        result[model]={'checks':checks,'passes':all(checks.values())}
    return result


def run(root,out,cached=None):
    if out.exists():raise FileExistsError(out)
    frames,sources=port.inputs(root)
    if sources!=json.loads(REFERENCE.read_text())['sources']:raise ValueError('Original input identity mismatch')
    q=aligned_panel(frames)
    out.mkdir(parents=True)
    identity={'spec_sha256':port.sha(SPEC),'sources':sources,'parent_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              'environment':dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__,sklearn=sklearn.__version__),
              'code':{str(x):port.sha(x) for x in [Path(__file__),Path(inc.__file__),Path(inc.b.__file__),Path(port.__file__),Path('research/ml_development/breadth_inputs.py'),Path('scripts/run_ml_etf_risk_screen.py')]}}
    (out/'identity_before_fits.json').write_text(json.dumps(identity,indent=2)+'\n')
    if cached is None:
        f=inc.forecasts(q,out)
    else:
        old=json.loads((cached/'identity_before_fits.json').read_text())
        if old['sources']!=sources or old['spec_sha256']!=identity['spec_sha256']:
            raise ValueError('Cached forecast source/spec mismatch')
        for path, digest in old['code'].items():
            if path!=str(Path(__file__)) and port.sha(path)!=digest:
                raise ValueError('Cached forecast dependency mismatch')
        identity['cached_forecast_identity']=old
        identity['cached_files']={}
        for name in ['forecasts.csv','fits.csv','calibration.csv']:
            source=cached/name
            identity['cached_files'][name]=port.sha(source)
            (out/name).write_bytes(source.read_bytes())
        f=pd.read_csv(out/'forecasts.csv',float_precision='round_trip',parse_dates=['date','label_end'])
        expected=q[q.weekly & q.date.dt.year.between(2018,2024)][['date','asset','label_end','target','bil_target']].reset_index(drop=True)
        pd.testing.assert_frame_equal(f[expected.columns],expected)
    fm=inc.forecast_metrics(f);fm.to_csv(out/'forecast_metrics.csv',index=False)
    fit=pd.read_csv(out/'fits.csv')
    if len(fit)!=42 or not (pd.to_datetime(fit.last_training_outcome)<pd.to_datetime(fit.first_validation_signal)).all():raise ValueError('Fit boundary failure')
    days=[];weights=[];fixed={}
    for scenario,cost in [('cost10',.001),('cost25',.0025),('fixed_gross',0.),('fixed_cost25',.0025)]:
        for policy in POLICIES:
            replay=fixed[policy] if scenario.startswith('fixed') else None
            d,w,orders=simulate(frames,f,policy,cost,replay)
            if scenario=='cost10':fixed[policy]=orders
            d['policy']=policy;d['scenario']=scenario;days.append(d)
            if len(w):w['policy']=policy;w['scenario']=scenario;weights.append(w)
        print(f'{scenario}: seventeen reconciled ledgers complete',flush=True)
        pd.concat(days,ignore_index=True).to_csv(out/'daily_ledger.csv',index=False)
    d=pd.concat(days,ignore_index=True);w=pd.concat(weights,ignore_index=True)
    w.to_csv(out/'target_weights.csv',index=False)
    orders=[dict(policy=name,execution_session=s,execution_date=frames['SPY'].index[s],**dict(zip(port.ALL_ASSETS,v))) for name,sch in fixed.items() for s,v in sorted(sch.items())]
    pd.DataFrame(orders).to_csv(out/'cost10_orders.csv',index=False)
    em=port.summaries(d);em.to_csv(out/'economic_metrics.csv',index=False)
    result=judge(fm,em)
    report=dict(**identity,status='EXPLORATORY_DECISION_ALIGNMENT',model_fits=42,new_model_fits=42 if cached is None else 0,ledgers=68,
                signals=int(f.date.nunique()),first_signal=str(f.date.min()),last_label=str(f.label_end.max()),
                reserved_2025_used=False,consistency=result,decision='CONTINUE_RESEARCH' if any(r['passes'] for r in result.values()) else 'CLOSE_THIS_ETF_ALPHA_DESIGN',
                files={x.name:port.sha(x) for x in out.glob('*.csv')},
                limitations='Repeatedly inspected development sample; descriptive criteria, no significance/power or promotion claim. Close-target risk and marginal cost approximations; next-open fills; historical adjusted prices; no-change control can drift beyond limits.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--input-root',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--cached-forecasts',type=Path)
    args=parser.parse_args();run(args.input_root,args.output_dir,args.cached_forecasts)
