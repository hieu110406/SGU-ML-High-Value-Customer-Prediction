"""Reproduce only Thuận's experiments at the exact deadline in the source workbook."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import tempfile
import warnings
from pathlib import Path

import joblib
os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir())/'thuan_mplconfig'))
os.environ.setdefault('XDG_CACHE_HOME', str(Path(tempfile.gettempdir())/'thuan_cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import openpyxl
import pandas as pd
from sklearn.cluster import DBSCAN, KMeans
from sklearn.decomposition import PCA
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import (adjusted_rand_score, calinski_harabasz_score,
    davies_bouldin_score, pairwise_distances, silhouette_score)
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, MinMaxScaler, PowerTransformer, StandardScaler
from threadpoolctl import threadpool_limits

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEADLINE = '2026-11-17T21:00:00.000Z'
RAW_HASH = '43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d'
FEATURES = ['Recency', 'Frequency', 'Monetary']
EXPECTED = ['A01-GN', 'A02-DB', 'A03-GN', 'A04-KM', 'B02-DB', 'B03-GN', 'B04-KM']
CONFIGS = {
    'A01': ('none', 'standard', .90), 'A02': ('none', 'standard', None),
    'A03': ('none', 'standard', 2), 'A04': ('none', 'standard', .95),
    'B01': ('log_all', 'standard', .90), 'B02': ('log_fm', 'standard', .90),
    'B03': ('yeo_johnson', 'standard', .90), 'B04': ('log_all', 'minmax', .90),
}
PARENTS = {'A01': None, 'A02': 'A01', 'A03': 'A01', 'A04': 'A01',
           'B02': 'B01', 'B03': 'B01', 'B04': 'B01'}
SPECIAL_CODES = {'POST', 'DOT', 'M', 'C2', 'C3', 'D', 'S', 'B', 'BANK CHARGES',
                 'ADJUST', 'ADJUST2', 'AMAZONFEE', 'CRUK', 'TEST001', 'TEST002'}


def log_fm(x):
    """Top-level function: joblib artifacts can be loaded by this module."""
    x = np.asarray(x, dtype=float).copy()
    x[:, 1:] = np.log1p(x[:, 1:])
    return x


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_safe(value):
    if isinstance(value, dict): return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [json_safe(v) for v in value]
    if isinstance(value, np.ndarray): return json_safe(value.tolist())
    if isinstance(value, np.generic): return json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value): return None
    return value


def write_json(path, value):
    Path(path).write_text(json.dumps(json_safe(value), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def assignments():
    w = openpyxl.load_workbook(HERE/'references/chienluocmodel_cap_nhat.xlsx', data_only=True)
    s = w['người nào chạy']
    rows = []
    for r in s.iter_rows(min_row=6, values_only=True):
        if str(r[4]).strip() == 'Thuận' and r[5] == DEADLINE:
            rows.append({'experiment': r[0], 'configuration': r[1], 'model_in_workbook': r[3],
                         'assignee': r[4], 'deadline_utc': r[5]})
    if [r['experiment'] for r in rows] != EXPECTED:
        raise ValueError('Assignments differ from the reviewed scope; inspect the source workbook.')
    for row in rows:
        expected_model={'GN':'GNN','KM':'KMeans','DB':'DBSCAN'}[row['experiment'].split('-')[1]]
        assert row['model_in_workbook']==expected_model, 'Model differs from the reviewed workbook'
    strategy={r[0]:r for r in w['những thí nghiệm'].iter_rows(min_row=6,values_only=True) if r[0]}
    transform_names={'none':None,'log_all':'log1p R,F,M','log_fm':'log1p F,M; giữ R',
                     'yeo_johnson':'Yeo–Johnson, standardize=False'}
    for config in {r['configuration'] for r in rows}|{'B01'}:
        kind,scale,pca=CONFIGS[config];spec=strategy[config]
        assert spec[3]=='RFM' and spec[4]==transform_names[kind]
        assert spec[5]==('Standard' if scale=='standard' else 'MinMax')
        assert spec[6]==({None:'Không',2:'2 PC',.9:'90%',.95:'95%'}[pca])
    return pd.DataFrame(rows)


def prepare_input():
    """Rebuild the group's 4,327-customer RFM from the sole approved raw source."""
    p = ROOT/'data/raw/Online Retail.xlsx'
    if sha256(p) != RAW_HASH: raise ValueError('Raw SHA-256 mismatch')
    raw = pd.read_excel(p, sheet_name='Online Retail')
    audit = []
    def record(name, frame):
        audit.append({'step': name, 'rows': len(frame), 'documents': frame.InvoiceNo.nunique(),
                      'customers_with_id': frame.CustomerID.nunique()})
    record('raw', raw)
    d = raw.copy()
    for c in ['Description', 'InvoiceNo', 'StockCode']:
        d[c] = d[c].fillna('Unknown Product').astype(str).str.strip().str.upper()
    d['Country'] = d.Country.astype(str).str.strip().replace({'EIRE':'Ireland'})
    record('normalize strings; fill Description', d)
    d = d.drop_duplicates(); record('drop duplicate normalized rows', d)
    d = d[~d.InvoiceNo.str.startswith('C')]; record('exclude cancellation documents', d)
    d = d[(d.Quantity > 0) & (d.UnitPrice > 0)]; record('positive quantity and price', d)
    d = d[~d.StockCode.isin(SPECIAL_CODES)]; record('exclude documented special stock codes', d)
    outlier = pd.Series(False, index=d.index)
    bounds = []
    for c in ['Quantity','UnitPrice']:
        x = np.log1p(d[c]); q1,q3 = x.quantile([.25,.75]); iqr = q3-q1
        low,high = q1-3*iqr,q3+3*iqr
        outlier |= (x < low) | (x > high)
        bounds.append({'feature':c,'space':'log1p','q1':q1,'q3':q3,'lower':low,'upper':high})
    d = d[~outlier]; record('exclude joint log1p 3-IQR transaction outliers', d)
    d = d[d.CustomerID.notna()].copy(); record('exclude missing CustomerID', d)
    d['CustomerID'] = d.CustomerID.astype(int).astype(str)
    d['Revenue'] = d.Quantity*d.UnitPrice
    g = d.groupby('CustomerID', sort=True)
    rfm = pd.DataFrame({'Recency':(pd.Timestamp('2011-12-10')-g.InvoiceDate.max().dt.normalize()).dt.days,
                       'Frequency':g.InvoiceNo.nunique(),'Monetary':g.Revenue.sum()}).reset_index()
    assert rfm.CustomerID.is_unique and not rfm[FEATURES].isna().any().any()
    assert (rfm[FEATURES]>0).all().all()
    assert np.isclose(rfm.Monetary.sum(), d.Revenue.sum(), atol=1e-6, rtol=0)
    shared_path = ROOT/'notebooks/02_baseline_kmeans/12-11-2026-hieu-kmeans/data/customer_features.csv'
    shared = pd.read_csv(shared_path,dtype={'CustomerID':str}).sort_values('CustomerID').reset_index(drop=True)
    assert rfm.CustomerID.equals(shared.CustomerID), 'Customer set differs from the group reference'
    checks = [{'feature':c,'max_abs_error':float((rfm[c]-shared[c]).abs().max()),
               'mismatched_customers':int((~np.isclose(rfm[c],shared[c],atol=1e-6,rtol=0)).sum())} for c in FEATURES]
    assert all(c['mismatched_customers']==0 for c in checks), 'RFM differs from group reference'
    common = HERE/'shared'; common.mkdir(exist_ok=True)
    rfm.to_csv(common/'customer_rfm.csv',index=False)
    log = pd.DataFrame(audit); log['removed_since_previous']=(-log.rows.diff()).fillna(0).astype(int)
    log.to_csv(common/'cleaning_log.csv',index=False)
    provenance = {'raw_path':'data/raw/Online Retail.xlsx','raw_sha256':RAW_HASH,'raw_rows':len(raw),
                  'clean_rows':len(d),'customers':len(rfm),'reference_date':'2011-12-10',
                  'reference_rfm_sha256':sha256(shared_path),'rfm_checks':checks,
                  'outlier_bounds':bounds,'special_stock_codes':sorted(SPECIAL_CODES),
                  'note':'Experimental reproduction of the group RFM, not an official cleaning policy.'}
    write_json(common/'provenance.json',provenance)
    return rfm,log,provenance


