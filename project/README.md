# Phân khúc khách hàng bằng RFM và hành vi mua hàng

> **Nguồn raw duy nhất của dự án:** `data/raw/Online Retail.xlsx` (1 sheet).
> Dùng [notebook EDA](notebooks/01_eda/eda_raw_moi.ipynb),
> [hướng dẫn chạy](notebooks/01_eda/README.md), [báo cáo EDA](reports/bao_cao_eda_raw_moi.md)
> và [đề xuất sau EDA](reports/de_xuat_sau_eda.md).
> Dữ liệu từng được chọn nhầm và mọi kết quả tính từ dữ liệu đó **không hợp lệ cho dự án**.
> Các sản phẩm thử nghiệm còn lưu cần được tính lại; mã tiền xử lý chưa tương thích trực tiếp
> schema raw. Xem [kiểm kê nguồn](reports/kiem_ke_eda_raw_moi.md) và [quy ước dự án](AGENTS.md).

Đồ án cuối kỳ môn **Máy học** — Trường Đại học Sài Gòn, Khoa Công nghệ Thông tin.
**Nhóm 15 – DCT124C3** · Giảng viên hướng dẫn: **Đỗ Như Tài**

| MSSV | Họ và tên | Ký hiệu |
|---|---|---|
| 3124411003 | Nguyễn Quốc An (trưởng nhóm) | A |
| 3124411093 | Nguyễn Trung Hiếu | H |
| 3124411191 | Ngô Nguyên | N |
| 3124411296 | Lê Nam Thuận | T |

> **Tình trạng:** EDA đã chạy với raw duy nhất. Chính sách cleaning và bộ đặc trưng
> chưa được nhóm chốt; tiền xử lý chưa tương thích trực tiếp raw này và chưa có kết quả
> mô hình được xác minh từ raw này. Các phần khác là công việc đang phát triển.

---

## 1. Giới thiệu

Doanh nghiệp bán lẻ trực tuyến ghi nhận lượng giao dịch lớn từ những nhóm khách hàng
có hành vi mua rất khác nhau. Dự án chuyển dữ liệu giao dịch ở cấp dòng hóa đơn thành
đặc trưng ở cấp khách hàng (RFM và RFM mở rộng), rồi dùng các thuật toán phân cụm
để tìm các nhóm khách hàng có thể diễn giải, trong đó có nhóm giá trị giao dịch lịch sử cao.

**Loại bài toán:** gom cụm (học không giám sát), dữ liệu không có nhãn.
**Đầu vào:** giao dịch bán lẻ (`InvoiceNo`, `Quantity`, `UnitPrice`, `CustomerID`, `InvoiceDate`, ...).
**Đầu ra:** nhãn cụm của từng khách hàng và hồ sơ mô tả (cluster profile) của mỗi cụm.

**Câu hỏi nghiên cứu**

1. Có thể chia khách hàng thành bao nhiêu nhóm có ý nghĩa dựa trên RFM và hành vi mua hàng?
2. Trong K-Means, Hierarchical Clustering và DBSCAN, thuật toán nào cho chất lượng cụm tốt nhất và dễ diễn giải nhất?
3. Mỗi cụm có đặc điểm gì và nên áp dụng chiến lược kinh doanh nào?

> **Lưu ý về phạm vi:** tên repository có từ "Prediction", nhưng hướng thực hiện là
> **phân cụm dựa trên lịch sử**, không phải dự báo giá trị tương lai. Phân cụm RFM
> không tự chứng minh khả năng dự báo. Nhóm "giá trị cao" được xác định từ hồ sơ cụm
> (Monetary, Frequency, tỷ trọng doanh thu), chưa có ngưỡng nào được chốt.

## 2. Dữ liệu

- **Raw duy nhất:** `data/raw/Online Retail.xlsx`, sheet `Online Retail`.
- **Nguồn mô tả:** [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail),
  giao dịch của nhà bán lẻ trực tuyến tại Anh; đơn giá GBP theo mô tả nguồn.
