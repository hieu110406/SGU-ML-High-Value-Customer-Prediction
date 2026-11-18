from pathlib import Path
import ast
import json
import uuid

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / 'project/notebooks/03_clustering_eval/17-11-2026_hieu_gmm_a04/gmm.ipynb'
nb = json.loads(PATH.read_text(encoding='utf-8'))

def make(kind, source):
    c = dict(cell_type=kind, metadata={}, id=uuid.uuid4().hex[:8], source=source.strip().splitlines(keepends=True))
    if kind == 'code':
        ast.parse(source.strip())
        c.update(execution_count=None, outputs=[])
    return c

def replace(index, source, kind=None):
    old = nb['cells'][index]
    new = make(kind or old['cell_type'], source)
    new['id'] = old.get('id', new['id'])
    new['metadata'] = old.get('metadata', {})
    nb['cells'][index] = new

early_md = make('markdown', '''
## Đối chiếu đầu vào và thiết lập với A01 K-Means

A01 là notebook K-Means trong `17-11-2026-hieu-kmeans-rfm`. Kiểm tra dữ liệu
theo CustomerID và giá trị RFM trước khi so sánh. Hai ngưỡng PCA có thể giữ
cùng số thành phần; số PC của A04 được xác nhận tại bước PCA bên dưới.
Phần so sánh nhãn và chất lượng cụm nằm sau ô train GMM, khi đã có nhãn A04.
''')
early_code = make('code', '''
from hashlib import sha256

A01_DIR = find('notebooks/02_baseline_kmeans/17-11-2026-hieu-kmeans-rfm')
A01_DATA = A01_DIR / 'data/customer_features.csv'
with (A01_DIR / 'kmeans_PCA_params.json').open(encoding='utf-8') as f:
    a01_params = json.load(f)
df_a01 = pd.read_csv(A01_DATA, dtype={'CustomerID': 'string'})
assert df['CustomerID'].notna().all() and df['CustomerID'].is_unique
assert df_a01['CustomerID'].notna().all() and df_a01['CustomerID'].is_unique
assert a01_params['features'] == FEATURES, 'Hai model phải dùng cùng thứ tự đặc trưng RFM.'
assert set(df_a01['CustomerID']) == set(df['CustomerID']), 'Hai model khác tập khách hàng.'

# Căn theo CustomerID, không dựa vào thứ tự dòng của hai file.
X_a01_aligned = df_a01.set_index('CustomerID').loc[df['CustomerID'], FEATURES]
assert np.isfinite(X_a01_aligned.to_numpy(dtype=float)).all()
assert np.allclose(X_a01_aligned.to_numpy(dtype=float), X.to_numpy(dtype=float),
                   rtol=1e-12, atol=1e-9), 'Giá trị RFM khác nhau; chưa so sánh trực tiếp.'
same_input_hash = sha256(DATA.read_bytes()).hexdigest() == sha256(A01_DATA.read_bytes()).hexdigest()
print('Cùng tập khách và giá trị RFM: Có')
print('File đầu vào có SHA-256 trùng nhau:', same_input_hash)

setup_comparison = pd.DataFrame([
    {'Tiêu chí': 'Thuật toán', 'A01 K-Means': 'K-Means', 'A04 GMM': 'GaussianMixture'},
    {'Tiêu chí': 'Đặc trưng', 'A01 K-Means': ', '.join(a01_params['features']), 'A04 GMM': ', '.join(FEATURES)},
    {'Tiêu chí': 'Số khách', 'A01 K-Means': len(df_a01), 'A04 GMM': len(df)},
    {'Tiêu chí': 'Biến đổi log1p', 'A01 K-Means': 'Không (theo notebook A01)', 'A04 GMM': 'Không'},
    {'Tiêu chí': 'Chuẩn hóa', 'A01 K-Means': a01_params['scaling'], 'A04 GMM': 'StandardScaler'},
    {'Tiêu chí': 'Ngưỡng PCA', 'A01 K-Means': a01_params['pca']['variance_threshold'], 'A04 GMM': PCA_VAR},
    {'Tiêu chí': 'Số PC', 'A01 K-Means': a01_params['pca']['n_components'], 'A04 GMM': 'Tính tại bước PCA bên dưới'},
    {'Tiêu chí': 'Seed', 'A01 K-Means': a01_params['kmeans']['random_state'], 'A04 GMM': RANDOM_STATE},
    {'Tiêu chí': 'n_init', 'A01 K-Means': a01_params['kmeans']['n_init'], 'A04 GMM': N_INIT},
    {'Tiêu chí': 'Khảo sát', 'A01 K-Means': 'k=2..10 (theo notebook A01)',
     'A04 GMM': f'k={min(K_RANGE)}..{max(K_RANGE)}; ' + ', '.join(COV_TYPES)},
    {'Tiêu chí': 'Quy tắc chọn', 'A01 K-Means': a01_params['selection'],
     'A04 GMM': f'BIC nhỏ nhất; hội tụ; cụm nhỏ nhất >= {MIN_CLUSTER_FRAC:.0%} số khách'},
])
display(setup_comparison)
''')