def transform(config, x):
    kind,scale,pca = CONFIGS[config]
    steps=[]
    if kind=='log_all': steps.append(('transform',FunctionTransformer(np.log1p,validate=True)))
    elif kind=='log_fm': steps.append(('transform',FunctionTransformer(log_fm,validate=True)))
    elif kind=='yeo_johnson': steps.append(('transform',PowerTransformer(method='yeo-johnson',standardize=False)))
    steps.append(('scaler', StandardScaler() if scale=='standard' else MinMaxScaler()))
    if pca is not None: steps.append(('pca',PCA(n_components=pca,svd_solver='full')))
    prep=Pipeline(steps)
    z=prep.fit_transform(x)
    assert np.isfinite(z).all()
    details={'configuration':config,'transform':kind,'scaler':type(prep['scaler']).__name__,
             'pca_requested':pca,'model_input_dimensions':z.shape[1]}
    if 'pca' in prep.named_steps:
        pc=prep['pca']; details.update(pca_explained_variance_ratio=pc.explained_variance_ratio_,
            pca_explained_variance_total=float(pc.explained_variance_ratio_.sum()),pca_components=pc.components_)
    if kind=='yeo_johnson': details['yeo_johnson_lambdas']=prep['transform'].lambdas_
    return prep,z,details


