"""Raw-only EDA. Never imports the production cleaning/features/model pipeline.

All derived columns and customer aggregates are temporary analytical views.
Only summaries, audit samples, figures, and provenance are exported.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np
import pandas as pd

SEED = 1505
RAW_NAME = "Online Retail.xlsx"
COLUMNS = ["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate",
           "UnitPrice", "CustomerID", "Country"]
CUSTOMER_COLUMNS = ["n_invoices", "monetary", "avg_order_value", "n_stock_codes",
                    "total_quantity", "active_days", "observed_span_days",
                    "avg_purchase_gap_days", "recency_days"]
SOURCE_URL = "https://archive.ics.uci.edu/dataset/352/online+retail"
PURCHASE_RULE = ("InvoiceNo và CustomerID có mã, InvoiceDate hợp lệ; không có tiền tố C; "
                 "Quantity > 0 và UnitPrice > 0, cả hai hữu hạn. Giữ nguyên dòng trùng "
                 "và mã dịch vụ; chỉ là phạm vi khảo sát, chưa phải quy tắc clean.")
BLUE, ORANGE, GOLD, GREY = "#2266a0", "#b95e14", "#aa8518", "#596575"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(project, *args):
    return subprocess.check_output(["git", "-C", str(project.parent), *args], text=True).strip()


def protected_hashes(project):
    """Protect raw, processed, production code and the separate Form 2 survey."""
    roots = [project / "data", project / "src", project / "app", project / "configs",
             project / "tests", project / "experiments/form2_manual_behavior_raw_survey"]
    paths = [p for root in roots for p in root.rglob("*") if p.is_file()
             and "__pycache__" not in p.parts]
    return {p.relative_to(project).as_posix(): sha(p) for p in sorted(paths) if p.is_file()}


def numeric_summary(frame, columns, population):
    records = []
    for col in columns:
        s = frame[col].replace([np.inf, -np.inf], np.nan).dropna()
        q = s.quantile([.25, .5, .75, .95, .99])
        q1, med, q3, p95, p99 = q.tolist()
        iqr = q3 - q1
        low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        records.append(dict(population=population, variable=col, count=len(s),
                            missing_or_nonfinite=len(frame)-len(s), minimum=s.min(),
                            maximum=s.max(), mean=s.mean(), median=med, std=s.std(ddof=1),
                            q1=q1, q3=q3, iqr=iqr, p95=p95, p99=p99, skewness=s.skew(),
                            iqr_lower=low, iqr_upper=high,
                            outside_iqr=int((s.lt(low) | s.gt(high)).sum())))
    return pd.DataFrame(records)


def correlations(frame, cols):
    assert not {"InvoiceNo", "CustomerID", "StockCode"}.intersection(cols)
    numeric = frame[cols].replace([np.inf, -np.inf], np.nan)
    valid = numeric.notna().astype("int64")
    return {"pearson": numeric.corr(method="pearson", min_periods=3),
            "spearman": numeric.corr(method="spearman", min_periods=3),
            "pairwise_counts": valid.T @ valid}


def load_analysis(project):
    project = Path(project).resolve()
    raw_path = project / "data/raw" / RAW_NAME
    before = protected_hashes(project)
    raw_hash = sha(raw_path)
    sheets = pd.read_excel(raw_path, sheet_name=None, engine="openpyxl")
    sheet_records = []
    for name, frame in sheets.items():
        sheet_records.append(dict(sheet=name, rows=len(frame), columns=len(frame.columns),
                                  column_names=" | ".join(map(str, frame.columns)),
                                  all_blank_rows=int(frame.isna().all(axis=1).sum()),
                                  repeated_header_rows=int(frame.astype("string").eq(
                                      pd.Series(frame.columns, index=frame.columns)).all(axis=1).sum())))
    # No silent concatenation of unknown sheets or schema conversion.
    if list(sheets) != ["Online Retail"] or list(next(iter(sheets.values())).columns) != COLUMNS:
        raise ValueError("Workbook schema/sheets changed; inspect before extending EDA.")
    sheet_name, raw = next(iter(sheets.items()))
    df = raw.copy(deep=True)
    for col in ["InvoiceNo", "StockCode", "CustomerID", "Country"]:
        df[col] = df[col].astype("string").str.strip().replace("", pd.NA)
    # Preserve exact descriptions for code-description ambiguity audits.
    df["Description"] = df.Description.astype("string")
    # Excel reads numeric customer identifiers as floats because nulls exist.
    df["CustomerID"] = df.CustomerID.str.replace(r"(?<=\d)\.0$", "", regex=True)
    df["InvoiceDate"] = pd.to_datetime(df.InvoiceDate, errors="coerce")
    for col in ["Quantity", "UnitPrice"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["SignedLineValue"] = df.Quantity * df.UnitPrice
    df["is_c"] = df.InvoiceNo.str.upper().str.startswith("C", na=False)
    df["document_type"] = np.where(df.is_c, "C-prefix", "Non-C")
    purchase_mask = (df.InvoiceNo.notna() & df.CustomerID.notna() & df.InvoiceDate.notna()
                     & ~df.is_c & df.Quantity.gt(0) & df.UnitPrice.gt(0)
                     & np.isfinite(df.Quantity) & np.isfinite(df.UnitPrice))
    purchase = df.loc[purchase_mask].copy()
    ref = df.InvoiceDate.max().normalize() + pd.Timedelta(days=1)
    orders = purchase.groupby(["CustomerID", "InvoiceNo"], as_index=False).agg(
        order_date=("InvoiceDate", "min"), order_value=("SignedLineValue", "sum"))
    orders = orders.sort_values(["CustomerID", "order_date", "InvoiceNo"])
    orders["gap_days"] = orders.groupby("CustomerID").order_date.diff().dt.total_seconds() / 86400
    customers = purchase.groupby("CustomerID").agg(
        n_invoices=("InvoiceNo", "nunique"), monetary=("SignedLineValue", "sum"),
        n_stock_codes=("StockCode", "nunique"), total_quantity=("Quantity", "sum"),
        active_days=("InvoiceDate", lambda s: s.dt.normalize().nunique()),
        first_purchase=("InvoiceDate", "min"), last_purchase=("InvoiceDate", "max"))
    customers["avg_order_value"] = customers.monetary / customers.n_invoices
    customers["observed_span_days"] = (customers.last_purchase-customers.first_purchase).dt.total_seconds()/86400
    customers["recency_days"] = (ref-customers.last_purchase).dt.total_seconds()/86400
    customers["avg_purchase_gap_days"] = orders.groupby("CustomerID").gap_days.mean()
    a = dict(project=project, raw_path=raw_path, raw_hash=raw_hash, sheet_name=sheet_name,
             raw=raw, df=df, purchase=purchase, customers=customers, orders=orders,
             reference_date=ref, protected_before=before, tables={}, figures=[], comments={},
             run_started=datetime.now(timezone(timedelta(hours=7))).isoformat(),
             git_head=git(project, "rev-parse", "HEAD"), git_branch=git(project, "branch", "--show-current"),
             git_status_at_run=git(project, "status", "--short"),
             output=project / "experiments/eda_raw_moi",
             figure_dir=project / "notebooks/01_eda/figures/raw")
    a["output"].mkdir(parents=True, exist_ok=True)
    a["figure_dir"].mkdir(parents=True, exist_ok=True)
    a["tables"]["workbook_sheets"] = pd.DataFrame(sheet_records)
    build_tables(a)
    return a


def build_tables(a):
    raw, d, p, c, t = a["raw"], a["df"], a["purchase"], a["customers"], a["tables"]
    n = len(d)
    t["raw_inventory"] = pd.DataFrame([
        ("raw_file", a["raw_path"].relative_to(a["project"]).as_posix()),
        ("sha256", a["raw_hash"]), ("size_bytes", a["raw_path"].stat().st_size),
        ("format", "XLSX"), ("sheet", a["sheet_name"]), ("rows", n), ("columns", len(raw.columns)),
        ("date_min", d.InvoiceDate.min()), ("date_max", d.InvoiceDate.max()),
        ("source_timezone", "Không được cung cấp; không chuyển múi giờ"),
        ("invoices_including_C", d.InvoiceNo.nunique()), ("known_customer_ids", d.CustomerID.nunique()),
        ("stock_codes", d.StockCode.nunique()), ("countries", d.Country.nunique()),
        ("schema_note", "Một sheet; giữ schema raw InvoiceNo/UnitPrice/CustomerID; bí danh cột cũ chỉ dùng để đối chiếu lịch sử")
    ], columns=["item", "value"])
    meanings = [("Mã chứng từ; C là dấu hiệu hủy theo UCI", "identifier", "mã"),
                ("Mã hàng; có thể gồm mã dịch vụ/điều chỉnh", "identifier/category", "mã"),
                ("Mô tả hàng", "text", "văn bản"), ("Số lượng trên dòng, có dấu", "measure", "đơn vị hàng"),
                ("Thời điểm chứng từ, chưa biết múi giờ", "datetime", "thời gian nguồn"),
                ("Đơn giá theo mô tả UCI", "measure", "GBP/đơn vị"),
                ("Mã khách; không phải biến số liên tục", "identifier", "mã"),
                ("Quốc gia của khách theo UCI", "category", "nhãn")]
    t["data_dictionary"] = pd.DataFrame([dict(column=col, raw_dtype=str(raw[col].dtype),
        eda_dtype=str(d[col].dtype), meaning=meaning, role=role, unit=unit)
        for col, (meaning, role, unit) in zip(COLUMNS, meanings)])
    t["column_mapping"] = pd.DataFrame({"legacy_column_alias": ["Invoice", "StockCode", "Description", "Quantity",
        "InvoiceDate", "Price", "Customer ID", "Country"], "current_raw_column": COLUMNS,
        "eda_column": COLUMNS, "action": ["Bí danh cũ để đối chiếu; phân tích nhận schema raw, không đổi Excel gốc"]*8})
    samples = pd.concat([raw.head(5).assign(sample="head"), raw.tail(5).assign(sample="tail")])
    t["raw_samples"] = samples.rename_axis("zero_based_row").reset_index()
    t["missing_values"] = pd.DataFrame({"column": COLUMNS, "raw_null_count": raw.isna().sum().values,
        "empty_or_whitespace": [int(raw[col].astype("string").str.fullmatch(r"\s*", na=False).sum()) for col in COLUMNS],
        "eda_missing_count": d[COLUMNS].isna().sum().values,
        "eda_missing_pct": 100*d[COLUMNS].isna().mean().values})
    exact_extra, exact_all = raw.duplicated(), raw.duplicated(keep=False)
    masks = {"missing_customer": d.CustomerID.isna(), "missing_description": d.Description.isna(),
        "exact_duplicate_extra": exact_extra, "all_rows_in_duplicate_groups": exact_all,
        "C_prefix": d.is_c, "quantity_negative": d.Quantity.lt(0), "quantity_zero": d.Quantity.eq(0),
        "price_negative": d.UnitPrice.lt(0), "price_zero": d.UnitPrice.eq(0),
        "missing_invoice": d.InvoiceNo.isna(), "invalid_or_missing_date": d.InvoiceDate.isna(),
        "invalid_or_nonfinite_quantity": ~np.isfinite(d.Quantity),
        "invalid_or_nonfinite_price": ~np.isfinite(d.UnitPrice)}
    union = pd.concat(list(masks.values()), axis=1).any(axis=1)
    masks["union_any_issue_not_sum"] = union
    t["quality_issues"] = pd.DataFrame([dict(issue=k, rows=int(m.sum()), pct_rows=100*m.mean(),
        invoices=d.loc[m, "InvoiceNo"].nunique(), known_customers=d.loc[m, "CustomerID"].nunique(),
        signed_value=d.loc[m, "SignedLineValue"].sum(),
        absolute_value=d.loc[m, "SignedLineValue"].abs().sum(),
        rows_missing_customer=int((m & d.CustomerID.isna()).sum()),
        rows_zero_price=int((m & d.UnitPrice.eq(0)).sum()),
        note="Các nhóm chồng lấn; không cộng") for k,m in masks.items()])
    t["duplicate_criteria"] = pd.DataFrame([
        ("8 cột raw, dòng dư sau lần đầu", int(exact_extra.sum()), "Không tự xóa"),
        ("8 cột raw, mọi dòng thuộc nhóm trùng", int(exact_all.sum()), "Chồng lấn với dòng dư"),
        ("InvoiceNo + StockCode, dòng dư", int(raw.duplicated(["InvoiceNo", "StockCode"]).sum()),
         "Không phải khóa dòng; có thể nhiều lần thêm hàng/giá khác nhau")], columns=["criterion", "rows", "interpretation"])
    t["duplicate_samples"] = raw.loc[exact_all].head(16).rename_axis("zero_based_row").reset_index()
    d["quantity_sign"] = np.select([d.Quantity.lt(0), d.Quantity.eq(0), d.Quantity.gt(0)],
                                   ["negative", "zero", "positive"], default="missing")
    d["price_sign"] = np.select([d.UnitPrice.lt(0), d.UnitPrice.eq(0), d.UnitPrice.gt(0)],
                                ["negative", "zero", "positive"], default="missing")
    t["document_quantity_counts"] = pd.crosstab(d.document_type, d.quantity_sign).reindex(
        index=["Non-C", "C-prefix"], columns=["negative", "zero", "positive", "missing"], fill_value=0)
    t["document_status"] = d.groupby("document_type").agg(rows=("InvoiceNo", "size"),
        invoices=("InvoiceNo", "nunique"), customers=("CustomerID", "nunique"), signed_value=("SignedLineValue", "sum"))
    t["invoice_prefixes"] = d.assign(prefix=d.InvoiceNo.str.extract(r"^([^0-9]+)", expand=False).fillna("numeric"))\
        .groupby("prefix").agg(rows=("InvoiceNo", "size"), invoices=("InvoiceNo", "nunique"))
    t["price_sign_counts"] = d.groupby("price_sign").agg(rows=("UnitPrice", "size"),
        invoices=("InvoiceNo", "nunique"), customers=("CustomerID", "nunique"))
    t["nonpositive_price_samples"] = d.loc[d.UnitPrice.le(0), COLUMNS].head(12)
    t["negative_price_samples"] = d.loc[d.UnitPrice.lt(0), COLUMNS]
    conflict_records = []
    for key, col in [("InvoiceNo", "CustomerID"), ("InvoiceNo", "Country"),
                     ("InvoiceNo", "InvoiceDate"), ("CustomerID", "Country"),
                     ("StockCode", "Description"), ("Description", "StockCode")]:
        counts = d.groupby(key)[col].nunique(dropna=True)
        conflict_records.append(dict(key=key, attribute=col, keys_with_value=len(counts),
            keys_multiple_values=int(counts.gt(1).sum()), maximum_values=counts.max(),
            note="Dấu hiệu cần xem xét; không mặc định là lỗi"))
    t["identifier_conflicts"] = pd.DataFrame(conflict_records)
    inv = d.groupby("InvoiceNo").agg(rows=("StockCode", "size"), customers=("CustomerID", "nunique"),
        countries=("Country", "nunique"), timestamps=("InvoiceDate", "nunique"))
    t["invoice_conflict_samples"] = inv.loc[inv[["customers", "countries", "timestamps"]].gt(1).any(axis=1)].head(20)
    t["stock_description_audit"] = d.groupby("StockCode").agg(rows=("StockCode", "size"),
        n_descriptions=("Description", "nunique"), missing_description=("Description", lambda s: s.isna().sum()))\
        .sort_values(["n_descriptions", "rows"], ascending=False)
    t["nonstandard_stock_codes"] = d.loc[~d.StockCode.str.fullmatch(r"\d{5}[A-Za-z]*", na=False)]\
        .groupby("StockCode").agg(rows=("StockCode", "size"), signed_value=("SignedLineValue", "sum"))\
        .sort_values("rows", ascending=False)
    # Pattern is a screening rule, never an automatic product/service classification.
    t["numeric_summary"] = numeric_summary(d, ["Quantity", "UnitPrice", "SignedLineValue"], "raw lines")
    t["customer_summary"] = numeric_summary(c, CUSTOMER_COLUMNS, "temporary known-ID purchases")
    extreme = []
    for col in ["Quantity", "UnitPrice", "SignedLineValue"]:
        for kind, idx in [("minimum", d[col].nsmallest(3).index), ("maximum", d[col].nlargest(3).index)]:
            extreme.append(d.loc[idx, COLUMNS+["SignedLineValue"]].assign(extreme_variable=col, extreme_kind=kind))
    t["extreme_samples"] = pd.concat(extreme).rename_axis("zero_based_row").reset_index()
    for col, name in [("Country", "country_counts"), ("StockCode", "stock_code_counts"),
                      ("Description", "description_counts")]:
        counts = d[col].value_counts(dropna=False)
        t[name] = pd.DataFrame({col: counts.index, "rows": counts.values, "pct_rows": 100*counts.values/n})
    t["categorical_summary"] = pd.DataFrame([dict(variable=col, unique_nonmissing=d[col].nunique(),
        missing=d[col].isna().sum(), singleton_categories=int(d[col].value_counts().eq(1).sum()),
        categories_under_100_lines=int(d[col].value_counts().lt(100).sum()))
        for col in ["InvoiceNo", "CustomerID", "StockCode", "Description", "Country"]])
    month = d.InvoiceDate.dt.to_period("M")
    monthly = d.groupby(month).agg(rows=("InvoiceNo", "size"), invoices=("InvoiceNo", "nunique"),
        signed_line_value=("SignedLineValue", "sum"), first_timestamp=("InvoiceDate", "min"), last_timestamp=("InvoiceDate", "max"))
    monthly["temporary_purchase_value"] = p.groupby(p.InvoiceDate.dt.to_period("M")).SignedLineValue.sum()
    monthly["temporary_purchase_value"] = monthly.temporary_purchase_value.fillna(0)
    monthly["boundary_month"] = monthly.index.isin([month.min(), month.max()])
    monthly["note"] = np.where(monthly.boundary_month, "Tháng biên; đối chiếu thời điểm đầu/cuối", "Trong cửa sổ quan sát")
    monthly.index = monthly.index.astype(str)
    monthly.index.name = "month"
    t["monthly_activity"] = monthly
    t["weekday_counts"] = d.InvoiceDate.dt.dayofweek.value_counts().reindex(range(7), fill_value=0).rename_axis("weekday_0_Mon").to_frame("rows")
    t["hour_counts"] = d.InvoiceDate.dt.hour.value_counts().reindex(range(24), fill_value=0).rename_axis("source_hour").to_frame("rows")
    t["country_document_counts"] = pd.crosstab(d.Country, d.document_type).reindex(columns=["Non-C", "C-prefix"], fill_value=0)
    country_order = p.Country.value_counts().head(6).index.tolist()
    a["top_countries"] = country_order
    t["country_value_summary"] = p.groupby("Country").SignedLineValue.agg(["size", "median", "mean", "min", "max"])
    for level, frame, cols in [("line", d, ["Quantity", "UnitPrice", "SignedLineValue"]),
                                ("customer", c, CUSTOMER_COLUMNS)]:
        for method, table in correlations(frame, cols).items():
            t[f"correlations_{level}_{method}"] = table
    formula = [
        ("SignedLineValue", "raw", "Quantity * UnitPrice, không làm tròn", "GBP có dấu"),
        ("n_invoices", "customer", "nunique(InvoiceNo) trong tập mua tạm", "hóa đơn/khách"),
        ("monetary", "customer", "sum(Quantity * UnitPrice) trong tập mua tạm", "GBP/khách"),
        ("avg_order_value", "customer", "monetary / n_invoices", "GBP/hóa đơn"),
        ("n_stock_codes", "customer", "nunique(StockCode), gồm mã dịch vụ", "mã/khách"),
        ("total_quantity", "customer", "sum(Quantity)", "đơn vị hàng/khách"),
        ("active_days", "customer", "nunique(InvoiceDate.normalize())", "ngày có mua/khách"),
        ("observed_span_days", "customer", "(max(date)-min(date)).total_seconds()/86400", "ngày quan sát"),
        ("avg_purchase_gap_days", "customer", "mean(diff(min date mỗi InvoiceNo)), sắp theo thời gian; một đơn = NaN", "ngày/hai hóa đơn"),
        ("recency_days", "customer", f"({a['reference_date'].isoformat()} - max(date)).total_seconds()/86400", "ngày")]
    t["aggregation_formulas"] = pd.DataFrame(formula, columns=["variable", "grain", "formula", "unit"])
    t["analysis_scopes"] = pd.DataFrame([
        ("raw", n, d.InvoiceNo.nunique(), d.CustomerID.nunique(), "Toàn bộ dòng raw, không bỏ trùng"),
        ("temporary_purchase", len(p), p.InvoiceNo.nunique(), len(c), PURCHASE_RULE),
        ("customer", len(c), p.InvoiceNo.nunique(), len(c), "Tổng hợp tạm; không xuất bộ feature khách"),
        ("gap_defined", int(c.avg_purchase_gap_days.notna().sum()), None, int(c.avg_purchase_gap_days.notna().sum()),
         "Khách có >=2 hóa đơn; không điền 0 cho khách một đơn")],
        columns=["scope", "observations", "invoices", "customers", "filter"])
    t["customer_coverage"] = pd.DataFrame([
        ("raw_known_ids", d.CustomerID.nunique()), ("temporary_purchase_customers", len(c)),
        ("raw_ids_without_eligible_purchase", d.CustomerID.nunique()-len(c)),
        ("customers_one_invoice", int(c.n_invoices.eq(1).sum())),
        ("pct_customers_one_invoice", 100*c.n_invoices.eq(1).mean()),
        ("gap_defined_customers", int(c.avg_purchase_gap_days.notna().sum())),
        ("signed_value_missing_id", d.loc[d.CustomerID.isna(), "SignedLineValue"].sum()),
        ("raw_signed_value", d.SignedLineValue.sum()),
        ("temporary_purchase_value", p.SignedLineValue.sum())], columns=["metric", "value"])
    t["correlation_variable_audit"] = pd.DataFrame([
        (col, "excluded identifier", "Không có ý nghĩa như số liên tục") for col in ["InvoiceNo", "CustomerID", "StockCode"]] +
        [(col, "included numeric", "Q*P" if col == "SignedLineValue" else
          "M/F; phụ thuộc đại số" if col == "avg_order_value" else "Tổng hợp tạm" if col in CUSTOMER_COLUMNS else "Đo trực tiếp")
         for col in ["Quantity", "UnitPrice", "SignedLineValue"] + CUSTOMER_COLUMNS], columns=["variable", "decision", "note"])
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.titlesize": 12,
        "axes.labelsize": 11, "figure.facecolor": "white", "axes.spines.top": False,
        "axes.spines.right": False, "axes.grid": True, "grid.alpha": .18,
        "axes.prop_cycle": matplotlib.cycler(color=[BLUE, ORANGE, GOLD, GREY])})


def md_table(df, limit=12):
    """Markdown without the optional tabulate dependency."""
    if df.index.name is not None or not isinstance(df.index, pd.RangeIndex):
        df = df.reset_index()
    view = df.head(limit).copy()
    def fmt(x):
        if pd.isna(x): return "NA"
        if isinstance(x, (float, np.floating)): return f"{x:,.4f}".rstrip("0").rstrip(".")
        return str(x).replace("|", "/").replace("\n", " ")
    return "\n".join(["| " + " | ".join(map(str, view.columns)) + " |",
        "| " + " | ".join(["---"]*len(view.columns)) + " |"] +
        ["| " + " | ".join(fmt(x) for x in row) + " |" for row in view.itertuples(index=False, name=None)])


def table_sheet(a, name):
    """Stable sheet ID; the workbook catalog maps IDs to descriptive table names."""
    return f"T{list(a['tables']).index(name) + 1:02d}"


def _comment(scope, observation, evidence, meaning, limitation):
    return (f"**Phạm vi:** {scope}\n\n**Quan sát:** {observation}\n\n"
            f"**Bằng chứng:** {evidence}\n\n**Ý nghĩa:** {meaning}\n\n**Giới hạn / câu hỏi tiếp:** {limitation}")


def _slog(s):
    return np.sign(s)*np.log1p(np.abs(s))


def make_figure(a, key):
    """One chart per call, with a shared data-backed interpretation and inventory."""
    d, p, c, t = a["df"], a["purchase"], a["customers"], a["tables"]
    n = len(d)
    source_tables, scope, count = [], "Toàn bộ raw", n
    fig, ax = plt.subplots(figsize=(11, 5.8))
    title = key
    obs = evidence = meaning = limit = ""
    if key == "missing_values":
        m = t["missing_values"].sort_values("eda_missing_pct")
        ax.barh(m.column, m.eda_missing_pct, color=BLUE)
        for i, row in enumerate(m.itertuples()):
            ax.text(row.eda_missing_pct+.2, i, f"{row.eda_missing_count:,}", va="center")
        ax.set(xlabel="Dòng thiếu / toàn bộ dòng (%)", ylabel="Cột nguồn", xlim=(0, max(1, m.eda_missing_pct.max()*1.3)))
        title = "Giá trị thiếu theo cột"
        source_tables = ["missing_values", "customer_coverage"]
        missing = int(d.CustomerID.isna().sum())
        obs = "Thiếu mã khách làm giảm phạm vi có thể tổng hợp hành vi theo khách."
        evidence = f"CustomerID thiếu {missing:,}/{n:,} dòng ({missing/n:.2%}); giá trị có dấu của nhóm này {d.loc[d.CustomerID.isna(), 'SignedLineValue'].sum():,.2f} GBP."
        meaning = "Cần giữ thống kê giao dịch vô danh riêng với phân tích khách có mã."
        limit = "Không suy ra danh tính khách thiếu, không coi mọi dòng vô danh là một khách; giá trị có dấu chưa là doanh thu thuần."
    elif key == "document_quantity_price":
        plt.close(fig)
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        status = t["document_status"]
        axes[0].bar(status.index, status.rows, color=[ORANGE, BLUE])
        axes[0].set(xlabel="Trạng thái chứng từ", ylabel="Số dòng")
        t["document_quantity_counts"].plot.bar(stacked=False, ax=axes[1], color=[ORANGE, GREY, BLUE, GOLD], rot=0)
        axes[1].set(xlabel="Trạng thái chứng từ", ylabel="Số dòng")
        axes[1].legend(title="Dấu Quantity", fontsize=9, loc="upper right")
        price = t["price_sign_counts"]
        axes[2].bar(price.index, price.rows, color=BLUE)
        axes[2].set(xlabel="Dấu đơn giá", ylabel="Số dòng")
        for axis in axes:
            axis.set_yscale("symlog", linthresh=1)
            axis.set_ylabel("Số dòng (trục symlog, ngưỡng 1)")
        title = "Chứng từ C, dấu số lượng và đơn giá"
        source_tables = ["document_status", "document_quantity_counts", "price_sign_counts", "negative_price_samples"]
        obs = "Cần phân biệt dấu số lượng với dấu hiệu chứng từ hủy."
        evidence = f"C: {int(d.is_c.sum()):,} dòng/{d.loc[d.is_c, 'InvoiceNo'].nunique():,} chứng từ; Q âm không C: {int((d.Quantity.lt(0)&~d.is_c).sum()):,}; giá âm {int(d.UnitPrice.lt(0).sum()):,}, giá 0 {int(d.UnitPrice.eq(0).sum()):,} dòng."
        meaning = "Một quy tắc chỉ dựa vào tiền tố C có thể bỏ sót điều chỉnh khác."
        limit = "Những nhóm này chồng lấn; C chưa được ghép với đơn gốc. Không tự kết luận giá 0 là quà tặng hay lỗi."
    elif key == "raw_distributions":
        plt.close(fig)
        fig, axes = plt.subplots(3, 2, figsize=(13, 11))
        for i, (col, unit) in enumerate([("Quantity", "đơn vị hàng"), ("UnitPrice", "GBP/đơn vị"), ("SignedLineValue", "GBP có dấu")]):
            values = d[col].replace([np.inf, -np.inf], np.nan).dropna()
            axes[i,0].hist(_slog(values), bins=70, color=BLUE)
            axes[i,0].set(xlabel=f"sign(x) × ln(1+|x|), x={col} ({unit})", ylabel="Số dòng", title=f"Histogram {col}")
            axes[i,1].boxplot(values, vert=False, flierprops={"markersize": 2, "alpha": .3})
            axes[i,1].set_xscale("symlog", linthresh=1)
            axes[i,1].set(xlabel=f"{col} ({unit}), symlog ngưỡng 1", ylabel="Toàn bộ dòng hữu hạn", title=f"Boxplot {col}")
        title = "Phân phối toàn miền; giữ số âm, 0 và cực trị"
        source_tables = ["numeric_summary", "extreme_samples"]
        s = t["numeric_summary"].set_index("variable")
        obs = "Trung vị và cực trị cách xa nhau; cần xem phân vị trước khi chọn cách biến đổi."
        evidence = "; ".join(f"{col}: median={s.loc[col,'median']:,.2f}, p99={s.loc[col,'p99']:,.2f}, min={s.loc[col,'minimum']:,.2f}, max={s.loc[col,'maximum']:,.2f}" for col in s.index)
        meaning = "Độ nhạy của tổng giá trị và khoảng cách phân cụm với khách mua lớn cần được khảo sát."
        limit = "Đổi tọa độ chỉ để hiển thị, không scale dữ liệu hay cắt quan sát. Ngoại lệ IQR là cờ kiểm tra; Q×P có phụ thuộc công thức và chưa là doanh thu thuần."
    elif key in ["country_counts", "stock_code_counts"]:
        col = "Country" if key == "country_counts" else "StockCode"
        top = t[key].head(12).iloc[::-1]
        ax.barh(top[col].astype(str), top.rows, color=BLUE)
        ax.set(xlabel="Số dòng giao dịch", ylabel=col)
        title = f"Top 12 {col} theo số dòng"
        source_tables = [key, "categorical_summary"]
        first = t[key].iloc[0]
        scope = f"Toàn bộ raw; hiển thị top 12 {col}; phần còn lại {n-int(top.rows.sum()):,} dòng"
        count = int(top.rows.sum())
        obs = f"Nhóm nhiều dòng nhất là {first[col]}."
        evidence = f"Nhóm đầu có {int(first.rows):,} dòng ({first.pct_rows:.2f}% toàn raw); top 12 có {int(top.rows.sum()):,}/{n:,} dòng; {d[col].nunique():,} giá trị khác nhau."
        meaning = "Cần đánh giá mức tập trung khi đề xuất nhóm danh mục và tỷ lệ hành vi."
        limit = "Xếp hạng số dòng không đồng nghĩa số sản phẩm bán, doanh số hay số khách. Nhãn quốc gia/mã hàng chưa được chuẩn hóa nghiệp vụ."
    elif key in ["monthly_activity", "monthly_values"]:
        m = t["monthly_activity"]
        x = np.arange(len(m))
        if key == "monthly_activity":
            plt.close(fig); fig, axes = plt.subplots(2,1,figsize=(11,7), sharex=True)
            axes[0].plot(x,m.rows,marker="o", color=BLUE); axes[0].set(ylabel="Số dòng")
            axes[1].plot(x,m.invoices,marker="s",color=ORANGE); axes[1].set(ylabel="Số InvoiceNo khác nhau", xlabel="Tháng thời gian nguồn")
            axes[1].set_xticks(x, m.index, rotation=0, fontsize=9)
            title = "Số dòng và số chứng từ theo tháng"
            obs = f"Tháng có nhiều dòng nhất trong cửa sổ là {m.rows.idxmax()}."
            evidence = f"Đỉnh {m.rows.max():,} dòng; tháng cuối {m.index[-1]} có {m.rows.iloc[-1]:,} dòng và chỉ đến {d.InvoiceDate.max()}."
        else:
            ax.plot(x,m.signed_line_value,marker="o",label="Raw: tổng có dấu Q×P",color=BLUE)
            ax.plot(x,m.temporary_purchase_value,marker="s",linestyle="--",label="Tập mua tạm có ID: tổng Q×P",color=ORANGE)
            ax.set(xlabel="Tháng thời gian nguồn", ylabel="Tổng giá trị (GBP)")
            ax.set_xticks(x,m.index,fontsize=9); ax.legend(fontsize=9)
            title = "Giá trị có dấu của raw và giá trị tập mua tạm"
            obs = "Hai tổng thuộc hai phạm vi; chênh lệch phản ánh cả điều kiện lọc và dòng vô danh."
            evidence = f"Raw có dấu {d.SignedLineValue.sum():,.2f} GBP; tập mua tạm {p.SignedLineValue.sum():,.2f} GBP."
        for axis in fig.axes:
            axis.axvspan(x[-1]-.35,x[-1]+.35,color=GREY,alpha=.12)
        source_tables = ["monthly_activity", "analysis_scopes"]
        meaning = "Cửa sổ dữ liệu và mùa vụ có thể ảnh hưởng tần suất/giá trị quan sát của khách."
        limit = f"Tháng cuối thiếu ngày; không diễn giải giảm tháng cuối như suy giảm kinh doanh. Dữ liệu từ {d.InvoiceDate.min()} đến {d.InvoiceDate.max()}, chưa rõ múi giờ; các tổng chưa xác định là doanh thu thuần."
    elif key == "weekday_hour":
        plt.close(fig); fig, axes = plt.subplots(1,2,figsize=(13,5))
        axes[0].bar(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"],t["weekday_counts"].rows,color=BLUE)
        axes[0].set(xlabel="Thứ (thời gian nguồn)",ylabel="Số dòng")
        axes[1].bar(t["hour_counts"].index,t["hour_counts"].rows,color=BLUE)
        axes[1].set(xlabel="Giờ nguồn (chưa rõ múi giờ)",ylabel="Số dòng",xticks=range(0,24,2))
        title = "Tần suất theo thứ và giờ nguồn"
        source_tables = ["weekday_counts", "hour_counts"]
        hour = t["hour_counts"].rows.idxmax()
        obs = f"Nhiều dòng nhất tại giờ {hour}."
        evidence = f"Giờ {hour}: {t['hour_counts'].loc[hour,'rows']:,} dòng; thứ Bảy: {t['weekday_counts'].loc[5,'rows']:,} dòng."
        meaning = "Có thể đề xuất đặc trưng tỷ lệ giao dịch theo thời điểm sau khi hiểu quy trình ghi nhận."
        limit = "Tần suất gộp phụ thuộc số ngày được ghi nhận và lượng dòng mỗi đơn; không chứng minh giờ đặt hàng thực hay lịch mở cửa."
    elif key == "customer_distributions":
        plt.close(fig); fig, axes = plt.subplots(1,3,figsize=(15,5))
        for axis, col, unit in zip(axes,["n_invoices","monetary","avg_order_value"],["hóa đơn/khách","GBP/khách","GBP/hóa đơn"]):
            axis.hist(np.log1p(c[col]), bins=45, color=BLUE)
            axis.set(xlabel=f"ln(1+{col}) [{unit}]",ylabel="Số khách", title=col)
        title = "Phân phối hành vi khách trong tập mua tạm"
        source_tables = ["customer_summary", "customer_coverage", "aggregation_formulas"]
        scope, count = PURCHASE_RULE, len(c)
        s = t["customer_summary"].set_index("variable")
        obs = "Tần suất và giá trị quan sát khác nhau giữa khách."
        evidence = "; ".join(f"{col}: median {s.loc[col,'median']:,.2f}, p99 {s.loc[col,'p99']:,.2f}, max {s.loc[col,'maximum']:,.2f}" for col in ["n_invoices","monetary","avg_order_value"])
        meaning = "Phân vị hỗ trợ so sánh RobustScaler/log1p với các cách giữ nguyên thang ở bước sau."
        limit = "Chỉ biến đổi tọa độ hiển thị; chưa fit scaler. Giữ trùng và mã dịch vụ có thể ảnh hưởng tổng; không phải bộ đặc trưng chính thức."
    elif key == "customer_gaps":
        gaps = c.avg_purchase_gap_days.dropna()
        ax.hist(gaps, bins=45, color=BLUE)
        ax.set(xlabel="Khoảng cách trung bình giữa hai hóa đơn (ngày)",ylabel="Số khách có >=2 hóa đơn")
        title = "Khoảng cách mua; giữ thiếu cho khách một đơn"
        source_tables = ["customer_summary", "customer_coverage", "aggregation_formulas"]
        scope, count = "Khách có >=2 hóa đơn trong tập mua tạm; min timestamp mỗi hóa đơn", len(gaps)
        single = int(c.n_invoices.eq(1).sum())
        obs = "Khoảng cách chỉ xác định khi quan sát ít nhất hai hóa đơn."
        evidence = f"{single:,}/{len(c):,} khách có một hóa đơn ({single/len(c):.2%}), giữ NaN; {len(gaps):,} khách có gap, median {gaps.median():.2f} ngày."
        meaning = "Thiếu gap là thiếu do cấu trúc hành vi, không phải mặc định khoảng cách bằng 0."
        limit = "Hóa đơn khác nhau có thể cùng thời điểm (gap 0 hợp lệ); chưa xác nhận hóa đơn trùng nghiệp vụ và không quan sát trước/sau cửa sổ raw."
    elif key == "quantity_price_hexbin":
        finite = d[["Quantity","UnitPrice"]].replace([np.inf,-np.inf],np.nan).dropna()
        hb = ax.hexbin(_slog(finite.Quantity),_slog(finite.UnitPrice), gridsize=55,mincnt=1,bins="log",cmap="Blues")
        fig.colorbar(hb,ax=ax,label="Số dòng mỗi ô (màu log)")
        ax.set(xlabel="sign(Q) × ln(1+|Q|), Q [đơn vị hàng]",ylabel="sign(P) × ln(1+|P|), P [GBP/đơn vị]")
        title = "Số lượng và đơn giá trên toàn raw hữu hạn"
        source_tables = ["correlations_line_pearson","correlations_line_spearman","correlations_line_pairwise_counts","numeric_summary"]
        count = len(finite)
        obs = "Mật độ tập trung theo miền giá/số lượng; hai hệ số có thể khác nhau do đuôi và thứ hạng."
        evidence = corr_sentence(a,"line","Quantity","UnitPrice")
        meaning = "Kiểm tra dạng quan hệ trước khi cân nhắc đặc trưng số lượng/giá."
        limit = "Hexbin dùng toàn bộ cặp hữu hạn, không lấy mẫu; đổi tọa độ chỉ để nhìn. Không diễn giải tương quan là nhân quả hay cầu theo giá."
    elif key == "customer_frequency_value":
        ax.scatter(c.n_invoices,c.monetary,s=12,alpha=.25,color=BLUE,edgecolors="none")
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.set(xlabel="Số hóa đơn/khách (log)",ylabel="Giá trị tập mua tạm (GBP/khách, log)")
        title = "Số hóa đơn và tổng giá trị theo khách"
        source_tables = ["correlations_customer_pearson","correlations_customer_spearman","correlations_customer_pairwise_counts"]
        scope, count = PURCHASE_RULE, len(c)
        obs = "Các điểm trải rộng về giá trị ngay tại cùng số hóa đơn."
        evidence = corr_sentence(a,"customer","n_invoices","monetary")
        meaning = "Cần đánh giá tần suất cùng giá trị đơn, thay vì chọn một hệ số duy nhất."
        limit = "Toàn bộ khách, không mẫu/cắt; tổng giá trị phụ thuộc số đơn và giá trị đơn; tương quan không chứng minh nhân quả."
    elif key == "country_value_boxplot":
        countries = a["top_countries"]
        values = [p.loc[p.Country.eq(country),"SignedLineValue"].to_numpy() for country in countries]
        ax.boxplot(values, tick_labels=countries, flierprops={"markersize":2,"alpha":.2})
        ax.set_yscale("log"); ax.set(xlabel="Quốc gia (top 6 theo số dòng tập mua)",ylabel="Q×P trên dòng mua tạm (GBP, log)")
        title = "Giá trị dòng mua theo quốc gia"
        source_tables = ["country_value_summary","analysis_scopes"]
        count = sum(map(len,values)); scope = f"{PURCHASE_RULE} Top 6 quốc gia theo số dòng; không cắt cực trị."
        summaries = t["country_value_summary"].loc[countries]
        obs = "Phân phối giá trị trên dòng cần đọc cùng cỡ mẫu khác nhau của quốc gia."
        evidence = "; ".join(f"{country}: n={int(summaries.loc[country,'size']):,}, median={summaries.loc[country,'median']:.2f} GBP" for country in countries)
        meaning = "Đánh giá đặc trưng quốc gia cùng hành vi, tránh để nhóm có nhiều dòng chi phối kết luận."
        limit = f"Không phải giá trị mỗi khách; {len(p)-count:,} dòng ngoài top 6 không hiện. Không kiểm định khác biệt hay khẳng định quốc gia gây ra giá trị mua."
    elif key == "country_document_status":
        top = t["country_counts"].Country.head(10).tolist()
        counts = t["country_document_counts"].loc[top]
        shares = counts.div(counts.sum(axis=1),axis=0)*100
        shares.plot.barh(stacked=True,ax=ax,color=[BLUE,ORANGE])
        ax.set(xlabel="Tỷ lệ dòng trong mỗi quốc gia (%)",ylabel="Quốc gia",xlim=(0,100))
        ax.legend(title="Chứng từ",loc="lower left",bbox_to_anchor=(0,1.01),ncol=2,borderaxespad=0)
        title = "Quốc gia và trạng thái chứng từ"
        source_tables = ["country_document_counts","country_counts"]
        count = int(counts.to_numpy().sum()); scope = "Raw, top 10 quốc gia theo số dòng; tỷ lệ theo tổng dòng mỗi quốc gia"
        obs = "Thành phần chứng từ C được so sánh theo mẫu số riêng từng quốc gia."
        evidence = "; ".join(f"{country}: C {counts.loc[country,'C-prefix']:,}/{int(counts.loc[country].sum()):,} dòng ({shares.loc[country,'C-prefix']:.2f}%)" for country in top[:4])
        meaning = "Cần làm rõ cách nhận diện trả hàng trước khi thêm tỷ lệ hoàn trả theo khách/nhóm."
        limit = f"{n-count:,} dòng ngoài top 10 không hiện; tỷ lệ chứng từ C không phải tỷ lệ hàng trả và không ghép đơn mua gốc."
    elif key == "customer_multivariate":
        plt.close(fig); fig, axes = plt.subplots(1,2,figsize=(13,5.5))
        sample = c.sample(n=min(2000,len(c)),random_state=SEED)
        labels={"n_invoices":"Số hóa đơn/khách", "avg_order_value":"AOV (GBP/hóa đơn)",
                "n_stock_codes":"Số mã hàng/khách", "monetary":"Giá trị mua tạm (GBP/khách)"}
        for axis, x, y in [(axes[0],"n_invoices","avg_order_value"),(axes[1],"n_stock_codes","monetary")]:
            points = axis.scatter(sample[x],sample[y],c=sample.recency_days,s=13,alpha=.6,cmap="cividis")
            axis.set_xscale("log");axis.set_yscale("log")
            axis.set(xlabel=labels[x]+" (log)",ylabel=labels[y]+" (log)")
            fig.colorbar(points,ax=axis,label="Recency tạm (ngày)")
        title = "Đa biến: tần suất, giá trị đơn, độ đa dạng mã và recency"
        source_tables = ["correlations_customer_pearson","correlations_customer_spearman","customer_summary","aggregation_formulas"]
        count=len(sample); scope=f"Mẫu {count:,}/{len(c):,} khách của tập mua tạm, random_state={SEED}"
        obs = "Các cặp kiểm tra sự bổ sung giữa cường độ mua, giá trị mỗi đơn và số mã mua."
        evidence = corr_sentence(a,"customer","n_invoices","avg_order_value")+" "+corr_sentence(a,"customer","n_stock_codes","monetary")
        meaning = "Cân nhắc thông tin trùng lặp giữa RFM và biến hành vi trước khi chọn tập biến."
        limit = "Hệ số tính trên toàn bộ khách đủ điều kiện theo cặp; scatter chỉ mẫu. Màu recency là mô tả, không là nhãn hay dự báo; mã hàng chưa phân loại sản phẩm."
    elif key.startswith("correlation_"):
        _, level, method = key.split("_",2)
        table_name = f"correlations_{level}_{method}"
        matrix = t[table_name]
        plt.close(fig); fig, ax = plt.subplots(figsize=(11,9) if level=="customer" else (7.5,6))
        is_count = method=="pairwise_counts"
        im=ax.imshow(matrix.to_numpy(),cmap="Blues" if is_count else "RdBu_r",
                     vmin=0 if is_count else -1,vmax=None if is_count else 1)
        fig.colorbar(im,ax=ax,label="Số quan sát hợp lệ theo cặp" if is_count else "Hệ số r / rho")
        ax.set_xticks(range(len(matrix)),matrix.columns,rotation=45,ha="right")
        ax.set_yticks(range(len(matrix)),matrix.index)
        ax.set(xlabel="Biến đo / tổng hợp",ylabel="Biến đo / tổng hợp")
        for i in range(len(matrix)):
            for j in range(len(matrix)):
                v=matrix.iloc[i,j]
                label=f"{int(v):,}" if is_count else f"{v:.2f}" if pd.notna(v) else "NA"
                ax.text(j,i,label,ha="center",va="center",fontsize=9,
                    color="white" if (is_count and v>matrix.max().max()*.55) or (not is_count and abs(v)>.65) else "#222222")
        title=f"{method} — cấp {'dòng raw' if level=='line' else 'khách tạm'}"
        source_tables=[table_name,"correlation_variable_audit","aggregation_formulas"]
        count = n if level=="line" else len(c)
        scope = "Toàn bộ dòng raw hữu hạn theo cặp" if level=="line" else PURCHASE_RULE+" Toàn bộ khách, hữu hạn theo cặp."
        minimum, maximum=int(matrix.min().min()),int(matrix.max().max())
        if is_count:
            obs="Số cặp hợp lệ có thể khác nhau; không điền 0 cho dữ liệu chưa xác định."
            evidence=f"n theo cặp từ {minimum:,} đến {maximum:,}; gap thiếu ở {int(c.avg_purchase_gap_days.isna().sum()):,} khách một đơn." if level=="customer" else f"n theo cặp từ {minimum:,} đến {maximum:,}."
        else:
            obs="Pearson mô tả tuyến tính; Spearman mô tả đơn điệu theo hạng, nhạy khác nhau với cực trị."
            evidence=corr_sentence(a,level,"Quantity" if level=="line" else "n_invoices","UnitPrice" if level=="line" else "monetary")
        meaning="Chọn biến theo ý nghĩa và độ trùng thông tin, không tự loại chỉ vì hệ số cao."
        limit="Pairwise finite deletion, min_periods=3; không impute và không lấy mẫu ma trận. IDs bị loại. SignedLineValue=Q×P và AOV=M/F có phụ thuộc công thức; tương quan không chứng minh nhân quả."
    else:
        plt.close(fig); raise KeyError(key)
    fig.suptitle(title,fontsize=15,y=.99)
    footer=f"Nguồn: {RAW_NAME} | sheet {a['sheet_name']} | n hiển thị={count:,} | SHA256 {a['raw_hash'][:12]}"
    fig.text(.02,.025,footer,fontsize=9,color=GREY)
    fig.tight_layout(rect=(0,.06,1,.94))
    path=a["figure_dir"]/f"{key}.png"
    fig.savefig(path,dpi=150,facecolor="white")
    plt.close(fig)
    comment=_comment(scope,obs,evidence,meaning,limit)
    a["comments"][key]=comment
    record=dict(figure_id=key,title=title,path=path.relative_to(a["project"]).as_posix(),
        population_scope=scope,observations_displayed=count,
        source_tables=";".join(source_tables),raw_file=f"data/raw/{RAW_NAME}",
        sheet=a["sheet_name"],raw_sha256=a["raw_hash"],figure_sha256=sha(path),
        seed=SEED if key=="customer_multivariate" else None,
        note="Các bộ lọc/biến đổi chỉ phục vụ EDA; xem nhận xét 5 ý trong notebook/báo cáo")
    a["figures"]=[r for r in a["figures"] if r["figure_id"]!=key]+[record]
    return path,comment


def corr_sentence(a, level, x, y):
    t=a["tables"]
    pearson=t[f"correlations_{level}_pearson"].loc[x,y]
    spearman=t[f"correlations_{level}_spearman"].loc[x,y]
    count=int(t[f"correlations_{level}_pairwise_counts"].loc[x,y])
    return f"{x}–{y}: n={count:,}, Pearson={pearson:.4f}, Spearman={spearman:.4f}."


FIGURE_SECTIONS = [
    ("2. Chất lượng dữ liệu", ["missing_values","document_quantity_price"]),
    ("4. Phân tích đơn biến", ["raw_distributions","country_counts","stock_code_counts"]),
    ("5. Thời gian và khách hàng", ["monthly_activity","monthly_values","weekday_hour","customer_distributions","customer_gaps"]),
    ("6. Hai biến và đa biến", ["quantity_price_hexbin","customer_frequency_value","country_value_boxplot","country_document_status","customer_multivariate"]),
    ("7. Tương quan", [f"correlation_{level}_{method}" for level in ["line","customer"]
                           for method in ["pearson","spearman","pairwise_counts"]])]


def validate_analysis(a):
    d,p,c,t=a["df"],a["purchase"],a["customers"],a["tables"]
    np.testing.assert_allclose(d.SignedLineValue,d.Quantity*d.UnitPrice,equal_nan=True)
    assert len(c)==p.CustomerID.nunique()
    assert c.index.is_unique and c.n_invoices.ge(1).all()
    assert c.loc[c.n_invoices.eq(1),"avg_purchase_gap_days"].isna().all()
    assert c.loc[c.n_invoices.gt(1),"avg_purchase_gap_days"].notna().all()
    np.testing.assert_allclose(c.monetary.sum(),p.SignedLineValue.sum(),rtol=1e-12)
    np.testing.assert_allclose(c.avg_order_value*c.n_invoices,c.monetary,rtol=1e-12)
    assert int(t["monthly_activity"].rows.sum())==len(d)
    np.testing.assert_allclose(t["monthly_activity"].signed_line_value.sum(),d.SignedLineValue.sum(),rtol=1e-12)
    assert int(t["country_document_counts"].to_numpy().sum())==len(d)
    # Independently calculate selected coefficients and pair sample sizes.
    from scipy.stats import pearsonr, spearmanr
    for level, frame, x, y in [("line",d,"Quantity","UnitPrice"),
                               ("customer",c,"n_invoices","monetary"),
                               ("customer",c,"n_invoices","avg_purchase_gap_days")]:
        pair=frame[[x,y]].replace([np.inf,-np.inf],np.nan).dropna()
        assert len(pair)==t[f"correlations_{level}_pairwise_counts"].loc[x,y]
        np.testing.assert_allclose(pearsonr(pair[x],pair[y]).statistic,t[f"correlations_{level}_pearson"].loc[x,y],atol=1e-12)
        np.testing.assert_allclose(spearmanr(pair[x],pair[y]).statistic,t[f"correlations_{level}_spearman"].loc[x,y],atol=1e-12)
    assert a["protected_before"]==protected_hashes(a["project"])
    assert sha(a["raw_path"])==a["raw_hash"]
    expected={key for _, keys in FIGURE_SECTIONS for key in keys}
    assert {r["figure_id"] for r in a["figures"]}==expected
    return {"raw_unchanged": True,"protected_files_unchanged": True,
            "aggregation_reconciled": True,"correlations_checked_against_scipy": True,
            "monthly_and_categorical_totals_reconciled": True,
            "figures_expected": len(expected),"figures_created":len(a["figures"])}


def write_report(a):
    d,c,t=a["df"],a["customers"],a["tables"]
    parts=["# EDA raw dự án — dữ liệu thiếu mã khách và phân phối cần được nhóm xem xét\n",
        "## Kết quả chính\n",
        f"Raw hiện tại có **{len(d):,} dòng**, {len(a['raw'].columns)} cột, {d.InvoiceNo.nunique():,} chứng từ và {d.CustomerID.nunique():,} mã khách; thời gian {d.InvoiceDate.min()}–{d.InvoiceDate.max()}.\n",
        f"CustomerID thiếu ở **{d.CustomerID.isna().sum():,} dòng ({d.CustomerID.isna().mean():.2%})**. Có {a['raw'].duplicated().sum():,} dòng trùng dư trên 8 cột; đây là vấn đề cần xác minh nghiệp vụ, chưa tự bỏ trùng.\n",
        f"Phạm vi mua tạm có {len(a['purchase']):,} dòng / {len(c):,} khách. **{c.n_invoices.eq(1).mean():.2%}** khách chỉ có một hóa đơn và chưa xác định khoảng cách mua. Tháng cuối kết thúc ngày {d.InvoiceDate.max().date()}, nên không so trực tiếp với tháng đầy đủ.\n",
        "## 0. Bối cảnh, mục tiêu và phạm vi\n",
        "Bài toán phân cụm khách hàng không giám sát cần hiểu chất lượng và hành vi trước khi chốt xử lý. Một dòng raw là một dòng hàng/chứng từ; InvoiceNo nhóm nhiều dòng, CustomerID có thể nhóm nhiều chứng từ. Mã chứng từ không phải mã giao dịch duy nhất trên mỗi dòng. Không dùng mã định danh như biến số liên tục.\n",
        "Câu hỏi: dữ liệu thiếu/trùng/bất thường ở đâu; giao dịch thay đổi theo thời gian, giá, lượng ra sao; hành vi giữa khách khác nhau thế nào; quan hệ nào có ích và phương án xử lý nào cần nhóm so sánh?\n",
        "Mọi tổng hợp chỉ khảo sát trong bộ nhớ. Không tạo dữ liệu sạch/feature chính thức, không fit encoding/scaler hay mô hình.\n",
        "## 1. Nguồn và kiểm kê\n",
        f"Nguồn mô tả: [UCI Online Retail]({SOURCE_URL}), đối chiếu ngày 05/11/2026. Nguồn raw duy nhất của dự án là `data/raw/Online Retail.xlsx`; các số liệu bên dưới được tính trực tiếp từ file này. Sự khớp schema/kích thước không chứng minh đầy đủ chuỗi tải file. Đơn giá GBP theo mô tả UCI; workbook không tự cung cấp tiền tệ hay múi giờ.\n",
        md_table(t["raw_inventory"],30),"\n### Từng sheet\n",md_table(t["workbook_sheets"]),
        "\n### Từ điển và đối chiếu cột\n",md_table(t["data_dictionary"]),md_table(t["column_mapping"]),
        "\n### Đầu/cuối workbook\n",md_table(t["raw_samples"]),
        "\n### Phạm vi và công thức khảo sát\n",PURCHASE_RULE,md_table(t["analysis_scopes"]),
        md_table(t["aggregation_formulas"],20),
        "\nNgày tham chiếu recency là nửa đêm kế tiếp ngày lớn nhất của raw; không dùng ngày chạy. Mỗi hóa đơn dùng min timestamp cho gap. Một khách có nhiều quốc gia được giữ nguyên theo dòng; chưa gán quốc gia chính thức cho khách.\n"]
    for section, keys in FIGURE_SECTIONS:
        parts.extend([f"\n## {section}\n"])
        if section.startswith("2."):
            parts += [md_table(t["quality_issues"],30),"\nCác nhóm chồng lấn; dòng union là hợp, không phải tổng. Số chứng từ và số khách trong mỗi nhóm cũng không cộng được.\n",
                      md_table(t["duplicate_criteria"]),md_table(t["identifier_conflicts"]),
                      "\nCác bảng duplicate_samples, negative_price_samples, invoice_conflict_samples và stock_description_audit nằm trong [workbook kết quả](../experiments/eda_raw_moi/ket_qua_eda.xlsx). Nhiều mô tả hoặc nhiều nước không tự chứng minh lỗi.\n",
                      "\nID và Country chỉ strip khoảng trắng trong bản sao; Description giữ nguyên chuỗi để kiểm tra quan hệ mã–mô tả. Các loại và ánh xạ cột được ghi trong data_dictionary/column_mapping.\n"]
        if section.startswith("5."):
            parts += [md_table(t["monthly_activity"],20),md_table(t["customer_summary"],20),md_table(t["customer_coverage"],20)]
        for key in keys:
            record=next(r for r in a["figures"] if r["figure_id"]==key)
            parts += [f"\n### {record['title']}\n",
                f"![{record['title']}](../{record['path']})\n",a["comments"][key],
                "\n\nBảng bằng chứng trong [workbook](../experiments/eda_raw_moi/ket_qua_eda.xlsx): "+", ".join(f"{name} ({table_sheet(a, name)})" for name in record["source_tables"].split(";"))+".\n"]
        if section.startswith("2."):
            parts += ["\n## 3. Thống kê mô tả\n",md_table(t["numeric_summary"]),md_table(t["categorical_summary"]),
                      "\nBảng số có count, min/max, mean/median, std mẫu, q1/q3, IQR, p95/p99 và skew. Không tính trung bình mã định danh. Tần suất đầy đủ và nhóm hiếm trong các bảng country/stock/description_counts và categorical_summary.\n"]
    parts += ["\n## 8. Đề xuất và quyết định chờ nhóm\n",
        "Xem [đề xuất sau EDA](de_xuat_sau_eda.md): so sánh nhiều lựa chọn về clean, encoding, scaling và feature. Đặc trưng thủ công, RFM và kết hợp đều là đề xuất chưa chốt.\n",
        "Cần thống nhất: xử lý khách thiếu mã; định nghĩa trùng; nhận diện/ghép hủy-trả; giá 0/âm; mã dịch vụ; ngoại lệ và khách mua sỉ; cửa sổ lịch sử; công thức giá trị/gap; dùng danh mục hay chỉ hành vi; cách scaling và tập biến.\n",
        "## 9. Tái lập và kiểm tra\n",
        "Mở [notebook](../notebooks/01_eda/eda.ipynb), Restart Kernel → Run All. [README EDA](../notebooks/01_eda/README.md) có lệnh chạy. [Kiểm kê nguồn](kiem_ke_eda.md) mô tả raw duy nhất và các hạn chế cần lưu ý.\n",
        f"SHA-256 raw: `{a['raw_hash']}`. [Workbook kết quả](../experiments/eda_raw_moi/ket_qua_eda.xlsx) chứa metadata, danh mục hình và bảng thống kê. Notebook và báo cáo dùng cùng bảng/nhận xét tạo trong một lần chạy.\n",
        "Các kiểm tra tự động đối chiếu tổng dòng theo tháng/quốc gia, tổng giá trị theo khách, AOV, gap một đơn, cặp tương quan với scipy và checksum vùng bảo vệ; kết quả nằm trong sheet Metadata của workbook.\n",
        "Giới hạn: một nhà bán lẻ và cửa sổ lịch sử hữu hạn; không đại diện toàn thị trường, không biết lịch sử ngoài cửa sổ, chưa ghép chứng từ trả với mua, chưa có nhãn mục tiêu. Không suy ra quan hệ nhân quả hay dự báo từ EDA này.\n"]
    path=a["project"]/"reports/bao_cao_eda.md"
    path.write_text("\n\n".join(parts),encoding="utf-8")
    return path


def export_results(a):
    checks=validate_analysis(a)
    workbook=a["output"]/"ket_qua_eda.xlsx"
    legacy_audit=a["output"]/"deleted_legacy_eda.csv"
    if workbook.exists():
        with pd.ExcelFile(workbook, engine="openpyxl") as existing:
            deleted = pd.read_excel(existing, sheet_name="Da_xoa_EDA_cu") if "Da_xoa_EDA_cu" in existing.sheet_names else pd.DataFrame()
    elif legacy_audit.exists():
        deleted=pd.read_csv(legacy_audit, encoding="utf-8-sig")
    else:
        deleted=pd.DataFrame(columns=["path", "sha256", "bytes"])
    inventory=[dict(table_id=name,sheet=table_sheet(a,name),rows=len(table),columns=len(table.columns),
                    includes_index=table.index.name is not None or not isinstance(table.index,pd.RangeIndex))
               for name,table in a["tables"].items()]
    report=write_report(a)
    module_dir=Path(__file__).parent
    code_paths=[module_dir/"eda_raw_analysis.py",module_dir/"build_eda_raw_notebook.py"]
    notebook=json.loads((module_dir/"eda.ipynb").read_text(encoding="utf-8"))
    cell_sources=[{"cell_type":cell["cell_type"],"source":cell["source"]} for cell in notebook["cells"]]
    metadata=dict(run_started=a["run_started"],run_completed=datetime.now(timezone(timedelta(hours=7))).isoformat(),
        client_timezone="Asia/Bangkok",source_timestamp_timezone="unspecified; no conversion",
        raw_file=a["raw_path"].relative_to(a["project"]).as_posix(),raw_sha256=a["raw_hash"],
        raw_size_bytes=a["raw_path"].stat().st_size,sheets=a["tables"]["workbook_sheets"].to_dict("records"),
        git_head=a["git_head"],git_branch=a["git_branch"],git_status_at_run=a["git_status_at_run"],
        python=platform.python_version(),versions={p:importlib.metadata.version(p) for p in
            ["pandas","numpy","matplotlib","openpyxl","scipy","nbformat","nbclient"]},
        code_sha256={p.name:sha(p) for p in code_paths},
        notebook_source_sha256=hashlib.sha256(json.dumps(cell_sources,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
        source_url=SOURCE_URL,source_description_checked_date="2026-11-05",
        purchase_scope=PURCHASE_RULE,reference_date=a["reference_date"].isoformat(),
        sampling={"customer_multivariate":{"n":min(2000,len(a["customers"])),"seed":SEED},
                  "correlation_matrices":"all finite pairs; no sampling or imputation"},
        figure_count=len(a["figures"]),table_count=len(inventory),checks=checks,
        protected_before=a["protected_before"],protected_after=protected_hashes(a["project"]),
        protected_unchanged=True,report_sha256=sha(report),
        official_cleaning_encoding_scaling_features_models_applied=False)
    # One workbook retains all inspectable tables, run metadata, figures, and deletion audit.
    # The original workbook is read-only; this is a separate EDA results artifact.
    with pd.ExcelWriter(workbook, engine="openpyxl", datetime_format="yyyy-mm-dd hh:mm:ss") as writer:
        pd.DataFrame(inventory).to_excel(writer, sheet_name="Danh_muc_bang", index=False)
        pd.DataFrame(a["figures"]).to_excel(writer, sheet_name="Danh_muc_hinh", index=False)
        pd.DataFrame([(k,json.dumps(v,ensure_ascii=False,default=str)) for k,v in metadata.items()],
                     columns=["item","value_json"]).to_excel(writer, sheet_name="Metadata", index=False)
        deleted.to_excel(writer, sheet_name="Da_xoa_EDA_cu", index=False)
        for item in inventory:
            a["tables"][item["table_id"]].to_excel(writer, sheet_name=item["sheet"], index=item["includes_index"])
        for sheet in writer.book.worksheets:
            sheet.freeze_panes="A2"
            # Preserve literal text from raw, including any leading '=' character.
            for row in sheet.iter_rows():
                for cell in row:
                    if cell.data_type == "f":
                        cell.data_type = "s"
    return metadata
