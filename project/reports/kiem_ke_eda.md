# Kiểm kê nguồn raw và phạm vi EDA

Dự án chỉ sử dụng **một file raw**: `data/raw/Online Retail.xlsx`, sheet `Online Retail`. Dữ liệu từng được chọn nhầm không phải nguồn của dự án; mọi số liệu, hình, bảng đã xử lý và kết quả tính từ dữ liệu đó đều không hợp lệ. Những sản phẩm của thành viên còn lưu chỉ được giữ để đối chiếu công việc, không dùng làm bằng chứng hay đầu vào.

## 1. Trạng thái repository trước khi dựng EDA

| Nội dung | Kết quả kiểm tra ban đầu |
|---|---|
| Repository | `D:/cnpm/SGU-ML-High-Value-Customer-Prediction` |
| Nhánh / commit | `main` / `c95b536e12e001fd67ceef5a2ace46faba778b9d` |
| Git ban đầu | Không có thay đổi chưa commit hoặc tệp untracked tại thời điểm kiểm tra ban đầu |
| Raw duy nhất | `data/raw/Online Retail.xlsx` |
| Múi giờ làm việc khi kiểm tra | Asia/Bangkok |

Trạng thái Git sau các thay đổi không còn sạch. Theo yêu cầu, 43 tệp EDA từ dữ liệu chọn nhầm đã được xóa; danh sách và checksum trước khi xóa nằm trong sheet `Da_xoa_EDA_cu` của [workbook kết quả](../experiments/eda_raw_moi/ket_qua_eda.xlsx).

## 2. Kiểm kê workbook raw

Các số liệu dưới đây được tính trực tiếp từ file raw duy nhất; không sao chép số đếm từ trang nguồn.

| Nội dung | Kết quả |
|---|---|
| Tên file / định dạng | `data/raw/Online Retail.xlsx` / XLSX |
| Kích thước | 23.715.344 byte |
| SHA-256 | `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d` |
| Sheet | 1: `Online Retail` |
| Số dòng giao dịch / số cột | 541.909 / 8, không tính dòng tiêu đề |
| Thời gian nhỏ nhất – lớn nhất | 2010-12-01 08:26:00 – 2011-12-09 12:50:00 |
| Chứng từ khác nhau | 25.900, gồm chứng từ tiền tố C |
| Khách hàng có mã | 4.372 |
| Mã hàng / nhãn quốc gia | 4.070 / 38 |
| Dòng thiếu CustomerID / Description | 135.080 / 1.454 |
| Dòng trùng dư trên 8 cột | 5.268 |
| Dòng toàn bộ giá trị thiếu / dòng tiêu đề lặp | 0 / 0 |
| Kiểm tra XML | Vùng A1:H541910; 541.910 dòng vật lý gồm header; không có dòng không chứa ô |
| Múi giờ thời điểm nguồn | Không được cung cấp; không chuyển múi giờ |

### Các cột và vai trò

| Cột raw | Kiểu đọc được | Vai trò |
|---|---|---|
| InvoiceNo | object | Mã chứng từ; C là dấu hiệu hủy |
| StockCode | object | Mã hàng; có thể gồm mã dịch vụ/điều chỉnh |
| Description | object | Mô tả hàng |
| Quantity | int64 | Số lượng trên dòng, có dấu |
| InvoiceDate | datetime64[us] | Thời điểm ghi trong nguồn |
| UnitPrice | float64 | Đơn giá, GBP/đơn vị theo mô tả UCI |
| CustomerID | float64 | Mã khách hàng có thể thiếu; không phải biến số liên tục |
| Country | str | Nhãn quốc gia |

Kiểu đọc có thể khác giữa các phiên bản pandas. Bản sao trong bộ nhớ chuẩn hóa ID thành chuỗi; file Excel gốc không thay đổi.

### Mẫu đầu và cuối

