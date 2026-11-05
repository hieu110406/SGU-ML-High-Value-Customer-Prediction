"""Reproducible EDA figures and data-driven Vietnamese interpretations."""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # PNGs are displayed explicitly; no GUI/Tk dependency.
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from eda_analysis import CORRELATION_COLUMNS, PAIRS, REFERENCE_DATE, checksum

BLUE, GOLD, ORANGE = "#2166ac", "#a37c00", "#c56b28"
GROUPS = ["UK", "Other-country", "Multi-country"]
GROUP_COLORS = [BLUE, ORANGE, GOLD]
SHORT = ["R", "F", "M", "AOV", "Gap", "Tenure", "Codes*", "Qty*", "Qty/order*"]
LABELS = {"Frequency":"Purchase invoices", "Monetary":"Purchase value (GBP)", "Recency":"Recency (days)",
          "avg_order_value":"AOV (GBP/invoice)", "n_stock_codes_candidate":"Retained StockCode count*",
          "avg_purchase_gap_days":"Mean purchase gap (days)", "observed_tenure_days":"Observed tenure (days)",
          "total_quantity_candidate":"Retained units*", "avg_quantity_per_order_candidate":"Retained units/invoice*"}

# All figures are presented once in the single EDA notebook.
FIGURES = {
    "missing_values_by_column": (2, "Dữ liệu thiếu theo cột"),
    "invoices_by_c_prefix": (2, "Loại chứng từ C/không C"),
    "raw_transaction_full_distributions": (3, "Phân phối giao dịch thô"),
    "raw_categorical_distributions": (3, "Phân phối biến phân loại"),
    "customer_behavior_distributions": (3, "Phân phối hành vi khách hàng"),
    "customer_purchase_gaps": (3, "Khoảng cách mua và số đơn"),
    "rfm_experimental_distributions": (3, "Phân phối từng biến RFM"),
    "invoices_by_month": (4, "Hóa đơn theo tháng"),
    "signed_line_value_by_month": (4, "Giá trị theo tháng và phạm vi chính sách"),
    "transactions_by_weekday_hour": (4, "Tần suất theo thứ và giờ"),
    "country_activity": (5, "Hoạt động theo quốc gia"),
    "country_activity_excluding_uk": (5, "Quốc gia ngoài UK"),
    "customer_frequency_vs_monetary": (6, "Num vs Num: quan hệ giữa các đặc trưng"),
    "customer_value_by_country": (6, "Num vs Cat: quốc gia và nhóm số đơn"),
    "country_vs_invoice_type": (6, "Cat vs Cat: quốc gia và chứng từ"),
    "customer_order_group_by_country": (6, "Cat vs Cat: quốc gia và nhóm khách"),
    "rfm_multivariate_scatter": (7, "RFM đồng thời"),
    "behavior_multivariate_scatter": (7, "Đặc trưng thủ công đồng thời"),
    "country_frequency_monetary": (7, "Frequency/Monetary theo quốc gia"),
    "correlation_spearman_heatmap": (8, "Ma trận tương quan Spearman"),
    "correlation_pearson_heatmap": (8, "Ma trận tương quan Pearson"),
    "correlation_pairwise_counts": (8, "Số quan sát hợp lệ theo cặp"),
    "clean_transaction_full_distributions": (9, "Phân phối sau chính sách hiện tại"),
    "preprocessing_row_flow": (10, "Đối chiếu số dòng qua pipeline"),
}


def configure_style():
    plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":11, "axes.titlesize":12,
                         "axes.labelsize":11, "figure.titlesize":14, "axes.spines.top":False,
                         "axes.spines.right":False, "savefig.dpi":140})


def _number(value, decimals=0):
    return f"{value:,.{decimals}f}"


def _compact(value, position=None):
    if abs(value) >= 1_000_000:
        return f"{value/1_000_000:g}M"
    if abs(value) >= 1000:
        return f"{value/1000:g}k"
    return f"{value:g}"


