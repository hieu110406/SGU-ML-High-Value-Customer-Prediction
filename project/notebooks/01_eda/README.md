# EDA từ raw hiện tại

Notebook chính là [eda.ipynb](eda.ipynb), đọc duy nhất
`data/raw/Online Retail.xlsx`, sheet `Online Retail`, SHA-256
`43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`.

Hướng dẫn cài môi trường, chạy và kiểm tra tập trung tại
[README dự án](../../README.md#luồng-chạy).

- [Workbook EDA](../../experiments/eda_raw_moi/ket_qua_eda.xlsx)
- [Báo cáo EDA](../../reports/bao_cao_eda.md)
- [Báo cáo tiến độ hiện tại](../../reports/bao_cao_tien_do.md)
- [Kiểm kê EDA lịch sử](../../reports/kiem_ke_eda.md)
- [Lựa chọn cần nhóm chốt](../../reports/de_xuat_sau_eda.md)

`eda_raw_analysis.py` tính toán/vẽ/xuất; `build_eda_raw_notebook.py` dựng cấu trúc.
Dựng lại notebook xóa output và cần thực thi lại từ đầu.

EDA chuẩn hóa mã trên bản sao trong bộ nhớ, giữ thời gian nguồn và raw nguyên byte.
Tập mua khảo sát loại C, thiếu mã và lượng/giá không dương nhưng **giữ dòng trùng**,
mã dịch vụ và ngoại lệ; không phải dữ liệu clean chính thức. Gap khách một đơn là NaN.
Biến đổi log/symlog trên trục hình chỉ phục vụ hiển thị, không phải fit scaler.

Baseline thử nghiệm được cho phép riêng ngày 06/11/2026 có cấu hình/đầu ra tách biệt;
không suy ra rằng nhóm đã chốt chính sách chính thức từ khảo sát EDA này.