- **SHA-256:** `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`.
- **Giấy phép:** đối chiếu điều khoản trên trang nguồn khi tái sử dụng.

### Các thuộc tính

| Cột | Ý nghĩa |
|---|---|
| `InvoiceNo` | Mã chứng từ; tiền tố `C` là dấu hiệu hủy |
| `StockCode` | Mã hàng (có cả mã dịch vụ/điều chỉnh như `POST`, `D`, `M`) |
| `Description` | Tên hàng |
| `Quantity` | Số lượng trên dòng (có thể âm) |
| `InvoiceDate` | Thời điểm lập hóa đơn |
| `UnitPrice` | Đơn giá (GBP/đơn vị) |
| `CustomerID` | Mã khách hàng (có dòng thiếu) |
| `Country` | Quốc gia của khách hàng |

### Số liệu thô đã kiểm tra từ raw duy nhất

| Chỉ tiêu | Giá trị |
|---|---|
| Số sheet / số dòng / số cột | 1 / 541.909 / 8 |
| Thời gian quan sát | 01/12/2010 08:26 – 09/12/2011 12:50 |
| Mã khách hàng quan sát được | 4.372 |
| Mã chứng từ duy nhất, gồm C | 25.900 |
| Số nhãn quốc gia | 38 |
| Dòng thiếu `CustomerID` | 135.080 |
| Dòng trùng dư trên 8 cột | 5.268 |

Đây là thống kê raw, chưa phải quy mô tập huấn luyện. Chi tiết, đơn vị và giới hạn
được tính từ cùng file trong [báo cáo EDA](reports/bao_cao_eda_raw_moi.md).

## 3. Cấu trúc thư mục

Toàn bộ mã nằm trong thư mục `project/`.

```text
project/
├── app/                  # Demo: backend.py, streamlit_app.py
├── configs/              # YAML cấu hình thử nghiệm dự kiến
├── data/
│   ├── raw/              # Dữ liệu gốc, không chỉnh sửa
│   ├── processed/        # Sản phẩm không hợp lệ với raw duy nhất; chưa sử dụng
│   └── feature/          # Sau feature engineering (RFM, RFM mở rộng)
├── experiments/          # Kết quả EDA và phần việc thử nghiệm
├── notebooks/
│   ├── 01_eda/                 # eda_raw_moi
│   ├── 02_baseline_kmeans/     # kmeans_v1_elbow, kmeans_v2_silhouette
│   ├── 03_clustering_eval/     # hierarchical_v1_ward, dbscan_v1_eps_grid
│   ├── 04_pca_profiling/       # pca_v1, profiling_v1
│   └── 05_data_processing/
├── reports/              # Báo cáo, slide (reports/slides/)
├── results/
│   └── final/            # Kết quả bản cuối dùng trong báo cáo
├── src/                  # Mã Python hóa từ notebook; là nền cho backend
│   ├── preprocessing.py  # Làm sạch dữ liệu
│   ├── features.py       # RFM, RFM mở rộng, chuẩn hóa
│   ├── models.py         # KMeans, Hierarchical, DBSCAN
│   ├── evaluation.py     # Silhouette, Davies-Bouldin, Calinski-Harabasz, độ ổn định
│   ├── visualization.py  # PCA, biểu đồ cụm, cluster profiling
│   ├── excel_logger.py   # Ghi nhật ký thực nghiệm ra Excel
│   └── run_experiment.py # Điểm vào chạy một thực nghiệm theo YAML
├── requirements.txt
└── README.md
```

Quy trình làm việc: khám phá và chọn tham số trong `notebooks/`, sau đó chuyển phần
đã ổn định sang `src/`, ghi tham số tốt nhất vào `configs/`, chạy bằng
`run_experiment.py` và lưu kết quả vào `experiments/`, bản cuối vào `results/final/`.

## 4. Cài đặt

Yêu cầu: **Python 3.12** (phiên bản dùng để kiểm tra EDA). Thư viện trong
`requirements.txt`: numpy, pandas, scikit-learn, scipy, matplotlib, seaborn, PyYAML,
openpyxl, jupyter, streamlit.

