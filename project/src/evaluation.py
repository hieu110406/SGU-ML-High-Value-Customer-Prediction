"""Internal clustering measures on the full fitted population, without labels."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import davies_bouldin_score, silhouette_score


def evaluate_clustering(values, labels) -> dict:
    values = np.asarray(values, dtype=float)
    labels = np.asarray(labels)
    if values.ndim != 2 or len(labels) != len(values) or not np.isfinite(values).all():
        raise ValueError("Features and labels must align and features must be finite.")
    clusters, counts = np.unique(labels, return_counts=True)
    if not 2 <= len(clusters) < len(values):
        raise ValueError("Internal measures require 2 through n_samples - 1 clusters.")
    return {
        "silhouette": float(silhouette_score(values, labels, metric="euclidean")),
        "davies_bouldin": float(davies_bouldin_score(values, labels)),
        "cluster_sizes": {int(k): int(v) for k, v in zip(clusters, counts)},
        "evaluation_customers": len(values),
    }
