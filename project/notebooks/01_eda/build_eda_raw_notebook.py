"""Build the raw-only EDA notebook with short, ordered presentation cells.

Rebuilding clears saved outputs: execute eda.ipynb afterward.
"""
from pathlib import Path
import nbformat as nbf


def build():
    notebook = nbf.v4.new_notebook()
    cells = []
    def md(text): cells.append(nbf.v4.new_markdown_cell(text.strip()))
    def code(text): cells.append(nbf.v4.new_code_cell(text.strip()))
    def table(name, limit=12): code(f'show_table("{name}", limit={limit})')
    def figure(key): code(f'show_figure("{key}")')

    md("""# EDA từ raw hiện tại — Online Retail

## Mục lục

0. [Bối cảnh và câu hỏi](#0.-Bối-cảnh-và-câu-hỏi)
1. [Nguồn và kiểm kê](#1.-Nguồn-và-kiểm-kê)
2. [Chất lượng dữ liệu](#2.-Chất-lượng-dữ-liệu)
3. [Thống kê mô tả](#3.-Thống-kê-mô-tả)
4. [Phân tích đơn biến](#4.-Phân-tích-đơn-biến)
5. [Thời gian và khách hàng](#5.-Thời-gian-và-khách-hàng)
6. [Hai biến và đa biến](#6.-Hai-biến-và-đa-biến)
7. [Tương quan](#7.-Tương-quan)
8. [Phương án sau EDA](#8.-Phương-án-sau-EDA)
9. [Xuất kết quả và kiểm tra](#9.-Xuất-kết-quả-và-kiểm-tra)

**Chạy:** chọn kernel theo [README](README.md), **Restart Kernel → Run All**.
Raw duy nhất của dự án là `data/raw/Online Retail.xlsx`; các số liệu/nhận xét bên dưới
được tính từ file này. Các sản phẩm từ dữ liệu từng chọn nhầm không hợp lệ cho dự án.
""")
    md("""## 0. Bối cảnh và câu hỏi

Phân cụm khách hàng không giám sát cần hiểu giao dịch trước khi chọn cách xử lý và biến hành vi.
Một **dòng raw** là dòng hàng/chứng từ; **InvoiceNo** nhóm nhiều dòng; **CustomerID** nhóm nhiều hóa đơn.
Không xem mã định danh như biến số liên tục; không coi khách thiếu mã là một khách thật.

Các câu hỏi: (1) thiếu/trùng/bất thường ở đâu; (2) giao dịch phân bố theo thời gian, lượng và giá ra sao;
(3) hành vi giữa khách khác nhau thế nào; (4) các biến liên hệ ra sao; (5) nhóm cần so sánh phương án xử lý nào?

Chỉ dùng raw hiện tại. Bản sao và tổng hợp trong bộ nhớ phục vụ EDA; không tạo dữ liệu sạch/feature chính thức,
không fit encoder/scaler, không huấn luyện mô hình. Múi giờ nguồn chưa được cung cấp.
""")
    code('''from pathlib import Path
import sys
from IPython.display import display, Markdown, Image

# Works from the repository root, project/, or this notebook's directory.
project = next(candidate for parent in [Path.cwd(), *Path.cwd().parents]
               for candidate in [parent / "project", parent]
               if (candidate / "data/raw/Online Retail.xlsx").is_file())
module_dir = project / "notebooks/01_eda"
sys.path.insert(0, str(module_dir))
from eda_raw_analysis import load_analysis, make_figure, export_results, md_table, table_sheet, PURCHASE_RULE

analysis = load_analysis(project)

def show_table(name, limit=12):
    frame = analysis["tables"][name]
    display(Markdown(f"**{name}** — {len(frame):,} dòng × {len(frame.columns)} cột; sheet {table_sheet(analysis, name)} trong workbook kết quả."))
    view = frame.head(limit).copy()
    numeric_columns = view.select_dtypes(include="number").columns
    view[numeric_columns] = view[numeric_columns].round(4)
    display(view)

def show_figure(key):
    path, comment = make_figure(analysis, key)
    display(Image(filename=str(path), width=1000))
    display(Markdown(comment))
    record = next(row for row in analysis["figures"] if row["figure_id"] == key)
    names = ", ".join(f"{name} ({table_sheet(analysis, name)})"
                      for name in record["source_tables"].split(";"))
    display(Markdown("Bảng bằng chứng trong [workbook](../../experiments/eda_raw_moi/ket_qua_eda.xlsx): " + names))

raw = analysis["df"]
customers = analysis["customers"]
display(Markdown(
    f"**Kết quả tính hiện tại:** {len(raw):,} dòng raw, "
    f"{raw.InvoiceNo.nunique():,} chứng từ, {raw.CustomerID.nunique():,} mã khách. "
    f"Thiếu CustomerID: {raw.CustomerID.isna().sum():,} dòng ({raw.CustomerID.isna().mean():.2%}). "
    f"Tập mua khảo sát: {len(analysis['purchase']):,} dòng/{len(customers):,} khách; "
    f"{customers.n_invoices.eq(1).mean():.2%} khách có một hóa đơn."))''')
    md("""## 1. Nguồn và kiểm kê

Nguồn mô tả: [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail), đã đọc ngày 05/11/2026.
GBP dựa trên mô tả UCI, chưa có khai báo tiền tệ trong workbook. Các con số đo trực tiếp từ file local;
khớp cấu trúc không đủ chứng minh chuỗi tải file. [Kiểm kê nguồn](../../reports/kiem_ke_eda.md)
ghi file raw duy nhất, phạm vi và giới hạn tái lập.
""")
    for name, limit in [("raw_inventory",30),("workbook_sheets",12),("data_dictionary",12),
                        ("column_mapping",12),("raw_samples",12)]: table(name,limit)
    md("""## 2. Chất lượng dữ liệu

Các vấn đề có thể chồng lấn. **Không cộng số dòng, chứng từ hay khách của các nhóm như nhóm độc lập.**
Trùng InvoiceNo+StockCode không mặc nhiên trùng giao dịch. C là dấu hiệu chứng từ hủy;
không thay thế quy trình ghép trả hàng với đơn gốc. Ngưỡng IQR chỉ gắn cờ khảo sát.
""")
    for name in ["missing_values","quality_issues","duplicate_criteria","duplicate_samples",
                 "document_status","invoice_prefixes","document_quantity_counts","price_sign_counts",
                 "negative_price_samples","nonpositive_price_samples","identifier_conflicts",
                 "invoice_conflict_samples","stock_description_audit","nonstandard_stock_codes"]: table(name,30 if name=="quality_issues" else 12)
    for key in ["missing_values","document_quantity_price"]: figure(key)
    md("""## 3. Thống kê mô tả

Bảng số gồm count hữu hạn, min/max, mean/median, std mẫu, q1/q3, IQR, p95/p99, skew và số dòng ngoài IQR1.5.
Không tính trung bình CustomerID/InvoiceNo/StockCode. Tần suất đầy đủ và nhóm hiếm được xuất riêng.
Mẫu cực trị giúp kiểm tra ngữ cảnh; không kết luận mọi điểm lớn là lỗi.
""")
    for name in ["numeric_summary","categorical_summary","extreme_samples"]: table(name,20)
    md("""## 4. Phân tích đơn biến

Histogram toàn miền dùng sign(x)×ln(1+|x|), boxplot dùng trục symlog để giữ số âm/0/cực trị;
đây chỉ là tọa độ hiển thị. Không cắt hay bỏ quan sát; bảng mô tả vẫn ở đơn vị gốc.
Top danh mục xếp theo **số dòng**, có số dòng phần còn lại trong nhận xét.
""")
    for key in ["raw_distributions","country_counts","stock_code_counts"]: figure(key)
    md("""## 5. Thời gian và khách hàng

Số dòng và số hóa đơn là hai đại lượng khác nhau. Tổng có dấu Q×P của raw chưa được gọi là doanh thu thuần.
Tháng biên cần đọc theo timestamp thực tế, đặc biệt tháng cuối chưa đầy đủ.

Phạm vi mua và mọi công thức dưới đây là **khảo sát tạm thời**. Giữ nguyên trùng/mã dịch vụ;
không gán quốc gia duy nhất cho khách có nhiều quốc gia. Không dùng ngày chạy để tính recency.
""")
    code('display(Markdown(PURCHASE_RULE))')
    for name in ["analysis_scopes","aggregation_formulas","monthly_activity","customer_summary","customer_coverage"]: table(name,20)
    for key in ["monthly_activity","monthly_values","weekday_hour","customer_distributions","customer_gaps"]: figure(key)
    md("""## 6. Hai biến và đa biến

Chọn Quantity–UnitPrice để xem hành vi lượng/giá; số hóa đơn–giá trị để xem cường độ mua;
giá trị dòng–quốc gia để so phân phối với cỡ mẫu; quốc gia–trạng thái chứng từ để xem thành phần.
Hai scatter đa biến kiểm tra tần suất/giá trị đơn và đa dạng mã/giá trị, màu là recency.
Scatter đa biến lấy mẫu có seed; các thống kê và tương quan luôn dùng toàn bộ tập đủ điều kiện.
""")
    for key in ["quantity_price_hexbin","customer_frequency_value","country_value_boxplot",
                "country_document_status","customer_multivariate"]: figure(key)
    md("""## 7. Tương quan

**Pearson** đo liên hệ tuyến tính; **Spearman** đo liên hệ đơn điệu theo hạng.
Hai cấp phân tích tách riêng: toàn bộ dòng raw và tổng hợp khách trong tập mua tạm.
Ma trận tính trên toàn bộ giá trị hữu hạn theo cặp (`min_periods=3`), không lấy mẫu/điền 0.
Mỗi cấp có cùng tập biến cho hai hệ số và bảng số cặp hợp lệ.

IDs bị loại. SignedLineValue=Q×P và AOV=M/F có phụ thuộc đại số;
tương quan cao không tự đòi hỏi loại biến, cũng không chứng minh quan hệ nhân quả.
Scatter ở phần 6 giúp đọc hình dạng quan hệ thay vì chỉ nhìn hệ số.
""")
    table("correlation_variable_audit",20)
    for level in ["line","customer"]:
        for method in ["pearson","spearman","pairwise_counts"]:
            figure(f"correlation_{level}_{method}")
        table(f"correlations_{level}_pairwise_counts",20)
    md("""## 8. Phương án sau EDA

Xem [đề xuất sau EDA](../../reports/de_xuat_sau_eda.md): các hướng data cleaning, encoding,
scaling và feature engineering kèm ưu/nhược, ảnh hưởng, bằng chứng và câu hỏi chờ thống nhất.
Thứ tự đề xuất: đặc trưng hành vi thủ công → RFM → ba hướng chỉ thủ công / chỉ RFM / kết hợp.

Các quyết định còn chờ nhóm: thiếu mã khách/mô tả; định nghĩa trùng; ghép hủy/trả;
giá 0/âm; mã dịch vụ; ngoại lệ/khách mua sỉ; cửa sổ quan sát và công thức hành vi;
danh mục/encoding; scaling; bộ biến và kiểm soát thông tin trùng.
Không phương án nào được áp dụng vào pipeline ở notebook này.
""")
    md("""## 9. Xuất kết quả và kiểm tra

Xuất thống kê/mẫu kiểm tra, danh mục hình/bảng và metadata vào một workbook, cùng báo cáo từ **cùng bảng trong bộ nhớ**.
Không xuất giao dịch đã làm sạch hay ma trận feature khách. Kiểm tra checksum raw, mã production,
processed và khảo sát Form 2; kiểm tra tổng, gap/AOV và cặp tương quan bằng scipy.
""")
    code('''metadata = export_results(analysis)
display(Markdown(f"**Đã xuất {metadata['figure_count']} hình và {metadata['table_count']} bảng trong một workbook.**"))
display(metadata["checks"])
display(Markdown("[Báo cáo EDA](../../reports/bao_cao_eda.md) · "
                 "[Workbook bảng, metadata và danh mục hình](../../experiments/eda_raw_moi/ket_qua_eda.xlsx)"))''')
    md("""### Giới hạn khi diễn giải

Cửa sổ một nhà bán lẻ hữu hạn, chưa biết múi giờ, chưa ghép chứng từ trả với mua và chưa xác nhận mã hàng thực.
Không quan sát được tuổi khách thật hay hoạt động trước/sau raw. Khách một đơn giữ gap thiếu.
Số liệu có dấu chưa là doanh thu thuần; tương quan không chứng minh nhân quả hoặc khả năng dự báo.
""")
    notebook.cells=cells
    notebook.metadata={"kernelspec":{"display_name":"Python 3 (EDA)","language":"python","name":"python3"},
                       "language_info":{"name":"python"}}
    nbf.validate(notebook)
    path=Path(__file__).with_name("eda.ipynb")
    nbf.write(notebook,path)
    print(f"Built {path.name}: {len(cells)} cells")


if __name__ == "__main__":
    build()
