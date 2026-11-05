"""Markdown report assembled from executed EDA tables and the same figure notes."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pandas as pd

from eda_analysis import CORRELATION_COLUMNS, checksum, validate_analysis
from eda_presentation import FIGURES, LABELS, narrative


def md_table(frame, columns=None, limit=None, index=False):
    if index:
        frame=frame.reset_index()
    if columns:
        frame=frame[columns]
    if limit:
        frame=frame.head(limit)
    def value(v):
        if pd.isna(v): return "Chưa xác định"
        if isinstance(v, bool): return "Có" if v else "Không"
        if isinstance(v, int): return f"{v:,}"
        if isinstance(v, float):
            return f"{v:,.0f}" if v.is_integer() else f"{v:,.6f}".rstrip("0").rstrip(".")
        return str(v).replace("|", "/").replace("\n", " ")
    lines=["| "+" | ".join(map(str,frame.columns))+" |", "| "+" | ".join(["---"]*len(frame.columns))+" |"]
    lines += ["| "+" | ".join(value(v) for v in row)+" |" for row in frame.itertuples(index=False,name=None)]
    return "\n".join(lines)


def figure_block(result,key):
    note=narrative(result,key)
    return (f"### {FIGURES[key][1]}\n\n**Câu hỏi phân tích.** {note['question']}\n\n"
            f"**Dữ liệu và phạm vi.** {note['scope']}\n\n"
            f"![{FIGURES[key][1]}](../notebooks/01_eda/figures/{key}.png)\n\n"
            f"**Nhận xét.** {note['observed']}\n\n**Ý nghĩa đối với dự án.** {note['meaning']}\n\n"
            f"**Giới hạn / bước tiếp theo.** {note['limit']}\n")


def figure_inventory(project):
    root=Path(project).parent
    prefix="project/notebooks/01_eda/figures/"
    tracked=subprocess.check_output(["git","ls-tree","-r","--name-only","HEAD",prefix],cwd=root,text=True).splitlines()
    old={}
    for relative in tracked:
        if relative.endswith(".png"):
            content=subprocess.check_output(["git","show",f"HEAD:{relative}"],cwd=root)
            old[Path(relative).name]=hashlib.sha256(content).hexdigest()
    current={name+".png" for name in FIGURES}
    rows=[]
    for name in sorted(set(old)|current):
        path=Path(project)/"notebooks/01_eda/figures"/name
        status=("Tái tạo/thay thế" if name in old else "Tạo mới") if name in current else "Đã xóa hình cũ không dùng"
        current_hash=checksum(path) if name in current and path.exists() else ""
        if current_hash and old.get(name)==current_hash:
            status="Giữ nguyên nội dung"
        rows.append(dict(name=name,status=status,old_sha256=old.get(name,""),
                         sha256=current_hash,
                         notebook="eda_v1.ipynb" if name in current else ""))
    return pd.DataFrame(rows)


def feature_definitions():
    return pd.DataFrame([
        ("Recency", "(2011-12-10 − last_purchase_time)/86400 giây", "ngày", "Không thiếu", "Độ gần đây; phụ thuộc mốc tham chiếu"),
        ("Frequency = n_orders", "nunique(Invoice) trên khách", "hóa đơn", "Không thiếu", "Hai tên cùng một phép đo; chỉ dùng một lần"),
        ("Monetary = total_purchase_value", "Σ Quantity × Price chính xác", "GBP", "Không thiếu", "M=F×AOV; có thể gồm đơn chỉ còn một phần dòng"),
        ("avg_order_value", "Monetary / Frequency", "GBP/đơn", "Không thiếu", "Liên hệ công thức với F/M; xem tương quan và độ lệch"),
        ("n_stock_codes_candidate", "nunique(StockCode giữ lại)", "mã ứng viên", "Không thiếu", "Chưa phải số sản phẩm được xác minh"),
        ("total_quantity_candidate", "Σ Quantity giữ lại", "đơn vị ứng viên", "Không thiếu", "Chưa xác minh đơn vị sản phẩm; phụ thuộc mã giữ lại"),
        ("avg_quantity_per_order_candidate", "total_quantity_candidate / Frequency", "đơn vị ứng viên/đơn", "Không thiếu", "Quan hệ công thức Q=F×Q/đơn"),
        ("avg_purchase_gap_days", "mean(diff(thời điểm từng Invoice đã sắp xếp))", "ngày", "NaN nếu 1 đơn", "Với F>1: gap=(tenure−R)/(F−1); 0 có thể hợp lệ"),
        ("observed_tenure_days", "(2011-12-10 − first_purchase_time)/86400 giây", "ngày", "Không thiếu", "Lịch sử quan sát, không phải tuổi thật khách hàng"),
        ("n_distinct_products / avg_quantity_per_order / total_quantity", "Chỉ tính với mapping product/non_product hoàn chỉnh", "sản phẩm / đơn vị sản phẩm", "Thiếu toàn bộ", "Chưa có danh mục được phê duyệt, không thay bằng ứng viên"),
        ("return_rate", "Chưa có nguồn hoàn trả đã xác minh / ghép đơn gốc", "Chưa xác định", "Thiếu toàn bộ", "Không suy từ C và không điền 0")
    ],columns=["Biến", "Công thức", "Đơn vị", "Giá trị thiếu", "Khả năng dùng / giới hạn"])


def write_report(result):
    validate_analysis(result)
    project,t,meta=result["project"],result["tables"],result["metadata"]
    b=t["customer_behavior"]
    parts=["# Báo cáo quá trình phân tích khám phá dữ liệu\n",
           "## 0. Giới thiệu quá trình EDA\n",
           "Dự án **Phân khúc khách hàng bằng RFM và hành vi mua hàng trên Online Retail II** giải quyết bài toán phân cụm không giám sát từ lịch sử giao dịch. Một dòng nguồn là dòng hàng/bút toán; một Invoice gồm nhiều dòng; một khách có nhiều Invoice. Bảng đặc trưng dự kiến có đúng một dòng/Customer ID. Không tạo nhãn dự đoán hoặc metric mô hình chưa chạy.\n",
           "Câu hỏi EDA: quy mô và chất lượng nguồn ra sao; lượng/giá/giá trị phân phối thế nào; hoạt động theo thời gian/quốc gia; đặc trưng hành vi liên hệ hay trùng thông tin gì; cần xử lý thiếu/ngoại lệ/scaling thế nào trước phân cụm?\n",
           "**Phạm vi chính sách.** Báo cáo trước dùng `1c7ce32`. Lần này gọi nguyên trạng `src.preprocessing.clean_data` ở HEAD dưới đây trong bộ nhớ và tách Guest khỏi khảo sát khách hàng sau pipeline. Chưa tìm thấy bằng chứng nhóm phê duyệt chính sách chính thức trong các tài liệu/mã đã kiểm tra; mọi bảng hành vi, RFM và scaling dưới đây là **thử nghiệm theo mã hiện tại, cần nhóm xác nhận**. Không thay đổi quy tắc tiền xử lý của Thuận.\n",
           "**Khảo sát trước sửa (05/11/2026).** Nền mã `df066ee`, trạng thái Git sạch; EDA v1 có 56 cell, EDA v2 có 25 cell và đang tái hiện chính sách cũ. Đã có chất lượng, thời gian/quốc gia, phân phối, một scatter số đơn–giá trị và RFM/scaling; chưa có bộ phân tích hai/đa biến và ma trận tương quan đầy đủ như bản này. Mười sáu PNG cũ đã được đối chiếu với đường dẫn trong notebook/báo cáo trước khi thay thế.\n",
           md_table(pd.DataFrame([dict(raw_rows=len(result['raw']),raw_invoices=result['raw'].Invoice.nunique(),raw_known_customers=result['raw']['Customer ID'].nunique(),
                                       pipeline_rows=len(result['clean']),pipeline_guest_rows=int(result['clean'].IsGuest.sum()),
                                       survey_rows=len(result['purchase']),survey_invoices=int(b.Frequency.sum()),survey_customers=len(b))])),
           "\n**Đọc nhanh kết quả.** "+narrative(result,"customer_purchase_gaps")["observed"]+" "+narrative(result,"correlation_pairwise_counts")["observed"]+"\n",
           "## 1. Giới thiệu bộ dữ liệu\n",
           "Nguồn: Daqing Chen (2012), [Online Retail II — UCI](https://archive.ics.uci.edu/dataset/502/online+retail+ii), DOI [10.24432/C5CG6D](https://doi.org/10.24432/C5CG6D). UCI mô tả giao dịch bán lẻ tại Anh, đơn giá GBP và tiền tố C là hủy; tệp cục bộ là `data/raw/online_retail_II.xlsx`. Nguồn không có nhãn cụm, thời điểm gia nhập thật hoặc liên kết hoàn trả đã xác minh.\n",
           md_table(t["sheet_profile"]), "\n**Nhận xét.** Hai sheet không phải hai khoảng rời nhau. Khoảng chồng lấn bên dưới được tính từ min/max thời điểm; chỉ kiểm tra tám cột mới xác định trùng nội dung.\n",
           md_table(t["overlap"]), "\n### Kiểu dữ liệu và dòng mẫu\n",md_table(t["schema"]),"\n",md_table(t["samples"]),
           "\n### Từ điển dữ liệu và đơn vị quan sát\n",
           md_table(pd.DataFrame([
               ("Invoice","Định danh chứng từ, không phải số đo; có C/hủy/điều chỉnh"),
               ("StockCode","Định danh mã hàng/bút toán, chưa mặc định toàn bộ là sản phẩm"),
               ("Description","Mô tả có thể thiếu/thay đổi, không dùng làm khóa"),
               ("Quantity","Lượng trên dòng; có âm/điều chỉnh"),
               ("InvoiceDate","Thời điểm nguồn, không có múi giờ"),
               ("Price","Đơn giá GBP/đơn vị"),
               ("Customer ID","Định danh khách có thể thiếu; không tính trung bình mã"),
               ("Country","Quốc gia theo bản ghi, có nhãn Unspecified và khách nhiều quốc gia")], columns=["Cột","Ý nghĩa"])),
           "\nSố dòng ≠ số Invoice ≠ số khách. Invoice được đếm duy nhất trong góc nhìn tương ứng; khách chỉ đếm ID thật. `LineValue = Quantity × Price` (GBP/dòng) là biến dẫn xuất; `Revenue` của pipeline được làm tròn từng dòng nên giữ riêng. Toàn bộ nguồn được dùng cho chất lượng/thời gian/quốc gia; chỉ tập mua có ID được dùng cho đặc trưng.\n",
           "## 2. Kiểm tra chất lượng dữ liệu\n",
           md_table(t["missing"]), "\n",md_table(t["missing_by_sheet"]),"\n",figure_block(result,"missing_values_by_column"),
           "### Trùng nội dung\n\nĐếm trên tám cột nguồn, không thêm Sheet vào khóa. `keep=first` đếm bản dư; `keep=False` đếm mọi dòng thuộc nhóm trùng. Số mẫu chung khác số dòng sheet sau khớp mẫu chung.\n",
           md_table(t["duplicates"]),
           "\n**Nhận xét / ý nghĩa.** Dòng dư toàn bộ = tổng dòng dư từng sheet + số mẫu chung. Trùng có thể làm tăng giá trị/lượng, trong khi số Invoice duy nhất ít nhạy hơn. Giống nội dung chưa tự chứng minh lỗi kỹ thuật; chính sách giữ/bỏ cần nhóm xác nhận.\n",
           "### Giá trị đặc biệt, mã hàng và tính nhất quán\n",md_table(t["anomalies"]),"\n",figure_block(result,"invoices_by_c_prefix"),
           "Các điều kiện trong bảng giao nhau; không cộng các tỷ lệ. Lượng âm không C, giá 0/âm và C có lượng không âm cần đối chiếu nghiệp vụ.\n",
           md_table(t["stock_audit"].query("listed_special or not pattern_candidate").sort_values("rows",ascending=False),limit=15,index=True),
           "\nBảng trên chỉ 15 mã nhiều dòng nhất trong nhóm đặc biệt/khác mẫu; toàn bộ ở `tables['stock_audit']`. Loại phí hữu hạn chưa tạo danh mục sản phẩm đầy đủ; giữ chỉ số sản phẩm chính thức NaN.\n",
           md_table(t["consistency"]),
           "\n**Ảnh hưởng / xử lý.** Invoice nhiều thời điểm dùng earliest công khai trong khảo sát, cần nhóm xác nhận; khách nhiều quốc gia giữ nhóm Multi-country; nhiều Description có thể chỉ là sửa mô tả. Không gộp tùy ý khóa hoặc quốc gia.\n",
           md_table(pd.DataFrame([
               ("Thiếu Customer ID",str(int(t['missing'].set_index('column').loc['Customer ID','missing_rows'])),"Không gán được hành vi cá nhân","Pipeline dùng Guest; EDA tách khỏi bảng khách"),
               ("Trùng tám cột",str(int(t['duplicates'].iloc[0]['count'])),"Có thể tăng lượng/giá trị","Đối chiếu drop_duplicates sau chuẩn hóa; cần nhóm xác nhận"),
               ("C / lượng âm / giá không dương","Xem bảng anomalies; nhóm giao nhau","Có nhiều ý nghĩa nghiệp vụ","Kiểm kê riêng; chưa có verified return_rate"),
               ("Mã đặc biệt",str(int(t['stock_audit'].loc[t['stock_audit'].listed_special,'rows'].sum())),"Phí/điều chỉnh có thể ảnh hưởng AOV","Đối chiếu SPECIAL_CODES, chưa xác minh danh mục"),
               ("Khóa nhiều thời điểm / quốc gia","Xem consistency","Ảnh hưởng R/gap/diễn giải quốc gia","Earliest và Multi-country là lựa chọn EDA cần xác nhận")],columns=["Vấn đề","Số lượng / bằng chứng","Ảnh hưởng","Hướng xử lý / xác nhận"])),
           "\n## 3. Phân tích đơn biến\n",
           "### Biến số giao dịch\n\nCount, mean/median, min/max, Q1/Q3/IQR, P95/P99 và skew được tính trên toàn miền hữu hạn; không đưa ID vào thống kê số học.\n",
           md_table(t["transaction_profile"].query("population == 'raw_including_C'"),["variable","count","missing","mean","median","minimum","maximum","q1","q3","iqr","p95","p99","skewness"]),
           "\n",figure_block(result,"raw_transaction_full_distributions"),figure_block(result,"raw_categorical_distributions"),
           "### Biến số khách hàng và RFM riêng lẻ\n",md_table(t["customer_profile"],["variable","count","missing","mean","median","q1","q3","iqr","p95","p99","maximum","skewness"]),
           "\n",figure_block(result,"customer_behavior_distributions"),figure_block(result,"customer_purchase_gaps"),figure_block(result,"rfm_experimental_distributions"),
           "**Kết luận đơn biến.** Đọc dấu skew cùng phân vị/cực trị thay vì gán một dạng phân phối cho mọi biến. F/M/AOV/mã ứng viên có đuôi lớn; gap thiếu ở khách một đơn; chỉ số sản phẩm và hoàn trả thiếu toàn bộ. Những khác biệt này cần được xử lý trước tính khoảng cách phân cụm.\n",
           "## 4. Phân tích theo thời gian\n",md_table(t["monthly"],index=True),"\n",figure_block(result,"invoices_by_month"),figure_block(result,"signed_line_value_by_month"),
           "### Theo thứ và giờ\n",md_table(t["weekday"],index=True),"\n",md_table(t["hour"],index=True),"\n",figure_block(result,"transactions_by_weekday_hour"),
           "**Tháng biên.** Ngày đầu là 01/12/2009 nên không có bằng chứng thiếu ngày lịch đầu tháng; vẫn không biết lịch sử trước nguồn. Tháng 12/2011 kết thúc 09/12, là tháng chưa đủ. Không so mức cuối tháng như suy giảm trọn tháng.\n",
           "## 5. Phân tích theo quốc gia\n",md_table(t["countries"],limit=15,index=True),"\n",figure_block(result,"country_activity"),figure_block(result,"country_activity_excluding_uk"),
           f"**Unspecified.** Nhãn này có {int(t['countries'].loc['Unspecified','rows']) if 'Unspecified' in t['countries'].index else 0:,} dòng nguồn; không gán cho một quốc gia thật. Khách có nhiều quốc gia trong tập mua hiện tại: {int(b.n_countries.gt(1).sum()):,}; nhóm này tách riêng khi phân tích cấp khách.\n",
           "## 6. Phân tích hai biến\n\n### 6.1. Num vs Num\n",
           md_table(t["bivariate_numeric"]),"\n",figure_block(result,"customer_frequency_vs_monetary"),
           "### 6.2. Num vs Cat\n",md_table(t["numeric_by_country"],index=True),"\n",md_table(t["numeric_by_order_group"],index=True),"\n",figure_block(result,"customer_value_by_country"),
           "### 6.3. Cat vs Cat\n\nBảng số đếm và phần trăm theo **hàng** được tách riêng, không đổi mẫu số giữa các nhóm. Quốc gia cấp dòng dùng UK/Other-country; cấp khách dùng UK/Other-country/Multi-country từ các dòng mua trong cùng cửa sổ.\n",
           md_table(t["country_invoice_counts"],index=True),"\n",md_table(t["country_invoice_row_pct"],index=True),"\n",figure_block(result,"country_vs_invoice_type"),
           md_table(t["country_order_counts"],index=True),"\n",md_table(t["country_order_row_pct"],index=True),"\n",figure_block(result,"customer_order_group_by_country"),
           "## 7. Phân tích đa biến\n",figure_block(result,"rfm_multivariate_scatter"),figure_block(result,"behavior_multivariate_scatter"),figure_block(result,"country_frequency_monetary"),
           "## 8. Ma trận tương quan\n",
           "Tính Spearman và Pearson trên cùng bảng mỗi khách một dòng. Chỉ dùng biến số có ít nhất hai giá trị khác nhau; mỗi cặp dùng khách hữu hạn ở cả hai biến (pairwise deletion), tối thiểu 3 quan sát. Không điền thiếu hoặc biến ID thành số. Chỉ có chín biến đủ điều kiện dưới đây; các biến bị loại được kiểm kê riêng.\n",
           md_table(pd.DataFrame({"Tên trong ma trận":CORRELATION_COLUMNS,"Nhãn / đơn vị":[LABELS[c] for c in CORRELATION_COLUMNS]})),"\n",md_table(t["correlation_column_audit"]),
           "\n**Kiểm tra cột.** Bốn chỉ số sản phẩm/hoàn trả thiếu toàn bộ do chưa có nguồn xác nhận; Customer ID là định danh không phải số đo. Trong dữ liệu thực tế không có cột hằng trong tập đề xuất; hàm hỗ trợ nhận diện và loại cột hằng nếu xuất hiện khi chạy nguồn khác. Giá trị không hữu hạn được giữ là thiếu khi đếm cặp, không âm thầm chuyển thành 0.\n",
           "### Bảng hệ số Spearman\n",md_table(t["correlation_spearman"],index=True),"\n",figure_block(result,"correlation_spearman_heatmap"),
           "### Bảng hệ số Pearson trên thang gốc\n",md_table(t["correlation_pearson"],index=True),"\n",figure_block(result,"correlation_pearson_heatmap"),
           "### Số khách hợp lệ theo từng cặp\n",md_table(t["correlation_pairwise_counts"],index=True),"\n",figure_block(result,"correlation_pairwise_counts"),
           "Các cặp nổi bật có hệ số/phương pháp/n ở mục 6.1 và trên scatter cùng biến. F–M hoặc F–AOV chịu liên hệ cộng dồn/công thức; gap còn phụ thuộc R, tenure và F. Không tự động loại biến chỉ vì tương quan cao: cần so độ ổn định cụm, trọng số và khả năng diễn giải sau khi nhóm chốt bộ biến.\n",
           "## 9. Độ lệch và ngoại lệ\n",
           "Tukey IQR 1.5 trên thang gốc chỉ gắn cờ điều tra. Đây là phép khảo sát khác với bộ lọc log-IQR k=3 hiện có của Thuận. Không xóa thêm khách hoặc winsorize trong EDA.\n",
           md_table(t["transaction_profile"],["population","variable","count","q1","q3","iqr","p95","p99","iqr_lower","iqr_upper","outside_iqr","outside_iqr_pct"]),"\n",
           md_table(t["customer_profile"],["variable","count","q1","q3","p95","p99","maximum","outside_iqr","outside_iqr_pct"]),"\n",figure_block(result,"clean_transaction_full_distributions"),
           "### Mẫu cực trị để đối chiếu\n",md_table(t["extreme_rows"],["variable","direction","Invoice","StockCode","Quantity","Price","LineValue","InvoiceDate"],limit=12),
           "\n**Nhận xét / ý nghĩa.** Ví dụ đối dấu ở Invoice mua và C chỉ là ứng viên điều tra, chưa xác minh hoàn trả. Giá trị đặc biệt có thể là nghiệp vụ; khách giá trị cao có thể hợp lệ. Không có bằng chứng đủ để phân loại các cực trị này thành lỗi đã xác minh. Nhóm cần đánh giá độ nhạy với chính sách ngoại lệ, đặc biệt vì pipeline hiện tại đã bỏ một số dòng trước tổng hợp khách.\n",
           "## 10. Đối chiếu tiền xử lý trước và sau\n",md_table(t["policy_settings"]),"\n",md_table(t["preprocessing_trace"]),"\n",figure_block(result,"preprocessing_row_flow"),
           "### Đầu ra đã lưu và lần chạy mới\n",md_table(t["stored_comparison"],["artifact","rows","customers","status"]),
           "\n`online_retail_clean.csv.gz`, `online_retail_cancellations.csv` và log processed là đầu ra lịch sử; tên/cột còn khác API hiện tại (`CustomerID`, `LineValue` thay vì `Customer ID`, `Revenue`, `IsGuest`). Mã mới `save_processed` sẽ tạo `data_clean.csv.gz` và `cleaning_log.csv`, nhưng EDA **không gọi hàm ghi này**. `experiments/eda_rebuild/` và khảo sát Form 2 thô được giữ nguyên, không dùng làm nguồn bảng mới. Chênh lệch được giải thích bởi chính sách (Guest, chuẩn hóa/trùng, mã đặc biệt, lọc ngoại lệ, không ghép hủy), không coi hai bộ số tương đương hoặc là biến động khách theo thời gian.\n",
           md_table(t["customer_summary"]),
           f"\n**Làm tròn.** Trong tập khảo sát ID thật, Σ Q×P = {result['purchase'].LineValue.sum():,.3f} GBP; Σ Revenue đã làm tròn từng dòng = {result['purchase'].Revenue.sum():,.3f} GBP; chênh Revenue − chính xác = {result['purchase'].Revenue.sum()-result['purchase'].LineValue.sum():,.6f} GBP. Monetary/AOV dùng giá trị chính xác thống nhất.\n",
           "## 11. Đặc trưng thủ công và định hướng RFM\n",
           "Mọi công thức dưới đây dùng cửa sổ **[2009-12-01, 2011-12-10)**, trên cùng tập dòng mua có ID sau clean_data hiện tại; đơn dùng earliest của các dòng còn lại. Các đặc trưng sản phẩm chưa được xác minh nên có cột ứng viên riêng.\n",
           md_table(feature_definitions()),"\n",md_table(t["feature_missing"],index=True),
           "\nPhân phối đầy đủ ở mục 3/9, quan hệ ở mục 6–8. Các biến chính thức thiếu toàn bộ chưa sẵn sàng làm đầu vào phân cụm; gap cần xử lý thiếu có căn cứ, mã/lượng ứng viên cần kiểm tra danh mục và đơn vị.\n",
           "### Log1p và scaling thử nghiệm\n\nDùng `log1p` R/F/M rồi StandardScaler (phương sai ddof=0), fit trên **toàn bộ khách trong snapshot thử nghiệm này**. Tham số chính xác được giữ trong CSV và output notebook. Không có nhãn giám sát, tập test hay mô hình phân cụm được fit; khi đánh giá theo thời gian trong tương lai phải fit lại đúng cửa sổ được phép.\n",
           md_table(t["scaling_parameters"]),
           "\n## 12. Tổng hợp phát hiện EDA\n",
           md_table(pd.DataFrame([
               (1, "Thiếu ID có quy mô đáng kể",narrative(result,"missing_values_by_column")["observed"],"Không đại diện toàn bộ khách","Giữ báo cáo Guest riêng"),
               (2, "Trùng/chồng lấn hai sheet",f"{int(t['duplicates'].iloc[0]['count']):,} dòng dư; xem mục 2","Có thể làm tăng giá trị/lượng","Nhóm xác nhận ý nghĩa trùng"),
               (3, "Quần thể mới khác chính sách cũ",f"{len(b):,} khách / {len(result['purchase']):,} dòng khảo sát; mục 10","Không trộn cũ/mới","Chốt chính sách với Thuận"),
               (4, "Nhịp mua thiếu có cấu trúc",narrative(result,"customer_purchase_gaps")["observed"],"Gap không bằng 0","Quy tắc thiếu/cờ một đơn"),
               (5, "UK chiếm ưu thế",f"{100*t['countries'].loc['United Kingdom','rows']/len(result['raw']):.2f}% dòng thô; mục 5","Hồ sơ cụm dễ bị UK chi phối","Đối chiếu cụm theo địa lý"),
               (6, "Quan hệ đặc trưng có phần do công thức",f"Spearman F–M={t['correlation_spearman'].loc['Frequency','Monetary']:.4f}; n={len(b):,}; mục 6/8","Tránh tăng trọng số lặp","So tập biến có kiểm soát"),
               (7, "Chưa có sản phẩm/hoàn trả xác minh",f"4 biến thiếu toàn bộ trên {len(b):,} khách; mục 8/11","Chưa đưa vào mô hình","Xác nhận mapping và nguồn hoàn trả"),
               (8, "Ngoại lệ cần điều tra",f"M max={b.Monetary.max():,.2f} GBP, IQR gắn cờ {int(t['customer_profile'].set_index('variable').loc['Monetary','outside_iqr']):,} khách; mục 9","Có thể là nhóm giá trị cao hợp lệ","Không xóa khách tự động; kiểm tra độ nhạy"),
           ],columns=["STT","Phát hiện","Bằng chứng","Ảnh hưởng","Hướng xử lý"])),
           "\n## 13. Hạn chế và vấn đề cần xác nhận\n",
           "1. **Thuận/nhóm trưởng:** chính sách chính thức, khác biệt cũ/mới và phiên bản dữ liệu/mã được dùng chung. Mã hiện tại chưa tự chứng minh phê duyệt nghiệp vụ.\n"
           "2. ID thiếu: Guest giữ ở tầng pipeline nhưng không là một khách; khảo sát ID thật chịu chọn mẫu.\n"
           "3. Trùng trong/giữa sheet: giữ/bỏ cần xác nhận; kiểm tra ý nghĩa của cùng tám cột.\n"
           "4. Danh mục sản phẩm/dịch vụ/điều chỉnh có phiên bản; regex và SPECIAL_CODES chưa đủ xác minh sản phẩm.\n"
           "5. Hoàn trả: chưa có nguồn xác minh và liên kết đơn gốc; return_rate chưa thực hiện. Chính sách hiện tại không ghép hủy.\n"
           "6. Khóa/thời điểm Invoice, quy tắc Country nhiều nhãn, cửa sổ và mốc RFM cần chốt; lịch sử bị cắt ở hai đầu.\n"
           "7. Ngoại lệ: pipeline lọc log-IQR dòng, EDA gắn cờ IQR khách; đánh giá độ nhạy với Thuận trước thay chính sách.\n"
           "8. Bộ biến, thiếu/scaling/trọng số phân cụm chưa được chọn chính thức; tương quan không tự quyết định loại biến.\n"
           "9. Chưa chạy mô hình, đánh giá cụm, kiểm định nguyên nhân hoặc dự báo; các vùng trên scatter chưa là cụm chính thức.\n"
           "10. Kiểm tra hiển thị: PNG được kiểm tra trực tiếp; notebook có output đã chạy. Bản HTML có thể tạo bằng nbconvert, nhưng chưa xác nhận bố cục notebook trong trình duyệt của người dùng.\n",
           "## 14. Danh sách hình và hướng dẫn chạy lại\n",
           "Toàn bộ EDA nằm trong một notebook: [eda_v1.ipynb](../notebooks/01_eda/eda_v1.ipynb). Luồng đọc là **cấu trúc/chất lượng → đơn biến → thời gian/quốc gia → hai/đa biến → tương quan → ngoại lệ → đối chiếu tiền xử lý → RFM/scaling → kiểm tra/xuất báo cáo**.\n",
           "- Đọc workbook và chạy pipeline trong bộ nhớ một lần; dùng cùng bảng khách cho mọi phép phân tích. Mỗi hình/bảng quan trọng được trình bày tại một vị trí phù hợp, không cần chạy notebook khác hoặc trao đổi cache giữa các notebook.\n"
           "- Mã tính/kiểm tra nằm trong `eda_analysis.py`, mã vẽ/nhận xét trong `eda_presentation.py`, mã báo cáo trong `eda_report.py`. Notebook gọi bằng các cell ngắn; toàn bộ công thức và mã nguồn có thể kiểm tra.\n"
           "- Kết quả mới: `experiments/eda_current_policy/`; kết quả lịch sử giữ tại `experiments/eda_rebuild/` và `experiments/form2_manual_behavior_raw_survey/`.\n",
           md_table(pd.DataFrame([dict(figure=f"{k}.png",section=section,title=title,notebook="eda_v1.ipynb") for k,(section,title) in FIGURES.items()])),
           "\n### Hình cũ: thay thế, giữ lại và xóa\n",
           "Bộ 24 PNG được giữ lại và trình bày đúng một lần trong notebook duy nhất. Kiểm kê so SHA256 với HEAD trong [figure_inventory.csv](../experiments/eda_current_policy/figure_inventory.csv). Gộp notebook không làm mất hình hoặc nội dung phân tích.\n",
           "### Môi trường và cách chạy\n\nTừ gốc repository, chọn môi trường có requirements cùng nbformat, nbclient, nbconvert, ipykernel, Pillow. Môi trường đã có tại `project/.venv-eda/`; môi trường Python mặc định có thể không đủ thư viện. Trong Jupyter chọn đúng kernel rồi Restart Kernel → Run All.\n",
           "```powershell\n& project/.venv-eda/Scripts/python.exe -X utf8 -m nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=1800 project/notebooks/01_eda/eda_v1.ipynb\n```\n",
           "Xuất 9 CSV kết quả cần bàn giao cùng metadata SHA256. Các bảng mô tả giao dịch/khách và mẫu cực trị được tính, kiểm tra và hiển thị trực tiếp trong notebook; không xuất thêm bản cache của chúng.\n",
           "Notebook tự tìm project từ thư mục làm việc trong repository, không dùng đường dẫn máy tác giả. Mỗi notebook có kiểm tra khóa/tổng/công thức/thiếu, mọi cặp tương quan được đối chiếu scipy, và SHA256 đầu vào trước/sau. Báo cáo dùng cùng bảng/nhận xét đã tính nên khi dữ liệu/chính sách đổi, chạy lại v1 sẽ cập nhật số và diễn giải; không sửa tay kết quả. Ngày/múi giờ nguồn không bị chuyển.\n",
           "### Dấu vết tái lập\n",
           md_table(pd.DataFrame([(k,str(meta[k])) for k in ["run_at","client_date","timezone","git_head","window_start","reference_date_exclusive","source_timestamp_timezone","python"]]+[("version."+k,v) for k,v in meta["versions"].items()],columns=["Trường","Giá trị"])),
           "\n",md_table(pd.DataFrame([(path,sha) for path,sha in meta["protected_before"].items()],columns=["Tệp được bảo vệ (SHA256 trước = sau)","SHA256"])),
           "\nChecksum mã EDA, đầu vào trước/sau, ngày chạy và phiên bản cũng có ở [run_metadata.json](../experiments/eda_current_policy/run_metadata.json). HEAD là nền mã; các thay đổi EDA chưa commit. Bảng thử nghiệm không phải dữ liệu đặc trưng chính thức.\n",
           "**Nguồn nội bộ đã đối chiếu:** [README](../README.md), [preprocessing.py](../src/preprocessing.py), [features.py](../src/features.py), [Form 2](form2_manual_behavior_features.md). Các mô tả tiến độ/API lịch sử trong README/Form 2 chưa phản ánh mọi thay đổi mã; căn cứ số liệu lần này là workbook và mã được hash trong lần chạy.\n",
           "**Hỗ trợ AI:** Codex hỗ trợ tổ chức mã EDA, viết diễn giải theo kết quả tính, tạo hình và rà soát tái lập. Nhóm cần đọc, xác nhận chính sách và chịu trách nhiệm nội dung nộp theo quy định học phần.\n"]
    path=project/"reports/bao_cao_qua_trinh_eda.md"
    path.write_text("\n".join(parts),encoding="utf-8")
    inventory=figure_inventory(project)
    out=project/"experiments/eda_current_policy"
    out.mkdir(parents=True,exist_ok=True)
    inventory.to_csv(out/"figure_inventory.csv",index=False,encoding="utf-8-sig")
    return path
