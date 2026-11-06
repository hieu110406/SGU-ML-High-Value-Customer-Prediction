# Phân khúc khách hàng bằng RFM và hành vi mua hàng

Đồ án môn **Máy học**, nhóm **15 – DCT124C3**, Trường Đại học Sài Gòn.
Giảng viên: Đỗ Như Tài. Thành viên: Nguyễn Quốc An, Nguyễn Trung Hiếu,
Ngô Nguyên và Lê Nam Thuận.

Dự án tổng hợp giao dịch thành đặc trưng khách hàng rồi phân cụm để mô tả giá trị
mua lịch sử. Monetary không phải lợi nhuận, giá trị vòng đời hoặc dự báo tương lai.
Phạm vi lần bàn giao này dừng ở K-Means baseline.

**Trạng thái:** EDA từ raw hiện tại được tái sử dụng và kiểm chứng. Ngày 06/11/2026,
người dùng cho phép chạy cấu hình **thử nghiệm riêng**, chưa phải quyết định chính
thức của toàn nhóm. Clean/feature thử nghiệm nằm trong `experiments/baseline/`,
không thay thế `data/processed/`. Xem [báo cáo tiến độ](reports/bao_cao_tien_do.md).

## Dữ liệu và phiên bản

Nguồn duy nhất: [Online Retail.xlsx](data/raw/Online%20Retail.xlsx), một sheet
`Online Retail`. Mô tả nguồn: [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail),
DOI [10.24432/C5BW33](https://doi.org/10.24432/C5BW33).

| Thuộc tính | Giá trị |
|---|---|
| SHA-256 | `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d` |
| Kích thước | 23.715.344 byte |
| Dòng × cột | 541.909 × 8 |
| Thời gian nguồn | 01/12/2010 08:26 – 09/12/2011 12:50; không có múi giờ |
| Chứng từ / khách có mã / quốc gia | 25.900 / 4.372 / 38 |
| Thiếu CustomerID / Description | 135.080 / 1.454 dòng |
| Dòng trùng dư trên đủ 8 cột | 5.268 |

Schema: `InvoiceNo`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`,
`UnitPrice`, `CustomerID`, `Country`. Đơn giá GBP theo UCI. Một dòng là một dòng
hàng/chứng từ, không phải một hóa đơn hoàn chỉnh hay một khách hàng.

Kiểm tra hash từ `project/`:

```powershell
Get-FileHash -LiteralPath 'data/raw/Online Retail.xlsx' -Algorithm SHA256
```

```bash
sha256sum 'data/raw/Online Retail.xlsx'
```

Không sửa raw. Sản phẩm từ `online_retail_II.xlsx` hoặc không xác minh được nguồn
không được dùng làm đầu vào/kết quả của raw hiện tại.

## Cấu trúc hiện tại

```text
project/
├── AGENTS.md
├── README.md
├── requirements.txt
├── data/
│   ├── raw/Online Retail.xlsx
│   ├── processed/data_clean.csv.gz       # Legacy, chưa đủ bằng chứng provenance
│   └── feature/                          # Giữ cấu trúc của nhóm
├── notebooks/
│   ├── 01_eda/
│   │   ├── eda.ipynb                     # Notebook EDA chính
│   │   ├── eda_raw_analysis.py
│   │   ├── build_eda_raw_notebook.py
│   │   └── figures/raw/
│   ├── 02_baseline_kmeans/
│   │   └── baseline_kmeans.ipynb        # Notebook chính: raw → RFM → K-Means → đánh giá
│   ├── 03_clustering_eval/               # Chưa triển khai trong phạm vi này
│   ├── 04_pca_profiling/                 # Khung công việc sau baseline
│   └── 05_data_processing/               # Notebook tiền xử lý lịch sử
├── src/                                  # Cleaning, features, models, đánh giá, runner
├── configs/kmeans_k4.yaml                 # Tên lịch sử; thực khảo sát k=2…10
├── experiments/
│   ├── eda_raw_moi/ket_qua_eda.xlsx
│   ├── eda_raw_moi/verification/
│   ├── baseline/                         # Đầu ra thử nghiệm riêng
│   └── form2_manual_behavior_raw_survey/  # Lịch sử, không dùng số liệu
├── reports/
│   ├── bao_cao_tien_do.md                 # Báo cáo hợp nhất hiện hành
│   ├── bao_cao_eda.md                     # Báo cáo EDA sinh từ mã
│   ├── de_xuat_sau_eda.md                 # Các lựa chọn cần nhóm xác nhận
│   ├── kiem_ke_eda.md                     # Kiểm kê lần dựng EDA trước
│   ├── form2_manual_behavior_features.md  # API/khảo sát lịch sử
│   ├── chuong_1_gioi_thieu_sprint1_T03.md  # Bản thảo học phần riêng
│   └── Nhom15_PhanKhucKhachHang_Proposal.docx
├── tests/
├── app/                                  # Khung demo; ngoài phạm vi lần này
└── results/final/                         # Chưa công bố kết quả chính thức
```

## Cài đặt

Dùng **Python 3.12**; lần kiểm tra dùng Python 3.12.15. Các lệnh chạy từ `project/`.
Tạo một môi trường `.venv`, không phụ thuộc `.venv-eda` cũ của máy tác giả.

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
& .venv/Scripts/python.exe -m pip install -r requirements.txt
```

Linux/macOS:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Trong các ví dụ sau, `python` là Python của môi trường vừa tạo. Trên PowerShell
có thể thay bằng `& .venv/Scripts/python.exe`; trên Linux/macOS dùng `.venv/bin/python`.
Phiên bản thư viện thực tế được ghi trong workbook kết quả.

## Luồng chạy

`Raw → EDA → cấu hình có trạng thái → cleaning có log → features/RFM → scaling → K-Means → đánh giá`

### EDA

Mở [eda.ipynb](notebooks/01_eda/eda.ipynb), chọn đúng kernel và
**Restart Kernel → Run All**, hoặc:

```bash
python -X utf8 -m nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=1800 notebooks/01_eda/eda.ipynb
python -X utf8 experiments/eda_raw_moi/verification/validate_independent.py
python -X utf8 experiments/eda_raw_moi/verification/verify_delivery.py
```

EDA ghi một [workbook](experiments/eda_raw_moi/ket_qua_eda.xlsx),
[hình](notebooks/01_eda/figures/raw/) và [báo cáo EDA](reports/bao_cao_eda.md).
Script kiểm tra cập nhật sheet kiểm chứng của cùng workbook. Chạy lại thay các
đầu ra EDA này; không tạo clean chính thức. Chỉ chạy `build_eda_raw_notebook.py`
khi sửa cấu trúc notebook vì việc dựng lại xóa output.

### Kiểm tra raw và từng bước

```bash
python -m src.run_experiment --config configs/kmeans_k4.yaml --stage audit
```

`audit` chỉ đọc và in kiểm tra raw. Có thể chạy riêng `--stage clean` hoặc
`--stage features` trên thư mục đầu ra chưa tồn tại để kiểm tra bước tương ứng.
Các stage này là lựa chọn thay thế cho lần chạy toàn bộ, không cần chạy tuần tự.
Log cleaning ghi dòng, hóa đơn và khách trước/sau từng bước; không cộng các cờ
chồng lấn.

### Baseline K-Means từ raw

Mở [baseline_kmeans.ipynb](notebooks/02_baseline_kmeans/baseline_kmeans.ipynb),
chọn kernel của môi trường đã cài ở trên, rồi **Restart Kernel → Run All**.
Notebook trình bày toàn bộ bước đọc raw, cleaning có log, RFM, scaling, khảo sát
k=2…10, chọn k và hồ sơ cụm. Bảng/biểu đồ đã lưu ngay trong notebook để mở xem;
chạy lại tính trong bộ nhớ và đối chiếu với artifact CLI nếu có, không ghi đè
raw, processed hoặc kết quả CLI. Cần giữ notebook trong repository cùng `src/`,
cấu hình và raw; notebook không phải tệp độc lập chỉ cần tải riêng để chạy.
Hai notebook `kmeans_v1_elbow.ipynb` và `kmeans_v2_silhouette.ipynb` là khung lịch sử,
được giữ để đối chiếu; dùng notebook chính ở trên.

Có thể thực hiện cùng luồng bằng CLI để xuất workbook, dữ liệu và mô hình:

```bash
python -m src.run_experiment --config configs/kmeans_k4.yaml
```

Để tái lập một lần chạy baseline đã hoàn thành trong cùng thư mục:

```bash
python -m src.run_experiment --config configs/kmeans_k4.yaml --stage baseline --overwrite
```

`--overwrite` chỉ thay các file đầu ra do runner quản lý trong thư mục thực nghiệm;
không xóa cả thư mục. Runner từ chối ghi đè đầu ra dở dang không xác minh được nguồn.
Tên `kmeans_k4.yaml` được giữ để tránh phá liên kết; nội dung thực khảo sát
**k=2…10**, không áp đặt k=4. Cấu hình thử nghiệm ngày 06/11/2026:

- Loại thiếu mã khách, chứng từ C, Quantity/UnitPrice không dương và bản sao hoàn toàn
  trên 8 cột; giữ mã dịch vụ, khách mua sỉ và ngoại lệ.
- Tất cả quốc gia; cửa sổ `[2010-12-01, 2011-12-10)`.
- R là số ngày lịch từ ngày mua cuối đến 10/12/2011; F là số InvoiceNo mua duy nhất;
  M là tổng Quantity × UnitPrice dòng mua giữ lại, chưa đối trừ trả hàng.
- Chỉ dùng RFM; `log1p` rồi `StandardScaler`; seed 42, n_init=20.
- Chọn k có Silhouette lớn nhất trên toàn bộ khách trong phạm vi khảo sát; dùng
  Elbow, Davies–Bouldin, kích thước và hồ sơ cụm để diễn giải. Không khẳng định tối ưu tuyệt đối.

Đầu ra trong `experiments/baseline/`:

| File | Nội dung |
|---|---|
| `results.xlsx` | Metadata, raw, log clean, features, kiểm tra RFM, scaling, metric, hồ sơ cụm |
| `cleaned.csv.gz` | Dòng mua sau clean, chỉ là dữ liệu thử nghiệm riêng |
| `assignments.csv.gz` | CustomerID, RFM, đặc trưng thủ công và Cluster |
| `artifacts.joblib` | Biến đổi, scaler và mô hình để tái lập |
| `metrics.png` | Elbow, Silhouette, Davies–Bouldin theo k |
| `cluster_profiles.png` | Hồ sơ cụm |
| `feature_distributions.png` | Phân phối đặc trưng trước/sau biến đổi |

Chi tiết công thức, số liệu thực chạy và giới hạn ở [báo cáo tiến độ](reports/bao_cao_tien_do.md).

### Kiểm tra mã

Từ **gốc repository**:

```bash
python -m unittest discover -s project/tests -v
```

Baseline đánh giá mô tả trong cùng cửa sổ lịch sử, chưa có tập kiểm định độc lập.
Khi đánh giá theo thời gian sau này, chỉ fit phép biến đổi trên tập phát triển.
Không dùng Accuracy, Precision hoặc Recall cho phân cụm không có nhãn thật.

## Tài liệu và phần việc tiếp theo

- [Báo cáo tiến độ](reports/bao_cao_tien_do.md): kiểm tra ban đầu, quyết định thử nghiệm,
  công thức, kết quả, kiểm thử và các điểm chờ nhóm xác nhận.
- [EDA](reports/bao_cao_eda.md) và [workbook bằng chứng](experiments/eda_raw_moi/ket_qua_eda.xlsx):
  tập mua khảo sát EDA giữ trùng nên quy mô khác clean baseline.
- [Đề xuất sau EDA](reports/de_xuat_sau_eda.md): phương án chính thức còn chờ nhóm chốt.
- [Quy ước dữ liệu](AGENTS.md): raw bất biến, không dùng kết quả từ nguồn chọn nhầm.
- `data/processed/` là sản phẩm legacy thiếu SHA/quy tắc đã được chốt, chưa dùng làm
  bằng chứng baseline hiện tại. Log có tên/số dòng của raw hiện tại nên không kết
  luận nó từ nguồn chọn nhầm. Form 2 có bằng chứng dùng raw sai; notebook tiền xử lý
  cũ giữ để tác giả đối chiếu. Chapter 1/Proposal giữ chức năng lịch sử, chưa sửa
  thành báo cáo kết quả cuối cùng.
- Hierarchical, DBSCAN, so sánh ít nhất hai mô hình theo yêu cầu học phần, demo và
  báo cáo cuối kỳ thuộc công việc sau baseline. Chưa hoàn thành toàn bộ đề tài.

## Nguồn và hỗ trợ AI

- Chen, D. [Online Retail, UCI](https://archive.ics.uci.edu/dataset/352/online+retail).
- Pedregosa et al. (2011), [Scikit-learn: Machine Learning in Python](https://jmlr.org/papers/v12/pedregosa11a.html).
- Tài liệu [K-Means](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html),
  [StandardScaler](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html),
  [Silhouette](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html).
- Codex hỗ trợ rà soát, sửa pipeline, kiểm thử và soạn tài liệu ngày 06/11/2026.
  Nhóm cần kiểm tra, hiểu mã và ghi nhận hỗ trợ AI theo quy định học phần; hỗ trợ AI
  không thay thế quyết định nghiệp vụ của nhóm.
