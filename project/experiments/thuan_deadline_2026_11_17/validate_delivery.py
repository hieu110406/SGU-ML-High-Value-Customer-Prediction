"""Validate real outputs against inputs, selected grids, and serialized models."""
import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score, silhouette_score
from threadpoolctl import threadpool_limits

import run_experiments as r


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--experiment',nargs='+',choices=r.EXPECTED,default=r.EXPECTED)
    args=parser.parse_args()
    scope=r.assignments()
    assert scope.experiment.tolist()==r.EXPECTED
    assert scope.assignee.eq('Thuận').all() and scope.deadline_utc.eq(r.DEADLINE).all()
    assert r.sha256(r.ROOT/'data/raw/Online Retail.xlsx')==r.RAW_HASH
    features=pd.read_csv(r.HERE/'shared/customer_rfm.csv',dtype={'CustomerID':str})
    x=features[r.FEATURES]
    provenance=json.loads((r.HERE/'shared/provenance.json').read_text(encoding='utf-8'))
    assert len(features)==provenance['customers']==4327
    assert all(c['mismatched_customers']==0 for c in provenance['rfm_checks'])
    # Audit formulas independently of the pipeline's fitted transformation.
    sample=x.iloc[:20].to_numpy(float)
    mixed=r.log_fm(sample)
    np.testing.assert_array_equal(mixed[:,0],sample[:,0])
    np.testing.assert_allclose(mixed[:,1:],np.log1p(sample[:,1:]))
    np.testing.assert_array_equal(sample,x.iloc[:20].to_numpy(float))
    for config in ['A01','A02','A03','A04','B02','B03','B04']:
        prep,z,d=r.transform(config,x)
        if config=='A02':assert z.shape[1]==3 and 'pca' not in prep.named_steps
        if config=='A03':assert z.shape[1]==2
        if config=='B03':assert not prep['transform'].standardize and len(prep['transform'].lambdas_)==3
        if config=='B04':
            transformed=prep['scaler'].transform(np.log1p(x.to_numpy()))
            np.testing.assert_allclose(transformed.min(axis=0),0,atol=1e-12)
            np.testing.assert_allclose(transformed.max(axis=0),1,atol=1e-12)
        target=r.CONFIGS[config][2]
        if isinstance(target,float):assert d['pca_explained_variance_total']>=target-1e-12
    checked=[];pending=[]
    for exp in args.experiment:
        folder=r.HERE/'results'/exp
        if not (folder/'parameters.json').exists():
            raise AssertionError('Missing experiment: '+exp)
        p=json.loads((folder/'parameters.json').read_text(encoding='utf-8'))
        assert p['status']=='completed',p
        labels=pd.read_csv(folder/'labels.csv',dtype={'CustomerID':str})
        assert labels.CustomerID.equals(features.CustomerID)
        np.testing.assert_allclose(labels[r.FEATURES],x,atol=1e-8,rtol=0)
        pipeline=joblib.load(folder/'pipeline.joblib');z=pipeline['preprocessing'].transform(x)
        saved=pd.read_csv(folder/'model_input.csv',dtype={'CustomerID':str})
        assert saved.CustomerID.equals(features.CustomerID)
        np.testing.assert_allclose(z,saved.filter(like='input_').to_numpy(),atol=1e-9,rtol=0)
        lab=labels.cluster.to_numpy()
        if exp.endswith('-DB'):
            best=p['selected'];fitted=r.DBSCAN(eps=best['eps'],min_samples=int(best['min_samples'])).fit_predict(z)
            assert adjusted_rand_score(lab,fitted)==1
            assert p['preprocessing']['pca_requested'] is None if exp=='A02-DB' else p['preprocessing']['pca_requested']==.9
            assert best['noise_pct']<=5
        else:np.testing.assert_array_equal(lab,pipeline.predict(x))
        evaluation=z
        if exp.endswith('-GN'):
            from gnn_model import torch_api, link_metrics
            model=pipeline['model'];torch=torch_api()
            embedding=pd.read_csv(folder/'embeddings.csv',dtype={'CustomerID':str})
            assert embedding.CustomerID.equals(features.CustomerID)
            np.testing.assert_allclose(model.embeddings_,embedding.filter(like='embedding_'),atol=1e-12)
            np.testing.assert_allclose(model.recompute_embeddings(),model.embeddings_,atol=1e-7,rtol=0)
            state=torch.load(folder/'encoder_state.pt',map_location='cpu',weights_only=True)
            for key,value in model.state_dict_.items():np.testing.assert_array_equal(state[key].numpy(),value)
            split=np.load(folder/'graph_splits.npz')
            n=len(features)
            def edge_ids(name):
                edges=split[name]
                assert ((edges[:,0]<edges[:,1])&(edges>=0).all(axis=1)&(edges<n).all(axis=1)).all()
                ids=set((edges[:,0]*n+edges[:,1]).tolist())
                assert len(ids)==len(edges)
                return ids
            pos=[edge_ids(k) for k in ['train_positive','validation_positive','test_positive']]
            neg=[edge_ids(k) for k in ['validation_negative','test_negative','last_train_negative']]
            assert not(pos[0]&pos[1] or pos[0]&pos[2] or pos[1]&pos[2])
            assert not(set.union(*pos)&set.union(*neg))
            assert not(neg[0]&neg[1] or neg[0]&neg[2] or neg[1]&neg[2])
            assert len(pos[1])==len(neg[0]) and len(pos[2])==len(neg[1])
            actual_link=link_metrics(torch.tensor(model.embeddings_,dtype=torch.float32),split['test_positive'],split['test_negative'])
            for metric,value in actual_link.items():assert np.isclose(value,p['gnn_training']['test_link_metrics'][metric],atol=1e-12)
            hist=pd.read_csv(folder/'training_history.csv')
            epoch=int(p['gnn_training']['best_epoch'])
            assert np.isclose(hist.loc[hist.epoch==epoch,'validation_link_bce'].iloc[0],p['gnn_training']['best_validation_bce'],atol=1e-10)
            assert p['gnn_training']['best_validation_bce']<p['gnn_training']['initial_validation_bce']
            # Known-node inference must fail instead of silently predicting on a changed graph.
            try:model.predict(z[::-1])
            except ValueError:pass
            else:raise AssertionError('GNN accepted reordered nodes')
            assert p['actual_model']=='GNNClustering' and 'bic' not in p['selected']
            evaluation=model.embeddings_
        mask=lab!=-1
        actual=silhouette_score(evaluation[mask],lab[mask])
        assert np.isclose(actual,p['selected']['silhouette'],atol=1e-10,rtol=0)
        grid=pd.read_csv(folder/'search.csv');eligible=grid[grid.eligible]
        assert np.isclose(actual,eligible.silhouette.max(),atol=1e-10,rtol=0)
        prof=pd.read_csv(folder/'profiles.csv')
        assert prof.customers.sum()==len(features)
        assert np.isclose(prof.monetary_pct.sum(),100,atol=1e-8)
        for name in ['clusters.png','profiles.png','search.png']:
            assert (folder/'figures'/name).stat().st_size>1000
        checked.append(exp)
    result={'passed':True,'checked':checked,'pending':[e for e in r.EXPECTED if e not in checked],'customers':len(features),
            'raw_sha256':r.RAW_HASH,'checks':'scope, raw hash, RFM provenance, transforms, PCA, full-data Silhouette, search optimum, reloaded models, GNN weight replay, disjoint edge splits and negatives, held-out link metrics, validation checkpoint, node-order rejection, DBSCAN replay, profiles, workbook'}
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    with threadpool_limits(limits=1):main()