def scores(z,labels,distances=None):
    mask=labels!=-1; lab=labels[mask]; zz=z[mask]
    sizes=pd.Series(lab).value_counts()
    out={'n_clusters':len(sizes),'noise_pct':float(100*(~mask).mean()),
         'smallest_cluster':int(sizes.min()) if len(sizes) else 0,
         'largest_cluster_pct_all':float(100*sizes.max()/len(labels)) if len(sizes) else 0,
         'silhouette':None,'dbi':None,'chi':None}
    if 2<=len(sizes)<len(lab):
        if distances is None: sil=silhouette_score(zz,lab)
        else:
            dm=distances if mask.all() else distances[np.ix_(mask,mask)]
            sil=silhouette_score(dm,lab,metric='precomputed')
        out.update(silhouette=float(sil),dbi=float(davies_bouldin_score(zz,lab)),
                   chi=float(calinski_harabasz_score(zz,lab)))
    return out


def fit_model(family,params,z):
    if family=='KM': return KMeans(n_clusters=int(params['k']),random_state=42,n_init=20).fit(z)
    if family=='DB': return DBSCAN(eps=float(params['eps']),min_samples=int(params['min_samples'])).fit(z)
    if family=='GN':
        from gnn_model import GNNClustering
        return GNNClustering(n_clusters=int(params['k'])).fit(z)
    raise ValueError(family)


def predict_labels(family,model,z):
    return model.predict(z) if family=='GN' else model.labels_


def search(family,z):
    if family=='GN':
        from gnn_model import GNNClustering
        model=GNNClustering().fit_encoder(z)
        embeddings=model.embeddings_
        distances=pairwise_distances(embeddings,n_jobs=1);np.fill_diagonal(distances,0)
        rows=[]
        for k in range(2,11):
            model.select_clusters(k)
            rows.append({'k':k,**scores(embeddings,model.labels_,distances),'inertia':float(model.clusterer_.inertia_)})
        grid=pd.DataFrame(rows)
        grid['eligible']=grid.silhouette.notna()&(grid.smallest_cluster>=math.ceil(.01*len(z)))
        valid=grid[grid.eligible].sort_values(['silhouette','k'],ascending=[False,True])
        if valid.empty:return grid,None,None,None
        best=valid.iloc[0].to_dict();best['selected']=True
        model.select_clusters(int(best['k']))
        return grid,best,model,model.labels_
    distances=pairwise_distances(z,n_jobs=1)
    np.fill_diagonal(distances,0)
    rows=[]
    if family=='KM': candidates=[{'k':k} for k in range(2,11)]
    elif family=='DB': candidates=[{'eps':e,'min_samples':m} for m in [4,6,8,10,15,20] for e in [.1,.2,.3,.4,.5,.7,1.,1.5,2.]]
    else: raise ValueError(family)
    for params in candidates:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always',ConvergenceWarning)
            model=fit_model(family,params,z)
        labels=predict_labels(family,model,z)
        row={**params,**scores(z,labels,distances),'warnings':' | '.join(str(w.message) for w in caught)}
        if family=='KM': row['inertia']=float(model.inertia_)
        rows.append(row)
    grid=pd.DataFrame(rows)
    if family=='DB':
        grid['eligible']=(grid.n_clusters>=2)&(grid.noise_pct<=5)&grid.silhouette.notna()
        valid=grid[grid.eligible].sort_values(['silhouette','noise_pct','eps','min_samples'],ascending=[False,True,True,True])
    else:
        grid['eligible']=grid.silhouette.notna()
        valid=grid[grid.eligible].sort_values(['silhouette','k'],ascending=[False,True])
    if valid.empty: return grid,None,None,None
    best=valid.iloc[0].to_dict(); model=fit_model(family,best,z)
    labels=predict_labels(family,model,z)
    best['selected']=True
    return grid,best,model,labels


