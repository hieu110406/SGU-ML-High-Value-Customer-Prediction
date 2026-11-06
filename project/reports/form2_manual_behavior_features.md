# Form 2 — Đặc trưng hành vi mua thủ công

> **Không sử dụng số liệu khảo sát trong tài liệu này:** Phần số liệu và CSV Form 2
> bên dưới được tính từ dữ liệu từng chọn nhầm, không hợp lệ cho dự án và không phải
> nguồn dữ liệu của dự án. Raw duy nhất là `data/raw/Online Retail.xlsx`. Giữ nội dung
> để tác giả đối chiếu công việc; cần tính lại trước khi sử dụng bất kỳ kết quả nào.
> Notebook cũ và các lệnh chạy liên quan không còn sử dụng được.

**Mốc chính sách của báo cáo:** các kết quả làm sạch, khảo sát khách hàng và RFM trong bản EDA này dùng chính sách tại commit `1c7ce32`. `main` đã có thay đổi tiền xử lý tại commit `d17492d`; các con số ở đây chưa đánh giá chính sách mới đó. Notebook giữ mã tái hiện chính sách cũ ngay trong một ô riêng để chạy độc lập, không sửa hoặc gọi API cũ đã bị xóa khỏi `src/preprocessing.py`. Các mô tả “hiện tại/current” trong kết quả đã lưu được hiểu tại mốc `1c7ce32`.

**Ngô Nguyên — 3124411191 — Nhóm 15.** Phạm vi: hành vi trước RFM;
chưa chuẩn hóa, chọn biến mô hình hay gắn nhãn khách hàng.

Tài liệu này mô tả API đặc trưng trong `src/features.py` và lưu bối cảnh khảo sát
Form 2 trước đây. Các bảng kèm Form 2 là **khảo sát thử nghiệm từ bản sao dữ liệu
thô**, không phải đầu ra tiền xử lý hoặc bảng đặc trưng chính thức.

**Phạm vi hiện tại:** xem [hướng dẫn EDA](../notebooks/01_eda/README.md) và
[báo cáo EDA](bao_cao_eda.md), được tính từ raw duy nhất. Mô tả API và
ví dụ tổng quát bên dưới được giữ để tác giả rà soát; chúng chưa xác nhận rằng
pipeline hoặc bộ đặc trưng chính thức đã sẵn sàng cho raw của dự án.

> **Cập nhật 06/11/2026:** API hành vi bên dưới vẫn dùng schema nội bộ `Customer ID`/`Invoice`/`Price`. Luồng baseline mới đọc raw `CustomerID`/`InvoiceNo`/`UnitPrice`, chuyển đổi tên sau clean và bổ sung `build_rfm`; không dùng trực tiếp ví dụ/cột lịch sử làm lệnh chạy raw. Bảng khách xuất baseline đưa khóa về `CustomerID`. Xem [README](../README.md) và [báo cáo tiến độ](bao_cao_tien_do.md) cho luồng hiện hành.

## Giao diện

Hợp đồng Form 2 ban đầu trong `src/features.py` mô tả 4 hàm thuần, nhận/trả `pandas.DataFrame`, không đọc/ghi tệp:

| Hàm | Đầu vào | Đầu ra |
|---|---|---|
| `aggregate_purchase_orders` | Các dòng mua đã được bên gọi chọn | Một dòng cho mỗi `(Customer ID, Invoice)`, giá trị đơn, thời điểm, số dòng và số thời điểm nguồn |
| `build_customer_behavior_features` | Cùng dữ liệu mua, tùy chọn phân loại StockCode | Một dòng/`Customer ID` có ít nhất một dòng mua trong cửa sổ |
| `audit_stock_codes` | Góc nhìn giao dịch, có thể gồm C/âm | Số dòng, tối đa 3 mô tả ví dụ và dấu hiệu hình thức của từng StockCode |
| `audit_c_documents` | Góc nhìn **trước khi loại** C/âm | Kiểm kê theo khách hàng: số dòng, số mã chứng từ, mã C, dòng lượng âm và tỷ trọng mã C |

Hai mốc `window_start` và `reference_date` bắt buộc. Cửa sổ đóng trái, mở phải:
**`window_start <= InvoiceDate < reference_date`**. Ví dụ ngày tham chiếu
`2011-12-10 00:00` bao gồm ngày 09/12, loại đúng mốc tham chiếu và mọi dòng về sau.
Không tự lấy ngày lớn nhất của dữ liệu làm mốc. Ngày thiếu/lỗi bị báo lỗi vì
không biết dòng có thuộc cửa sổ không; không tự gán múi giờ. Bảng phân loại mã hàng
do bên gọi cung cấp cũng cần phù hợp thông tin đã biết tại mốc tham chiếu.