def narrative(result, key):
    if key == "rfm_experimental_distributions":
        b = result["tables"]["customer_behavior"]
        return dict(
            question="R, F, M riêng lẻ có miền và độ lệch thế nào?",
            scope=f"Thử nghiệm trên {len(b):,} khách có ID; một dòng/khách, cùng cửa sổ [2009-12-01, 2011-12-10). Dùng bảng khách đã tính trong notebook; Guest không là một khách.",
            observed=f"Trung vị R={b.Recency.median():.2f} ngày; F={b.Frequency.median():.0f} hóa đơn; M={b.Monetary.median():,.2f} GBP. R thiếu {b.Recency.isna().sum()}, F thiếu {b.Frequency.isna().sum()}, M thiếu {b.Monetary.isna().sum()} khách; skew R/F/M={b.Recency.skew():.2f}/{b.Frequency.skew():.2f}/{b.Monetary.skew():.2f}.",
            meaning="RFM thử nghiệm đủ dữ liệu cho khảo sát biến đổi; F/M có thang khác R nên cần cân nhắc trọng số và scaling.",
            limit="R = reference − last invoice time; F = n_orders, M = total_purchase_value. Mốc tham chiếu 2011-12-10 loại trừ, không phải ngày hiện tại. Chưa chọn bộ biến mô hình chính thức.")
    requested_key = key
    t, raw, b = result["tables"], result["raw"], result["tables"]["customer_behavior"]
    n, nr = len(b), len(raw)
    customer_scope = f"Thử nghiệm trên {n:,} khách có ID; một dòng/khách, sau clean_data hiện tại; cửa sổ [2009-12-01, 2011-12-10). Guest được loại khỏi khảo sát khách sau pipeline."
    raw_scope = f"{nr:,} dòng thô của hai sheet, giữ C, âm, trùng và ID thiếu."
    default_limit = "Quan sát mô tả trong một cửa sổ; chưa phải quan hệ nhân quả hay cụm chính thức. Chính sách nghiệp vụ cần nhóm xác nhận."
    rho = t["correlation_spearman"]
    profile = t["customer_profile"].set_index("variable")
    single = int(b.Frequency.eq(1).sum())
    notes = {}

    def add(name, question, scope, observed, meaning, limit=default_limit):
        notes[name] = dict(question=question, scope=scope, observed=observed, meaning=meaning, limit=limit)

    missing = t["missing"].set_index("column")
    add("missing_values_by_column", "Cột nào thiếu và ảnh hưởng thế nào đến quan sát khách hàng?", raw_scope,
        f"Customer ID thiếu {missing.loc['Customer ID','missing_rows']:,}/{nr:,} dòng ({missing.loc['Customer ID','missing_pct']:.2f}%); Description thiếu {missing.loc['Description','missing_rows']:,} dòng. Các cột còn lại không thiếu.",
        "Phân tích khách có ID chỉ đại diện phần định danh được; Guest không đại diện một cá nhân.", "Không suy ra phân bố hành vi của dòng vô danh từ nhóm có ID; Description được pipeline điền nhưng không tạo thông tin sản phẩm mới.")
    c = t["invoice_types"].loc["C"]
    add("invoices_by_c_prefix", "Chứng từ C chiếm bao nhiêu mã hóa đơn và dòng?", raw_scope,
        f"Có {int(c.invoices):,}/{raw.Invoice.nunique():,} mã C ({100*c.invoices/raw.Invoice.nunique():.2f}%), tương ứng {int(c.rows):,} dòng; mẫu số mã khác mẫu số dòng.",
        "Cần giữ chứng từ C để kiểm kê riêng trước khi tạo giá trị mua.", "C là chỉ báo hủy theo UCI; chưa xác minh được trả hàng hay ghép đơn gốc. Không coi tỷ lệ mã C là return_rate.")
    p = t["transaction_profile"].query("population == 'raw_including_C'").set_index("variable")
    add("raw_transaction_full_distributions", "Quantity, Price, LineValue lệch và có đuôi thế nào?", raw_scope,
        "; ".join(f"{v}: median={p.loc[v,'median']:,.2f}, P99={p.loc[v,'p99']:,.2f}, min={p.loc[v,'minimum']:,.2f}, max={p.loc[v,'maximum']:,.2f}, skew={p.loc[v,'skewness']:.2f}" for v in p.index)+".",
        "Miền âm/dương và cực trị khiến mean đơn lẻ khó diễn giải; cần chọn góc nhìn mua trước log/scaling.", "Histogram có bin symlog; boxplot giữ toàn miền symlog, ngưỡng IQR tính trên thang gốc. Skew có dấu của giá/giá trị thô chịu tác động cực trị âm; không tự gọi mọi biến là lệch phải. Không cắt dữ liệu.")
    codes = t["code_groups"].sort_values("rows", ascending=False)
    add("raw_categorical_distributions", "Các nhóm StockCode tập trung ở đâu?", raw_scope,
        "; ".join(f"{name}: {int(row.rows):,} dòng ({100*row.rows/nr:.2f}%)" for name,row in codes.iterrows())+". Nhãn nhóm mã chỉ dựa danh sách pipeline và hình thức mã.",
        "Không đồng nhất số StockCode ứng viên với số sản phẩm đã xác minh.", "SPECIAL_CODES chỉ là danh sách loại hiện tại; regex không xác nhận sản phẩm. Mỗi dòng thuộc đúng một nhóm trong hình.")
    add("customer_behavior_distributions", "Hành vi từng khách có phân phối lệch đến đâu?", customer_scope,
        "; ".join(f"{LABELS[c]}: median={profile.loc[c,'median']:,.2f}, P99={profile.loc[c,'p99']:,.2f}, max={profile.loc[c,'maximum']:,.2f}, skew={profile.loc[c,'skewness']:.2f}" for c in ["Frequency","Monetary","avg_order_value","n_stock_codes_candidate"])+".",
        "Đuôi dài có thể chi phối khoảng cách Euclidean; khảo sát log1p/scaling và độ nhạy thay vì loại khách giá trị lớn.", "Histogram và boxplot dùng thang log1p hiển thị, không xóa khách. * chỉ mã/đơn vị ứng viên; chưa xác minh danh mục sản phẩm.")
    add("customer_purchase_gaps", "Có bao nhiêu khách đủ lịch sử để tính khoảng cách mua?", customer_scope,
        f"{single:,}/{n:,} khách ({100*single/n:.2f}%) chỉ một Invoice; {n-single:,} khách còn lại có gap, trung vị {b.avg_purchase_gap_days.median():.2f} ngày. Gap nhỏ nhất {b.avg_purchase_gap_days.min():.2f} ngày.",
        "Gap thiếu có ý nghĩa cấu trúc; khi phân cụm cần chính sách thiếu/cờ một đơn, giữ 0 thật nếu các hóa đơn cùng thời điểm.", "Không điền NaN bằng 0. Invoice nhiều thời điểm dùng earliest trong các dòng giữ lại; chưa biết lịch sử trước/sau cửa sổ.")
    m = t["monthly"]
    peak = m.invoices.idxmax()
    add("invoices_by_month", "Số Invoice duy nhất biến động theo tháng ra sao?", raw_scope,
        f"Có {len(m)} tháng; tháng nhiều mã chứng từ nhất {peak}: {int(m.loc[peak,'invoices']):,}. Tháng cuối {m.index[-1]} có {int(m.iloc[-1].invoices):,} mã và {int(m.iloc[-1].rows):,} dòng, chỉ đến {raw.InvoiceDate.max():%d/%m/%Y}.",
        "Mức hoạt động và độ dài quan sát có thể ảnh hưởng Frequency/tenure.", "Bao gồm C. Tháng 12/2010 có hai sheet chồng lấn và có dòng trùng; 12/2011 chưa đủ tháng. Không suy diễn mùa vụ dài hạn hay nguyên nhân từ đường xu hướng.")
    add("signed_line_value_by_month", "Giá trị có dấu và giá trị giữ lại bởi pipeline khác nhau thế nào?", raw_scope+f" Đường thứ hai: {len(result['clean']):,} dòng sau clean_data, gồm Guest.",
        f"Tổng thô có dấu {raw.LineValue.sum():,.3f} GBP; sau pipeline {result['clean'].LineValue.sum():,.3f} GBP. Tháng cuối tương ứng {m.iloc[-1].signed_value_gbp:,.2f} và {m.iloc[-1].current_value_gbp:,.2f} GBP.",
        "Phải giữ nhãn phạm vi khi diễn giải Monetary; loại C/âm và ngoại lệ thay đổi giá trị được quan sát.", "Hai đường khác quần thể/chính sách, không phải tác động nhân quả hoặc doanh thu thuần đã xác minh. Giá trị dùng Q×P chính xác, không cộng Revenue đã làm tròn.")
    peak_cell = t["weekday_hour"].stack().idxmax()
    week = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    add("transactions_by_weekday_hour", "Dòng giao dịch tập trung vào thứ và giờ nào?", raw_scope,
        f"Ô cao nhất là {week[peak_cell[0]]} lúc {peak_cell[1]} giờ: {int(t['weekday_hour'].loc[peak_cell]):,} dòng; tổng các ô {int(t['weekday_hour'].to_numpy().sum()):,} dòng.",
        "Giúp mô tả thời điểm hoạt động, chưa đủ căn cứ chọn đặc trưng thói quen từng khách.", "Đây là heatmap tần suất, không phải tương quan. Giờ nguồn không có múi giờ; không tự chuyển sang giờ Bangkok. Ô không xuất hiện được biểu diễn bằng 0 đếm.")
    uk = t["countries"].loc["United Kingdom"]
    for key,question in [("country_activity","Quốc gia nào chiếm ưu thế theo bốn đơn vị đo?"), ("country_activity_excluding_uk","Ngoài UK, thị trường nào nổi bật?")]:
        remaining = t["countries"].drop(index="United Kingdom")
        top = remaining.index[0]
        add(key, question, raw_scope+" Top 10 theo số dòng; bảng đầy đủ giữ trong tables['countries'].",
            f"UK: {int(uk.rows):,}/{nr:,} dòng ({100*uk.rows/nr:.2f}%), {int(uk.invoices):,} mã Invoice, {int(uk.customers):,} khách và giá trị có dấu {uk.signed_value_gbp:,.2f} GBP. Ngoài UK, {top} dẫn đầu số dòng ({int(remaining.iloc[0].rows):,}).",
            "Cụm toàn bộ dữ liệu sẽ phản ánh mạnh thị trường UK; nên kiểm tra hồ sơ cụm theo quốc gia.", "Khách hoặc Invoice có thể thuộc nhiều quốc gia nên số đếm distinct theo quốc gia không cộng thành tổng toàn nguồn. Unspecified là nhãn chưa xác định; hình ngoài UK không đại diện cơ cấu toàn bộ.")
    add("customer_frequency_vs_monetary", "F–M, R–M, F–AOV, số mã–M và lượng–giá trị liên hệ thế nào?", customer_scope,
        "; ".join(f"{x}–{y}: Spearman={rho.loc[x,y]:.4f}, n={int(t['correlation_pairwise_counts'].loc[x,y]):,}, xu hướng {'đồng biến' if rho.loc[x,y]>0 else 'nghịch biến'}" for x,y in PAIRS)+". Scatter toàn bộ khách thể hiện cùng chiều liên hệ trên trục log1p, đồng thời còn độ phân tán lớn ở mỗi mức F.",
        "So sánh các quan hệ để cân nhắc thông tin bổ sung; F và số đơn là cùng một phép đo nên chỉ vẽ một lần.", "M = F × AOV và giá trị từng dòng = Quantity × Price nên các biến liên hệ một phần do công thức. Log1p chỉ để hiển thị; hệ số tính trên dữ liệu gốc. Alpha giảm chồng điểm, không lấy mẫu hoặc cắt đuôi.")
    country = t["numeric_by_country"]
    order = t["numeric_by_order_group"]
    add("customer_value_by_country", "Giá trị và số đơn khác nhau giữa nhóm quốc gia/khách một đơn ra sao?", customer_scope,
        "; ".join(f"{g}: n={int(v.n):,}, median M={v.median_Monetary:,.2f} GBP, F={v.median_Frequency:.1f}" for g,v in country.iterrows())+
        "; "+"; ".join(f"{g}: n={int(v.n):,}, median M={v.median_Monetary:,.2f} GBP" for g,v in order.iterrows())+".",
        "Mô tả khác biệt phân phối, giúp kiểm tra diễn giải cụm và nhóm có lịch sử ngắn.", "Country giữ nhãn nếu duy nhất; nhiều Country → Multi-country riêng, không gán theo tùy ý. Khách nhiều đơn được định nghĩa từ F nên chênh lệch M không là bằng chứng tác động. Nhóm ít khách không đủ suy rộng; boxplot log1p gồm mọi điểm.")
    for key,table_name,count_name,question,scope in [
        ("country_vs_invoice_type","country_invoice_row_pct","country_invoice_counts","Tỷ lệ dòng C thay đổi theo nhóm quốc gia không?",raw_scope),
        ("customer_order_group_by_country","country_order_row_pct","country_order_counts","Tỷ lệ khách một/nhiều đơn khác nhau giữa nhóm quốc gia không?",customer_scope)]:
        pct, counts = t[table_name],t[count_name]
        target = "C" if key == "country_vs_invoice_type" else "One invoice"
        add(key,question,scope, "; ".join(f"{g}: {int(counts.loc[g,target]):,}/{int(counts.loc[g].sum()):,} = {pct.loc[g,target]:.2f}% {target}" for g in pct.index)+".",
            "Bảng chéo và tỷ lệ theo hàng cho phép so nhóm có quy mô khác nhau.",
            "Mẫu số là tổng dòng trong hàng đối với loại chứng từ; tổng khách trong hàng đối với nhóm một/nhiều đơn. Đây là heatmap tỷ lệ/tần suất, không phải tương quan; không suy ra hoàn trả hay nhãn cụm.")
    add("rfm_multivariate_scatter", "R thay đổi thế nào đồng thời theo F và M?", customer_scope,
        f"Toàn bộ {n:,} khách được vẽ; Spearman F–M={rho.loc['Frequency','Monetary']:.4f}, R–M={rho.loc['Recency','Monetary']:.4f}, R–F={rho.loc['Recency','Frequency']:.4f}. R từ {b.Recency.min():.2f} đến {b.Recency.max():.2f} ngày.",
        "Màu R bổ sung mức gần đây cho quan hệ F/M; cần mô hình và đánh giá độ ổn định để kiểm tra các kiểu hành vi.", "X/Y dùng log1p, màu dùng ngày R gốc. Alpha và thứ tự điểm cố định để giảm chồng lấn, không lấy mẫu; vùng thị giác chưa phải cụm chính thức.")
    gapn = int(b.avg_purchase_gap_days.notna().sum())
    add("behavior_multivariate_scatter", "AOV/số mã và nhịp mua/tenure bổ sung gì cho Frequency?", customer_scope,
        f"Panel F–AOV tô màu số mã có {n:,} khách, Spearman F–AOV={rho.loc['Frequency','avg_order_value']:.4f}; panel F–gap tô màu tenure có {gapn:,} khách, loại khỏi hiển thị {n-gapn:,} khách thiếu gap. Spearman F–gap={rho.loc['Frequency','avg_purchase_gap_days']:.4f}, n={gapn:,}.",
        "Các đặc trưng tóm tắt giỏ và nhịp mua có thể bổ sung RFM nhưng liên hệ công thức cần xem kỹ.", "M=F×AOV; với F>1, gap=(tenure−R)/(F−1). Màu số mã hiển thị log1p; không coi các biến là độc lập hoặc đưa tất cả vào mô hình tự động.")
    add("country_frequency_monetary", "Quan hệ F–M có cùng phạm vi giữa các nhóm quốc gia không?", customer_scope,
        "; ".join(f"{g}: n={int(v.n):,}, median F={v.median_Frequency:.1f}, M={v.median_Monetary:,.2f} GBP" for g,v in country.iterrows())+". Các panel giữ chung trục log1p để so sánh miền quan sát.",
        "Kiểm tra liệu hồ sơ hành vi chỉ phản ánh quy mô thị trường; Country dùng diễn giải, chưa chọn là biến số đầu vào.", "Multi-country được giữ thành nhóm riêng từ các dòng mua còn lại. Các nhóm quy mô khác nhau; không suy ra khác biệt có ý nghĩa thống kê hay cụm địa lý.")
    gap = "avg_purchase_gap_days"
    audit = t["correlation_column_audit"]
    for key,method,table in [("correlation_spearman_heatmap","Spearman","correlation_spearman"), ("correlation_pearson_heatmap","Pearson","correlation_pearson")]:
        corr = t[table]
        add(key,f"{method} cho thấy cặp nào liên hệ hoặc trùng thông tin?",customer_scope+" Chỉ 9 biến số cùng phạm vi; pairwise complete observations.",
            f"{method} F–M={corr.loc['Frequency','Monetary']:.4f} (n={n:,}); R–M={corr.loc['Recency','Monetary']:.4f} (n={n:,}); F–gap={corr.loc['Frequency',gap]:.4f} (n={gapn:,}). Có {int(audit.status.eq('all_missing').sum())} cột thiếu toàn bộ và {int(audit.status.eq('non_numeric').sum())} cột không phải số bị loại trước tính; {int(audit.status.eq('constant').sum())} cột hằng trong dữ liệu thực tế.",
            "Spearman xem quan hệ đơn điệu; Pearson nhạy đuôi lớn. Cân nhắc trùng thông tin với công thức M=F×AOV và Q=F×Q/đơn; không tự động loại biến chỉ vì hệ số cao.", "Không điền NaN bằng 0. Mỗi cặp có thể dùng tập khách khác; không diễn giải tương quan như nhân quả hay bằng chứng chất lượng phân cụm. R/F/M không chứa ID, timestamp hoặc nhãn Country.")
    add("correlation_pairwise_counts", "Mỗi hệ số có bao nhiêu khách hợp lệ?",customer_scope,
        f"Cặp không chứa gap có {n:,} quan sát; các cặp chứa gap có {gapn:,}. Chênh {n-gapn:,} chính là khách một Invoice; đường chéo gap cũng {gapn:,}.",
        "Đọc n cùng hệ số; các hệ số chứa gap chỉ mô tả khách mua nhiều đơn, có thể chịu sai lệch chọn mẫu.", "Ma trận n dùng số nguyên int64 và giao hai cờ hữu hạn, không dùng len toàn bảng cho mọi cặp. NaN vẫn là chưa quan sát, không phải nhịp mua 0.")
    clean_profile = t["transaction_profile"].query("population == 'current_pipeline_including_Guest'").set_index("variable")
    add("clean_transaction_full_distributions", "Sau các bộ lọc hiện tại, đuôi phân phối còn lớn không?",f"{len(result['clean']):,} dòng đầu ra clean_data, gồm Guest; Q/P dương, đã lọc log-IQR k=3 của pipeline.",
        "; ".join(f"{v}: median={clean_profile.loc[v,'median']:,.2f}, P99={clean_profile.loc[v,'p99']:,.2f}, max={clean_profile.loc[v,'maximum']:,.2f}, ngoài IQR1.5={int(clean_profile.loc[v,'outside_iqr']):,}" for v in clean_profile.index)+".",
        "Lọc cực trị ở cấp dòng của pipeline chưa làm mất toàn bộ đuôi dài ở cấp khách; cần kiểm tra độ nhạy khi phân cụm.", "EDA chỉ gắn cờ IQR1.5 trên thang gốc, không xóa thêm dòng/khách. Pipeline đã loại log-IQR k=3 là chính sách hiện có của Thuận; đề xuất giữ/xử lý khác cần nhóm xác nhận.")
    flow = t["preprocessing_trace"]
    add("preprocessing_row_flow", "Mỗi bước mã hiện tại giữ lại bao nhiêu dòng/hóa đơn/khách?",raw_scope+" Chạy clean_data nguyên trạng và đối chiếu trace độc lập, không ghi processed.",
        f"{nr:,} dòng thô → {len(result['clean']):,} dòng đầu ra pipeline (có {int(result['clean'].IsGuest.sum()):,} dòng Guest) → {len(result['purchase']):,} dòng khảo sát ID thật, {int(b.Frequency.sum()):,} hóa đơn, {n:,} khách. Bước log-IQR loại {int(flow.loc[flow.step.eq('Sau lọc ngoại lệ của pipeline'),'removed_rows'].iloc[0]):,} dòng.",
        "Đếm riêng khách định danh và dòng Guest; đầu ra cũ trong processed không tương đương lần chạy này.", "Đã xác minh khớp mã hiện tại, chưa có bằng chứng chính sách được phê duyệt. Đầu ra cũ dùng chính sách khác (bỏ ID thiếu, ghép C); không ghi đè dữ liệu cũ hoặc so chênh lệch như biến động hành vi.")
    return notes[requested_key]


