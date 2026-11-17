import ast
import json
from pathlib import Path

p = Path('project/notebooks/03_clustering_eval/17-11-2026_hieu_gmm_a04/gmm.ipynb')
nb = json.loads(p.read_text(encoding='utf-8'))

def put(cell, text):
    cell['source'] = text.strip().splitlines(keepends=True)

cells = []
for cell in nb['cells']:
    src = ''.join(cell['source'])
    # Remove only the comparison code and its explanatory section added last turn.
    if cell['cell_type'] == 'code' and (
        src.startswith('from hashlib import sha256') or
        src.startswith("a01_pipeline = joblib.load(A01_DIR")
    ):
        continue
    if cell['cell_type'] == 'markdown' and (
        src.startswith('## So sánh kết quả A04 GMM với A01 K-Means') or
        src.startswith('**Cách đọc:** dùng bảng chấm điểm chung')
    ):
        continue
    if src.startswith('## Đối chiếu đầu vào và thiết lập với A01 K-Means'):
        put(cell, '''
**Nhận xét so với A01 K-Means:** A04 GMM sử dụng cùng tập 4.327 khách hàng và ba
đặc trưng Recency, Frequency, Monetary như A01. Cả hai đều không biến đổi log1p,
dùng StandardScaler, seed 42 và n_init=10. Vì vậy, dữ liệu đầu vào và một số
thiết lập được giữ thống nhất để thuận tiện đối chiếu.

Khác biệt nằm ở thuật toán, ngưỡng PCA và quy tắc chọn cấu hình. A01 dùng K-Means,
PCA ngưỡng 90% và chọn k theo Silhouette cao nhất. A04 dùng GMM, tăng ngưỡng PCA
lên 95%, khảo sát thêm bốn dạng hiệp phương sai và chọn BIC thấp nhất trong các
cấu hình hội tụ, có cụm nhỏ nhất đạt ít nhất 1% số khách. Ngưỡng PCA cao hơn
không nhất thiết làm số thành phần tăng; cần xem số PC thực giữ lại ở bước sau.
Các khác biệt này chưa đủ để kết luận A04 tốt hơn A01; cần đối chiếu kết quả
phân cụm và hồ sơ RFM sau khi chạy mô hình.
''')
    elif src.startswith('**Nhận xét:** kiểm tra trạng thái hội tụ'):
        put(cell, '**Nhận xét:** kiểm tra trạng thái hội tụ, số vòng EM và số khách từng cụm từ kết quả chạy hiện tại. Kết hợp các chỉ số với hồ sơ RFM để đánh giá ý nghĩa của các cụm.')
    elif cell['cell_type'] == 'code' and "res.to_csv(OUT / 'gmm_a04_grid.csv'" in src:
        lines = [line for line in src.splitlines() if not any(token in line for token in (
            'comparison_a01.to_csv', "'ari_vs_a01_kmeans':", "'comparison_space':", "'same_input_sha256_as_a01':"))]
        src = '\n'.join(lines).replace("Đã lưu kết quả A04 và bảng so sánh với A01 vào:", "Đã lưu kết quả A04 vào:")
        put(cell, src)
        cell['outputs'] = []
        cell['execution_count'] = None
    elif src.startswith('**Kết luận A04 GMM:**'):
        put(cell, '''
**Kết luận A04 GMM:** đánh giá kết quả dựa trên BIC, Silhouette, DBI, quy mô và
hồ sơ RFM của các cụm trong lần chạy hiện tại. Khi đối chiếu với A01 K-Means,
cần xét sự khác nhau về thuật toán, PCA và quy tắc chọn cấu hình; chưa kết luận
mô hình tốt hơn chỉ từ thiết lập. Monetary phản ánh chi tiêu lịch sử, chưa phải
lợi nhuận hoặc dự báo giá trị tương lai.
''')
    cells.append(cell)
nb['cells'] = cells
for cell in cells:
    if cell['cell_type'] == 'code':
        src = ''.join(cell['source'])
        ast.parse(src)
        assert not any(token in src for token in ['comparison_a01', 'ari_vs_a01_kmeans', 'same_input_hash', 'a01_pipeline', 'setup_comparison'])
assert nb['cells'][4]['cell_type'] == 'markdown'
p.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('Replaced comparison code with Markdown; no dangling comparison variables; syntax valid.')