def profile(rfm,labels):
    p=rfm.assign(cluster=labels).groupby('cluster').agg(customers=('CustomerID','size'),
        Recency_median=('Recency','median'),Frequency_median=('Frequency','median'),
        Monetary_median=('Monetary','median'),Monetary_sum=('Monetary','sum'))
    p['customer_pct']=100*p.customers/len(rfm)
    p['monetary_pct']=100*p.Monetary_sum/rfm.Monetary.sum()
    return p.reset_index()


def plots(exp,family,z,labels,grid,prof,out):
    figs=out/'figures'; figs.mkdir(exist_ok=True)
    if z.shape[1]>=2: coords=z[:,:2]
    else: coords=np.column_stack([z[:,0],np.zeros(len(z))])
    fig,ax=plt.subplots(figsize=(8,5))
    for cluster in sorted(np.unique(labels)):
        mask=labels==cluster
        ax.scatter(coords[mask,0],coords[mask,1],s=12,alpha=.55,label=f'{cluster} (n={mask.sum()})',
                   marker='x' if cluster==-1 else 'o')
    space='GNN embedding' if family=='GN' else 'Model input'
    ax.set(xlabel=space+' coordinate 1',ylabel=space+' coordinate 2',title=exp+' — first 2 '+space.lower()+' dimensions')
    ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(figs/'clusters.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,4,figsize=(16,4))
    for ax,col in zip(axes,['customers','Recency_median','Frequency_median','Monetary_median']):
        ax.bar(prof.cluster.astype(str),prof[col]);ax.set_title(col);ax.set_xlabel('Cluster (-1 = noise)')
    fig.suptitle(exp+' — original RFM profiles');fig.tight_layout();fig.savefig(figs/'profiles.png',dpi=150);plt.close(fig)
    if family in ['KM','GN']:
        cols=['silhouette','dbi','inertia']
        fig,axes=plt.subplots(1,3,figsize=(14,4))
        for ax,col in zip(axes,cols):
            ax.plot(grid.k,grid[col],marker='o')
            ax.set(xlabel='k',title=col)
    else:
        fig,axes=plt.subplots(1,2,figsize=(12,4))
        for ms,g in grid.groupby('min_samples'):
            axes[0].plot(g.eps,g.silhouette,marker='.',label=str(ms));axes[1].plot(g.eps,g.noise_pct,marker='.',label=str(ms))
        axes[0].set(xlabel='eps',ylabel='Silhouette, non-noise');axes[1].set(xlabel='eps',ylabel='Noise (%)')
        axes[1].axhline(5,color='black',ls='--');axes[0].legend(title='min_samples',fontsize=7)
        fig2,ax=plt.subplots(figsize=(8,4))
        for ms in [4,6,8,10,15,20]:
            d=NearestNeighbors(n_neighbors=ms).fit(z).kneighbors(z)[0][:,-1]
            ax.plot(np.sort(d),label=str(ms))
        ax.set(xlabel='Customers sorted by distance',ylabel='k-distance',ylim=(0,3));ax.legend(title='min_samples')
        fig2.tight_layout();fig2.savefig(figs/'k_distance.png',dpi=150);plt.close(fig2)
    fig.suptitle(exp+' — parameter search');fig.tight_layout();fig.savefig(figs/'search.png',dpi=150);plt.close(fig)


def compare_parent(config,family,x,labels,z,best):
    parent=PARENTS[config]
    if parent is None: return None
    _,zp,details=transform(parent,x)
    # Fixed target-selected parameters isolate preprocessing; this is not a separately tuned experiment.
    m=fit_model(family,best,zp);lp=predict_labels(family,m,zp)
    common=StandardScaler().fit_transform(x)
    return {'parent_configuration':parent,'purpose':'fixed-parameter preprocessing diagnostic, not a tuned parent experiment',
        'target_dimensions':z.shape[1],'parent_dimensions':zp.shape[1],
        'ari':float(adjusted_rand_score(labels,lp)),
        'target_common_rfm_scores':scores(common,labels),'parent_common_rfm_scores':scores(common,lp),
        'parent_input_scores':scores(zp,lp),'parent_preprocessing':details,
        'same_distance_geometry':bool(np.allclose(pairwise_distances(z[:300]),pairwise_distances(zp[:300]),atol=1e-10,rtol=1e-10))}


def run_one(exp,rfm):
    config,family=exp.split('-')
    print(f'Running {exp}',flush=True)
    out=HERE/'results'/exp;out.mkdir(parents=True,exist_ok=True)
    x=rfm[FEATURES];prep,z,details=transform(config,x)
    grid,best,model,labels=search(family,z)
    grid.to_csv(out/'search.csv',index=False)
    if model is None:
        result={'experiment':exp,'status':'no_eligible_candidate','preprocessing':details}
        write_json(out/'parameters.json',result);return result
    prof=profile(rfm,labels);prof.to_csv(out/'profiles.csv',index=False)
    labeled=rfm.copy();labeled['cluster']=labels
    if family=='GN':model.save_training_artifacts(out,rfm.CustomerID)
    labeled.to_csv(out/'labels.csv',index=False)
    pd.DataFrame(z,columns=[f'input_{i+1}' for i in range(z.shape[1])]).assign(CustomerID=rfm.CustomerID).to_csv(out/'model_input.csv',index=False)
    pipeline=Pipeline([('preprocessing',prep),('model',model)])
    joblib.dump(pipeline,out/'pipeline.joblib')
    loaded=joblib.load(out/'pipeline.joblib')
    zz=loaded['preprocessing'].transform(x)
    assert np.allclose(zz,z,atol=1e-10)
    if family!='DB': assert np.array_equal(loaded.predict(x),labels)
    else: assert np.array_equal(loaded['model'].labels_,labels)
    comp=compare_parent(config,family,x,labels,z,best)
    if comp:write_json(out/'parent_comparison.json',comp)
    clustering_space=model.embeddings_ if family=='GN' else z
    plots(exp,family,clustering_space,labels,grid,prof,out)
    if family=='GN':
        fig,ax=plt.subplots(figsize=(8,4))
        h=model.history_;ax.plot(h.epoch,h.train_link_bce,label='train');ax.plot(h.epoch,h.validation_link_bce,label='validation')
        ax.axvline(model.training_['best_epoch'],color='black',ls='--',label='selected checkpoint')
        ax.set(xlabel='Epoch',ylabel='Balanced edge BCE',title=exp+' — GCN graph autoencoder training')
        ax.legend();fig.tight_layout();fig.savefig(out/'figures/training.png',dpi=150);plt.close(fig)
    result={'experiment':exp,'assignee':'Thuận','deadline_utc':DEADLINE,'status':'completed',
            'actual_model':type(model).__name__,'customers':len(x),'preprocessing':details,
            'selected':best,'model_parameters':model.get_params(),'raw_sha256':RAW_HASH,
            'evaluation_space':'actual model input; DBSCAN excludes noise for internal metrics',
            'comparison':comp,'all_customers_common_space_scores':scores(StandardScaler().fit_transform(x),labels)}
    if family=='GN':
        result.update(gnn_training=model.training_,embedding_dimensions=model.embedding_dim,
            evaluation_space='learned GNN embeddings; K-Means readout, k selected by embedding Silhouette with minimum cluster size 1%',
            preprocessed_input_scores=scores(z,labels))
        write_json(out/'gnn_training.json',model.training_)
    result['limitations']=['Exploratory clustering, not future value prediction; Monetary is historical sales, not profit.',
        'No ground-truth labels or held-out predictive evaluation.',
        'Internal scores from different feature spaces and DBSCAN subsets are not directly comparable.',
        'The cleaning policy reproduces the shared group RFM; it is not a newly approved official policy.']
    if best['largest_cluster_pct_all']>=90:result['limitations'].append('Largest cluster contains at least 90% of customers; high Silhouette alone does not imply a useful segmentation.')
    if best['smallest_cluster']<math.ceil(.01*len(x)):result['limitations'].append('A selected cluster contains less than 1% of customers; inspect profiles before use.')
    if family=='GN':result['limitations'].extend([
        'Transductive GNN: graph/embeddings apply to the fitted customers and their original order; unseen nodes require graph reconstruction and retraining.',
        'Held-out link prediction evaluates reconstruction of an RFM-derived graph, not business outcomes, customer value prediction, or segmentation ground truth.',
        'Only one fixed random seed and one GNN architecture are evaluated; graph and architecture choices are explicit implementation assumptions.'])
    write_json(out/'parameters.json',result)
    print(f"Completed {exp}: clusters={best['n_clusters']}, silhouette={best['silhouette']:.6f}",flush=True)
    return json_safe(result)


def workbook(scope,rfm,cleaning,provenance):
    results=[]
    for exp in EXPECTED:
        p=HERE/'results'/exp/'parameters.json'
        if p.exists():results.append(json.loads(p.read_text(encoding='utf-8')))
    summary=[]
    for r in results:
        best=r.get('selected',{})
        summary.append({'experiment':r['experiment'],'model':r.get('actual_model'),'status':r['status'],
            'customers':r.get('customers'),'dimensions':r['preprocessing']['model_input_dimensions'],
            'evaluation_space':r.get('evaluation_space'),'embedding_dimensions':r.get('embedding_dimensions'),
            'test_link_auc':r.get('gnn_training',{}).get('test_link_metrics',{}).get('roc_auc'),
            'test_link_ap':r.get('gnn_training',{}).get('test_link_metrics',{}).get('average_precision'),
            **{k:best.get(k) for k in ['k','eps','min_samples','n_clusters','noise_pct','silhouette','dbi','chi','smallest_cluster','largest_cluster_pct_all']}})
    with pd.ExcelWriter(HERE/'Working_details_Thuan_2026_11_17.xlsx',engine='openpyxl') as writer:
        scope.to_excel(writer,sheet_name='Phan_cong',index=False)
        pd.DataFrame(summary).to_excel(writer,sheet_name='Tong_hop',index=False)
        cleaning.to_excel(writer,sheet_name='Lam_sach',index=False)
        pd.DataFrame(provenance['rfm_checks']).to_excel(writer,sheet_name='Kiem_chung_RFM',index=False)
        rfm.to_excel(writer,sheet_name='RFM_dau_vao',index=False)
        versions={m:importlib.metadata.version(m) for m in ['numpy','pandas','scikit-learn','scipy','matplotlib','openpyxl','joblib','threadpoolctl']}
        versions['python']=platform.python_version()
        try:versions['torch']=importlib.metadata.version('torch')
        except importlib.metadata.PackageNotFoundError:pass
        pd.DataFrame([{'key':k,'value':str(v)} for k,v in {**provenance,**versions}.items()]).to_excel(writer,sheet_name='Nguon_va_moi_truong',index=False)
        notes=[
            'Chỉ 7 mục của Thuận, lọc chính xác deadline UTC trong Excel. Giờ Việt Nam: 04:00 ngày 18/11/2026.',
            'Các quy tắc search là lựa chọn triển khai kế thừa repo, không phải nội dung có đủ trong Excel.',
            'KM: k=2..10, seed 42, n_init=20, chọn Silhouette lớn nhất; không cấm cụm nhỏ.',
            'DB: eps=.1,.2,.3,.4,.5,.7,1,1.5,2; min_samples=4,6,8,10,15,20; >=2 cụm, noise<=5%; chọn Silhouette non-noise cao nhất.',
            'GN là GNN theo xác nhận người dùng: Graph Autoencoder 2 lớp GCN, kNN=15, hidden=32, embedding=8; K-Means readout k=2..10; chọn Silhouette embedding cao nhất trong cụm >=1% khách.',
            'GN: cạnh train/val/test=80/10/10; checkpoint chọn bằng BCE validation; test chỉ đánh giá tái dựng graph, không dùng chọn checkpoint/k.',
            'Chỉ số tính đầy đủ; GN trên embedding, KM trên đầu vào PCA/scaler, DBSCAN loại noise khỏi Silhouette/DBI/CHI. Không có BIC/AIC cho GNN.',
            'Không so trực tiếp Silhouette giữa không gian khác nhau; xem thêm common RFM scores và ARI.',
            'Parent comparison dùng cùng tham số model đã chọn ở target; không phải baseline đã được tune riêng.',
            'PCA là đầu vào mô hình, không chỉ để vẽ; hình chỉ hiển thị 2 tọa độ đầu nên có thể che chiều khác.',
            'DBSCAN không có predict cho khách mới; labels_ chỉ áp dụng đúng khách, đúng thứ tự khi fit.',
            'Monetary là giá trị mua lịch sử GBP, không phải lợi nhuận hay dự báo tương lai.',
        ]
        pd.DataFrame({'Luu_y':notes}).to_excel(writer,sheet_name='Giai_thich',index=False)
        for r in results:
            exp=r['experiment'];folder=HERE/'results'/exp
            pd.read_csv(folder/'search.csv').to_excel(writer,sheet_name=exp+'_grid',index=False)
            if (folder/'profiles.csv').exists():pd.read_csv(folder/'profiles.csv').to_excel(writer,sheet_name=exp+'_profile',index=False)
            if (folder/'training_history.csv').exists():pd.read_csv(folder/'training_history.csv').to_excel(writer,sheet_name=exp+'_train',index=False)
        for s in writer.book:
            s.freeze_panes='A2';s.auto_filter.ref=s.dimensions
            for cell in s[1]:cell.font=openpyxl.styles.Font(bold=True,color='FFFFFF');cell.fill=openpyxl.styles.PatternFill('solid',fgColor='24465B')
            for col in s.columns:
                letter=col[0].column_letter
                s.column_dimensions[letter].width=min(70,max(16,max(len(str(c.value or '')) for c in list(col)[:100])+2))
    write_json(HERE/'shared/environment.json',versions)
    strategy=openpyxl.load_workbook(HERE/'references/chienluocmodel_cap_nhat.xlsx')
    assigned=strategy['người nào chạy']
    completed={r['experiment'] for r in results if r['status']=='completed'}
    for row in assigned.iter_rows(min_row=6):
        if row[0].value in completed and row[4].value=='Thuận' and row[5].value==DEADLINE:
            row[6].value='hoàn thành'
    sheet=strategy.create_sheet('ket_qua_Thuan')
    if summary:
        keys=list(summary[0]);sheet.append(keys)
        for row in summary:sheet.append([row.get(k) for k in keys])
    sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
    for c in sheet[1]:c.font=openpyxl.styles.Font(bold=True)
    for col in sheet.columns:sheet.column_dimensions[col[0].column_letter].width=22
    strategy.properties.creator=None;strategy.properties.lastModifiedBy=None
    strategy.save(HERE/'chienluocmodel_ket_qua_Thuan_2026_11_17.xlsx')
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment',nargs='+',choices=EXPECTED,default=EXPECTED)
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    scope=assignments()
    rfm,cleaning,provenance=prepare_input()
    if not args.prepare_only:
        for exp in args.experiment:run_one(exp,rfm)
    summary=workbook(scope,rfm,cleaning,provenance)
    print(pd.DataFrame(summary).to_string(index=False),flush=True)


if __name__=='__main__':
    # Keep pickle's custom callable importable from CLI and notebooks.
    import sys
    sys.modules.setdefault('run_experiments',sys.modules[__name__])
    log_fm.__module__='run_experiments'
    with threadpool_limits(limits=1):main()
