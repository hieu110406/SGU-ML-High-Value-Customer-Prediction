import json
from pathlib import Path

path = Path('project/notebooks/02_baseline_kmeans/17-11-2026-hieu-kmeans-rfm/kmeans.ipynb')
nb = json.loads(path.read_text(encoding='utf-8'))

def cell(index, source, kind=None):
    target = nb['cells'][index]
    if kind:
        target['cell_type'] = kind
    target['source'] = source.strip().splitlines(keepends=True)
    if target['cell_type'] == 'code':
        target['outputs'] = []
        target['execution_count'] = None

cell(0, '# K-Means trên tập feature A (RFM) đã tiền xử lý\n\nNotebook sử dụng nguyên dữ liệu đầu vào; chỉ fit StandardScaler, PCA và K-Means. Kết quả mô tả hành vi mua trong lịch sử, chưa phải dự báo giá trị khách hàng tương lai.')
cell(5, '''
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score
''')
cell(6, '''
# Chạy từ thư mục notebook, project/ hoặc gốc repository.
relative_dir = Path('notebooks/02_baseline_kmeans/17-11-2026-hieu-kmeans-rfm')
candidates = [Path.cwd(), Path.cwd() / relative_dir, Path.cwd() / 'project' / relative_dir]
BASE_DIR = next((p for p in candidates if (p / 'data/customer_features.csv').is_file()), None)
if BASE_DIR is None:
    raise FileNotFoundError('Không tìm thấy data/customer_features.csv của notebook.')
FIGURES_DIR = BASE_DIR / 'figures'
FIGURES_DIR.mkdir(exist_ok=True)
df = pd.read_csv(BASE_DIR / 'data/customer_features.csv', dtype={'CustomerID': 'string'})
FEATURE_A = ['Recency', 'Frequency', 'Monetary']
X = df[FEATURE_A].copy()
display(X.head())
''')
cell(7, '## Kiểm tra đầu vào (không thay đổi dữ liệu đã tiền xử lý)')
cell(8, '''
display(X.isna().sum().rename('Số giá trị thiếu'))
assert df['CustomerID'].notna().all(), 'CustomerID bị thiếu.'
assert df['CustomerID'].is_unique, 'Cần một dòng cho mỗi CustomerID.'
assert len(X) >= 3, 'Cần ít nhất 3 khách hàng để khảo sát k.'
assert all(pd.api.types.is_numeric_dtype(X[c]) for c in FEATURE_A), 'RFM phải là số.'
assert np.isfinite(X.to_numpy(dtype=float)).all(), 'RFM có missing hoặc giá trị vô hạn.'
assert X['Recency'].ge(0).all(), 'Recency phải không âm.'
assert X['Frequency'].gt(0).all(), 'Frequency phải dương.'
assert X['Monetary'].gt(0).all(), 'Monetary phải dương trong tập mua RFM này.'
''')
cell(9, '''
# Một cấu hình chung cho cả khảo sát k và mô hình cuối.
KMEANS_PARAMS = dict(random_state=RANDOM_STATE, init=INIT, n_init=N_INIT,
                     max_iter=MAX_ITER, tol=TOL)
''')
cell(14, '## PCA giữ tối thiểu 90% phương sai\n\nNếu phải giữ cả ba thành phần thì PCA chỉ đổi hệ trục, không giảm số chiều. StandardScaler không loại bỏ ảnh hưởng của ngoại lệ; cần xem thêm kích thước và hồ sơ cụm khi diễn giải.')
cell(15, '''
pca_features = PCA(n_components=n_components, svd_solver='full')
X_pca = pca_features.fit_transform(X_scaled)
assert X_pca.shape == (X_scaled.shape[0], n_components)
assert np.isfinite(X_pca).all()
assert pca_features.explained_variance_ratio_.sum() >= threshold - 1e-12
print('Số chiều PCA:', n_components)
print('Phương sai giữ lại:', pca_features.explained_variance_ratio_.sum())
print('Đã giảm chiều.' if n_components < X.shape[1] else 'Giữ đủ các chiều; PCA chỉ đổi hệ trục.')
''')
cell(16, '''
results = []
candidate_models = {}
max_k = min(10, len(X_pca) - 1, len(np.unique(X_pca, axis=0)))
for k in range(2, max_k + 1):
    candidate = KMeans(n_clusters=k, **KMEANS_PARAMS)
    candidate_labels = candidate.fit_predict(X_pca)
    if not 2 <= len(np.unique(candidate_labels)) < len(X_pca):
        continue
    candidate_models[k] = candidate
    results.append({
        'k': k,
        'Silhouette': silhouette_score(X_pca, candidate_labels),
        'DBI': davies_bouldin_score(X_pca, candidate_labels),
        'CHI': calinski_harabasz_score(X_pca, candidate_labels),
        'Inertia': candidate.inertia_,
    })
if not results:
    raise ValueError('Không có phương án k hợp lệ để đánh giá.')
metrics = pd.DataFrame(results)
display(metrics.round(4))
''')
cell(17, '''
fig, axes = plt.subplots(1, 4, figsize=(18, 4))
for ax, col in zip(axes, ['Silhouette', 'DBI', 'CHI', 'Inertia']):
    ax.plot(metrics['k'], metrics[col], marker='o')
    ax.set_xlabel('k')
    ax.set_title(col)
fig.tight_layout()
fig.savefig(FIGURES_DIR / 'kmeans_metrics.png', dpi=300, bbox_inches='tight')
plt.show()
best_k = int(metrics.loc[metrics['Silhouette'].idxmax(), 'k'])
print('K đề xuất theo Silhouette trong phạm vi khảo sát:', best_k)
''')
cell(18, '''
best_row = metrics.loc[metrics['k'].eq(best_k)].iloc[0]
dbi_k = int(metrics.loc[metrics['DBI'].idxmin(), 'k'])
chi_k = int(metrics.loc[metrics['CHI'].idxmax(), 'k'])
display(Markdown(
    f"Chọn **k={best_k}** theo Silhouette lớn nhất ({best_row['Silhouette']:.4f}) "
    f"trong phạm vi khảo sát. DBI thấp nhất ở k={dbi_k}; CHI cao nhất ở k={chi_k}. "
    "Các chỉ số đều tính trên dữ liệu PCA dùng để fit K-Means. "
    "Đây là đánh giá nội bộ trên cùng tập khách hàng; cần kết hợp Elbow, kích thước "
    "và hồ sơ cụm, chưa khẳng định k tối ưu tuyệt đối."
))
''', 'code')
cell(19, '## Dùng mô hình tốt nhất đã fit trong vòng khảo sát')
cell(20, '''
# Tái sử dụng đúng mô hình được chấm điểm, không fit lại trên RFM gốc.
model = candidate_models[best_k]
labels = model.labels_.copy()
assert np.array_equal(model.predict(X_pca), labels)
''')
cell(21, '''
result = df[['CustomerID'] + FEATURE_A].copy()
result['cluster'] = labels
print('Số lượng theo cụm:')
display(result['cluster'].value_counts().sort_index())
display(result.head())
''')
cell(22, '''
# PCA riêng cho hình vẽ, không thay đổi PCA đầu vào của mô hình.
pca_plot = PCA(n_components=2, svd_solver='full')
coords = pca_plot.fit_transform(X_scaled)
centers_scaled = pca_features.inverse_transform(model.cluster_centers_)
centers_2d = pca_plot.transform(centers_scaled)
fig, ax = plt.subplots(figsize=(9, 6))
scatter = ax.scatter(coords[:, 0], coords[:, 1], c=labels,
                     cmap='tab10', s=18, alpha=0.65, rasterized=True)
ax.scatter(centers_2d[:, 0], centers_2d[:, 1], c='black', marker='X', s=160,
           edgecolors='white', linewidths=1.2, label='Tâm cụm (chiếu 2D)')
ax.set_title(f'K-Means RFM — PCA 2D để trực quan hóa (k={best_k})')
ax.set_xlabel(f'PC1 ({pca_plot.explained_variance_ratio_[0]:.1%} phương sai)')
ax.set_ylabel(f'PC2 ({pca_plot.explained_variance_ratio_[1]:.1%} phương sai)')
ax.legend(loc='best')
fig.colorbar(scatter, ax=ax, label='Cluster', ticks=sorted(np.unique(labels)))
fig.tight_layout()
fig.savefig(FIGURES_DIR / 'kmeans_clusters_pca.png', dpi=300, bbox_inches='tight')
plt.show()
''')
cell(24, '''
cluster_medians = result.groupby('cluster')[FEATURE_A].median()
display(cluster_medians)
''')
cell(29, '''
for cluster_id, row in cluster_medians.iterrows():
    count = int(cluster_count.loc[cluster_id])
    display(Markdown(
        f"**Cụm {cluster_id}:** {count:,} khách ({count / len(labels):.2%}); "
        f"trung vị R={row['Recency']:.2f} ngày, F={row['Frequency']:.2f} hóa đơn, "
        f"M={row['Monetary']:.2f} GBP."
    ))
display(Markdown(
    "R thấp biểu thị mua gần đây hơn; F và M cao biểu thị mua thường xuyên và "
    "chi tiêu lịch sử cao hơn. Nhãn cụm chỉ là mã định danh, không phải thứ hạng. "
    "Cần đối chiếu cả ba đặc trưng và quy mô cụm trước khi đặt tên nghiệp vụ như VIP; "
    "Monetary không phải lợi nhuận hoặc giá trị tương lai."
))
''', 'code')
cell(30, '## Lưu pipeline và kiểm tra nạp lại\n\n`kmeans_model.pkl` chứa Pipeline đã fit (scaler → PCA → K-Means). Đầu vào dự đoán là DataFrame RFM gốc theo FEATURE_A, không chuẩn hóa lần nữa.')
cell(31, '''
final_metrics = {
    'Silhouette': silhouette_score(X_pca, labels),
    'DBI': davies_bouldin_score(X_pca, labels),
    'CHI': calinski_harabasz_score(X_pca, labels),
    'Inertia': model.inertia_,
}
for name, value in final_metrics.items():
    print(f'{name}: {value:.6f}')
    assert np.isclose(value, best_row[name]), f'{name} không khớp vòng khảo sát.'

# Các thành phần đã fit; không gọi fit lần nữa.
pipeline = Pipeline([('scaler', scaler), ('pca', pca_features), ('kmeans', model)])
model_path = BASE_DIR / 'kmeans_model.pkl'
joblib.dump(pipeline, model_path)
loaded_pipeline = joblib.load(model_path)
assert np.array_equal(loaded_pipeline.predict(X), labels), 'Nạp lại không tái lập được nhãn.'
with (BASE_DIR / 'kmeans_PCA_params.json').open('w', encoding='utf-8') as f:
    json.dump({
        'features': FEATURE_A,
        'scaling': 'StandardScaler',
        'pca': {'n_components': n_components, 'variance_threshold': threshold,
                'explained_variance_ratio': pca_features.explained_variance_ratio_.tolist()},
        'kmeans': model.get_params(),
        'selection': 'max Silhouette on X_pca among surveyed k',
        'metrics': final_metrics,
    }, f, ensure_ascii=False, indent=4)
print('Đã lưu pipeline và kiểm tra nhãn sau khi nạp lại khớp hoàn toàn.')
''')

# Các hình còn lại dùng đường dẫn thống nhất.
replacements = {
    '"figures/PCA.png"': 'FIGURES_DIR / "PCA.png"',
    '"figures/kmeans_cluster_distribution.png"': 'FIGURES_DIR / "kmeans_cluster_distribution.png"',
    '"figures/kmeans_rfm_comparison.png"': 'FIGURES_DIR / "kmeans_rfm_comparison.png"',
}
for target in nb['cells']:
    source = ''.join(target['source'])
    for old, new in replacements.items():
        source = source.replace(old, new)
    target['source'] = source.splitlines(keepends=True)
    if target['cell_type'] == 'code':
        target['execution_count'] = None
        target['outputs'] = []
path.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('Updated', path)
