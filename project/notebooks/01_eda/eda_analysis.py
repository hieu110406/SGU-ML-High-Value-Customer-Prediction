"""Computations for the single EDA notebook; no writes to raw/processed/src.

Current clean_data is evaluated as an experimental policy, not a business approval.
All customer statistics use the same known-ID purchase window. No model is fit.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

WINDOW_START = "2009-12-01"
REFERENCE_DATE = "2011-12-10"
SOURCE_COLUMNS = ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate",
                  "Price", "Customer ID", "Country"]
CORRELATION_COLUMNS = ["Recency", "Frequency", "Monetary", "avg_order_value",
                       "avg_purchase_gap_days", "observed_tenure_days",
                       "n_stock_codes_candidate", "total_quantity_candidate",
                       "avg_quantity_per_order_candidate"]
PAIRS = [("Frequency", "Monetary"), ("Recency", "Monetary"),
         ("Frequency", "avg_order_value"), ("n_stock_codes_candidate", "Monetary"),
         ("total_quantity_candidate", "Monetary"),
         ("avg_quantity_per_order_candidate", "avg_order_value")]
EXPORT_TABLES = (
    "customer_behavior", "rfm", "rfm_transformed", "correlation_spearman", "correlation_pearson",
    "correlation_pairwise_counts", "correlation_column_audit", "preprocessing_trace", "scaling_parameters",
)
MATRIX_TABLES = {"correlation_spearman", "correlation_pearson", "correlation_pairwise_counts"}


def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identifier(series):
    return (series.astype("string").str.strip()
            .str.replace(r"(?<=\d)\.0$", "", regex=True).replace("", pd.NA))


def protected_hashes(project):
    paths = [*project.glob("data/raw/*"), *project.glob("data/processed/*"),
             *project.glob("src/*.py"),
             *project.glob("experiments/form2_manual_behavior_raw_survey/*"),
             *project.glob("experiments/eda_rebuild/tables/*")]
    return {p.relative_to(project).as_posix(): checksum(p) for p in paths if p.is_file()}


def descriptive(frame, columns, population):
    records = []
    for column in columns:
        values = frame[column]
        if not pd.api.types.is_numeric_dtype(values):
            raise TypeError(f"Not numeric: {column}")
        finite = values[np.isfinite(values)]
        quantiles = finite.quantile([.25, .5, .75, .95, .99])
        q1, median, q3, p95, p99 = quantiles
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outside = int((finite.lt(lower) | finite.gt(upper)).sum())
        records.append(dict(population=population, variable=column, count=len(finite),
                            missing=int(values.isna().sum()), nonfinite=int((~np.isfinite(values) & values.notna()).sum()),
                            mean=finite.mean(), median=median, minimum=finite.min(), maximum=finite.max(),
                            q1=q1, q3=q3, iqr=iqr, p95=p95, p99=p99, skewness=finite.skew(),
                            iqr_lower=lower, iqr_upper=upper, outside_iqr=outside,
                            outside_iqr_pct=100 * outside / len(finite) if len(finite) else np.nan))
    return pd.DataFrame(records)


def correlation_tables(frame, requested):
    """Pairwise finite observations; no imputation and no conversion of IDs to numbers."""
    audit, usable = [], []
    for column in requested:
        if column not in frame:
            audit.append(dict(variable=column, status="absent", valid=0, missing=len(frame), unique=0))
            continue
        values = frame[column]
        if not pd.api.types.is_numeric_dtype(values):
            audit.append(dict(variable=column, status="non_numeric", valid=int(values.notna().sum()),
                              missing=int(values.isna().sum()), unique=values.nunique()))
            continue
        finite = values.where(np.isfinite(values))
        unique = finite.nunique()
        status = "all_missing" if not finite.notna().any() else "constant" if unique < 2 else "included"
        audit.append(dict(variable=column, status=status, valid=int(finite.notna().sum()),
                          missing=int(finite.isna().sum()), unique=unique))
        if status == "included":
            usable.append(column)
    numeric = frame[usable].replace([np.inf, -np.inf], np.nan)
    valid = numeric.notna().astype("int64")  # avoid boolean/int8 matrix multiplication overflow
    counts = valid.T @ valid
    return (numeric.corr(method="spearman", min_periods=3),
            numeric.corr(method="pearson", min_periods=3), counts, pd.DataFrame(audit))


def _current_policy_trace(source, preprocessing):
    """Independent stage audit checked against unmodified clean_data and its log."""
    rows = []

    def record(name, frame, reason):
        customer = frame["Customer ID"]
        rows.append(dict(step=name, rows=len(frame), invoices=frame.Invoice.nunique(),
                         known_customers=customer[customer.ne("Guest")].nunique(),
                         anonymous_rows=int((customer.isna() | customer.eq("Guest")).sum()), reason=reason))

    work = source.copy()
    record("Dữ liệu thô", work, "Gộp đúng 8 cột nguồn; không đưa Sheet vào khóa trùng")
    work["Description"] = work.Description.fillna("Unknown Product").astype(str).str.strip().str.upper()
    for column in ["Invoice", "StockCode"]:
        work[column] = work[column].astype(str).str.strip().str.upper()
    work["Country"] = work.Country.astype(str).str.strip().replace({"EIRE": "Ireland"})
    record("Chuẩn hóa văn bản", work, "Description thiếu được điền; EIRE → Ireland")
    work = work.drop_duplicates()
    record("Sau bỏ trùng đã chuẩn hóa", work, "Quy tắc mã hiện tại; không khẳng định mọi trùng là lỗi")
    work = work[~work.Invoice.str.startswith("C")]
    record("Sau bỏ chứng từ C", work, "Không ghép C với đơn gốc trong chính sách hiện tại")
    work = work[work.Quantity.gt(0) & work.Price.gt(0)]
    record("Sau giữ Q/P dương", work, "Quantity > 0 và Price > 0")
    work = work[~work.StockCode.isin(preprocessing.SPECIAL_CODES)]
    record("Sau bỏ mã đặc biệt", work, "Danh sách SPECIAL_CODES hiện tại; chưa phải danh mục sản phẩm")
    work = work[~preprocessing.outlier_mask(work)]
    record("Sau lọc ngoại lệ của pipeline", work, "IQR × 3 trên log1p Quantity/Price; bao gồm cả dòng thiếu ID khi fit ngưỡng")
    work = work.copy()
    work["Customer ID"] = work["Customer ID"].map(lambda v: "Guest" if pd.isna(v) else str(int(v)))
    record("Đầu ra clean_data (có Guest)", work, "Guest là nhãn dòng vô danh, không phải một khách thật")
    work["Revenue"] = (work.Quantity * work.Price).round(2)
    work["IsGuest"] = work["Customer ID"].eq("Guest")
    work = work.sort_values(["InvoiceDate", "Invoice"]).reset_index(drop=True)
    clean, log = preprocessing.clean_data(source)
    pd.testing.assert_frame_equal(work, clean)
    assert log.iloc[:, 1].tolist() == [r["rows"] for r in rows]
    purchase = clean.loc[~clean.IsGuest & clean.InvoiceDate.ge(WINDOW_START)
                         & clean.InvoiceDate.lt(REFERENCE_DATE)].copy()
    record("Tập khảo sát khách có ID", purchase, "Lựa chọn EDA sau pipeline; không sửa quy tắc Guest của Thuận")
    trace = pd.DataFrame(rows)
    trace["removed_rows"] = -trace.rows.diff().fillna(0).astype(int)
    return clean, purchase, trace, log


def load_analysis(project):
    project = Path(project).resolve()
    sys.path.insert(0, str(project))
    from src import preprocessing
    from src.features import aggregate_purchase_orders, build_customer_behavior_features

    before = protected_hashes(project)
    print("Đọc hai sheet từ workbook gốc...", flush=True)
    sheets = pd.read_excel(project / "data/raw/online_retail_II.xlsx", sheet_name=None, engine="openpyxl")
    source = pd.concat(sheets.values(), ignore_index=True)
    assert source.columns.tolist() == SOURCE_COLUMNS
    assert source.InvoiceDate.notna().all()
    raw = source.copy()
    for column in ["Invoice", "StockCode", "Customer ID"]:
        raw[column] = identifier(raw[column])
    raw["LineValue"] = raw.Quantity * raw.Price
    raw["invoice_type"] = np.where(raw.Invoice.str.upper().str.startswith("C"), "C", "Non-C")
    raw["country_group"] = np.where(raw.Country.eq("United Kingdom"), "UK", "Other-country")
    code = raw.StockCode.str.upper()
    raw["code_group"] = np.select([code.isin(preprocessing.SPECIAL_CODES),
                                   code.str.fullmatch(r"\d{5}[A-Z]*", na=False)],
                                  ["Listed special", "Product-like pattern"], default="Other code")
    t = {}
    t["sheet_profile"] = pd.DataFrame([dict(sheet=name, rows=len(s), columns=len(s.columns),
                                           date_min=s.InvoiceDate.min(), date_max=s.InvoiceDate.max(),
                                           invoices=identifier(s.Invoice).nunique(), customers=s["Customer ID"].nunique(),
                                           duplicate_excess=int(s.duplicated(SOURCE_COLUMNS).sum()))
                                      for name, s in sheets.items()])
    t["schema"] = pd.DataFrame([dict(sheet=name, column=c, dtype=str(s[c].dtype),
                                    non_null=int(s[c].notna().sum())) for name, s in sheets.items() for c in SOURCE_COLUMNS])
    t["samples"] = pd.concat([s.head(2).assign(sheet=name) for name, s in sheets.items()], ignore_index=True)
    t["missing"] = pd.DataFrame(dict(column=SOURCE_COLUMNS, missing_rows=source.isna().sum().values,
                                    missing_pct=100 * source.isna().mean().values, denominator_rows=len(source)))
    t["missing_by_sheet"] = pd.DataFrame([dict(sheet=name, column=c, missing_rows=int(s[c].isna().sum()),
                                             denominator_rows=len(s), missing_pct=100 * s[c].isna().mean())
                                        for name, s in sheets.items() for c in ["Customer ID", "Description"]])
    a, b = list(sheets.values())
    shared = a.drop_duplicates().merge(b.drop_duplicates(), on=SOURCE_COLUMNS, how="inner", validate="one_to_one")
    matching_second = b.merge(a.drop_duplicates(), on=SOURCE_COLUMNS, how="inner", validate="many_to_one")
    t["duplicates"] = pd.DataFrame([
        ("Dòng trùng dư toàn bộ (keep=first)", int(source.duplicated().sum()), len(source)),
        ("Mọi dòng thuộc nhóm trùng (keep=False)", int(source.duplicated(keep=False).sum()), len(source)),
        ("Tổng dòng trùng dư trong từng sheet", sum(int(s.duplicated().sum()) for s in sheets.values()), len(source)),
        ("Mẫu nội dung 8 cột chung giữa hai sheet", len(shared), len(source)),
        ("Dòng sheet sau khớp mẫu sheet trước", len(matching_second), len(b))], columns=["definition", "count", "denominator_rows"])
    assert t["duplicates"].iloc[0]["count"] == t["duplicates"].iloc[2]["count"] + len(shared)
    overlap_start = max(s.InvoiceDate.min() for s in sheets.values())
    overlap_end = min(s.InvoiceDate.max() for s in sheets.values())
    t["overlap"] = pd.DataFrame([dict(start=overlap_start, end=overlap_end,
                                      rows=int(raw.InvoiceDate.between(overlap_start, overlap_end).sum()))])
    c_mask = raw.invoice_type.eq("C")
    masks = {"Invoice có tiền tố C": c_mask, "Quantity < 0": raw.Quantity.lt(0),
             "Quantity = 0": raw.Quantity.eq(0), "Price < 0": raw.Price.lt(0),
             "Price = 0": raw.Price.eq(0), "Quantity âm không C": raw.Quantity.lt(0) & ~c_mask,
             "C có Quantity >= 0": c_mask & raw.Quantity.ge(0)}
    t["anomalies"] = pd.DataFrame([dict(condition=k, rows=int(m.sum()), denominator_rows=len(raw),
                                       pct=100*m.mean(), invoices=raw.loc[m, "Invoice"].nunique()) for k,m in masks.items()])
    t["stock_audit"] = raw.groupby("StockCode", dropna=False).agg(
        rows=("Invoice", "size"), example_description=("Description", lambda v: " | ".join(v.dropna().astype(str).unique()[:2])))
    t["stock_audit"]["listed_special"] = t["stock_audit"].index.str.upper().isin(preprocessing.SPECIAL_CODES)
    t["stock_audit"]["pattern_candidate"] = t["stock_audit"].index.str.fullmatch(r"\d{5}[A-Za-z]*")
    checks = [("Invoice có nhiều Customer ID", raw.groupby("Invoice")["Customer ID"].nunique()),
              ("Invoice có nhiều thời điểm", raw.groupby("Invoice").InvoiceDate.nunique()),
              ("Khách có nhiều Country", raw.groupby("Customer ID").Country.nunique()),
              ("StockCode có nhiều Description", raw.groupby("StockCode").Description.nunique())]
    t["consistency"] = pd.DataFrame([dict(check=name, affected=int(v.gt(1).sum()), denominator=len(v),
                                          pct=100*v.gt(1).mean()) for name,v in checks])
    print("Chạy clean_data hiện tại và kiểm tra từng bước trong bộ nhớ...", flush=True)
    clean, purchase, t["preprocessing_trace"], t["pipeline_log"] = _current_policy_trace(source, preprocessing)
    clean["LineValue"] = clean.Quantity * clean.Price
    purchase["LineValue"] = purchase.Quantity * purchase.Price
    t["transaction_profile"] = pd.concat([descriptive(raw, ["Quantity", "Price", "LineValue"], "raw_including_C"),
                                           descriptive(clean, ["Quantity", "Price", "LineValue"], "current_pipeline_including_Guest")], ignore_index=True)
    t["invoice_types"] = raw.groupby("invoice_type").agg(rows=("Invoice", "size"), invoices=("Invoice", "nunique"))
    t["code_groups"] = raw.groupby("code_group").size().to_frame("rows")
    raw["month"] = raw.InvoiceDate.dt.to_period("M").astype(str)
    t["monthly"] = raw.groupby("month").agg(rows=("Invoice", "size"), invoices=("Invoice", "nunique"), signed_value_gbp=("LineValue", "sum"))
    t["monthly"]["current_value_gbp"] = clean.groupby(clean.InvoiceDate.dt.to_period("M").astype(str)).LineValue.sum()
    t["monthly"]["partial_boundary"] = False
    first, last = raw.InvoiceDate.min(), raw.InvoiceDate.max()
    # Calendar coverage flags, not a claim that every calendar day must contain purchases.
    t["monthly"].loc[str(first.to_period("M")), "partial_boundary"] = first.day != 1
    t["monthly"].loc[str(last.to_period("M")), "partial_boundary"] = last.day != last.days_in_month
    t["weekday"] = raw.groupby(raw.InvoiceDate.dt.dayofweek).size().reindex(range(7), fill_value=0).to_frame("rows")
    t["hour"] = raw.groupby(raw.InvoiceDate.dt.hour).size().reindex(range(24), fill_value=0).to_frame("rows")
    t["weekday_hour"] = pd.crosstab(raw.InvoiceDate.dt.dayofweek, raw.InvoiceDate.dt.hour).reindex(index=range(7), columns=range(24), fill_value=0)
    t["countries"] = raw.groupby("Country", dropna=False).agg(rows=("Invoice", "size"), invoices=("Invoice", "nunique"),
                                                               customers=("Customer ID", "nunique"), signed_value_gbp=("LineValue", "sum")).sort_values("rows", ascending=False)
    behavior = build_customer_behavior_features(purchase, window_start=WINDOW_START, reference_date=REFERENCE_DATE,
                                                invoice_time_policy="earliest", include_optional=True)
    orders = aggregate_purchase_orders(purchase, window_start=WINDOW_START, reference_date=REFERENCE_DATE, invoice_time_policy="earliest")
    totals = purchase.groupby("Customer ID").agg(total_purchase_value=("LineValue", "sum"),
                                                 total_quantity_candidate=("Quantity", "sum"), n_stock_codes_candidate=("StockCode", "nunique"))
    behavior = behavior.merge(totals, on="Customer ID", validate="one_to_one")
    behavior["avg_quantity_per_order_candidate"] = behavior.total_quantity_candidate / behavior.n_orders
    # One-country customers retain that label; multi-country customers get a separate group.
    geography = purchase.groupby("Customer ID").agg(n_countries=("Country", "nunique"), country=("Country", "first"))
    geography.loc[geography.n_countries.gt(1), "country"] = "Multi-country"
    behavior = behavior.merge(geography, on="Customer ID", validate="one_to_one")
    behavior["country_group"] = np.select([behavior.country.eq("United Kingdom"), behavior.country.eq("Multi-country")],
                                           ["UK", "Multi-country"], default="Other-country")
    behavior["order_group"] = np.where(behavior.n_orders.eq(1), "One invoice", "Multiple invoices")
    behavior["Recency"] = (pd.Timestamp(REFERENCE_DATE)-pd.to_datetime(behavior.last_purchase_time)).dt.total_seconds()/86400
    behavior["Frequency"] = behavior.n_orders
    behavior["Monetary"] = behavior.total_purchase_value
    t["customer_behavior"] = behavior
    t["rfm"] = behavior[["Customer ID", "Recency", "Frequency", "Monetary"]].copy()
    t["customer_profile"] = descriptive(behavior, CORRELATION_COLUMNS, "known_ID_current_policy_experimental")
    t["feature_missing"] = behavior[["avg_purchase_gap_days", "n_distinct_products", "avg_quantity_per_order", "total_quantity", "return_rate"]].isna().sum().to_frame("missing_customers")
    t["customer_summary"] = pd.DataFrame([dict(customers=len(behavior), invoices=len(orders), rows=len(purchase),
                                               single_invoice_customers=int(behavior.n_orders.eq(1).sum()),
                                               multiple_timestamp_orders=int(orders.n_timestamps.gt(1).sum()),
                                               multi_country_customers=int(behavior.n_countries.gt(1).sum()),
                                               exact_value_gbp=purchase.LineValue.sum(),
                                               rounded_value_gbp=purchase.Revenue.sum())])
    t["numeric_by_country"] = behavior.groupby("country_group").agg(n=("Customer ID", "size"),
        median_Monetary=("Monetary", "median"), median_Frequency=("Frequency", "median"), median_AOV=("avg_order_value", "median"))
    t["numeric_by_order_group"] = behavior.groupby("order_group").agg(n=("Customer ID", "size"),
        median_Monetary=("Monetary", "median"), median_AOV=("avg_order_value", "median"))
    t["country_invoice_counts"] = pd.crosstab(raw.country_group, raw.invoice_type)
    t["country_invoice_row_pct"] = t["country_invoice_counts"].div(t["country_invoice_counts"].sum(axis=1), axis=0)*100
    t["country_order_counts"] = pd.crosstab(behavior.country_group, behavior.order_group)
    t["country_order_row_pct"] = t["country_order_counts"].div(t["country_order_counts"].sum(axis=1), axis=0)*100
    requested = CORRELATION_COLUMNS + ["n_distinct_products", "avg_quantity_per_order", "total_quantity", "return_rate", "Customer ID"]
    (t["correlation_spearman"], t["correlation_pearson"], t["correlation_pairwise_counts"],
     t["correlation_column_audit"]) = correlation_tables(behavior, requested)
    t["bivariate_numeric"] = pd.DataFrame([dict(x=x,y=y, spearman=t["correlation_spearman"].loc[x,y],
                                               pearson=t["correlation_pearson"].loc[x,y],
                                               n=t["correlation_pairwise_counts"].loc[x,y]) for x,y in PAIRS])
    logged = np.log1p(t["rfm"][["Recency", "Frequency", "Monetary"]])
    scaler = StandardScaler()
    scaled = scaler.fit_transform(logged)
    t["rfm_transformed"] = t["rfm"][["Customer ID"]].copy()
    for i,c in enumerate(logged.columns):
        t["rfm_transformed"]["log1p_"+c] = logged[c]
        t["rfm_transformed"]["z_log1p_"+c] = scaled[:,i]
    t["scaling_parameters"] = pd.DataFrame(dict(feature=logged.columns, mean_log1p=scaler.mean_,
        variance_log1p=scaler.var_, scale_log1p=scaler.scale_, fit_customers=len(behavior)))
    t["extreme_rows"] = pd.concat([raw.nsmallest(2,c).assign(variable=c, direction="smallest") for c in ["Quantity", "Price", "LineValue"]]+
                                  [raw.nlargest(2,c).assign(variable=c, direction="largest") for c in ["Quantity", "Price", "LineValue"]])
    comparisons = []
    for relative in ["data/processed/online_retail_clean.csv.gz", "experiments/eda_rebuild/tables/customer_behavior.csv", "experiments/form2_manual_behavior_raw_survey/customer_behavior_experimental.csv"]:
        path = project/relative
        if not path.exists():
            comparisons.append(dict(artifact=relative, status="missing"))
            continue
        stored = pd.read_csv(path, low_memory=False)
        customer_column = "CustomerID" if "CustomerID" in stored else "Customer ID"
        comparisons.append(dict(artifact=relative, rows=len(stored), customers=stored[customer_column].nunique(),
                                columns="; ".join(stored.columns),
                                status="historical_scope_not_equivalent_to_current_run"))
    t["stored_comparison"] = pd.DataFrame(comparisons)
    t["policy_settings"] = pd.DataFrame([("API", "src.preprocessing.clean_data"),
        ("SPECIAL_CODES", ", ".join(sorted(preprocessing.SPECIAL_CODES))),
        ("Pipeline outlier", f"log1p {preprocessing.OUTLIER_COLS}; k={preprocessing.OUTLIER_K}"),
        ("Customer EDA", "Exclude Guest AFTER pipeline; same window for every feature"),
        ("Invoice time", "earliest within retained purchase rows"),
        ("Status", "experimental_current_code_not_official_policy")], columns=["setting", "value"])
    metadata = dict(run_at=datetime.now(ZoneInfo("Asia/Bangkok")).isoformat(), client_date="2026-11-05", timezone="Asia/Bangkok",
                    git_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=project, text=True).strip(),
                    initial_scope="current clean_data, known-ID customers; unapproved business policy",
                    window_start=WINDOW_START, reference_date_exclusive=REFERENCE_DATE,
                    source_timestamp_timezone="unspecified; no timezone conversion", python=platform.python_version(),
                    versions={m:importlib.metadata.version(m) for m in ["pandas", "numpy", "matplotlib", "scipy", "scikit-learn", "openpyxl", "nbformat", "nbclient"]},
                    protected_before=before,
                    eda_source_sha256={p.name:checksum(p) for p in Path(__file__).parent.glob("eda_*.py")})
    result = dict(project=project, raw=raw, clean=clean, purchase=purchase, orders=orders, tables=t, metadata=metadata)
    validate_analysis(result)
    return result


def validate_customer_tables(t):
    """Validate customer formulas, RFM, correlations and scaling from computed tables."""
    b = t["customer_behavior"].set_index("Customer ID")
    assert b.index.is_unique
    np.testing.assert_allclose(b.avg_order_value*b.Frequency, b.Monetary, rtol=1e-12)
    assert b.loc[b.Frequency.eq(1), "avg_purchase_gap_days"].isna().all()
    assert b.loc[b.Frequency.gt(1), "avg_purchase_gap_days"].notna().all()
    # Telescoping identity independently checks every mean inter-invoice gap.
    expected = (pd.to_datetime(b.last_purchase_time)-pd.to_datetime(b.first_purchase_time)).dt.total_seconds()/86400/(b.Frequency-1).replace(0,np.nan)
    np.testing.assert_allclose(b.avg_purchase_gap_days, expected, equal_nan=True)
    assert b[["n_distinct_products", "avg_quantity_per_order", "total_quantity", "return_rate"]].isna().all().all()
    assert b.Recency.gt(0).all()
    for name in ["rfm", "rfm_transformed"]:
        assert t[name]["Customer ID"].is_unique
        assert t[name]["Customer ID"].tolist() == b.index.tolist()
    for name in ["Recency", "Frequency", "Monetary"]:
        np.testing.assert_allclose(t["rfm"][name], b[name], rtol=1e-12)
    counts = t["correlation_pairwise_counts"]
    assert counts.equals(counts.T)
    from scipy.stats import spearmanr, pearsonr
    for i,x in enumerate(counts.index):
        for y in counts.columns[i:]:
            pair = b[[x,y]].dropna() if x != y else b[[x]].dropna()
            assert counts.loc[x,y] == len(pair)
            left = pair[x].to_numpy()
            right = pair[y].to_numpy()
            np.testing.assert_allclose(t["correlation_spearman"].loc[x,y], spearmanr(left,right).statistic, atol=1e-12)
            np.testing.assert_allclose(t["correlation_pearson"].loc[x,y], pearsonr(left,right).statistic, atol=1e-12)
    logged = np.log1p(b[["Recency", "Frequency", "Monetary"]].astype(float))
    parameters = t["scaling_parameters"].set_index("feature").loc[logged.columns]
    np.testing.assert_allclose(parameters.mean_log1p, logged.mean(), rtol=1e-12)
    np.testing.assert_allclose(parameters.variance_log1p, logged.var(ddof=0), rtol=1e-12)
    np.testing.assert_allclose(parameters.scale_log1p, logged.std(ddof=0), rtol=1e-12)
    assert parameters.fit_customers.eq(len(b)).all()
    for name in logged:
        np.testing.assert_allclose(t["rfm_transformed"]["log1p_"+name], logged[name], rtol=1e-12)
        expected_z = (logged[name]-parameters.loc[name, "mean_log1p"])/parameters.loc[name, "scale_log1p"]
        np.testing.assert_allclose(t["rfm_transformed"]["z_log1p_"+name], expected_z, atol=1e-12)
    z = t["rfm_transformed"].filter(like="z_log1p_")
    np.testing.assert_allclose(z.mean(), 0, atol=1e-12)
    np.testing.assert_allclose(z.std(ddof=0), 1, atol=1e-12)
    return "Đạt: khóa khách, AOV/gap, RFM, mọi cặp tương quan/n và tham số scaling."


def validate_analysis(result):
    """Reconcile important results against the original transaction/order inputs."""
    t, p, orders = result["tables"], result["purchase"], result["orders"]
    b = t["customer_behavior"].set_index("Customer ID")
    validate_customer_tables(t)
    assert len(b) == p["Customer ID"].nunique()
    assert b.n_transaction_rows.sum() == len(p)
    pd.testing.assert_series_equal(b.Frequency.sort_index(), p.groupby("Customer ID").Invoice.nunique().sort_index(),
                                   check_names=False, check_index_type=False, check_dtype=False)
    exact = (p.Quantity*p.Price).groupby(p["Customer ID"]).sum().sort_index()
    np.testing.assert_allclose(b.Monetary.sort_index(), exact, rtol=1e-12)
    assert len(orders) == b.Frequency.sum()
    assert t["country_invoice_counts"].to_numpy().sum() == len(result["raw"])
    assert t["country_order_counts"].to_numpy().sum() == len(b)
    np.testing.assert_allclose(t["country_invoice_row_pct"].sum(axis=1), 100)
    np.testing.assert_allclose(t["country_order_row_pct"].sum(axis=1), 100)
    assert protected_hashes(result["project"]) == result["metadata"]["protected_before"]
    return "Đạt: khóa, công thức, tổng, khoảng cách, mọi cặp tương quan/n, scaling và checksum nguồn."


def export_tables(result):
    output = result["project"] / "experiments/eda_current_policy/tables"
    output.mkdir(parents=True, exist_ok=True)
    for name in EXPORT_TABLES:
        result["tables"][name].to_csv(output/f"{name}.csv", index=name in MATRIX_TABLES, encoding="utf-8-sig")
    metadata = {**result["metadata"], "protected_after": protected_hashes(result["project"])}
    metadata["protected_unchanged"] = metadata["protected_before"] == metadata["protected_after"]
    metadata["table_sha256"] = {name:checksum(output/f"{name}.csv") for name in EXPORT_TABLES}
    (output.parent/"run_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    result["metadata"] = metadata
    return output