def _scatter(ax, b, x, y, **kwargs):
    ax.scatter(np.log1p(b[x]), np.log1p(b[y]), s=12, alpha=.35, edgecolors="none", **kwargs)
    ax.set(xlabel="log1p " + LABELS[x], ylabel="log1p " + LABELS[y])


def _distribution(frame, columns, title, signed=False):
    fig, axes = plt.subplots(len(columns),2, figsize=(12,3.4*len(columns)), layout="constrained")
    for i,c in enumerate(columns):
        x = frame[c].dropna().to_numpy(dtype=float)
        if signed:
            forward = lambda v: np.sign(v)*np.log1p(np.abs(v))
            inverse = lambda v: np.sign(v)*np.expm1(np.abs(v))
            bins = np.unique(inverse(np.linspace(forward(x.min()), forward(x.max()),70)))
            axes[i,0].hist(x,bins=bins,color=BLUE)
            axes[i,0].set_xscale("symlog",linthresh=1)
            axes[i,0].xaxis.get_major_locator().set_params(numticks=9)
            axes[i,1].boxplot(x, orientation="horizontal", flierprops=dict(markersize=2, alpha=.25, markeredgecolor=BLUE))
            axes[i,1].set_xscale("symlog",linthresh=1)
            axes[i,1].xaxis.get_major_locator().set_params(numticks=9)
            xlabel = c + " (symlog display)"
        else:
            axes[i,0].hist(np.log1p(x),bins=45,color=BLUE)
            axes[i,1].boxplot(x,orientation="horizontal",flierprops=dict(markersize=2,alpha=.25,markeredgecolor=BLUE))
            axes[i,1].set_xlim(left=0)
            axes[i,1].set_xscale("function",functions=(np.log1p,np.expm1))
            ticks=[0,1,3,10,30,100,300,1000,3000,10000,30000,100000,300000,1000000]
            ticks=[v for v in ticks if v<=x.max()]
            if len(ticks)>8:
                ticks=[v for v in [0,1,10,100,1000,10000,100000,1000000] if v<=x.max()]
            axes[i,1].set_xticks(ticks)
            axes[i,1].xaxis.set_major_formatter(FuncFormatter(_compact))
            xlabel = "log1p " + LABELS.get(c,c)
        axes[i,0].set(title=c+" | histogram", xlabel=xlabel, ylabel=f"Observations (n={len(x):,})")
        axes[i,1].set(title=c+" | boxplot (original-value IQR)",
                      xlabel=xlabel if signed else LABELS.get(c,c)+" (log1p axis)", yticks=[])
    fig.suptitle(title)
    return fig


