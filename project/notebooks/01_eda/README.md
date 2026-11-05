# Chạy lại EDA theo mã tiền xử lý hiện tại

EDA phục vụ **phân cụm khách hàng không giám sát**. Các bảng hành vi, RFM và scaling
là **thử nghiệm theo mã hiện tại**, chưa có căn cứ xác nhận nhóm đã phê duyệt chính sách.
Báo cáo cũ tại chính sách `1c7ce32` và đầu ra processed đã lưu có phạm vi khác;
không trộn các số cũ với lần chạy mới.

Mỗi notebook tự đọc `data/raw/online_retail_II.xlsx`, gọi nguyên trạng
`src.preprocessing.clean_data` trong bộ nhớ rồi tạo tập khảo sát khách có ID.
Pipeline vẫn giữ Guest theo mã của Thuận; EDA loại Guest **sau** pipeline khi tổng hợp khách.
Không thay đổi mã thành viên khác, workbook, processed, Form 2 hoặc các bảng EDA cũ.
Không chạy notebook tiền xử lý có cell ghi processed.

- `eda_v1.ipynb`: giới thiệu/chất lượng, đơn biến, thời gian/quốc gia,
  Num vs Num, Num vs Cat, Cat vs Cat, đa biến và tương quan. Tạo 24 PNG,
  9 CSV mới, metadata/kiểm kê hình và cập nhật báo cáo Markdown từ bảng đã tính.
- `eda_v2_outlier.ipynb`: chạy độc lập, tập trung phân phối/ngoại lệ/RFM/scaling.
  Tính lại từ nguồn, tái tạo có chủ đích 5 PNG chuyên sâu cùng tên; không đọc cache,
  không ghi CSV hoặc báo cáo của v1.
- `eda_analysis.py`: đọc/kiểm kê, trace đối chiếu clean_data, bảng khách/RFM,
  Spearman/Pearson/n theo cặp và các kiểm tra công thức.
- `eda_presentation.py`: toàn bộ mã vẽ và nhận xét tiếng Việt từ số liệu thực thi.
- `eda_report.py`: cấu trúc báo cáo 0–14, công thức/bảng và kiểm kê hình.

Mã notebook chỉ gọi các hàm dùng lại tại đây. Mọi công thức/biến đổi có thể kiểm tra;
không chỉ giữ hình tĩnh. Bảng đầy đủ ở `analysis['tables']` sau Run All.

## Môi trường và lệnh chạy

Dùng thư viện trong `project/requirements.txt`, cùng `nbformat`, `nbclient`,
`nbconvert`, `ipykernel`, `Pillow`. Môi trường hiện có `project/.venv-eda/` đã đủ thư viện.
Python mặc định có thể không có các thư viện này. Từ gốc repository:

```powershell
& project/.venv-eda/Scripts/python.exe -X utf8 -m nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=1800 project/notebooks/01_eda/eda_v1.ipynb
& project/.venv-eda/Scripts/python.exe -X utf8 -m nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=1800 project/notebooks/01_eda/eda_v2_outlier.ipynb
```

Hoặc mở bằng Jupyter, chọn đúng kernel của môi trường và **Restart Kernel → Run All**.
Mỗi notebook chạy riêng được; thứ tự trên dùng để tái tạo đầy đủ bộ bàn giao.
Notebook tự tìm `project/` trong repository, không có đường dẫn máy tác giả.
Đọc Excel có thể mất vài phút; không cần tải dữ liệu hoặc gọi mạng khi chạy lại.

## Đầu ra và kiểm tra

- Hình: `notebooks/01_eda/figures/*.png`.
- Bảng mới: `experiments/eda_current_policy/tables/`: customer_behavior, rfm,
  rfm_transformed, correlation_spearman, correlation_pearson,
  correlation_pairwise_counts, correlation_column_audit, preprocessing_trace,
  scaling_parameters.
- Dấu vết: `experiments/eda_current_policy/run_metadata.json` và `figure_inventory.csv`.
- [Báo cáo EDA](../../reports/bao_cao_qua_trinh_eda.md) dùng đường dẫn hình tương đối.

Cửa sổ [2009-12-01, 2011-12-10); nguồn không ghi múi giờ. Invoice nhiều thời điểm dùng
earliest trong các dòng còn lại. Khách nhiều quốc gia → Multi-country, không gán tùy ý.
F = n_orders; M = total_purchase_value (Q×P chính xác), không đếm trùng biến cùng nghĩa.
Không điền gap NaN của khách một đơn bằng 0, không giả định regex xác minh sản phẩm,
không biến mã khách thành biến số liên tục. Ngưỡng IQR của EDA chỉ gắn cờ điều tra.

Run All kiểm tra khóa, tổng hóa đơn/dòng/giá trị, AOV và gap độc lập, mọi hệ số bằng scipy,
số hợp lệ từng cặp, scaling và SHA256 của raw/processed/src/bảng lịch sử trước/sau.
Metadata ghi Python/thư viện, HEAD, mốc thời gian và checksum. Hai notebook giữ output đã chạy;
hình phải được kiểm tra trực tiếp trước khi tuyên bố kiểm tra hiển thị.
Không tự suy diễn vùng scatter thành cụm hoặc tạo kết quả mô hình chưa chạy.

## Hình lịch sử

Giữ 13 tên PNG cũ và tái tạo cho phạm vi mới, thêm 11 PNG. Ba hình dư được thay thế:
`customer_orders_vs_value.png` bằng panel sáu cặp số;
`signed_line_value_by_country.png` gộp trong panel quốc gia bốn chỉ tiêu;
`raw_transaction_histograms_p01_p99.png` bằng histogram/boxplot toàn miền symlog.
Danh sách/SHA256 nằm trong figure_inventory.csv. Sau khi bộ hình mới đã kiểm tra,
ba hình dư được xóa trong phạm vi EDA; Run All không tự xóa tệp.

Các quyết định về trùng, Guest, C/hoàn trả, danh mục mã, ngoại lệ, RFM và bộ biến/scaling
cần Thuận/nhóm trưởng xác nhận trước dùng làm đầu vào mô hình chính thức.
