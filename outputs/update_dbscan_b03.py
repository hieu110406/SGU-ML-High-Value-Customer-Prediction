import ast
import json
from pathlib import Path

target = Path('project/notebooks/03_clustering_eval/17-11-2026-hieu-dbscan-b03/dbscan.ipynb')
nb = json.loads(target.read_text(encoding='utf-8'))

def setcell(i, source, kind=None):
    c = nb['cells'][i]
    c['cell_type'] = kind or c['cell_type']
    c['source'] = source.strip().splitlines(keepends=True)
    if c['cell_type'] == 'code':
        ast.parse(source.strip())
        c['outputs'] = []
        c['execution_count'] = None

setcell(0, '''
# B03 DBSCAN: Yeo–Johnson trên RFM

Đối chứng với B01: thay log1p bằng Yeo–Johnson (`standardize=False`), sau đó
StandardScaler và PCA giữ ít nhất 90% phương sai. Giữ cùng dữ liệu, lưới DBSCAN
và quy tắc chọn của B01. Lambda được fit riêng cho từng biến RFM và lưu để tái lập.

Các file A03 đã có trong thư mục là kết quả bản sao trước khi sửa; không phải
kết quả B03. Chạy notebook để tạo các đầu ra có tiền tố `dbscan_b03`.

## Params
''')
setcell(1, '''
EXPERIMENT = 'B03-DB'
FEATURES = ['Recency', 'Frequency', 'Monetary']
POWER_METHOD = 'yeo-johnson'
POWER_STANDARDIZE = False
PCA_VAR = 0.90
# Giữ cùng lưới và điều kiện chọn với B01 DBSCAN.
MIN_SAMPLES_GRID = [4, 6, 8, 10, 15, 20]
EPS_GRID = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.7, 1.0, 1.5, 2.0]
MAX_NOISE = 0.05
MIN_CLUSTERS = 2
''')
setcell(3, '''
from pathlib import Path
from hashlib import sha256
import json
import joblib
import numpy as np
import pandas as pd
import sklearn
import matplotlib.pyplot as plt
from IPython.display import display
from sklearn.preprocessing import PowerTransformer, StandardScaler
from sklearn.decomposition import PCA
from sklearn.pipeline import Pipeline
from sklearn.cluster import DBSCAN
from sklearn.neighbors import NearestNeighbors
from sklearn.metrics import silhouette_score, davies_bouldin_score

def find(rel):
    for parent in [Path.cwd(), *Path.cwd().parents]:
        for candidate in (parent / rel, parent / 'project' / rel):
            if candidate.exists():
                return candidate.resolve()
    raise FileNotFoundError(f'Không tìm thấy trong repository: {rel}')

BASE_DIR = find('notebooks/03_clustering_eval/17-11-2026-hieu-dbscan-b03')
# Cùng đầu vào đã tiền xử lý với B01; không thay đổi file feature.
DATA = find('notebooks/02_baseline_kmeans/12-11-2026-hieu-kmeans/data/customer_features.csv')
FIG, OUT = BASE_DIR / 'figures', BASE_DIR / 'data'
FIG.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)
df = pd.read_csv(DATA, dtype={'CustomerID': 'string'})
X = df[FEATURES].copy()
assert df['CustomerID'].notna().all() and df['CustomerID'].is_unique
assert np.isfinite(X.to_numpy(dtype=float)).all(), 'RFM có missing hoặc giá trị vô hạn.'
assert (X >= 0).all().all(), 'Tập RFM mua đầu vào phải không âm.'
assert X.nunique().gt(1).all(), 'PowerTransformer cần các biến không hằng.'
assert len(X) >= max(MIN_SAMPLES_GRID)
print('Dữ liệu đầu vào:', X.shape)
display(X.describe().round(2))
''')
setcell(4, '''
**Phạm vi:** dùng RFM đã tiền xử lý của nhóm, giữ X trên thang gốc để mô tả cụm.
Thí nghiệm này không làm lại cleaning hoặc xác minh chuỗi raw → features.
Không lấy CustomerID hay các cột hành vi khác làm đầu vào DBSCAN.
''')
setcell(5, '''
## Yeo–Johnson rồi StandardScaler

Fit Yeo–Johnson trên cả R, F, M, không áp dụng log1p trước đó.
`standardize=False` để bước power transform chỉ biến đổi phân phối;
StandardScaler được fit riêng sau biến đổi. Lambda của mỗi biến phải được giữ lại.
''')
setcell(6, '''
power = PowerTransformer(method=POWER_METHOD, standardize=POWER_STANDARDIZE)
X_power = power.fit_transform(X)
assert np.isfinite(X_power).all()
lambda_by_feature = dict(zip(FEATURES, map(float, power.lambdas_)))
display(pd.Series(lambda_by_feature, name='Lambda đã fit'))

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_power)
display(pd.DataFrame({
    'skew_raw': X.skew(),
    'skew_yeo_johnson': pd.DataFrame(X_power, columns=FEATURES).skew(),
}).round(3))
''')
setcell(7, '''
pca_full = PCA(svd_solver='full').fit(X_scaled)
cum = np.cumsum(pca_full.explained_variance_ratio_)
n_pc = min(int(np.searchsorted(cum, PCA_VAR) + 1), len(FEATURES))
pca_b03 = PCA(n_components=n_pc, svd_solver='full')
Z = pca_b03.fit_transform(X_scaled)
assert np.isfinite(Z).all()
assert pca_b03.explained_variance_ratio_.sum() >= PCA_VAR - 1e-12
print('Phương sai tích lũy:', cum.round(4))
print(f'Số PC giữ lại: {n_pc}/{len(FEATURES)}; phương sai giữ {pca_b03.explained_variance_ratio_.sum():.2%}')
''')
setcell(8, '**PCA:** ngưỡng là 90% phương sai, không cố định 2 chiều. Số thành phần được tính lại sau Yeo–Johnson và StandardScaler.')
setcell(9, '**Đối chiếu B01:** thay phép biến đổi log1p bằng Yeo–Johnson; giữ StandardScaler, ngưỡng PCA 90%, lưới và quy tắc chọn. Không kết luận tốt hơn B01 trước khi có kết quả B03.')
src = ''.join(nb['cells'][11]['source'])
src = src.replace('A03-DB — k-distance trên PCA 2 thành phần', 'B03-DB — k-distance (Yeo–Johnson + Standard + PCA 90%)')
src = src.replace('A03_k_distance.png', 'dbscan_b03_k_distance.png')
setcell(11, src)
setcell(12, '**Cách đọc:** điểm bẻ cong của đường k-distance gợi ý vùng eps cần xem xét. Lưới eps được giữ giống B01 để đối chiếu; không thay ngưỡng nhiễu sau khi xem điểm số.')
src = ''.join(nb['cells'][14]['source'])
src = src.replace('# Z là dữ liệu PCA 2 thành phần của A03', '# Z: Yeo–Johnson → StandardScaler → PCA 90% của B03')
src = src.replace('labels_a03', 'labels_b03')
src = src.replace('& (grid["noise_pct"] <= MAX_NOISE * 100)', '& (grid["noise_pct"] <= MAX_NOISE * 100)\n    & grid["silhouette"].notna()')
setcell(14, src)
setcell(15, '**Đánh giá lưới:** xem số cấu hình đạt điều kiện, Silhouette/DBI trên điểm không nhiễu, tỷ lệ nhiễu và kích thước cụm. Các nhận xét số liệu phải dựa trên lần chạy B03 này.')
setcell(16, '''
## Chọn cấu hình

Giữ quy tắc B01: ít nhất 2 cụm (không tính nhiễu), nhiễu không quá 5%,
Silhouette cao nhất trong các cấu hình đạt điều kiện và có điểm hợp lệ.
Nếu không có cấu hình đạt, ghi nhận rõ và vẫn lưu lưới cùng lambda đã fit.
''')
setcell(17, '''
valid = grid.loc[eligible].sort_values('silhouette', ascending=False)
best = None
selected_model = None
labels = None
if valid.empty:
    print('Không có cấu hình B03 đạt điều kiện; không tự nới ngưỡng để chọn model.')
else:
    best = valid.iloc[0]
    print('Cấu hình được chọn:')
    print(best.to_string())
    labels = labels_b03[(float(best['eps']), int(best['min_samples']))]
    selected_model = DBSCAN(eps=float(best['eps']), min_samples=int(best['min_samples'])).fit(Z)
    assert np.array_equal(selected_model.labels_, labels)
''')
setcell(19, '''
prof = None
if labels is None:
    print('Chưa có model đạt điều kiện để mô tả cụm.')
else:
    prof = X.assign(cluster=labels).groupby('cluster').agg(
        customers=('Monetary', 'size'),
        Recency=('Recency', 'median'),
        Frequency=('Frequency', 'median'),
        Monetary=('Monetary', 'median'),
        Monetary_sum=('Monetary', 'sum'))
    prof['customer_share_pct'] = 100 * prof['customers'] / len(X)
    total_monetary = prof['Monetary_sum'].sum()
    prof['Monetary_share_pct'] = 100 * prof['Monetary_sum'] / total_monetary if total_monetary > 0 else np.nan
    display(prof.drop(columns='Monetary_sum').round(2))
''')
setcell(20, '**Hồ sơ cụm:** dùng RFM gốc để diễn giải, không dùng giá trị sau power transform. Nhãn -1 là nhiễu theo mật độ, không tự đồng nghĩa khách có giá trị thấp.')
setcell(21, '''
if labels is None:
    print('Bỏ qua hình cụm: không có cấu hình đạt điều kiện.')
else:
    fig, ax = plt.subplots(figsize=(9, 6))
    noise = labels == -1
    y = Z[:, 1] if Z.shape[1] >= 2 else np.zeros(len(Z))
    ax.scatter(Z[~noise, 0], y[~noise], c=labels[~noise], cmap='tab10', s=14, alpha=0.6, label='Cụm')
    ax.scatter(Z[noise, 0], y[noise], c='black', marker='x', s=30, label='Nhiễu')
    ax.set_xlabel('PC1')
    ax.set_ylabel('PC2' if Z.shape[1] >= 2 else 'Trục phụ bằng 0 (chỉ giữ 1 PC)')
    ax.set_title(f"B03-DB — eps={best['eps']}, min_samples={int(best['min_samples'])} (Yeo–Johnson; PCA 90%)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / 'dbscan_b03_clusters_pca.png', dpi=150)
    plt.show()
''')
setcell(22, '**Trực quan hóa:** hình dùng tối đa hai thành phần đầu. Kết hợp hình với tỷ lệ nhiễu, kích thước và hồ sơ cụm trước khi kết luận chất lượng B03.')
setcell(23, '''
## Lưu kết quả B03 và lambda đã fit

Lưu lambda theo tên biến vào JSON và lưu các đối tượng đã fit vào joblib.
Preprocessor nhận RFM gốc và tự áp dụng Yeo–Johnson → StandardScaler → PCA;
không gọi fit lại khi nạp. DBSCAN lưu nhãn của tập đã fit, không có hàm predict
cho khách mới như K-Means. Khi không có cấu hình đạt, vẫn lưu preprocessor,
lambda và lưới; trường dbscan trong artifact là None.
''')
setcell(24, '''
grid.to_csv(OUT / 'dbscan_b03_grid.csv', index=False)
if labels is not None:
    pd.DataFrame({'CustomerID': df['CustomerID'], 'cluster': labels}).to_csv(
        OUT / 'dbscan_b03_labels.csv', index=False)

preprocessor = Pipeline([('power', power), ('scaler', scaler), ('pca', pca_b03)])
params = {
    'experiment': EXPERIMENT, 'parent_experiment': 'B01-DB', 'features': FEATURES,
    'data_sha256': sha256(DATA.read_bytes()).hexdigest(),
    'transform': 'Yeo-Johnson', 'method': POWER_METHOD, 'standardize': POWER_STANDARDIZE,
    'lambda_by_feature': lambda_by_feature, 'scaler': 'StandardScaler',
    'pca_variance': PCA_VAR, 'n_components': n_pc,
    'pca_variance_kept': float(pca_b03.explained_variance_ratio_.sum()),
    'eps_grid': EPS_GRID, 'min_samples_grid': MIN_SAMPLES_GRID,
    'max_noise': MAX_NOISE, 'min_clusters': MIN_CLUSTERS,
    'selection_status': 'selected' if best is not None else 'no_eligible_configuration',
    'selection_rule': 'max silhouette_non_noise subject to min_clusters and max_noise',
    'versions': {'numpy': np.__version__, 'pandas': pd.__version__, 'sklearn': sklearn.__version__},
}
if best is not None:
    params.update({
        'eps': float(best['eps']), 'min_samples': int(best['min_samples']),
        'n_clusters': int(best['n_clusters']), 'noise_pct': float(best['noise_pct']),
        'silhouette_non_noise': float(best['silhouette']), 'dbi_non_noise': float(best['dbi']),
    })
artifact = {
    'features': FEATURES, 'preprocessor': preprocessor, 'dbscan': selected_model,
    'customer_ids': df['CustomerID'].tolist(), 'params': params,
}
artifact_path = BASE_DIR / 'dbscan_b03_artifacts.joblib'
joblib.dump(artifact, artifact_path)
loaded = joblib.load(artifact_path)
assert np.allclose(loaded['preprocessor'].transform(X), Z)
assert np.array_equal(loaded['preprocessor']['power'].lambdas_, power.lambdas_)
if labels is not None:
    assert np.array_equal(loaded['dbscan'].labels_, labels)
with (OUT / 'dbscan_b03_params.json').open('w', encoding='utf-8') as f:
    json.dump(params, f, ensure_ascii=False, indent=2, allow_nan=False)
print('Đã lưu tham số, lambda và artifact B03; kiểm tra nạp lại khớp.')
print('Trạng thái:', params['selection_status'])
''')
for c in nb['cells']:
    if c['cell_type'] == 'code':
        ast.parse(''.join(c['source']))
        c['outputs'] = []
        c['execution_count'] = None
target.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('Updated', target)
