"""Đọc raw và cleaning mua dương theo cấu hình thử nghiệm được chỉ định.

``clean_purchases`` dùng cho baseline hiện tại. ``clean_data`` và
``save_processed`` được giữ để đối chiếu công việc cũ, không phải chính sách
cleaning chính thức và không được gọi từ luồng baseline mới.
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import pandas as pd

RAW_PATH = Path(__file__).resolve().parents[1] / "data/raw/Online Retail.xlsx"
PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data/processed"
RAW_SHA256 = "43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d"
RAW_SHEET = "Online Retail"
RAW_COLUMNS = [
    "InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate",
    "UnitPrice", "CustomerID", "Country",
]
PURCHASE_POLICY = "positive_purchases_v1"


RENAME = {"InvoiceNo": "Invoice", "UnitPrice": "Price", "CustomerID": "Customer ID"}


SPECIAL_CODES = {
    "POST", "DOT", "M", "C2", "C3", "D", "S", "B", "BANK CHARGES",
    "ADJUST", "ADJUST2", "AMAZONFEE", "CRUK", "TEST001", "TEST002",
}
OUTLIER_COLS = ["Quantity", "Price"]
OUTLIER_K = 3.0  


def load_raw(path: Path | str = RAW_PATH) -> pd.DataFrame:
    """Chỉ nhận workbook một sheet Online Retail với đúng tám cột nguồn.

    Không đổi tên cột, không làm sạch, không sửa workbook. Bên chạy thí nghiệm
    phải đối chiếu ``sha256_of(path)`` với phiên bản raw trong cấu hình.
    """
    sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    if list(sheets) != [RAW_SHEET]:
        raise ValueError(f"Workbook phải có duy nhất sheet {RAW_SHEET!r}; thực tế: {list(sheets)}")
    raw = sheets[RAW_SHEET]
    _require_raw_schema(raw)
    return raw


def _require_raw_schema(raw: pd.DataFrame) -> None:
    if not raw.columns.is_unique:
        raise ValueError("Tên cột raw phải duy nhất.")
    missing = sorted(set(RAW_COLUMNS) - set(raw.columns))
    extra = sorted(set(raw.columns) - set(RAW_COLUMNS))
    if missing or extra:
        raise ValueError(f"Sai schema Online Retail. Thiếu cột: {missing}; cột dư: {extra}")


def _normalised_id(values: pd.Series) -> pd.Series:
    """Chuỗi định danh, bỏ khoảng trắng/.0 do Excel; không cắt phần lẻ."""
    return (values.astype("string").str.strip()
            .str.replace(r"(?<=\d)\.0$", "", regex=True).replace("", pd.NA))


def clean_purchases(
    raw: pd.DataFrame, *, policy: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cleaning thử nghiệm; bắt buộc chọn ``positive_purchases_v1`` rõ ràng.

    Bỏ bản sao hoàn toàn trên tám cột raw (giữ lần đầu), bỏ ID khách thiếu,
    chứng từ C và Quantity/UnitPrice không dương. Giữ mọi mã dịch vụ và ngoại
    lệ; không điền Description, ghép trả hàng hay làm tròn giá trị từng dòng.
    Các dữ liệu số/ngày/khóa không hợp lệ bị báo lỗi, không bị sửa ngầm.
    Kết quả dùng schema nội bộ tương thích API hành vi đã có. Không đọc/ghi tệp,
    không thay đổi raw và không thay dữ liệu processed chính thức.

    Log tuần tự đếm lại dòng, chứng từ và khách trước/sau từng bước. Các số
    loại là hiệu liên tiếp, không phải tổng của các cờ có thể chồng lấn.
    """
    if policy != PURCHASE_POLICY:
        raise ValueError(f"Chính sách thử nghiệm được hỗ trợ: {PURCHASE_POLICY!r}; nhận {policy!r}")
    _require_raw_schema(raw)
    work = raw.copy(deep=True)
    records: list[dict] = []

    def counts(frame: pd.DataFrame) -> dict[str, int]:
        return {
            "rows": len(frame),
            "invoices": int(_normalised_id(frame["InvoiceNo"]).nunique()),
            "customers": int(_normalised_id(frame["CustomerID"]).nunique()),
        }

    def record(step: str, rule: str, before: Mapping[str, int], *, note: str = "") -> None:
        after = counts(work)
        records.append({
            "step": step, "rule": rule,
            **{f"{key}_before": before[key] for key in before},
            **{f"{key}_after": after[key] for key in after},
            "rows_removed": before["rows"] - after["rows"], "note": note,
        })

    before = counts(work)
    record("raw", "Đầu vào đủ tám cột raw, chưa lọc", before)
    before = counts(work)
    work = work.drop_duplicates(subset=RAW_COLUMNS, keep="first").copy()
    record("exact_duplicates", "Bỏ bản sao hoàn toàn trên tám cột raw; keep=first", before,
           note="So sánh trước mọi chuẩn hóa; InvoiceNo–StockCode không phải khóa duy nhất.")

    before = counts(work)
    for column in ["InvoiceNo", "StockCode", "CustomerID"]:
        work[column] = _normalised_id(work[column])
    work["InvoiceNo"] = work["InvoiceNo"].str.upper()
    if work["InvoiceNo"].isna().any():
        raise ValueError("InvoiceNo thiếu; không thể xác định chứng từ mua.")
    known_ids = work["CustomerID"].dropna()
    if not known_ids.str.fullmatch(r"\d+").all():
        raise ValueError("CustomerID phải là định danh số nguyên không âm; không cắt phần thập phân.")
    try:
        dates = pd.to_datetime(work["InvoiceDate"], errors="raise", format="mixed")
    except (ValueError, TypeError) as exc:
        raise ValueError("InvoiceDate không hợp lệ; không tự điền hoặc sửa ngày.") from exc
    if dates.isna().any() or not isinstance(dates.dtype, np.dtype):
        raise ValueError("InvoiceDate phải có ngày đầy đủ, không tự gán hoặc đổi múi giờ.")
    if not pd.api.types.is_datetime64_dtype(dates.dtype):
        raise ValueError("InvoiceDate phải là datetime không có múi giờ như raw nguồn.")
    work["InvoiceDate"] = dates
    for column in ["Quantity", "UnitPrice"]:
        try:
            work[column] = pd.to_numeric(work[column], errors="raise").astype(float)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{column} phải là số hữu hạn.") from exc
        if not np.isfinite(work[column]).all():
            raise ValueError(f"{column} chứa giá trị thiếu hoặc không hữu hạn.")
    if not np.isfinite(work["Quantity"] * work["UnitPrice"]).all():
        raise ValueError("Quantity × UnitPrice không hữu hạn.")
    record("normalise_types", "Chuẩn hóa định danh, datetime và số; không điền thiếu mô tả", before,
           note="ID không phải đặc trưng số; không gộp khách vô danh thành Guest.")

    before = counts(work)
    work = work.loc[work["CustomerID"].notna()].copy()
    record("missing_customer", "Bỏ dòng thiếu CustomerID khỏi tập khách phân cụm", before)
    before = counts(work)
    work = work.loc[~work["InvoiceNo"].str.startswith("C")].copy()
    record("c_documents", "Bỏ chứng từ bắt đầu bằng C khỏi góc nhìn mua", before,
           note="Không ghép hoàn trả; Monetary là mua dương, không phải doanh thu thuần.")
    before = counts(work)
    work = work.loc[work["Quantity"].gt(0) & work["UnitPrice"].gt(0)].copy()
    record("nonpositive_values", "Giữ Quantity > 0 và UnitPrice > 0", before)
    before = counts(work)
    record("service_codes_outliers", "Giữ mọi mã dịch vụ và mọi ngoại lệ", before,
           note="Không áp danh mục SPECIAL_CODES hoặc lọc IQR của mã legacy.")

    clean = work.rename(columns=RENAME).copy()
    clean["Revenue"] = clean["Quantity"] * clean["Price"]
    clean["IsGuest"] = False
    clean = clean.sort_values(["InvoiceDate", "Invoice"], kind="stable").reset_index(drop=True)
    clean.attrs = {
        "cleaning_policy": policy, "approval_status": "experimental_user_authorized",
        "official_team_policy": False,
        "monetary_scope": "positive_purchase_lines_including_services_without_return_matching",
        "duplicate_scope": "exact_original_eight_columns_keep_first",
        "outliers": "kept", "service_codes": "kept", "line_value_rounding": "none",
    }
    log = pd.DataFrame.from_records(records)
    log.attrs = clean.attrs.copy()
    return clean, log