**Windows (PowerShell)**

```powershell
git clone https://github.com/hieu110406/SGU-ML-High-Value-Customer-Prediction.git
cd SGU-ML-High-Value-Customer-Prediction\project
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**Linux / macOS**

```bash
git clone https://github.com/hieu110406/SGU-ML-High-Value-Customer-Prediction.git
cd SGU-ML-High-Value-Customer-Prediction/project
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Kiểm tra dữ liệu đúng phiên bản (từ thư mục `project/`):

```bash
# Linux / macOS
sha256sum "data/raw/Online Retail.xlsx"
# Windows PowerShell
Get-FileHash -LiteralPath 'data/raw/Online Retail.xlsx' -Algorithm SHA256
```

Kết quả phải trùng với giá trị SHA256 ở mục 2.

## 5. Cách chạy

### 5.1. EDA raw hiện tại

Từ thư mục `project/`, chạy lại toàn bộ notebook (đọc Excel có thể mất vài phút):

```powershell
.\.venv-eda\Scripts\python.exe -X utf8 -m nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=1800 notebooks\01_eda\eda_raw_moi.ipynb
```

Hoặc mở tương tác bằng `.\.venv-eda\Scripts\python.exe -m jupyter lab notebooks/01_eda/eda_raw_moi.ipynb`,
chọn đúng kernel của `.venv-eda`, rồi **Restart Kernel → Run All**. Notebook chỉ đọc
`data/raw/`, không ghi vào dữ liệu gốc và có các `assert` kiểm tra nhất quán cuối notebook.

### 5.2. Chạy một thực nghiệm *(dự kiến — chưa triển khai)*

```bash
python -m src.run_experiment --config configs/kmeans_k4.yaml
```

Runner sẽ đọc YAML, chạy pipeline (làm sạch → RFM → chuẩn hóa → phân cụm → đánh giá),
lưu kết quả vào `experiments/<ngày>_<tên>/` và ghi một dòng vào nhật ký Excel
trong `results/`. Hiện lệnh này sẽ báo `NotImplementedError`.

### 5.3. Ứng dụng demo *(dự kiến — chưa triển khai)*

```bash
streamlit run app/streamlit_app.py
```

Demo dự kiến nạp mô hình đã chọn, hiển thị cụm trên PCA 2D/3D, hồ sơ từng cụm và
gán cụm cho khách hàng mới qua `app/backend.py`.

## 6. Phương pháp (kế hoạch)

1. **Làm sạch:** thảo luận cách xử lý `CustomerID` thiếu, chứng từ `C`, `Quantity`/`UnitPrice`
   bất thường và dòng trùng. Mỗi phương án cần ghi lý do và số dòng bị ảnh hưởng.
2. **Đặc trưng:** RFM chuẩn (Recency, Frequency = số hóa đơn, Monetary = tổng chi tiêu) và RFM mở rộng
   (giá trị đơn trung bình, số sản phẩm khác nhau, số lượng trung bình mỗi đơn, tỷ lệ hoàn trả, khoảng cách giữa hai lần mua).
   So sánh các phương án biến đổi và scaling phù hợp; chưa mặc định chốt `log1p` hay scaler.
3. **Mô hình:** K-Means trên RFM làm **baseline** (chọn k bằng Elbow và Silhouette, k từ 2 đến 10),
   Hierarchical (Ward, dendrogram, thử các kiểu liên kết) và DBSCAN (chọn `eps` bằng k-distance, thử nhiều `min_samples`).
   PCA dùng để trực quan hóa và khảo sát ảnh hưởng đến chất lượng cụm.
4. **Đánh giá:** Silhouette (độ đo chính), Davies-Bouldin, Calinski-Harabasz; cluster profiling
   (RFM trung bình, kích thước cụm, tỷ trọng doanh thu); đối chiếu với phân khúc RFM theo phân vị
   (luật thủ công) để xem giá trị tăng thêm của học máy; so sánh RFM với RFM mở rộng, có/không PCA.
