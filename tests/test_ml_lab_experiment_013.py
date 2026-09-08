import json
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from scripts import run_ml_lab_experiment_013 as exp
from tests import test_ml_lab_experiment_012 as fixtures


def test_disposition_all_branches_and_equality():
    rows=[]
    for memory in exp.ref.MEMORIES:
        for baseline in exp.BASELINES:
            for period in ['pre_2022','post_2022_2024','2021','2022']:
                rows.append(dict(memory_scheme=memory,comparison='price_ridge_minus_'+baseline,
                                 outcome='target_raw',period=period,mean_ic=.1,mean_spread=.1))
    s=pd.DataFrame(rows)
    assert exp.classify(s)['classification']=='EXPLORATORY_BASELINE_INCREMENT_RECURRENT'
    s.loc[s.memory_scheme=='expanding','mean_ic']=0
    assert exp.classify(s)['classification']=='MEMORY_DEPENDENT_BASELINE_INCREMENT'
    s.loc[s.period=='2021','mean_ic']=0
    assert exp.classify(s)['classification']=='NO_STABLE_PRIMARY_BASELINE_INCREMENT'


def test_tie_order_attribution_and_persistence():
    parts=[]
    for year in [2021,2022]:
        for model in ['price_ridge',*exp.BASELINES]:
            parts.append(pd.DataFrame(dict(memory_scheme='trailing_3y',test_year=year,
                timestamp=pd.Timestamp(f'{year}-01-01',tz='UTC'),ticker=exp.ref.exp5.UNIVERSE,
                model=model,score=[0]*7+[1]*7,target_raw=np.arange(14),forward_return=np.arange(14)/100)))
    p=pd.concat(parts,ignore_index=True)
    tables=exp.audit(p)
    shuffled=exp.audit(p.sample(frac=1,random_state=3))
    for k in tables:
        pd.testing.assert_frame_equal(tables[k],shuffled[k])
    a=tables['asset_contributions'].groupby(exp.KEYS+['model','outcome']).contribution.sum()
    b=tables['anchor_metrics'].set_index(exp.KEYS+['model','outcome']).spread
    np.testing.assert_allclose(a.sort_index(),b.sort_index())
    assert (tables['selection_persistence'].retained_fraction==1).all()
    p.loc[p.model=='price_ridge','score']=1
    with pytest.raises(ValueError,match='UNDEFINED_(IC|AGREEMENT)'):
        exp.audit(p)


def test_real_pipeline_no_fit_replay_and_corruption(tmp_path):
    fixtures.SyntheticRunnerTests.setUpClass()
    try:
        root=fixtures.SyntheticRunnerTests.root
        manifest=fixtures.SyntheticRunnerTests.manifest
        with patch.object(exp.ref.Ridge,'fit',side_effect=AssertionError('No refit allowed')):
            one=exp.run(root,manifest,tmp_path/'one',synthetic=True)
            two=exp.run(root,manifest,tmp_path/'two',synthetic=True)
        assert one==two and one['fits']==0
        assert len(one['artifact_files'])==11
        for name in [*one['artifact_files'].values(),'experiment_013_report.json']:
            assert (tmp_path/'one'/name).read_bytes()==(tmp_path/'two'/name).read_bytes()
        with pytest.raises(ValueError,match='OUTPUT_DIRECTORY_ALREADY_EXISTS'):
            exp.run(root,manifest,tmp_path/'one',synthetic=True)
        data=json.loads(manifest.read_text());data['inputs'][0]['sha256']='0'*64
        manifest.write_text(json.dumps(data))
        with pytest.raises(ValueError,match='HASH_MISMATCH'):
            exp.run(root,manifest,tmp_path/'bad',synthetic=True)
        assert not (tmp_path/'bad').exists()
    finally:
        fixtures.SyntheticRunnerTests.tearDownClass()
