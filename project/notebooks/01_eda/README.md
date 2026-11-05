# EDA từ raw hiện tại — điểm vào và cách chạy

Mở **[eda_raw_moi.ipynb](eda_raw_moi.ipynb)** cho raw duy nhất của dự án:
`project/data/raw/Online Retail.xlsx`. Kết quả từng tính từ dữ liệu chọn nhầm
không hợp lệ cho dự án.

## Nguồn và phạm vi

- Mô tả nguồn: [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail),
  đã đối chiếu ngày 05/11/2026. Đơn giá GBP dựa trên mô tả nguồn; múi giờ không được cung cấp.
- Raw local: 23.715.344 byte, sheet `Online Retail`, **541.909 dòng × 8 cột**;
  01/12/2010 08:26–09/12/2011 12:50, 25.900 chứng từ và 4.372 mã khách.
- SHA-256: `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`.
- Số liệu luôn tính lại từ workbook. Bộ đọc dừng nếu số sheet/schema đổi, không đọc processed/bảng cũ.
- Bản sao EDA chuyển ID thành chuỗi, strip khoảng trắng ở ID/Country; CustomerID bỏ
  hậu tố `.0` do Excel đọc số có thiếu. Description giữ nguyên chuỗi. Raw không sửa byte nào.

Tập mua **khảo sát tạm thời**: InvoiceNo và CustomerID có mã, InvoiceDate hợp lệ,
không có tiền tố C, Quantity > 0 và UnitPrice > 0, cả hai số hữu hạn.
Giữ trùng và mã dịch vụ; không áp quy tắc clean chính thức. Gap dùng min timestamp
của từng hóa đơn, khách một hóa đơn giữ NaN. Recency dùng nửa đêm kế tiếp ngày cuối raw,
không dùng ngày chạy. Công thức đầy đủ trong notebook và bảng `aggregation_formulas` của workbook.

## Chạy lại

Từ gốc repository, dùng môi trường EDA đã có:

```powershell
& project/.venv-eda/Scripts/python.exe -X utf8 -m nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=1800 project/notebooks/01_eda/eda_raw_moi.ipynb
```

Hoặc mở notebook, chọn kernel Python của môi trường EDA và **Restart Kernel → Run All**.
Notebook tìm project theo đường dẫn tương đối; không phụ thuộc đường dẫn máy tác giả.
Nếu cần tạo môi trường mới (Python 3.12+), từ gốc repository:

```powershell
python -m venv project/.venv-eda
& project/.venv-eda/Scripts/python.exe -m pip install -r project/requirements.txt nbformat nbclient nbconvert ipykernel Pillow
```

Phiên bản thực chạy ghi trong sheet `Metadata`. Không cần mạng/API khi phân tích.
Thời gian đọc Excel/vẽ có thể vài phút. Chạy lại sẽ ghi đè **kết quả EDA** bên dưới.
Muốn lưu một lần chạy làm lịch sử, sao lưu cả thư mục kết quả/hình/notebook/báo cáo trước khi chạy tiếp.

Sau khi thực thi notebook, kiểm tra lại đầu ra và đối chiếu với profile raw độc lập đã lưu:

```powershell
& project/.venv-eda/Scripts/python.exe -X utf8 project/experiments/eda_raw_moi/verification/validate_independent.py
& project/.venv-eda/Scripts/python.exe -X utf8 project/experiments/eda_raw_moi/verification/verify_delivery.py
```

Lệnh kiểm tra độc lập đọc lại raw trực tiếp và ghi các đối chiếu vào sheet `Kiem_chung_doc_lap`;
lệnh kiểm tra bàn giao ghi trạng thái vào sheet `Kiem_tra_ban_giao` của cùng workbook.
Các lệnh không tạo CSV hay JSON.

## Thứ tự và đầu ra

0. Bối cảnh, đơn vị dòng/chứng từ/khách và câu hỏi.
1. Kiểm kê raw, sheet, schema, dtypes, mẫu đầu/cuối, SHA-256.
2. Thiếu, trùng, C, dấu lượng/giá, định danh và mẫu bất thường.
3. Thống kê số, danh mục, phân vị/IQR, mẫu cực trị.
4. Đơn biến, top quốc gia/mã hàng, giữ số âm/0/cực trị.
5. Thời gian và hành vi khách tạm, gap thiếu cho khách một đơn.
6. Hai biến, phân loại–phân loại và đa biến có seed.
7. Pearson/Spearman và n theo cặp, tách cấp dòng/cấp khách, loại ID.
8. Phương án sau EDA, chưa chốt hay áp dụng.
9. Kiểm tra, xuất bảng/hình/metadata và báo cáo cùng số liệu.

| Thành phần hiện dùng | Đường dẫn từ project/ |
|---|---|
| Notebook có output | `notebooks/01_eda/eda_raw_moi.ipynb` |
| Tính toán, vẽ và xuất báo cáo | `notebooks/01_eda/eda_raw_analysis.py` |
| Dựng cấu trúc notebook | `notebooks/01_eda/build_eda_raw_notebook.py` |
| Hình mới | `notebooks/01_eda/figures/raw/` |
| Thống kê, danh mục, metadata, kiểm tra | [ket_qua_eda.xlsx](../../experiments/eda_raw_moi/ket_qua_eda.xlsx) |
| Báo cáo EDA mới | [bao_cao_eda_raw_moi.md](../../reports/bao_cao_eda_raw_moi.md) |
| Phương án chờ nhóm | [de_xuat_sau_eda.md](../../reports/de_xuat_sau_eda.md) |
| Kiểm kê nguồn | [kiem_ke_eda_raw_moi.md](../../reports/kiem_ke_eda_raw_moi.md) |

Mỗi hình có nguồn/hash, n hiển thị, bộ lọc, đơn vị, bảng bằng chứng và nhận xét 5 ý.
Ma trận dùng toàn bộ cặp hữu hạn, không impute; scatter đa biến có seed 1505, tối đa 2.000 khách.
Log/symlog chỉ là tọa độ hiển thị; chưa fit scaler/encoder hay mô hình.
Chỉ xuất thống kê/mẫu audit, không xuất giao dịch sạch hoặc bộ feature theo khách.

Chỉ chạy `build_eda_raw_notebook.py` khi sửa cấu trúc trình bày; script sẽ xóa output
của notebook mới, cần thực thi notebook từ đầu sau đó. Metadata ghi hash mã/cell source,
thời gian Asia/Bangkok, git HEAD và trạng thái cây làm việc.

## Các phần việc chưa hợp lệ với raw duy nhất

Các sản phẩm trong `data/processed/` và khảo sát Form 2 được giữ để tác giả đối chiếu,
nhưng số liệu tính từ dữ liệu chọn nhầm không hợp lệ và không dùng cho dự án.
Notebook và API tiền xử lý hiện có chưa tương thích trực tiếp schema raw; cần nhóm
thống nhất chính sách trước khi cập nhật hoặc chạy cleaning.

Các quyết định thiếu mã/mô tả, trùng, hủy/trả, giá 0/âm, mã dịch vụ, ngoại lệ, cửa sổ,
encoding/scaling và tập biến đều **chờ nhóm thống nhất**, xem tài liệu đề xuất.
