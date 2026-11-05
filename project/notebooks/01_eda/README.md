# EDA trong một notebook duy nhất

Mở [eda_v1.ipynb](eda_v1.ipynb) để chạy toàn bộ EDA của dự án phân cụm khách hàng.
Notebook đọc workbook và chạy pipeline trong bộ nhớ một lần, dùng cùng bảng dữ liệu
cho mọi phân tích; không cần notebook ngoại lệ riêng hoặc cache trao đổi giữa notebook.

## Thứ tự nội dung

0. Thiết lập, phạm vi và cách chạy.
1. Nguồn, cấu trúc và đơn vị quan sát.
2. Chất lượng dữ liệu.
3. Phân tích đơn biến giao dịch và khách hàng.
4. Thời gian.
5. Quốc gia.
6. Num vs Num, Num vs Cat, Cat vs Cat.
7. Phân tích đa biến.
8. Tương quan Spearman/Pearson và số quan sát theo cặp.
9. IQR giao dịch/khách hàng và mẫu cực trị.
10. Đối chiếu tiền xử lý trước/sau.
11. RFM, log1p và scaling thử nghiệm.
12. Kiểm tra, xuất kết quả và báo cáo.
13. Tổng hợp phát hiện, giới hạn và quyết định cần xác nhận.

Giữ **24 hình riêng biệt**, mỗi hình trình bày một lần; thống kê đơn biến và
bảng ngưỡng IQR có vai trò riêng. Phần ngoại lệ liên kết đến hình phân phối đã có,
không vẽ lại. Bộ đọc dữ liệu, tạo đặc trưng và fit scaler cũng chỉ thực hiện một lần.

## Chạy lại

Chọn đúng kernel theo requirements và dùng **Restart Kernel → Run All**.
Môi trường hiện có `project/.venv-eda/` đã đủ thư viện. Từ gốc repository:

```powershell
& project/.venv-eda/Scripts/python.exe -X utf8 -m nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=1800 project/notebooks/01_eda/eda_v1.ipynb
```

Thư viện: requirements của dự án cùng nbformat, nbclient, nbconvert, ipykernel, Pillow.
Notebook tự tìm project trong repository; không có đường dẫn máy tác giả.

## Mã và kết quả

- `eda_analysis.py`: đọc/kiểm kê, tạo bảng khách/RFM, thống kê và kiểm tra công thức.
- `eda_presentation.py`: mã vẽ và nhận xét từ số liệu thực thi.
- `eda_report.py`: tạo báo cáo 0–14 và kiểm kê hình.
- Hình: `notebooks/01_eda/figures/`.
- 9 CSV: `experiments/eda_current_policy/tables/`, gồm customer_behavior, rfm,
  rfm_transformed, scaling_parameters, preprocessing_trace và 4 bảng tương quan/kiểm kê cột.
- Metadata/checksum: `run_metadata.json`; kiểm kê hình: `figure_inventory.csv` trong cùng thư mục thực nghiệm.
- [Báo cáo EDA](../../reports/bao_cao_qua_trinh_eda.md) được cập nhật từ kết quả đã kiểm tra.

Bảng mô tả giao dịch/khách, IQR và mẫu cực trị nằm trong output và biến analysis['tables'];
không xuất thêm CSV cache. Các kiểm tra tích hợp xác minh khóa, tổng, AOV/gap,
RFM, mọi hệ số tương quan/n, scaling và SHA256 nguồn/mã trước/sau.

## Phạm vi

Cửa sổ [2009-12-01, 2011-12-10); giờ nguồn chưa có múi giờ. Gọi nguyên trạng clean_data
của Thuận trong bộ nhớ; Guest được tách khỏi khảo sát khách sau pipeline. Raw, processed,
module src và bảng EDA/Form 2 lịch sử được giữ nguyên.

F = n_orders; M = tổng Q×P chính xác. Gap của khách một đơn giữ NaN; các chỉ số sản phẩm/
hoàn trả chưa xác minh không điền 0. Ngưỡng IQR1.5 của EDA chỉ gắn cờ điều tra, khác
bộ lọc log-IQR k=3 sẵn có trong pipeline; không tự xóa thêm khách giá trị cao.
Kết quả hành vi/RFM/scaling còn thử nghiệm, cần Thuận/nhóm trưởng xác nhận chính sách.