Đầu vào mua cần 6 cột `Customer ID`, `Invoice`, `StockCode`, `InvoiceDate`,
`Quantity`, `Price`. Trong cửa sổ, Q/P phải hữu hạn và > 0, mã khách hàng/hóa đơn
khác thiếu, Invoice không có tiền tố C. Nếu vi phạm, hàm **báo lỗi**, không tự lọc
hoặc sửa thay pipeline tiền xử lý. Thiếu StockCode vẫn cho phép tính giá trị/thời gian,
nhưng chỉ số sản phẩm của khách hàng đó chưa xác định. Kiểu mã được đưa về chuỗi,
trim và bỏ đuôi `.0` như EDA; không gộp các mã có số 0 đầu hoặc đoán danh tính.
Hàm tổng quát không ép mã khách hàng có 5 chữ số; riêng khảo sát thô dùng quy tắc EDA.

Invoice phải gắn một khách hàng trong cửa sổ. Mặc định `invoice_time_policy="require_unique"`
từ chối mã có nhiều thời điểm; bên gọi có thể chủ động chọn `"earliest"` để lấy
thời điểm sớm nhất **trong cửa sổ**. Các dòng ngoài cửa sổ không tham gia giá trị,
phân loại, thời điểm hay kiểm tra mâu thuẫn của góc nhìn mua. Hóa đơn có thể chỉ còn
một phần dòng tại biên cửa sổ hoặc sau bộ lọc của bên gọi; không mặc định là giỏ hàng đầy đủ.

## Công thức và đơn vị

Với khách hàng `c`, gọi `I_c` là tập Invoice duy nhất từ các dòng mua đầu vào
trong cửa sổ, `N_c = |I_c|`. Với hóa đơn `i`,
`V_i = Σ(Quantity_l × Price_l)` trên các dòng của hóa đơn và `t_i` theo chính sách thời điểm.

| Cột | Công thức | Đơn vị / điều kiện |
|---|---|---|
| `avg_order_value` | `Σ V_i / N_c` | GBP/đơn; cộng **mọi dòng đầu vào**, gồm phí/dịch vụ nếu bên gọi giữ chúng |
| `n_distinct_products` | Số StockCode khác nhau có nhãn `product` của khách hàng | Mã sản phẩm; không phải tổng số dòng hay tổng Quantity |
| `avg_quantity_per_order` | Tổng Quantity của các dòng `product` / `N_c` | Đơn vị sản phẩm/đơn; không cộng đơn vị của bưu phí/bút toán |
| `avg_purchase_gap_days` | Trung bình `t_(j) − t_(j−1)` sau sắp xếp **các hóa đơn** | Ngày = 86.400 giây, có phần lẻ; dưới 2 hóa đơn là `NaN` |
| `return_rate` | Chưa xác định trong Form 2 | `NaN` và trạng thái `undefined_no_verified_return_source`, kể cả khi không thấy C |
| `total_quantity` *(tùy chọn)* | Tổng Quantity của các dòng `product` | Đơn vị sản phẩm; có thể trùng thông tin với lượng/đơn và số đơn |
| `observed_tenure_days` *(tùy chọn)* | `(reference_date − min(t_i)) / 1 ngày` | Thời gian từ lần mua đầu **quan sát trong cửa sổ**; không phải tuổi thật của quan hệ khách hàng |

Các cột `n_orders`, `n_transaction_rows`, thời điểm đầu/cuối và trạng thái phân loại
phục vụ kiểm tra/mẫu số. Chưa chọn chúng làm đầu vào mô hình hoặc đổi tên thành RFM.
Hai hóa đơn khác nhau cùng thời điểm có khoảng cách 0 thật; một hóa đơn dù nhiều dòng
vẫn không đủ dữ liệu tính khoảng cách. Hóa đơn chỉ có dòng đã xác nhận không phải sản phẩm
có lượng sản phẩm bằng 0 và vẫn thuộc mẫu số nếu bên gọi giữ hóa đơn đó; nhóm cần chốt
định nghĩa đơn đủ điều kiện. Không đồng nhất 0 có căn cứ này với giá trị thiếu.