replace(13, '''
## So sánh kết quả A04 GMM với A01 K-Means

Nạp pipeline A01 đã lưu, không huấn luyện lại. Cả hai bộ nhãn được chấm trên
cùng ma trận RFM chuẩn hóa `X_scaled`, gồm toàn bộ khách theo cùng thứ tự.
Các điểm này là phép đánh giá chung, có thể khác điểm trên PCA riêng của mỗi model.
ARI đo mức giống nhau giữa hai cách chia cụm, không xác định model nào tốt hơn.
''')
replace(14, '''
a01_pipeline = joblib.load(A01_DIR / 'kmeans_model.pkl')
if not isinstance(a01_pipeline, Pipeline) or 'kmeans' not in a01_pipeline.named_steps:
    raise ValueError('File A01 chưa chứa pipeline scaler/PCA/K-Means. Chạy lại ô lưu pipeline của A01 trước.')
assert a01_pipeline['kmeans'].n_clusters == a01_params['kmeans']['n_clusters']
assert a01_pipeline['pca'].n_components_ == a01_params['pca']['n_components']

# A01 nhận RFM gốc; không truyền X_scaled vào pipeline đã chứa scaler.
labels_a01_kmeans = a01_pipeline.predict(X[FEATURES])
assert np.array_equal(model.predict(X_t), labels), 'Nhãn GMM không khớp pipeline hiện tại.'
comparison_rows = []
for name, lab in [('A01 K-Means', labels_a01_kmeans), ('A04 GMM', labels)]:
    sizes = pd.Series(lab).value_counts()
    assert 2 <= len(sizes) < len(X_scaled), f'{name}: không đủ cụm hợp lệ để chấm điểm.'
    comparison_rows.append({
        'Mô hình': name,
        'Không gian chấm điểm': 'RFM StandardScaler; toàn bộ khách',
        'Số cụm': len(sizes),
        'Cụm nhỏ nhất (khách)': int(sizes.min()),
        'Cụm lớn nhất (%)': 100 * sizes.max() / len(lab),
        'Silhouette': silhouette_score(X_scaled, lab),
        'DBI': davies_bouldin_score(X_scaled, lab),
        'CHI': calinski_harabasz_score(X_scaled, lab),
    })
comparison_a01 = pd.DataFrame(comparison_rows).set_index('Mô hình')
ari_vs_a01_kmeans = adjusted_rand_score(labels_a01_kmeans, labels)
display(comparison_a01.round(4))
print('Số PC: A01 =', a01_pipeline['pca'].n_components_, '| A04 =', n_pc)
print('ARI (A04 GMM so với A01 K-Means):', round(ari_vs_a01_kmeans, 4))
display(pd.crosstab(
    pd.Series(labels_a01_kmeans, name='A01 K-Means'),
    pd.Series(labels, name='A04 GMM'),
    margins=True, margins_name='Tổng',
))
print('Silhouette/CHI cao hơn và DBI thấp hơn là thuận lợi; cần xem thêm quy mô và hồ sơ RFM của cụm.')
print('ARI gần 1 biểu thị hai cách chia gần trùng nhau; ARI không phải chỉ số xếp hạng chất lượng.')
''')
replace(15, '''
**Cách đọc:** dùng bảng chấm điểm chung để đối chiếu độ tách biệt và quy mô cụm.
Bảng chéo cho biết khách trong từng cụm A01 được phân sang các cụm A04 thế nào.
Không so trực tiếp BIC của GMM với Inertia của K-Means vì chúng là hai tiêu chí khác nhau.
Đây là đối chiếu toàn bộ hai pipeline; khác biệt có thể đến từ cả PCA và thuật toán.
''')

