"""Đặc trưng hành vi thủ công; chưa tạo RFM hoặc chuẩn hóa cho mô hình.

Các hàm không đọc/ghi tệp và không triển khai chính sách làm sạch. Bên gọi
phải cung cấp góc nhìn các dòng mua phù hợp; dữ liệu C/âm được kiểm kê riêng.
Mọi phép tính chỉ dùng cửa sổ [window_start, reference_date).
Xem reports/form2_manual_behavior_features.md để biết công thức và giới hạn.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd


PURCHASE_COLUMNS = ["Customer ID", "Invoice", "StockCode", "InvoiceDate", "Quantity", "Price"]
ORDER_COLUMNS = ["Customer ID", "Invoice", "purchase_time", "order_value", "source_row_count", "n_timestamps"]
BEHAVIOR_COLUMNS = [
    "Customer ID", "n_transaction_rows", "n_orders", "avg_order_value",
    "n_distinct_products", "avg_quantity_per_order", "avg_purchase_gap_days",
    "first_purchase_time", "last_purchase_time", "n_unclassified_rows",
    "product_classification_status", "return_rate", "return_rate_status",
]


def _require_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    if not frame.columns.is_unique:
        raise ValueError("Tên cột phải duy nhất.")
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"Thiếu cột đầu vào: {missing}")


def _identifier(values: pd.Series) -> pd.Series:
    # Cùng quy tắc trim/.0 như EDA; không biến mã thành đại lượng liên tục.
    return (values.astype("string").str.strip()
            .str.replace(r"(?<=\d)\.0$", "", regex=True).replace("", pd.NA))


def _windowed(
    transactions: pd.DataFrame, *, window_start: str | pd.Timestamp,
    reference_date: str | pd.Timestamp,
) -> pd.DataFrame:
    _require_columns(transactions, ["InvoiceDate"])
    start, reference = pd.Timestamp(window_start), pd.Timestamp(reference_date)
    if pd.isna(start) or pd.isna(reference):
        raise ValueError("Cần hai mốc thời gian hợp lệ, không dùng NaT.")
    try:
        if start >= reference:
            raise ValueError("window_start phải nhỏ hơn reference_date.")
        dates = pd.to_datetime(transactions["InvoiceDate"], errors="raise", format="mixed")
        if dates.isna().any():
            raise ValueError("Có InvoiceDate thiếu; chưa xác định được dòng có nằm trong cửa sổ.")
        mask = dates.ge(start) & dates.lt(reference)
    except (TypeError, AttributeError) as exc:
        raise ValueError("Ngày nguồn và hai mốc phải tương thích múi giờ; không tự gán múi giờ.") from exc
    work = transactions.loc[mask].copy()
    work["InvoiceDate"] = dates.loc[mask]
    work = work.reset_index(drop=True)
    work.attrs = {
        "window_start": start.isoformat(), "reference_date": reference.isoformat(),
        "window_closed": "left", "input_rows": len(transactions), "window_rows": len(work),
        "outside_window_rows": int((~mask).sum()),
    }
    return work


def _purchases(transactions, *, window_start, reference_date) -> pd.DataFrame:
    _require_columns(transactions, PURCHASE_COLUMNS)
    work = _windowed(transactions, window_start=window_start, reference_date=reference_date)
    for column in ["Customer ID", "Invoice", "StockCode"]:
        work[column] = _identifier(work[column])
    if work[["Customer ID", "Invoice"]].isna().any().any():
        raise ValueError("Dòng mua trong cửa sổ phải có Customer ID và Invoice; không tự điền mã.")
    if work["Invoice"].str.upper().str.startswith("C").any():
        raise ValueError("Đầu vào mua chứa chứng từ C; giữ góc nhìn đó riêng và chốt chính sách trước.")
    for column in ["Quantity", "Price"]:
        work[column] = pd.to_numeric(work[column], errors="raise").astype(float)
        if not (np.isfinite(work[column]) & work[column].gt(0)).all():
            raise ValueError(f"Góc nhìn mua yêu cầu {column} hữu hạn và > 0; không tự xóa dòng.")
    work["_line_value"] = work["Quantity"] * work["Price"]
    if not np.isfinite(work["_line_value"]).all():
        raise ValueError("Quantity × Price không hữu hạn.")
    if work.groupby("Invoice")["Customer ID"].nunique().gt(1).any():
        raise ValueError("Một Invoice gắn nhiều Customer ID trong cửa sổ; cần đối chiếu khóa hóa đơn.")
    return work


def _orders(work: pd.DataFrame, invoice_time_policy: str) -> pd.DataFrame:
    if invoice_time_policy not in {"require_unique", "earliest"}:
        raise ValueError("invoice_time_policy phải là 'require_unique' hoặc 'earliest'.")
    orders = work.groupby(["Customer ID", "Invoice"], sort=True).agg(
        purchase_time=("InvoiceDate", "min"), order_value=("_line_value", "sum"),
        source_row_count=("Invoice", "size"), n_timestamps=("InvoiceDate", "nunique"),
    ).reset_index()
    if invoice_time_policy == "require_unique" and orders["n_timestamps"].gt(1).any():
        raise ValueError("Một hóa đơn có nhiều thời điểm. Chốt chính sách hoặc chọn 'earliest' rõ ràng.")
    if not np.isfinite(orders["order_value"]).all():
        raise ValueError("Tổng giá trị hóa đơn không hữu hạn.")
    return orders.loc[:, ORDER_COLUMNS]


def aggregate_purchase_orders(
    transactions: pd.DataFrame, *, window_start: str | pd.Timestamp,
    reference_date: str | pd.Timestamp, invoice_time_policy: str = "require_unique",
) -> pd.DataFrame:
    """Một dòng/(Customer ID, Invoice), order_value tính bằng GBP.

    Input: 6 cột PURCHASE_COLUMNS, chỉ các dòng mua do bên gọi chọn (Q/P > 0,
    không C). Giữ mọi dòng trùng. Mặc định từ chối hóa đơn có nhiều thời điểm;
    'earliest' dùng thời điểm sớm nhất trong cửa sổ khi bên gọi chủ động chọn.
    Không tự loại phí/dịch vụ khỏi giá trị đơn: order_value cộng mọi dòng đầu vào.
    """
    work = _purchases(transactions, window_start=window_start, reference_date=reference_date)
    orders = _orders(work, invoice_time_policy)
    orders.attrs = {**work.attrs, "invoice_time_policy": invoice_time_policy}
    return orders


def _stock_roles(roles: Mapping[str, str] | None) -> dict[str, str]:
    normalised = {}
    for code, role in (roles or {}).items():
        key = _identifier(pd.Series([code])).iloc[0]
        if pd.isna(key) or role not in {"product", "non_product"}:
            raise ValueError("Bảng StockCode phải có mã khác rỗng và nhãn product/non_product.")
        if key in normalised and normalised[key] != role:
            raise ValueError(f"StockCode {key} có nhãn mâu thuẫn sau chuẩn hóa.")
        normalised[key] = role
    return normalised


def build_customer_behavior_features(
    transactions: pd.DataFrame, *, window_start: str | pd.Timestamp,
    reference_date: str | pd.Timestamp, stock_code_roles: Mapping[str, str] | None = None,
    invoice_time_policy: str = "require_unique", include_optional: bool = False,
) -> pd.DataFrame:
    """Bảng hành vi: đúng một dòng/Customer ID có dòng mua trong cửa sổ.

    Giá trị đơn trung bình = mean(tổng Quantity × Price từng Invoice), GBP/đơn.
    Số sản phẩm = nunique(StockCode đã phân loại product); lượng/đơn = tổng lượng
    product / số Invoice. Thiếu phân loại ở bất kỳ dòng nào của khách hàng làm
    hai chỉ số sản phẩm thành NaN, không coi mọi StockCode là sản phẩm.
    Khoảng cách mua = mean(diff(thời điểm từng Invoice)), ngày = 86400 giây;
    một hóa đơn -> NaN; hai hóa đơn cùng thời điểm có khoảng cách 0 thực sự.
    return_rate luôn NaN trong Form 2 vì chưa có nguồn hoàn trả đã xác minh.
    include_optional thêm total_quantity (chỉ product) và observed_tenure_days
    (reference_date - lần mua đầu quan sát được; không phải tuổi khách hàng thật).
    Không biến đổi log, scale, chọn biến mô hình hoặc tạo đặc trưng RFM.
    """
    work = _purchases(transactions, window_start=window_start, reference_date=reference_date)
    orders = _orders(work, invoice_time_policy)
    roles = _stock_roles(stock_code_roles)
    columns = BEHAVIOR_COLUMNS + (["total_quantity", "observed_tenure_days"] if include_optional else [])
    if work.empty:
        result = pd.DataFrame(columns=columns)
    else:
        result = orders.groupby("Customer ID").agg(
            n_orders=("Invoice", "size"), avg_order_value=("order_value", "mean"),
            first_purchase_time=("purchase_time", "min"), last_purchase_time=("purchase_time", "max"),
        )
        result["n_transaction_rows"] = work.groupby("Customer ID").size()
        ordered = orders.sort_values(["Customer ID", "purchase_time", "Invoice"])
        gaps = ordered.groupby("Customer ID")["purchase_time"].diff() / pd.Timedelta(days=1)
        result["avg_purchase_gap_days"] = gaps.groupby(ordered["Customer ID"]).mean()

        role = work["StockCode"].map(roles).astype("string").fillna("unknown")
        unknown = role.eq("unknown")
        result["n_unclassified_rows"] = unknown.groupby(work["Customer ID"]).sum()
        complete = result["n_unclassified_rows"].eq(0)
        products = work.loc[role.eq("product")]
        # Zeros here mean all codes were classified but no product was present.
        product_counts = products.groupby("Customer ID")["StockCode"].nunique().reindex(result.index, fill_value=0)
        quantity = products.groupby("Customer ID")["Quantity"].sum().reindex(result.index, fill_value=0)
        result["n_distinct_products"] = product_counts.where(complete, np.nan)
        result["avg_quantity_per_order"] = (quantity / result["n_orders"]).where(complete, np.nan)
        result["product_classification_status"] = np.where(complete, "complete", "incomplete")
        if stock_code_roles is None:
            result["product_classification_status"] = "not_supplied"
        result["return_rate"] = np.nan
        result["return_rate_status"] = "undefined_no_verified_return_source"
        if include_optional:
            result["total_quantity"] = quantity.where(complete, np.nan)
            result["observed_tenure_days"] = (
                pd.Timestamp(reference_date) - result["first_purchase_time"]
            ) / pd.Timedelta(days=1)
        result = result.reset_index().loc[:, columns]
        numeric = result.select_dtypes(include="number")
        if np.isinf(numeric.to_numpy(dtype=float)).any():
            raise ValueError("Đặc trưng tổng hợp vượt miền số hữu hạn.")
    result.attrs = {
        **work.attrs, "invoice_time_policy": invoice_time_policy,
        "value_scope": "all_supplied_purchase_lines_including_non_products",
        "quantity_scope": "classified_product_lines_only", "duplicates": "preserved",
        "return_rate_definition": "unresolved", "optional_features_included": include_optional,
    }
    return result


def audit_stock_codes(
    transactions: pd.DataFrame, *, window_start: str | pd.Timestamp,
    reference_date: str | pd.Timestamp,
) -> pd.DataFrame:
    """Kiểm kê mã/mô tả trong cửa sổ; mẫu mã không xác nhận đó là sản phẩm.

    Nhận cả góc nhìn thô có C/âm. Không chọn mã/mô tả từ sau thời điểm tham chiếu.
    """
    _require_columns(transactions, ["StockCode", "InvoiceDate"])
    work = _windowed(transactions, window_start=window_start, reference_date=reference_date)
    work["StockCode"] = _identifier(work["StockCode"])
    if "Description" not in work:
        work["Description"] = pd.NA
    result = work.groupby("StockCode", dropna=False).agg(
        n_rows=("StockCode", "size"),
        example_descriptions=("Description", lambda v: " | ".join(v.dropna().astype(str).drop_duplicates().head(3))),
    ).reset_index()
    result["matches_product_code_pattern"] = result["StockCode"].str.fullmatch(r"\d{5}[A-Za-z]*", na=False)
    result.attrs = work.attrs.copy()
    return result


def audit_c_documents(
    transactions: pd.DataFrame, *, window_start: str | pd.Timestamp,
    reference_date: str | pd.Timestamp,
) -> pd.DataFrame:
    """Kiểm kê riêng chứng từ C/âm trước khi lọc mua, không phải tỷ lệ hoàn trả.

    C_document_share = nunique(mã C) / nunique(mọi mã có định danh) từng khách hàng.
    Các mã không C còn có điều chỉnh; không dùng số dòng làm mẫu số hóa đơn.
    Dòng thiếu Customer ID không thể gán cho một người, được đếm trong attrs.
    return_rate vẫn NaN ngay cả khi không quan sát mã C.
    """
    _require_columns(transactions, ["Customer ID", "Invoice", "InvoiceDate", "Quantity"])
    work = _windowed(transactions, window_start=window_start, reference_date=reference_date)
    for column in ["Customer ID", "Invoice"]:
        work[column] = _identifier(work[column])
    quantity = pd.to_numeric(work["Quantity"], errors="raise")
    missing_customer_rows = int(work["Customer ID"].isna().sum())
    work["_c_invoice"] = work["Invoice"].where(work["Invoice"].str.upper().str.startswith("C", na=False))
    work["_negative"] = quantity.lt(0)
    result = work.dropna(subset=["Customer ID"]).groupby("Customer ID").agg(
        n_source_rows=("Invoice", "size"), n_source_invoices=("Invoice", "nunique"),
        n_c_documents=("_c_invoice", "nunique"), n_negative_quantity_rows=("_negative", "sum"),
    )
    result["c_document_share"] = result["n_c_documents"] / result["n_source_invoices"].replace(0, np.nan)
    result["return_rate"] = np.nan
    result["return_rate_status"] = "undefined_no_verified_return_source"
    result = result.reset_index()
    result.attrs = {**work.attrs, "unassigned_customer_rows": missing_customer_rows,
                    "missing_quantity_rows": int(quantity.isna().sum())}
    return result
