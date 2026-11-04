# Chạy từng notebook EDA độc lập

**Mốc chính sách của báo cáo:** các kết quả làm sạch, khảo sát khách hàng và RFM trong bản EDA này dùng chính sách tại commit `1c7ce32`. `main` đã có thay đổi tiền xử lý tại commit `d17492d`; các con số ở đây chưa đánh giá chính sách mới đó. Notebook giữ mã tái hiện chính sách cũ ngay trong một ô riêng để chạy độc lập, không sửa hoặc gọi API cũ đã bị xóa khỏi `src/preprocessing.py`. Các mô tả “hiện tại/current” trong kết quả đã lưu được hiểu tại mốc `1c7ce32`.

Mở notebook bằng Jupyter, chọn môi trường Python có đủ thư viện rồi chọn
**Restart Kernel → Run All**. Mỗi notebook tự đọc dữ liệu và tính lại phần của mình;
không cần chạy notebook khác trước hoặc dùng script Python hỗ trợ EDA.

- `eda_v1.ipynb`: cấu trúc, chất lượng dữ liệu, đối chiếu pipeline, thời gian,
  quốc gia, hành vi, thống kê ngoại lệ và RFM thử nghiệm. Các bảng kiểm tra giữ trong
  notebook; chỉ xuất 3 CSV bàn giao vào `experiments/eda_rebuild/tables/` và PNG, không tạo JSON.
- `eda_v2_outlier.ipynb`: tự đọc workbook, chạy pipeline trong bộ nhớ rồi tính
  phân phối, ngoại lệ và RFM/scaling. Không xuất CSV/JSON riêng; thông tin tái lập và tham số
  được hiển thị trong notebook, PNG ở `figures/`.
  Notebook này không đọc cache hoặc bảng do `eda_v1` xuất.
- `preprocessing_v1.ipynb`: phần tiền xử lý hiện có của nhóm, được giữ nguyên.
  Không cần chạy notebook đó để chạy hai notebook EDA, vì nó có cell ghi processed.

Các phép tính EDA và code vẽ hình nằm trực tiếp trong notebook tương ứng.
Hai notebook vẫn sử dụng API sẵn có trong `src/preprocessing.py` và `src/features.py`
để thống nhất với pipeline của nhóm; không thay đổi các module đó.

Dùng Python có thư viện trong `project/requirements.txt`, cùng `nbformat`,
`nbclient`, `nbconvert`, `ipykernel`, `Pillow`. Môi trường và checksum nguồn được
hiển thị trong output từng notebook. Từ thư mục gốc repository, có thể chạy riêng:

```powershell
& project/.venv-eda/Scripts/python.exe -X utf8 -m jupyter nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=1800 project/notebooks/01_eda/eda_v1.ipynb
```

```powershell
& project/.venv-eda/Scripts/python.exe -X utf8 -m jupyter nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=1800 project/notebooks/01_eda/eda_v2_outlier.ipynb
```

Nếu dùng môi trường khác, thay đường dẫn Python và chọn đúng kernel của môi trường đó.
Notebook tự tìm `project/` từ working directory trong repository; không có đường dẫn
riêng của tác giả. Việc đọc workbook có thể mất vài phút.

`eda_v1` tính 35 bảng trong notebook, tạo lại 16 PNG và chỉ xuất 3 CSV:
`customer_behavior.csv`, `rfm.csv`, `rfm_transformed.csv`. Tham số scaling hiển thị đầy đủ
trong bảng `scaling_parameters` và output notebook; không cần JSON/CSV tham số riêng.
Các bảng thiếu/trùng/thống kê/quốc gia/ngoại lệ vẫn được tính và hiển thị trong notebook;
sau Run All, xem toàn bộ bằng biến `tables["tên_bảng"]`.
[Báo cáo quá trình EDA](../../reports/bao_cao_qua_trinh_eda.md) đã hoàn thành được giữ
riêng; Run All không ghi đè văn bản báo cáo. Khi thay dữ liệu hoặc chính sách, cập nhật
cả phần nhận xét trong notebook và nội dung báo cáo theo kết quả mới.
Notebook kiểm tra SHA256 của workbook và module nguồn trước/sau, đồng thời hiển thị
phiên bản thư viện. Dữ liệu gốc, processed và CSV khảo sát Form 2 cũ được giữ nguyên.
Thông tin nguồn Form 2 cũ đã chuyển sang phụ lục của báo cáo Form 2; các bảng cũ chỉ dùng
đối chiếu lịch sử, không thay cho bảng khảo sát mới.

RFM và fit scaling là phần bổ sung sau EDA được form ban đầu cho phép, được đánh dấu riêng
và vẫn là thử nghiệm; chưa chạy mô hình phân cụm. Các quy tắc mua/hủy/phí/trùng,
danh mục sản phẩm và lựa chọn cửa sổ vẫn **Cần nhóm xác nhận**.