def sha256_of(path: Path | str = RAW_PATH) -> str:
    """SHA-256 của file raw, để đối chiếu với `RAW_SHA256`."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def outlier_mask(df: pd.DataFrame, cols=OUTLIER_COLS, k: float = OUTLIER_K) -> pd.Series:
    """Đánh dấu dòng có ít nhất một cột nằm ngoài [Q1 - k*IQR, Q3 + k*IQR] trên thang log1p."""
    mask = pd.Series(False, index=df.index)
    for col in cols:
        x = np.log1p(df[col])
        q1, q3 = x.quantile([0.25, 0.75])
        iqr = q3 - q1
        mask |= (x < q1 - k * iqr) | (x > q3 + k * iqr)
    return mask


def clean_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """LEGACY: giữ để đối chiếu; không dùng làm cleaning baseline hiện tại.

    Quy tắc Guest, bỏ dịch vụ và lọc ngoại lệ của hàm cũ chưa phải phương án
    chính thức. Baseline thử nghiệm đã được chỉ định dùng ``clean_purchases``.
    Trả về ``(clean, log_df)`` theo hợp đồng cũ của thành viên.
    """
    needed = set(RENAME) | {"StockCode", "Description", "Quantity", "InvoiceDate", "Country"}
    missing = sorted(needed - set(raw.columns))
    if missing:
        raise ValueError(f"Thiếu cột của raw Online Retail: {missing}")

    log: list[tuple[str, int]] = [("Dữ liệu gốc (Online Retail.xlsx)", len(raw))]
    df = raw.rename(columns=RENAME).copy()

    
    df["Description"] = df["Description"].fillna("Unknown Product")
    df["Description"] = df["Description"].astype(str).str.strip().str.upper()
    df["Invoice"] = df["Invoice"].astype(str).str.strip().str.upper()
    df["StockCode"] = df["StockCode"].astype(str).str.strip().str.upper()
    df["Country"] = df["Country"].astype(str).str.strip().replace({"EIRE": "Ireland"})
    log.append(("Bước 1. Điền Description thiếu, chuẩn hóa văn bản, EIRE → Ireland", len(df)))

    
    df = df.drop_duplicates()
    log.append(("Bước 2. Bỏ dòng trùng lặp", len(df)))

    
    df = df[~df["Invoice"].str.startswith("C")]
    log.append(("Bước 3a. Bỏ hóa đơn hủy (Invoice bắt đầu bằng C)", len(df)))
    df = df[(df["Quantity"] > 0) & (df["Price"] > 0)]
    log.append(("Bước 3b. Giữ Quantity > 0 và Price > 0", len(df)))
    df = df[~df["StockCode"].isin(SPECIAL_CODES)]
    log.append(("Bước 3c. Bỏ mã hàng đặc biệt (POST, M, BANK CHARGES...)", len(df)))

  
    df = df[~outlier_mask(df)]
    log.append((f"Bước 4. Bỏ ngoại lai cực đoan (IQR x {OUTLIER_K:g} trên log1p)", len(df)))

    
    df["Customer ID"] = df["Customer ID"].map(lambda v: "Guest" if pd.isna(v) else str(int(v)))
    log.append(("Bước 5. Customer ID thiếu → 'Guest' (đổi kiểu sang chuỗi)", len(df)))

    df["Revenue"] = (df["Quantity"] * df["Price"]).round(2)
    df["IsGuest"] = df["Customer ID"].eq("Guest")
    df = df.sort_values(["InvoiceDate", "Invoice"]).reset_index(drop=True)

    log_df = pd.DataFrame(log, columns=["Bước", "Số dòng còn lại"])
    log_df["Số dòng bị loại"] = (-log_df["Số dòng còn lại"].diff()).fillna(0).astype(int)
    log_df["% còn lại so với gốc"] = (log_df["Số dòng còn lại"] / len(raw) * 100).round(2)
    return df, log_df


def save_processed(clean: pd.DataFrame, log_df: pd.DataFrame, out_dir: Path | str = PROCESSED_DIR) -> None:
    """LEGACY: có ghi đè; không dùng trong luồng baseline thử nghiệm hiện tại.

    Giữ API cũ cho thành viên đối chiếu. Bên gọi chịu trách nhiệm chọn nơi lưu
    và không ghi đè dữ liệu processed của nhóm bằng kết quả thử nghiệm.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    clean.to_csv(out / "data_clean.csv.gz", index=False, encoding="utf-8")
    log_df.to_csv(out / "cleaning_log.csv", index=False, encoding="utf-8-sig")