def plot_figure(result, key):
    configure_style()
    t,raw,b = result["tables"],result.get("raw"),result["tables"]["customer_behavior"]
    n = len(b)
    if key == "missing_values_by_column":
        fig,ax=plt.subplots(figsize=(10,4.5),layout="constrained")
        d=t["missing"]
        ax.barh(d.column,d.missing_pct,color=BLUE)
        for i,v in enumerate(d.missing_pct): ax.text(v+.2,i,f"{v:.2f}%",va="center")
        ax.set(xlabel=f"Missing rows (% of {len(raw):,} raw rows)",xlim=(0,28),title="Missing values | raw, both sheets")
    elif key == "invoices_by_c_prefix":
        fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout="constrained")
        for ax,col in zip(axes,["invoices","rows"]):
            d=t["invoice_types"][col]
            ax.bar(d.index,d.values,color=[ORANGE,BLUE])
            for i,v in enumerate(d): ax.text(i,v,f"{v:,}",ha="center",va="bottom")
            ax.margins(y=.15)
            ax.set(title=f"Raw {col} by document type",ylabel="Unique invoice IDs" if col=="invoices" else "Transaction rows",xlabel="Invoice prefix group")
    elif key in {"raw_transaction_full_distributions","clean_transaction_full_distributions"}:
        frame=raw if key.startswith("raw") else result["clean"]
        fig=_distribution(frame,["Quantity","Price","LineValue"],f"{'Raw incl. C' if key.startswith('raw') else 'Current pipeline incl. Guest'} | all {len(frame):,} rows\nQuantity: units; Price: GBP/unit; LineValue: GBP/row",signed=True)
    elif key == "raw_categorical_distributions":
        fig,ax=plt.subplots(figsize=(10,4.5),layout="constrained")
        d=t["code_groups"].sort_values("rows")
        ax.barh(d.index,d.rows,color=BLUE)
        ax.set(xlabel="Raw transaction rows",title=f"StockCode groups | {len(raw):,} raw rows; pattern is not verification")
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v,p:f"{v/1000:,.0f}k"))
    elif key == "customer_behavior_distributions":
        fig=_distribution(b,["Frequency","Monetary","avg_order_value","n_stock_codes_candidate"],f"Experimental known-ID customers | n={n:,}; * unverified codes")
    elif key == "customer_purchase_gaps":
        fig,axes=plt.subplots(1,2,figsize=(11,4.8),layout="constrained")
        gaps=b.avg_purchase_gap_days.dropna()
        axes[0].hist(gaps,bins=40,color=BLUE)
        axes[0].set(xlabel="Mean gap (days = 86400 seconds)",ylabel="Customers",title=f"Purchase gaps | n={len(gaps):,} valid buyers")
        count=b.order_group.value_counts().reindex(["One invoice","Multiple invoices"])
        axes[1].bar(count.index,count,color=[ORANGE,BLUE])
        for i,v in enumerate(count): axes[1].text(i,v,f"{v:,} ({100*v/n:.1f}%)",ha="center",va="bottom")
        axes[1].margins(y=.15)
        axes[1].set(ylabel="Customers",title=f"Experimental buyers | denominator {n:,}")
    elif key == "rfm_experimental_distributions":
        fig=_distribution(b,["Recency","Frequency","Monetary"],f"Experimental RFM | n={n:,}; reference {REFERENCE_DATE} exclusive")
    elif key in {"invoices_by_month","signed_line_value_by_month"}:
        fig,ax=plt.subplots(figsize=(13,5),layout="constrained")
        d=t["monthly"]; x=np.arange(len(d))
        if key == "invoices_by_month":
            ax.plot(x,d.invoices,"o-",color=BLUE,label="Raw, including C")
            ax.set(ylabel="Unique invoice IDs per month",title="Monthly invoices | raw; overlapping sheets retained")
        else:
            ax.plot(x,d.signed_value_gbp/1e6,"o-",color=BLUE,label="Raw signed Q × P (incl. C)")
            ax.plot(x,d.current_value_gbp/1e6,"s--",color=ORANGE,label="Current clean_data (incl. Guest)")
            ax.set(ylabel="Line value (million GBP)",title="Monthly line values | different policy populations")
        ax.axvspan(len(d)-1.4,len(d)-.6,color=GOLD,alpha=.12,label="Final month partial")
        ticks=list(range(0,len(d),3))
        if len(d)-1 not in ticks: ticks.append(len(d)-1)
        ax.set(xticks=ticks,xticklabels=[d.index[i] for i in ticks],xlabel="Calendar month (source time)")
        ax.legend(fontsize=10)
    elif key == "transactions_by_weekday_hour":
        fig,ax=plt.subplots(figsize=(13,5),layout="constrained")
        im=ax.imshow(t["weekday_hour"],aspect="auto",cmap="Blues",vmin=0)
        ax.set(xticks=range(24),yticks=range(7),yticklabels=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"],xlabel="Hour (source timezone unspecified)",ylabel="Weekday",title=f"Raw transaction rows | n={len(raw):,}; counts, not correlation")
        fig.colorbar(im,ax=ax,label="Transaction rows")
    elif key in {"country_activity","country_activity_excluding_uk"}:
        d=t["countries"]
        if key.endswith("excluding_uk"): d=d.drop(index="United Kingdom")
        d=d.head(10).iloc[::-1]
        fig,axes=plt.subplots(2,2,figsize=(13,11),layout="constrained")
        for ax,c,title in zip(axes.flat,["rows","invoices","customers","signed_value_gbp"],["Transaction rows","Unique Invoice IDs","Known Customer IDs","Signed value (GBP)"]):
            ax.barh(d.index,d[c],color=BLUE)
            ax.set(xlabel=title,title=title)
            ax.tick_params(axis="y",labelsize=10)
            ax.xaxis.set_major_formatter(FuncFormatter(_compact))
        fig.suptitle("Raw top countries by rows"+ (" | UK excluded" if key.endswith("excluding_uk") else " | includes C, missing IDs, duplicates"))
    elif key == "customer_frequency_vs_monetary":
        fig,axes=plt.subplots(3,2,figsize=(12,14),layout="constrained")
        for ax,(x,y) in zip(axes.flat,PAIRS):
            _scatter(ax,b,x,y,color=BLUE)
            ax.set_title(f"Spearman={t['correlation_spearman'].loc[x,y]:.3f} | n={n:,}")
        fig.suptitle("Num vs Num | experimental known-ID customers; all points")
    elif key == "customer_value_by_country":
        fig,axes=plt.subplots(1,3,figsize=(16,5.5),layout="constrained")
        for ax,c in zip(axes[:2],["Monetary","Frequency"]):
            groups=[g for g in GROUPS if b.country_group.eq(g).any()]
            arrays=[np.log1p(b.loc[b.country_group.eq(g),c]) for g in groups]
            labels=[g+f"\nn={len(a):,}" for g,a in zip(groups,arrays)]
            ax.boxplot(arrays,tick_labels=labels,flierprops=dict(markersize=2,alpha=.25))
            ax.set(ylabel="log1p "+LABELS[c],title="Customer "+c+" by country")
        groups=["One invoice","Multiple invoices"]
        arrays=[np.log1p(b.loc[b.order_group.eq(g),"Monetary"]) for g in groups]
        axes[2].boxplot(arrays,tick_labels=[g+f"\nn={len(a):,}" for g,a in zip(groups,arrays)],flierprops=dict(markersize=2,alpha=.25))
        axes[2].set(ylabel="log1p Purchase value (GBP)",title="Purchase value by order group")
        fig.suptitle(f"Num vs Cat | experimental known-ID customers | n={n:,}")
    elif key in {"country_vs_invoice_type","customer_order_group_by_country"}:
        prefix="country_invoice" if key=="country_vs_invoice_type" else "country_order"
        d,counts=t[prefix+"_row_pct"],t[prefix+"_counts"]
        fig,ax=plt.subplots(figsize=(10,4.8))
        fig.subplots_adjust(left=.30,right=.88,bottom=.18,top=.88)
        im=ax.imshow(d,aspect="auto",cmap="Blues",vmin=0,vmax=100)
        for i in range(len(d)):
            for j in range(len(d.columns)):
                v=d.iloc[i,j]
                ax.text(j,i,f"{v:.2f}%\n{counts.iloc[i,j]:,}",ha="center",va="center",color="white" if v>60 else "#222222")
        ax.set(xticks=range(len(d.columns)),xticklabels=d.columns,yticks=range(len(d)),
               yticklabels=[g+f" (n={int(counts.loc[g].sum()):,})" for g in d.index],xlabel="Invoice type" if prefix=="country_invoice" else "Customer order group",ylabel="Country group",
               title="Raw transaction rows | row percentages" if prefix=="country_invoice" else "Experimental customers | row percentages")
        fig.colorbar(im,ax=ax,label="Share within row (%)")
    elif key == "rfm_multivariate_scatter":
        fig,ax=plt.subplots(figsize=(10,7),layout="constrained")
        # Deterministic drawing order prevents a country/sort order from hiding a group.
        d=b.sample(frac=1,random_state=15)
        im=ax.scatter(np.log1p(d.Frequency),np.log1p(d.Monetary),c=d.Recency,cmap="cividis",s=14,alpha=.55,edgecolors="none")
        ax.set(xlabel="log1p Purchase invoices",ylabel="log1p Purchase value (GBP)",title=f"Experimental RFM | n={n:,}; color = Recency days")
        fig.colorbar(im,ax=ax,label="Recency (days)")
    elif key == "behavior_multivariate_scatter":
        fig,axes=plt.subplots(1,2,figsize=(15,6),layout="constrained")
        im=axes[0].scatter(np.log1p(b.Frequency),np.log1p(b.avg_order_value),c=np.log1p(b.n_stock_codes_candidate),cmap="cividis",s=12,alpha=.5,edgecolors="none")
        axes[0].set(xlabel="log1p Purchase invoices",ylabel="log1p AOV (GBP/invoice)",title=f"All {n:,} customers")
        fig.colorbar(im,ax=axes[0],label="log1p retained StockCode count*")
        d=b.dropna(subset=["avg_purchase_gap_days"])
        im=axes[1].scatter(np.log1p(d.Frequency),np.log1p(d.avg_purchase_gap_days),c=d.observed_tenure_days,cmap="cividis",s=12,alpha=.5,edgecolors="none")
        axes[1].set(xlabel="log1p Purchase invoices",ylabel="log1p Mean purchase gap (days)",title=f"Multiple-invoice customers | n={len(d):,}")
        fig.colorbar(im,ax=axes[1],label="Observed tenure (days)")
        fig.suptitle("Experimental behavior features | * unverified codes; all valid points")
    elif key == "country_frequency_monetary":
        fig,axes=plt.subplots(1,3,figsize=(16,5.5),sharex=True,sharey=True,layout="constrained")
        for ax,g,color in zip(axes,GROUPS,GROUP_COLORS):
            d=b[b.country_group.eq(g)]
            _scatter(ax,d,"Frequency","Monetary",color=color)
            ax.set_title(f"{g} | n={len(d):,}")
        fig.suptitle("Experimental F/M by country group | identical axis domains")
    elif key.startswith("correlation_"):
        table_name={"correlation_spearman_heatmap":"correlation_spearman","correlation_pearson_heatmap":"correlation_pearson","correlation_pairwise_counts":"correlation_pairwise_counts"}[key]
        d=t[table_name]
        fig,ax=plt.subplots(figsize=(10.5,9),layout="constrained")
        is_count=key=="correlation_pairwise_counts"
        im=ax.imshow(d,cmap="Blues" if is_count else "RdBu_r",vmin=0 if is_count else -1,vmax=n if is_count else 1)
        for i in range(len(d)):
            for j in range(len(d)):
                v=d.iloc[i,j]
                label=f"{int(v):,}" if is_count else f"{v:.2f}"
                white=(v/n>.65) if is_count else abs(v)>.65
                ax.text(j,i,label,ha="center",va="center",fontsize=10,color="white" if white else "#222222")
        ax.set(xticks=range(len(d)),yticks=range(len(d)),xticklabels=SHORT,yticklabels=SHORT,
               xlabel="Customer features",ylabel="Customer features",title=f"{'Pairwise valid customers' if is_count else table_name.replace('correlation_','').title()+' correlation'} | experimental n={n:,}")
        fig.colorbar(im,ax=ax,label="Valid customers" if is_count else "Correlation coefficient")
        fig.supxlabel("R: Recency | F: Frequency | M: Monetary | AOV: value/order | Gap: days\nTenure: days since first observed purchase | * unverified codes / units",fontsize=10)
    elif key == "preprocessing_row_flow":
        d=t["preprocessing_trace"]
        fig,ax=plt.subplots(figsize=(13,6.5))
        fig.subplots_adjust(left=.31,right=.97,bottom=.13,top=.9)
        ax.barh(d.step,d.rows,color=BLUE)
        for i,v in enumerate(d.rows): ax.text(v+5000,i,f"{v:,}",va="center",fontsize=10)
        ax.invert_yaxis()
        ax.set(xlim=(0,len(raw)*1.16),xlabel="Rows retained",title="Current clean_data + EDA known-ID selection | experimental policy")
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v,p:f"{v/1000:,.0f}k"))
    else:
        raise KeyError(key)
    return fig


def save_figure(result, key):
    path=result["project"] / "notebooks/01_eda/figures" / f"{key}.png"
    path.parent.mkdir(parents=True,exist_ok=True)
    fig=plot_figure(result,key)
    fig.savefig(path,dpi=140,bbox_inches="tight",facecolor="white")
    plt.close(fig)
    result["metadata"].setdefault("figure_sha256", {})[key] = checksum(path)
    return path


def show_figure(result, key):
    from IPython.display import display, Markdown, Image
    note=narrative(result,key)
    display(Markdown(f"**Câu hỏi:** {note['question']}\n\n**Dữ liệu và phạm vi:** {note['scope']}"))
    path=save_figure(result,key)
    display(Image(filename=str(path)))
    display(Markdown(f"**Nhận xét:** {note['observed']}\n\n**Ý nghĩa đối với phân cụm:** {note['meaning']}\n\n**Giới hạn / bước tiếp theo:** {note['limit']}"))


def show_tables(result, names, limit=16):
    from IPython.display import display, Markdown
    for name in names:
        frame=result["tables"][name]
        display(Markdown(f"**{name}** — {len(frame):,} dòng; đầy đủ ở `analysis['tables']['{name}']`."))
        display(frame.head(limit))