5. **Độ ổn định:** thiết kế cửa sổ thời gian phù hợp dữ liệu từ 12/2010 đến 12/2011 và thử nhiều `random_state`; không coi hai năm lịch có cùng thời lượng quan sát.

**Kiểm soát rò rỉ dữ liệu:** ngày tham chiếu và cửa sổ quan sát của RFM phải được cố định
trước khi tính đặc trưng; `StandardScaler` chỉ fit trên tập dùng để phân cụm, sau đó mới transform
tập còn lại. Chưa có ngày tham chiếu hay giá trị `random_state` nào được chốt trong repository.

## 7. Tiến độ và phần đã triển khai

| Hạng mục | Trạng thái |
|---|---|
| Cấu trúc thư mục, `requirements.txt`, `.gitignore` | Đã có |
| Dữ liệu thô `data/raw/` | Đã có |
| `notebooks/01_eda/eda_raw_moi.ipynb` | EDA từ raw duy nhất; xem [hướng dẫn](notebooks/01_eda/README.md) |
| Bản thảo Chương 1 (`reports/chuong_1_gioi_thieu_sprint1_T03.md`), Proposal | Đã có |
| `src/*.py`, `configs/*.yaml`, `app/*.py` | Có mã/cấu hình từng phần; chưa xác minh toàn bộ với raw duy nhất |
| K-Means, Hierarchical, DBSCAN, PCA, profiling | Notebook rỗng |
| Báo cáo đầy đủ, slide, demo Streamlit | Chưa bắt đầu |

Lịch chi tiết 02/11 – 18/11/2026 (8 sprint, 33 đầu việc) nằm trong tệp theo dõi tiến độ của nhóm.

## 8. Giới hạn đã biết

- Dữ liệu là giao dịch từ 12/2010 đến 12/2011 của một nhà bán lẻ tại Anh; kết luận không mặc nhiên đúng cho thời điểm khác hay doanh nghiệp khác.
- Không có chi phí, biên lợi nhuận hay nhân khẩu học, nên Monetary là giá trị giao dịch, không phải lợi nhuận hay giá trị vòng đời.
- Tháng cuối chỉ có dữ liệu đến 09/12/2011.
- Có mã hàng dịch vụ/điều chỉnh (`POST`, `D`, `M`, `B`, ...) cần phân loại trước khi diễn giải là hàng hóa.
- Không có múi giờ; thời gian được giữ nguyên theo nguồn.
- Dòng thiếu `CustomerID` không thể gán về khách hàng cụ thể; cách xử lý đang chờ nhóm thống nhất.
- `data/processed/` và `experiments/form2_manual_behavior_raw_survey/` có sản phẩm từ dữ liệu chọn nhầm, không hợp lệ cho raw duy nhất; giữ để người thực hiện đối chiếu, không dùng làm đầu vào/kết quả dự án.
- `src/preprocessing.py` chưa tương thích schema raw; không chạy cleaning trước khi nhóm thống nhất và cập nhật.

## 9. Tái lập và trung thực học thuật

- Dữ liệu gốc không bị sửa; có SHA256 để kiểm tra.
- Mỗi lần chạy thực nghiệm lưu riêng trong `experiments/`, không ghi đè.
- Mọi tham số tốt nhất được lưu trong `configs/` để chạy lại.
- Test set không dùng để chọn mô hình hay tinh chỉnh siêu tham số.
- **Công cụ AI hỗ trợ:** nhóm ghi rõ phần nào có sử dụng công cụ AI (viết mã, soạn thảo, rà soát) trong báo cáo, theo quy định của học phần. *(Thành viên cập nhật mục này khi có sử dụng.)*

## 10. Tài liệu tham khảo

- Chen, D. *Online Retail* [Dataset]. UCI Machine Learning Repository. https://archive.ics.uci.edu/dataset/352/online+retail
- Pedregosa, F. et al. (2011). Scikit-learn: Machine Learning in Python. *Journal of Machine Learning Research*, 12, 2825–2830.
- Các tài liệu lý thuyết về RFM và thuật toán phân cụm: bổ sung theo Chương 2 của báo cáo.