| Vị trí | InvoiceNo | StockCode | Quantity | InvoiceDate | UnitPrice | CustomerID | Country |
|---|---|---|---:|---|---:|---:|---|
| Đầu | 536365 | 85123A | 6 | 2010-12-01 08:26:00 | 2,55 | 17850 | United Kingdom |
| Thứ hai | 536365 | 71053 | 6 | 2010-12-01 08:26:00 | 3,39 | 17850 | United Kingdom |
| Áp cuối | 581587 | 23255 | 4 | 2011-12-09 12:50:00 | 4,15 | 12680 | France |
| Cuối | 581587 | 22138 | 3 | 2011-12-09 12:50:00 | 4,95 | 12680 | France |

## 3. Nguồn mô tả và giới hạn

Trang mô tả được sử dụng là [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail), DOI [10.24432/C5BW33](https://doi.org/10.24432/C5BW33), đã đối chiếu ngày 05/11/2026. Tên file, cấu trúc, quy mô và khoảng ngày cục bộ phù hợp mô tả nguồn; sự phù hợp không chứng minh đầy đủ chuỗi tải file. SHA-256 xác định phiên bản đầu vào đã phân tích.

Trang nguồn ghi không có giá trị thiếu, nhưng kiểm tra workbook cục bộ phát hiện thiếu CustomerID và Description như trên. Dùng kết quả đọc trực tiếp để đánh giá chất lượng. Một dòng giao dịch, một chứng từ và một khách hàng là ba đơn vị khác nhau.

## 4. Thành phần hiện dùng

| Thành phần | Vị trí | Vai trò / cách sử dụng |
|---|---|---|
| Raw duy nhất | `data/raw/Online Retail.xlsx` | Giữ nguyên, chỉ đọc |
| Notebook / mã EDA | `notebooks/01_eda/` | EDA từ raw duy nhất; không gọi pipeline cleaning |
| Hình | `notebooks/01_eda/figures/raw/` | 21 hình, nêu phạm vi và nguồn |
| Workbook kết quả | `experiments/eda_raw_moi/ket_qua_eda.xlsx` | Bảng thống kê, metadata, danh mục hình, kết quả kiểm tra |
| Báo cáo | `reports/bao_cao_eda_raw_moi.md` | Nhận xét từ cùng một lần chạy EDA |
| Đề xuất | `reports/de_xuat_sau_eda.md` | Phương án cleaning, encoding, scaling, feature chưa chốt |
| Phần việc tiền xử lý / Form 2 | `src/preprocessing.py`, `notebooks/05_data_processing/`, `data/processed/`, `experiments/form2_manual_behavior_raw_survey/` | API và kết quả từng có chưa được xác minh cho raw duy nhất; không dùng output từ dữ liệu chọn nhầm |

API tiền xử lý hiện dùng tên nội bộ `Invoice`, `Price`, `Customer ID`, chưa tương thích trực tiếp cột raw `InvoiceNo`, `UnitPrice`, `CustomerID`. Quy tắc cleaning cần nhóm thống nhất trước khi cập nhật pipeline. Chưa có bộ dữ liệu sạch hoặc bộ đặc trưng chính thức được tạo trong EDA.

## 5. Chạy lại và quyết định còn chờ

Làm theo [hướng dẫn EDA](../notebooks/01_eda/README.md). Notebook chạy lại từ raw duy nhất, ghi hình và một workbook; không tạo hàng loạt CSV/JSON. Các bảng khách hàng và công thức chỉ là khảo sát trong bộ nhớ, không được coi là pipeline chính thức.

Nhóm cần chốt cách xử lý thiếu ID/mô tả, trùng, hủy/trả, giá hoặc lượng bất thường, mã dịch vụ, ngoại lệ, cửa sổ thời gian, encoding, scaling và tập đặc trưng. Tương quan không chứng minh nhân quả; tháng cuối chỉ có dữ liệu đến ngày 09/12/2011.
