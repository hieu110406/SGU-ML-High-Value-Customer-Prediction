"""Khảo sát Form 2 trên bản sao nguồn; KHÔNG phải tiền xử lý/đặc trưng chính thức.

Chạy từ root repository; cần chọn rõ --window-start và --reference-date.
Không ghi vào data/raw hoặc data/processed. Thư mục đầu ra phải chưa tồn tại.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_DIR))
from src.features import (  # noqa: E402
    aggregate_purchase_orders, audit_c_documents, audit_stock_codes,
    build_customer_behavior_features,
)


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def identifier(values):
    return (values.astype("string").str.strip()
            .str.replace(r"(?<=\d)\.0$", "", regex=True).replace("", pd.NA))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-start", required=True)
    parser.add_argument("--reference-date", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    experiments_dir = (PROJECT_DIR / "experiments").resolve()
    if not output_dir.is_relative_to(experiments_dir) or output_dir == experiments_dir:
        parser.error("Đầu ra khảo sát phải nằm trong một thư mục con mới của project/experiments/.")
    if output_dir.exists():
        parser.error("Thư mục đầu ra đã tồn tại; chọn tên lần chạy khác, không tự ghi đè.")
    scope = {"window_start": args.window_start, "reference_date": args.reference_date}
    source = PROJECT_DIR / "data/raw/online_retail_II.xlsx"
    source_hash = checksum(source)
    print("Đang đọc tất cả sheet; nguồn chỉ đọc...", flush=True)
    with pd.ExcelFile(source, engine="openpyxl") as workbook:
        sheets = {name: pd.read_excel(workbook, sheet_name=name) for name in workbook.sheet_names}
    columns = list(next(iter(sheets.values())).columns)
    expected = {"Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"}
    if any(set(part.columns) != expected for part in sheets.values()):
        raise ValueError("Cấu trúc sheet khác EDA, cần kiểm tra trước khi gộp.")
    raw = pd.concat([part.loc[:, columns] for part in sheets.values()], ignore_index=True)
    print(f"Đã đọc {len(raw):,} dòng; kiểm kê StockCode và chứng từ C trước khi chọn dòng mua.", flush=True)
    stock_audit = audit_stock_codes(raw, **scope)
    c_audit = audit_c_documents(raw, **scope)

    # Chỉ là phân loại KHẢO SÁT. Mẫu mã 5 số + hậu tố chữ chưa phải danh mục sản phẩm xác minh.
    roles = dict.fromkeys(stock_audit.loc[stock_audit["matches_product_code_pattern"], "StockCode"], "product")
    non_products = {"POST", "D", "M", "B", "BANK CHARGES", "DOT"}
    special_examples = stock_audit.loc[stock_audit["StockCode"].isin(non_products)]
    print("Mã bút toán/phí được xem riêng trong khảo sát:")
    print(special_examples[["StockCode", "n_rows", "example_descriptions"]].to_string(index=False), flush=True)
    roles.update({key: "non_product" for key in non_products if key in set(stock_audit["StockCode"].dropna())})
    stock_audit["provisional_role"] = stock_audit["StockCode"].map(roles).astype("string").fillna("unknown")

    # Lặp lại điều kiện khảo sát của EDA 7.4, không tạo/sửa pipeline của Thuận.
    work = raw.copy()
    work["Invoice"] = identifier(work["Invoice"])
    work["StockCode"] = identifier(work["StockCode"])
    dates = pd.to_datetime(work["InvoiceDate"], errors="raise")
    customer = pd.to_numeric(work["Customer ID"], errors="raise")
    valid_customer = customer.notna() & np.isfinite(customer) & customer.between(10000, 99999) & customer.mod(1).eq(0)
    in_window = dates.ge(pd.Timestamp(args.window_start)) & dates.lt(pd.Timestamp(args.reference_date))
    invoice_customers = work.loc[in_window & valid_customer].groupby("Invoice")["Customer ID"].nunique()
    conflicts = invoice_customers[invoice_customers.gt(1)].index
    conditions = [
        ("Trong cửa sổ [start, reference)", in_window),
        ("Customer ID hợp lệ về hình thức như EDA", valid_customer),
        ("Invoice đúng 6 chữ số, không C", work["Invoice"].str.fullmatch(r"\d{6}", na=False)),
        ("Quantity > 0, Price > 0, tích hữu hạn", work["Quantity"].gt(0) & work["Price"].gt(0)
         & np.isfinite(work["Quantity"] * work["Price"])),
        ("Không có Invoice gắn nhiều Customer ID", ~work["Invoice"].isin(conflicts)),
    ]
    mask = pd.Series(True, index=work.index)
    steps = []
    previous = len(work)
    for label, condition in conditions:
        mask &= condition.fillna(False)
        selected = work.loc[mask]
        steps.append({"step": label, "rows_remaining": len(selected), "rows_removed_at_step": previous - len(selected),
                      "invoices": int(selected["Invoice"].nunique()), "customers": int(selected["Customer ID"].nunique())})
        previous = len(selected)
    candidate = work.loc[mask].copy()
    features = build_customer_behavior_features(candidate, **scope, stock_code_roles=roles,
                                                invoice_time_policy="earliest", include_optional=True)
    orders = aggregate_purchase_orders(candidate, **scope, invoice_time_policy="earliest")
    assert features["Customer ID"].is_unique
    assert len(features) == candidate["Customer ID"].nunique()
    assert features["n_transaction_rows"].sum() == len(candidate)
    assert features["return_rate"].isna().all()
    assert features.loc[features["n_orders"].eq(1), "avg_purchase_gap_days"].isna().all()

    # Đối chiếu độc lập bằng dict/set trên một số khách hàng, không thay dữ liệu phân tích bằng mẫu.
    ids = features["Customer ID"].tolist()
    if not ids:
        raise ValueError("Tập khảo sát rỗng, không xuất bảng giả.")
    single = features.loc[features["n_orders"].eq(1), "Customer ID"]
    checked_ids = sorted(set([ids[0], ids[len(ids) // 2], ids[-1], *single.head(1)]))
    indexed = features.set_index("Customer ID")
    for customer_id in checked_ids:
        rows = candidate.loc[identifier(candidate["Customer ID"]).eq(customer_id)]
        amounts, times = {}, {}
        for record in rows.to_dict("records"):
            key = record["Invoice"]
            amounts[key] = amounts.get(key, 0.0) + record["Quantity"] * record["Price"]
            times[key] = min(times.get(key, record["InvoiceDate"]), record["InvoiceDate"])
        observed = indexed.loc[customer_id]
        assert observed["n_orders"] == len(amounts)
        assert np.isclose(observed["avg_order_value"], sum(amounts.values()) / len(amounts))
        if len(times) < 2:
            assert pd.isna(observed["avg_purchase_gap_days"])
        else:
            gap = (max(times.values()) - min(times.values())).total_seconds() / 86400 / (len(times) - 1)
            assert np.isclose(observed["avg_purchase_gap_days"], gap)
    assert checksum(source) == source_hash

    metadata = {
        "data_status": "experimental_raw_survey_not_official", "source": "data/raw/online_retail_II.xlsx",
        "source_sha256": source_hash, "window": {**scope, "closed": "left"},
        "python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
        "sheet_rows": {name: len(part) for name, part in sheets.items()}, "raw_rows": len(raw),
        "candidate_rows": len(candidate), "candidate_invoices": int(features["n_orders"].sum()),
        "candidate_customers": len(features), "c_audit_customers": len(c_audit),
        "candidate_duplicate_excess_on_8_source_columns": int(candidate.duplicated(subset=columns).sum()),
        "orders_with_multiple_timestamps": int(orders["n_timestamps"].gt(1).sum()),
        "single_order_customers": int(features["n_orders"].eq(1).sum()),
        "customers_with_incomplete_product_classification": int(features["product_classification_status"].ne("complete").sum()),
        "stock_classification": {"product": "provisional regex: 5 digits plus optional letter suffix",
                                 "non_product": sorted(non_products), "other_codes": "unknown; not silently excluded"},
        "verified_return_rate": "undefined; all values NaN, not zero", "duplicates": "preserved",
        "purchase_time_policy": "earliest within selected window", "feature_scope": features.attrs,
        "c_document_audit_scope": c_audit.attrs, "filter_steps": steps,
        "independent_check_customer_ids": checked_ids,
        "limitations": ["No official preprocessing input or verified product catalog.",
                        "C/negative events not matched to original invoices; no verified return rate.",
                        "AOV includes retained service/adjustment lines; quantity counts classified products only.",
                        "Duplicate and overlapping sheet rows remain; amounts/quantities can be inflated.",
                        "Only eligible lines of an invoice may remain; not guaranteed complete baskets.",
                        "Tenure is observed within window; not true customer acquisition tenure."],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    for frame, name in [(features, "customer_behavior_experimental.csv"),
                        (c_audit, "c_document_audit_experimental.csv"),
                        (stock_audit, "stock_code_audit_experimental.csv")]:
        frame = frame.assign(data_status="experimental_raw_survey_not_official")
        frame.to_csv(output_dir / name, index=False, na_rep="NaN", encoding="utf-8-sig")
    (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: metadata[key] for key in ["raw_rows", "candidate_rows", "candidate_invoices", "candidate_customers",
          "single_order_customers", "customers_with_incomplete_product_classification"]}, ensure_ascii=False), flush=True)
    print("Xuất bảng KHẢO SÁT THỬ NGHIỆM và kiểm tra độc lập thành công:", output_dir, flush=True)


if __name__ == "__main__":
    main()