`stock_code_roles` là mapping `StockCode -> "product" / "non_product"` do bên gọi cung cấp.
Không có mapping hoặc bất kỳ dòng nào của khách hàng còn mã thiếu/chưa phân loại
thì `n_distinct_products`, `avg_quantity_per_order`, `total_quantity` của người đó là `NaN`.
Xem `product_classification_status` và `n_unclassified_rows`. Không dùng regex làm
chính sách phân loại mặc định của hàm. Tất cả dòng trùng vẫn được giữ, có thể tăng giá trị/lượng;
cần giải quyết chính sách trùng ở tiền xử lý trước khi dùng bảng chính thức.

Ví dụ gọi từ thư mục `project/`, với dữ liệu đã được bên gọi chọn:

```python
from src.features import build_customer_behavior_features

features = build_customer_behavior_features(
    purchase_transactions,
    window_start="2010-12-01", reference_date="2011-12-10",
    stock_code_roles=reviewed_stock_code_roles,
    invoice_time_policy="earliest",  # chỉ chọn sau khi thống nhất quy tắc
    include_optional=False,
)
assert features["Customer ID"].is_unique
```

## Hoàn trả: cần giữ gì trước khi loại chứng từ?

Giữ một góc nhìn riêng các dòng **có C hoặc Quantity < 0 hoặc UnitPrice <= 0** để
đối chiếu nghiệp vụ; EDA trên raw duy nhất thấy 1.336 dòng Quantity âm không có C.
Giữ CustomerID, InvoiceNo, StockCode, Description,
Quantity, UnitPrice, InvoiceDate, sheet và số dòng nguồn. Các trường liên kết hóa đơn mua gốc,
loại sự kiện (hủy/hoàn/điều chỉnh), lượng hoàn xác minh và trạng thái xác minh cần
được bổ sung từ đối chiếu; **không giả định chúng đã có trong workbook**.
Nguồn thô giữ nguyên hiện vẫn cho phép tái lập góc nhìn này sau khi lọc bảng mua.

Đề xuất để nhóm xác nhận: tỷ lệ **đơn có hoàn trả đã xác minh** =
số hóa đơn mua đủ điều kiện có ít nhất một sản phẩm được xác minh hoàn trước mốc /
tổng số hóa đơn mua đủ điều kiện của khách hàng. Hóa đơn mua gốc và sự kiện hoàn
đều phải trong `[start, reference)`, loại đơn gốc ngoài cửa sổ khỏi tử số; đếm một
đơn một lần dù hoàn nhiều dòng/lần. Cần nguồn hoàn đầy đủ, ghép được đơn gốc, loại trùng
theo chính sách và phân biệt hoàn thật với hủy/chiết khấu/điều chỉnh. Các đơn gần mốc
có ít thời gian phát sinh hoàn, nên so sánh có thể chịu lệch thời gian quan sát.
Đây là định nghĩa đề xuất, **chưa được triển khai như chỉ số xác minh**.

`audit_c_documents` chỉ tính `c_document_share = số mã C / mọi mã chứng từ có định danh`
trong cùng cửa sổ và khách hàng. Mẫu số gồm C và các bút toán khác, không phải số đơn
mua thành công. Dòng thiếu khách hàng được thống kê trong `DataFrame.attrs`, không
gán về một khách hàng chung. Bảng C là góc nhìn riêng, không bị mất khi lọc bảng mua;
`c_document_share` không thay thế `return_rate` và không mặc định đưa vào mô hình.

## Bảng khảo sát không hợp lệ: chỉ giữ để tác giả đối chiếu

**Không dùng các CSV và số liệu bên dưới cho dự án.** Chúng chưa được tính lại từ raw duy nhất.

Các file trong `experiments/form2_manual_behavior_raw_survey/`:

