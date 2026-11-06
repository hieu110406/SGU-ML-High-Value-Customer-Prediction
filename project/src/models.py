"""K-Means baseline; other clustering algorithms remain outside this milestone."""
from __future__ import annotations

import numpy as np
from sklearn.cluster import KMeans


def fit_kmeans(values, *, k: int, random_state: int, n_init: int, max_iter: int):
    """Fit only a finite, numeric customer matrix; identifiers never belong here."""
    values = np.asarray(values, dtype=float)
    if values.ndim != 2 or not np.isfinite(values).all():
        raise ValueError("K-Means requires a finite two-dimensional feature matrix.")
    if isinstance(k, bool) or not isinstance(k, int) or not 2 <= k < len(values):
        raise ValueError("k must be an integer from 2 to n_customers - 1.")
    if len(np.unique(values, axis=0)) < k:
        raise ValueError("Fewer distinct feature vectors than requested clusters.")
    model = KMeans(n_clusters=k, random_state=random_state, n_init=n_init,
                   max_iter=max_iter, algorithm="lloyd", tol=1e-4)
    return model.fit(values)
