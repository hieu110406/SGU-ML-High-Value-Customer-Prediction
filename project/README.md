# Phân khúc khách hàng bằng RFM và hành vi mua hàng trên Online Retail II

Đồ án cuối kỳ môn **Máy học** — Trường Đại học Sài Gòn, Khoa Công nghệ Thông tin.
**Nhóm 15 – DCT124C3** · Giảng viên hướng dẫn: **Đỗ Như Tài**

| MSSV | Họ và tên | Ký hiệu |
|---|---|---|
| 3124411003 | Nguyễn Quốc An (trưởng nhóm) | A |
| 3124411093 | Nguyễn Trung Hiếu | H |
| 3124411191 | Ngô Nguyên | N |
| 3124411296 | Lê Nam Thuận | T |

> **Tình trạng hiện tại (03/11/2026, Sprint 1):** mới hoàn thành khung dự án,
> dữ liệu thô và EDA v1. Các module trong `src/`, cấu hình trong `configs/`,
> ứng dụng trong `app/` và các notebook mô hình hóa **chưa được triển khai**.
> Mục [Tiến độ](#tiến-độ-và-phần-đã-triển-khai) liệt kê chi tiết; các lệnh đánh dấu
> *(dự kiến)* sẽ chỉ chạy được sau khi phần tương ứng hoàn thành.

---

## 1. Giới thiệu

Doanh nghiệp bán lẻ trực tuyến ghi nhận lượng giao dịch lớn từ những nhóm khách hàng
có hành vi mua rất khác nhau. Dự án chuyển dữ liệu giao dịch ở cấp dòng hóa đơn thành
đặc trưng ở cấp khách hàng (RFM và RFM mở rộng), rồi dùng các thuật toán phân cụm
để tìm các nhóm khách hàng có thể diễn giải, trong đó có nhóm giá trị giao dịch lịch sử cao.

**Loại bài toán:** gom cụm (học không giám sát), dữ liệu không có nhãn.
**Đầu vào:** giao dịch bán lẻ (`Invoice`, `Quantity`, `Price`, `Customer ID`, `InvoiceDate`, ...).
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

- **Nguồn:** [Online Retail II — UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/502/online+retail+ii)
  (Daqing Chen). Giao dịch của một nhà bán lẻ trực tuyến đăng ký tại Anh, đơn giá tính bằng GBP.
- **Tệp trong repo:** `data/raw/online_retail_II.xlsx` (khoảng 45 MB, 2 sheet: `Year 2009-2010`, `Year 2010-2011`).
  Tệp gốc **không được sửa**; mọi bước xử lý ghi ra thư mục khác.
- **SHA256 của tệp gốc** (để kiểm tra đúng phiên bản):
  `bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980`
- **Giấy phép dữ liệu:** theo trang UCI của bộ dữ liệu; vui lòng đối chiếu điều khoản trên trang nguồn khi tái sử dụng.

### Các thuộc tính

| Cột | Ý nghĩa |
|---|---|
| `Invoice` | Mã hóa đơn; tiền tố `C` là chứng từ hủy |
| `StockCode` | Mã hàng (có cả mã dịch vụ/điều chỉnh như `POST`, `D`, `M`) |
| `Description` | Tên hàng |
| `Quantity` | Số lượng trên dòng (có thể âm) |
| `InvoiceDate` | Thời điểm lập hóa đơn |
| `Price` | Đơn giá (GBP/đơn vị) |
| `Customer ID` | Mã khách hàng (có dòng thiếu) |
| `Country` | Quốc gia của khách hàng |

### Số liệu thô đã kiểm tra (EDA v1)

| Chỉ tiêu | Giá trị |
|---|---|
| Số dòng / số cột nguồn | 1.067.371 / 8 |
| Khoảng thời gian | 01/12/2009 – 09/12/2011 |
| Mã khách hàng quan sát được | 5.942 |
| Mã hóa đơn duy nhất (gồm hủy/điều chỉnh) | 53.628 |
| Số nhãn quốc gia | 43 |
| Dòng thiếu `Customer ID` | 243.007 |
| Dòng trùng dư trên 8 cột | 34.335 (22.202 mẫu trùng giữa hai sheet) |

Đây là thống kê dữ liệu **thô**, chưa phải quy mô tập huấn luyện. Hai sheet có thời gian
chồng lấn nên việc gộp sheet chưa đồng nghĩa với dữ liệu đã sạch.

## 3. Cấu trúc thư mục

Toàn bộ mã nằm trong thư mục `project/`.

```text
project/
├── app/                  # Demo: backend.py, streamlit_app.py
├── configs/              # YAML tham số mô hình tốt nhất (kmeans_k4, hierarchical_ward, dbscan_eps05)
├── data/
│   ├── raw/              # Dữ liệu gốc, không chỉnh sửa
│   ├── processed/        # Đã xử lý thiếu/hủy/trùng/không hợp lệ
│   └── feature/          # Sau feature engineering (RFM, RFM mở rộng)
├── experiments/          # Đầu ra từng lần chạy, không ghi đè
├── notebooks/
│   ├── 01_eda/                 # eda_v1, eda_v2_outlier
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

Yêu cầu: **Python 3.12** (phiên bản dùng để kiểm tra EDA v1). Thư viện trong
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
sha256sum data/raw/online_retail_II.xlsx
# Windows PowerShell
Get-FileHash data\raw\online_retail_II.xlsx -Algorithm SHA256
```

Kết quả phải trùng với giá trị SHA256 ở mục 2.

## 5. Cách chạy

### 5.1. EDA v1 (đã có)

Từ thư mục `project/`, chạy lại toàn bộ notebook (đọc Excel có thể mất vài phút):

```powershell
.\.venv\Scripts\python.exe -m nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=900 notebooks\01_eda\eda_v1.ipynb
```

Hoặc mở tương tác bằng `.\.venv\Scripts\python.exe -m jupyter lab notebooks/01_eda/eda_v1.ipynb`,
chọn đúng kernel của `.venv`, rồi **Restart Kernel → Run All**. Notebook chỉ đọc
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

1. **Làm sạch:** xử lý thiếu `Customer ID`, hóa đơn hủy (`C`), `Quantity`/`Price` không hợp lệ,
   dòng trùng và trùng giữa hai sheet. Mỗi quy tắc phải ghi rõ lý do và số dòng bị ảnh hưởng.
2. **Đặc trưng:** RFM chuẩn (Recency, Frequency = số hóa đơn, Monetary = tổng chi tiêu) và RFM mở rộng
   (giá trị đơn trung bình, số sản phẩm khác nhau, số lượng trung bình mỗi đơn, tỷ lệ hoàn trả, khoảng cách giữa hai lần mua).
   Biến lệch phải được biến đổi logarit rồi chuẩn hóa bằng `StandardScaler`.
3. **Mô hình:** K-Means trên RFM làm **baseline** (chọn k bằng Elbow và Silhouette, k từ 2 đến 10),
   Hierarchical (Ward, dendrogram, thử các kiểu liên kết) và DBSCAN (chọn `eps` bằng k-distance, thử nhiều `min_samples`).
   PCA dùng để trực quan hóa và khảo sát ảnh hưởng đến chất lượng cụm.
4. **Đánh giá:** Silhouette (độ đo chính), Davies-Bouldin, Calinski-Harabasz; cluster profiling
   (RFM trung bình, kích thước cụm, tỷ trọng doanh thu); đối chiếu với phân khúc RFM theo phân vị
   (luật thủ công) để xem giá trị tăng thêm của học máy; so sánh RFM với RFM mở rộng, có/không PCA.
5. **Độ ổn định:** phân cụm trên dữ liệu 2010 rồi gán cụm cho khách hàng 2011, và chạy lại với nhiều `random_state`.

**Kiểm soát rò rỉ dữ liệu:** ngày tham chiếu và cửa sổ quan sát của RFM phải được cố định
trước khi tính đặc trưng; `StandardScaler` chỉ fit trên tập dùng để phân cụm, sau đó mới transform
tập còn lại. Chưa có ngày tham chiếu hay giá trị `random_state` nào được chốt trong repository.

## 7. Tiến độ và phần đã triển khai

| Hạng mục | Trạng thái |
|---|---|
| Cấu trúc thư mục, `requirements.txt`, `.gitignore` | Đã có |
| Dữ liệu thô `data/raw/` | Đã có |
| `notebooks/01_eda/eda_v1.ipynb` | Hoàn thành, đã chạy |
| Bản thảo Chương 1 (`reports/chuong_1_gioi_thieu_sprint1_T03.md`), Proposal | Đã có |
| `src/*.py`, `configs/*.yaml`, `app/*.py` | Khung rỗng (docstring/TODO) |
| `eda_v2_outlier`, K-Means, Hierarchical, DBSCAN, PCA, profiling | Notebook rỗng |
| Báo cáo đầy đủ, slide, demo Streamlit | Chưa bắt đầu |

Lịch chi tiết 02/11 – 18/11/2026 (8 sprint, 33 đầu việc) nằm trong tệp theo dõi tiến độ của nhóm.

## 8. Giới hạn đã biết

- Dữ liệu là giao dịch 2009–2011 của một nhà bán lẻ tại Anh; kết luận không mặc nhiên đúng cho thời điểm khác hay doanh nghiệp khác.
- Không có chi phí, biên lợi nhuận hay nhân khẩu học, nên Monetary là giá trị giao dịch, không phải lợi nhuận hay giá trị vòng đời.
- Tháng cuối chỉ có dữ liệu đến 09/12/2011.
- Có mã hàng dịch vụ/điều chỉnh (`POST`, `D`, `M`, `B`, ...) cần phân loại trước khi diễn giải là hàng hóa.
- Không có múi giờ; thời gian được giữ nguyên theo nguồn.
- Khách hàng thiếu `Customer ID` không thể gán về khách hàng cụ thể nên bị loại khỏi phân cụm cấp khách hàng.

## 9. Tái lập và trung thực học thuật

- Dữ liệu gốc không bị sửa; có SHA256 để kiểm tra.
- Mỗi lần chạy thực nghiệm lưu riêng trong `experiments/`, không ghi đè.
- Mọi tham số tốt nhất được lưu trong `configs/` để chạy lại.
- Test set không dùng để chọn mô hình hay tinh chỉnh siêu tham số.
- **Công cụ AI hỗ trợ:** nhóm ghi rõ phần nào có sử dụng công cụ AI (viết mã, soạn thảo, rà soát) trong báo cáo, theo quy định của học phần. *(Thành viên cập nhật mục này khi có sử dụng.)*

## 10. Tài liệu tham khảo

- Chen, D. *Online Retail II* [Dataset]. UCI Machine Learning Repository. https://archive.ics.uci.edu/dataset/502/online+retail+ii
- Pedregosa, F. et al. (2011). Scikit-learn: Machine Learning in Python. *Journal of Machine Learning Research*, 12, 2825–2830.
- Các tài liệu lý thuyết về RFM và thuật toán phân cụm: bổ sung theo Chương 2 của báo cáo.