- `customer_behavior_experimental.csv`: một dòng/Customer ID, có nhãn `data_status` thử nghiệm.
- `stock_code_audit_experimental.csv`: kiểm kê mọi mã trong cửa sổ cùng mô tả ví dụ và phân loại tạm.
- `c_document_audit_experimental.csv`: góc nhìn chứng từ trước lọc mua; tỷ lệ hoàn trả vẫn `NaN`.
- [phụ lục thông tin nguồn](#nguon-form2): checksum nguồn, sheet, điều kiện lọc, số dòng/hóa đơn/khách hàng,
  thời điểm, giới hạn và khách hàng được kiểm tra độc lập.

Khảo sát cũ dùng các điều kiện trên bản sao nguồn: mã khách hàng nguyên dương 5 số,
mã hóa đơn 6 số, Q/P > 0 và tích hữu hạn, trong cửa sổ, không có mâu thuẫn khách hàng/hóa đơn.
Giữ mọi dòng trùng, ngoại lai, dịch vụ và phí trong giá trị đơn. Thời điểm hóa đơn lấy sớm nhất.
Regex 5 số + hậu tố chữ **chỉ là giả định sản phẩm tạm thời**; các mã POST, D, M, B,
BANK CHARGES, DOT được xem như bút toán/phí trong khảo sát sau khi kiểm kê mô tả.
Mã khác để chưa biết; cần danh mục chính thức để xác nhận cả các mã khớp regex.

Từ root repository, trong Python có các thư viện sẵn có:

```powershell
python -m unittest discover -s project/tests -v
python -X utf8 -m jupyter nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=1800 project/notebooks/01_eda/eda_v1.ipynb
```

Notebook EDA hiện tại tạo lại kết quả trong `experiments/eda_rebuild/`, bao gồm
3 CSV bàn giao (`customer_behavior`, `rfm`, `rfm_transformed`), hình và kết quả hiển thị trong notebook.
Các bảng kiểm tra chỉ hiển thị trong EDA; tham số scaling hiển thị trong notebook. Báo cáo chi tiết đã
hoàn thành được giữ riêng, không ghi lại bằng Run All. Chọn Python/kernel
có đủ thư viện theo [hướng dẫn EDA](../notebooks/01_eda/README.md).
Các CSV và phụ lục thông tin nguồn Form 2 cũ được giữ làm bằng chứng lịch sử, không bị ghi đè
và không được dùng thay cho kết quả trên tập sau pipeline hiện tại.

Fixture 8 dòng tự tạo trong `tests/test_features.py` chỉ phục vụ **kiểm thử**.
Khách `10001` có 5 dòng nhưng 3 đơn giá trị 28, 24, 4 GBP: AOV = 56/3,
3 mã sản phẩm, lượng sản phẩm = 10, lượng/đơn = 10/3 và khoảng cách trung bình = 5,5 ngày.
Khách `10002` có 1 dòng/1 đơn, khoảng cách là `NaN`. Các con số này **không phải kết quả dữ liệu thật**.

Lần khảo sát không hợp lệ cho dự án, với cửa sổ `[2009-12-01, 2011-12-10)`, từng ghi:
805.549 dòng mua ứng viên, 36.969 mã hóa đơn, **5.878 dòng khách hàng duy nhất**.
Có 1.623 khách hàng chỉ có 1 hóa đơn nên khoảng cách là `NaN`; 89 khách hàng còn
mã hàng chưa phân loại nên các chỉ số sản phẩm chưa xác định. `return_rate` là `NaN`
cho toàn bộ bảng. Chẳng hạn Customer ID **12350** có 17 dòng nguồn, 1 hóa đơn và
đúng **1 dòng đầu ra**, với khoảng cách `NaN`. Đây vẫn là kết quả **khảo sát thử nghiệm**.
Bộ 20 kiểm thử nhỏ đều đạt; bảng CSV đã đọc lại và kiểm tra khóa, tổng số dòng/đơn,
giá trị thiếu, thời điểm và checksum. Lần khảo sát cũ còn đối chiếu độc lập AOV/khoảng cách
trên 4 mã khách hàng ghi trong [phụ lục thông tin nguồn](#nguon-form2); checksum dữ liệu gốc giữ nguyên.
Các số liệu trên thuộc lần khảo sát thô cũ. Kết quả tích hợp với pipeline hiện tại
và sự khác nhau giữa hai phạm vi được trình bày trong báo cáo EDA mới.

## Các điểm cần Thuận/nhóm xác nhận

1. Giao diện đầu ra tiền xử lý, chính sách trùng trong/giữa sheet, hóa đơn hủy,
   lượng/giá không dương và các hóa đơn chỉ còn một phần dòng.
2. Danh mục StockCode sản phẩm/dịch vụ/điều chỉnh, cách xử lý mã lạ và phí trong giá trị đơn;
   hóa đơn chỉ có dịch vụ có được tính là một lần mua không.
3. Khóa hóa đơn, quy tắc khi có nhiều thời điểm, cửa sổ, mốc tham chiếu và đơn vị thời gian.
4. Góc nhìn giữ chứng từ trước lọc, nguồn xác minh/ghép đơn gốc và định nghĩa tỷ lệ hoàn trả.
5. Chọn biến sau khảo sát tương quan/độ lệch và chính sách giá trị thiếu; không mặc định
   dùng tất cả đặc trưng, thay `NaN` bằng 0 hoặc fit bộ chuẩn hóa ở bước này.


<a id="nguon-form2"></a>

## Phụ lục: thông tin nguồn lần khảo sát Form 2 cũ

Thông tin được chuyển nguyên giá trị từ metadata của lần khảo sát cũ trước khi xóa tệp JSON.
Các CSV khảo sát lịch sử được giữ nguyên.

| Trường | Giá trị |
|---|---|
| data_status | experimental_raw_survey_not_official |
| source | data/raw/online_retail_II.xlsx |
| source_sha256 | bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980 |
| window.window_start | 2009-12-01 |
| window.reference_date | 2011-12-10 |
| window.closed | left |
| python | 3.12.15 |
| pandas | 3.1.0 |
| numpy | 2.5.4 |
| sheet_rows.Year 2009-2010 | 525461 |
| sheet_rows.Year 2010-2011 | 541910 |
| raw_rows | 1067371 |
| candidate_rows | 805549 |
| candidate_invoices | 36969 |
| candidate_customers | 5878 |
| c_audit_customers | 5942 |
| candidate_duplicate_excess_on_8_source_columns | 26124 |
| orders_with_multiple_timestamps | 64 |
| single_order_customers | 1623 |
| customers_with_incomplete_product_classification | 89 |
| stock_classification.product | provisional regex: 5 digits plus optional letter suffix |
| stock_classification.non_product | ["B", "BANK CHARGES", "D", "DOT", "M", "POST"] |
| stock_classification.other_codes | unknown; not silently excluded |
| verified_return_rate | undefined; all values NaN, not zero |
| duplicates | preserved |
| purchase_time_policy | earliest within selected window |
| feature_scope.window_start | 2009-12-01T00:00:00 |
| feature_scope.reference_date | 2011-12-10T00:00:00 |
| feature_scope.window_closed | left |
| feature_scope.input_rows | 805549 |
| feature_scope.window_rows | 805549 |
| feature_scope.outside_window_rows | 0 |
| feature_scope.invoice_time_policy | earliest |
| feature_scope.value_scope | all_supplied_purchase_lines_including_non_products |
| feature_scope.quantity_scope | classified_product_lines_only |
| feature_scope.duplicates | preserved |
| feature_scope.return_rate_definition | unresolved |
| feature_scope.optional_features_included | true |
| c_document_audit_scope.window_start | 2009-12-01T00:00:00 |
| c_document_audit_scope.reference_date | 2011-12-10T00:00:00 |
| c_document_audit_scope.window_closed | left |
| c_document_audit_scope.input_rows | 1067371 |
| c_document_audit_scope.window_rows | 1067371 |
| c_document_audit_scope.outside_window_rows | 0 |
| c_document_audit_scope.unassigned_customer_rows | 243007 |
| c_document_audit_scope.missing_quantity_rows | 0 |
| filter_steps | [{"step": "Trong cửa sổ [start, reference)", "rows_remaining": 1067371, "rows_removed_at_step": 0, "invoices": 53628, "customers": 5942}, {"step": "Customer ID hợp lệ về hình thức như EDA", "rows_remaining": 824364, "rows_removed_at_step": 243007, "invoices": 44876, "customers": 5942}, {"step": "Invoice đúng 6 chữ số, không C", "rows_remaining": 805620, "rows_removed_at_step": 18744, "invoices": 36975, "customers": 5881}, {"step": "Quantity > 0, Price > 0, tích hữu hạn", "rows_remaining": 805549, "rows_removed_at_step": 71, "invoices": 36969, "customers": 5878}, {"step": "Không có Invoice gắn nhiều Customer ID", "rows_remaining": 805549, "rows_removed_at_step": 0, "invoices": 36969, "customers": 5878}] |
| independent_check_customer_ids | ["12346", "12350", "15315", "18287"] |
| limitations | ["No official preprocessing input or verified product catalog.", "C/negative events not matched to original invoices; no verified return rate.", "AOV includes retained service/adjustment lines; quantity counts classified products only.", "Duplicate and overlapping sheet rows remain; amounts/quantities can be inflated.", "Only eligible lines of an invoice may remain; not guaranteed complete baskets.", "Tenure is observed within window; not true customer acquisition tenure."] |
