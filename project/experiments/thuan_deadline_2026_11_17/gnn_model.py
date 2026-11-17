"""Transductive GCN graph autoencoder followed by clustering of learned embeddings.

The graph is constructed from preprocessed customer RFM, never from cluster labels.
Validation selects the encoder checkpoint; test edges never select a checkpoint or k.
"""
from __future__ import annotations

import copy
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClusterMixin
from sklearn.cluster import KMeans
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neighbors import NearestNeighbors


def torch_api():
    try:
        import torch
        return torch
    except ImportError as e:
        raise ImportError('Install requirements-gnn.txt to run the GNN experiments.') from e


def make_encoder(input_dim, hidden_dim, embedding_dim):
    torch=torch_api()
    class Encoder(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.conv1=torch.nn.Linear(input_dim,hidden_dim)
            self.conv2=torch.nn.Linear(hidden_dim,embedding_dim)
        def forward(self,x,adj):
            h=torch.relu(self.conv1(torch.sparse.mm(adj,x)))
            return self.conv2(torch.sparse.mm(adj,h))
    return Encoder()


def normalized_adjacency(n,edges):
    torch=torch_api()
    u,v=edges.T
    rows=np.concatenate([u,v,np.arange(n)])
    cols=np.concatenate([v,u,np.arange(n)])
    degree=np.bincount(rows,minlength=n).astype(float)
    values=1/np.sqrt(degree[rows]*degree[cols])
    return torch.sparse_coo_tensor(torch.tensor(np.stack([rows,cols]),dtype=torch.long),
        torch.tensor(values,dtype=torch.float32),(n,n)).coalesce()


def sample_non_edges(rng,n,count,forbidden):
    ids=np.empty(0,dtype=np.int64)
    while len(ids)<count:
        a=rng.integers(0,n,size=max(1000,3*(count-len(ids))))
        b=rng.integers(0,n,size=len(a))
        lo,hi=np.minimum(a,b),np.maximum(a,b)
        ok=(lo!=hi)&~forbidden[lo,hi]
        ids=np.unique(np.concatenate([ids,lo[ok]*n+hi[ok]]))
    # Sampling without replacement; shuffle to avoid preferring low node indices.
    rng.shuffle(ids);ids=ids[:count]
    return np.column_stack([ids//n,ids%n])


def split_graph(x,neighbors,seed):
    n=len(x)
    indices=NearestNeighbors(n_neighbors=neighbors+1,metric='euclidean').fit(x).kneighbors(x,return_distance=False)
    a=np.repeat(np.arange(n),indices.shape[1]);b=indices.ravel()
    mask=a!=b;a,b=a[mask],b[mask]
    ids=np.unique(np.minimum(a,b)*n+np.maximum(a,b))
    rng=np.random.default_rng(seed);rng.shuffle(ids)
    edges=np.column_stack([ids//n,ids%n]);nv=int(.1*len(edges));nt=nv
    val,test,train=edges[:nv],edges[nv:nv+nt],edges[nv+nt:]
    forbidden=np.zeros((n,n),dtype=bool)
    forbidden[edges[:,0],edges[:,1]]=True
    valneg=sample_non_edges(rng,n,len(val),forbidden)
    forbidden[valneg[:,0],valneg[:,1]]=True
    testneg=sample_non_edges(rng,n,len(test),forbidden)
    forbidden[testneg[:,0],testneg[:,1]]=True
    return {'train_positive':train,'validation_positive':val,'test_positive':test,
            'validation_negative':valneg,'test_negative':testneg},forbidden,rng


def logits(h,edges):
    return (h[edges[:,0]]*h[edges[:,1]]).sum(dim=1)


def link_metrics(h,positive,negative):
    torch=torch_api()
    with torch.no_grad():
        p=torch.sigmoid(logits(h,torch.tensor(positive,dtype=torch.long))).numpy()
        q=torch.sigmoid(logits(h,torch.tensor(negative,dtype=torch.long))).numpy()
    truth=np.r_[np.ones(len(p)),np.zeros(len(q))]
    probability=np.r_[p,q]
    return {'roc_auc':float(roc_auc_score(truth,probability)),
            'average_precision':float(average_precision_score(truth,probability))}


class GNNClustering(ClusterMixin,BaseEstimator):
    """CPU GCN-GAE with known-node inference; rejects changed node sets/order."""
    def __init__(self,n_clusters=2,neighbors=15,hidden_dim=32,embedding_dim=8,
                 max_epochs=200,patience=30,learning_rate=.01,weight_decay=1e-4,random_state=42):
        self.n_clusters=n_clusters;self.neighbors=neighbors;self.hidden_dim=hidden_dim
        self.embedding_dim=embedding_dim;self.max_epochs=max_epochs;self.patience=patience
        self.learning_rate=learning_rate;self.weight_decay=weight_decay;self.random_state=random_state

    def fit_encoder(self,x):
        torch=torch_api()
        torch.manual_seed(self.random_state);torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        self.input_=np.asarray(x,dtype=np.float64).copy()
        self.split_,forbidden,rng=split_graph(self.input_,self.neighbors,self.random_state)
        adj=normalized_adjacency(len(x),self.split_['train_positive'])
        features=torch.tensor(self.input_,dtype=torch.float32)
        encoder=make_encoder(features.shape[1],self.hidden_dim,self.embedding_dim)
        optimizer=torch.optim.Adam(encoder.parameters(),lr=self.learning_rate,weight_decay=self.weight_decay)
        positive=torch.tensor(self.split_['train_positive'],dtype=torch.long)
        valpos=torch.tensor(self.split_['validation_positive'],dtype=torch.long)
        valneg=torch.tensor(self.split_['validation_negative'],dtype=torch.long)
        def validation_loss(h):
            return .5*(torch.nn.functional.binary_cross_entropy_with_logits(logits(h,valpos),torch.ones(len(valpos)))+
                       torch.nn.functional.binary_cross_entropy_with_logits(logits(h,valneg),torch.zeros(len(valneg))))
        with torch.no_grad():
            initial=encoder(features,adj)
            initial_loss=float(validation_loss(initial))
            initial_metrics=link_metrics(initial,self.split_['validation_positive'],self.split_['validation_negative'])
        history=[];best_loss=float('inf');best_state=None;stale=0;best_epoch=0
        for epoch in range(1,self.max_epochs+1):
            encoder.train();optimizer.zero_grad()
            neg_array=sample_non_edges(rng,len(x),len(positive),forbidden)
            negative=torch.tensor(neg_array,dtype=torch.long)
            h=encoder(features,adj)
            loss=.5*(torch.nn.functional.binary_cross_entropy_with_logits(logits(h,positive),torch.ones(len(positive)))+
                     torch.nn.functional.binary_cross_entropy_with_logits(logits(h,negative),torch.zeros(len(negative))))
            if not torch.isfinite(loss):raise ValueError('Non-finite GNN loss')
            loss.backward();torch.nn.utils.clip_grad_norm_(encoder.parameters(),max_norm=5.)
            optimizer.step();encoder.eval()
            with torch.no_grad():vl=float(validation_loss(encoder(features,adj)))
            history.append({'epoch':epoch,'train_link_bce':float(loss.detach()),'validation_link_bce':vl})
            if vl<best_loss-1e-6:
                best_loss=vl;best_epoch=epoch;best_state=copy.deepcopy(encoder.state_dict());stale=0
            else:stale+=1
            if stale>=self.patience:break
        encoder.load_state_dict(best_state);encoder.eval()
        with torch.no_grad():h=encoder(features,adj)
        self.embeddings_=h.numpy().astype(np.float64)
        self.state_dict_={k:v.detach().numpy().copy() for k,v in best_state.items()}
        self.history_=pd.DataFrame(history)
        self.split_['last_train_negative']=neg_array
        self.training_={'architecture':'GCN(input,32)-ReLU-GCN(32,8); inner-product edge decoder',
            'graph':'symmetrized union 15-nearest-neighbor Euclidean graph from PCA/model input',
            'message_passing':'D^-1/2 (A_train + I) D^-1/2; validation/test positives removed',
            'train_positive_edges':len(positive),'validation_positive_edges':len(valpos),
            'test_positive_edges':len(self.split_['test_positive']),
            'epochs_run':len(history),'best_epoch':best_epoch,'initial_validation_bce':initial_loss,
            'best_validation_bce':best_loss,'initial_validation_diagnostic':initial_metrics,
            'validation_link_metrics':link_metrics(h,self.split_['validation_positive'],self.split_['validation_negative']),
            'test_link_metrics':link_metrics(h,self.split_['test_positive'],self.split_['test_negative']),
            'test_usage':'evaluated once after validation checkpoint selection; never used for training or cluster-k selection',
            'negative_sampling':'1:1 uniform non-edges; excludes all known positive edges and reserved validation/test negatives',
            'torch_version':torch.__version__,'device':'cpu','seed':self.random_state}
        return self

    def select_clusters(self,k):
        self.n_clusters=int(k)
        self.clusterer_=KMeans(n_clusters=self.n_clusters,n_init=20,random_state=self.random_state).fit(self.embeddings_)
        self.labels_=self.clusterer_.labels_.copy()
        return self

    def fit(self,x,y=None):
        return self.fit_encoder(x).select_clusters(self.n_clusters)

    def _check_input(self,x):
        a=np.asarray(x,dtype=float)
        if a.shape!=self.input_.shape or not np.allclose(a,self.input_,rtol=0,atol=1e-8):
            raise ValueError('Transductive GNN: requires the original customers in the original order. Rebuild the graph and retrain for changed/new customers.')

    def predict(self,x):
        self._check_input(x)
        return self.clusterer_.predict(self.embeddings_)

    def transform(self,x):
        self._check_input(x)
        return self.embeddings_.copy()

    def recompute_embeddings(self):
        torch=torch_api()
        encoder=make_encoder(self.input_.shape[1],self.hidden_dim,self.embedding_dim)
        encoder.load_state_dict({k:torch.tensor(v) for k,v in self.state_dict_.items()});encoder.eval()
        with torch.no_grad():
            h=encoder(torch.tensor(self.input_,dtype=torch.float32),normalized_adjacency(len(self.input_),self.split_['train_positive']))
        return h.numpy().astype(np.float64)

    def save_training_artifacts(self,folder,customer_ids):
        torch=torch_api()
        self.history_.to_csv(folder/'training_history.csv',index=False)
        pd.DataFrame(self.embeddings_,columns=[f'embedding_{j+1}' for j in range(self.embedding_dim)]).assign(CustomerID=np.asarray(customer_ids)).to_csv(folder/'embeddings.csv',index=False)
        np.savez_compressed(folder/'graph_splits.npz',**self.split_)
        torch.save({k:torch.tensor(v) for k,v in self.state_dict_.items()},folder/'encoder_state.pt')