# Remove descriptions inherited from B02 that no longer describe this A04 run.
replace(9, '**Nhận xét:** cấu hình GMM được chọn theo BIC nhỏ nhất trong các cấu hình hội tụ và có cụm nhỏ nhất đạt ngưỡng đã đặt. Đọc giá trị thực chạy từ bảng và hình bên trên.')
replace(12, '**Nhận xét:** kiểm tra trạng thái hội tụ, số vòng EM và số khách từng cụm từ kết quả chạy hiện tại. Phần tiếp theo đối chiếu trực tiếp với A01 K-Means.')
replace(18, '**Nhận xét:** dùng trung vị RFM gốc, tỷ trọng khách và tổng Monetary để diễn giải từng cụm. Nhãn cụm chỉ là mã định danh, không tự biểu thị thứ hạng giá trị.')
replace(20, '**Nhận xét:** hình thể hiện hai thành phần PCA đầu tiên. Đối chiếu hình với các chỉ số và hồ sơ cụm; không kết luận chất lượng chỉ từ hình chiếu 2D.')
replace(23, '''
**Kết luận A04 GMM:** tổng hợp kết quả từ bảng so sánh A01 K-Means và hồ sơ RFM
của lần chạy hiện tại. Silhouette, DBI và CHI trong bảng so sánh dùng chung dữ liệu
RFM chuẩn hóa; ARI mô tả mức tương đồng giữa hai cách phân cụm. Monetary là chi tiêu
lịch sử, chưa phải lợi nhuận hoặc dự báo giá trị tương lai.
''')

replace(22, '''
res.to_csv(OUT / 'gmm_a04_grid.csv', index=False)
pd.DataFrame({'CustomerID': df['CustomerID'], 'cluster': labels, 'max_proba': proba.max(axis=1).round(4)}) \\
    .to_csv(OUT / 'gmm_a04_labels.csv', index=False)
joblib.dump(model, 'gmm_a04_model.pkl')
comparison_a01.to_csv(OUT / 'gmm_a04_vs_a01_kmeans.csv')
params = {
    'experiment': 'A04-GMM', 'features': FEATURES, 'log_cols': [], 'scaler': 'StandardScaler',
    'pca_variance': PCA_VAR, 'n_components': n_pc, 'pca_variance_kept': float(cum[n_pc - 1]),
    'covariance_type': best['covariance_type'], 'k': int(best['k']), 'bic': float(best['BIC']),
    'silhouette': float(silhouette_score(Z, labels)), 'dbi': float(davies_bouldin_score(Z, labels)),
    'ari_vs_a01_kmeans': float(ari_vs_a01_kmeans),
    'comparison_space': 'RFM StandardScaler, all customers, aligned by CustomerID',
    'same_input_sha256_as_a01': same_input_hash,
}
with (OUT / 'gmm_a04_params.json').open('w', encoding='utf8') as f:
    json.dump(params, f, ensure_ascii=False, indent=2)
print('Đã lưu kết quả A04 và bảng so sánh với A01 vào:', OUT.resolve())
''')
for index in [8,19]:
    src=''.join(nb['cells'][index]['source'])
    src=src.replace('B02-GN — chỉ số theo k (log1p F,M; giữ R; Standard; PCA 90%)', 'A04 GMM — chỉ số theo k (RFM; Standard; PCA 95%)')
    src=src.replace('B02-GN —', 'A04 GMM —')
    replace(index,src)

# Insert immediately after original cell 3, before the PCA heading (original cell 4).
nb['cells'][4:4]=[early_md,early_code]
# Existing output belongs to the earlier B02 notebook; refresh it with Run All.
for c in nb['cells']:
    if c['cell_type']=='code':
        ast.parse(''.join(c['source']))
        c['outputs']=[]
        c['execution_count']=None
PATH.write_text(json.dumps(nb,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
print(PATH)
