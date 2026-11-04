"""Tiền xử lý Online Retail II cho bài toán phân cụm khách hàng RFM.

Các quy tắc và lý do chọn được giải thích trong
`notebooks/01_eda/preprocessing_v1.ipynb` (mục 5 và 6). Dữ liệu gốc không bị sửa.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RAW_PATH = Path("data/raw/online_retail_II.xlsx")
PROCESSED_DIR = Path("data/processed")

# Mã hàng không phải sản phẩm (phí, bưu phí, điều chỉnh sổ sách, hàng thử...).
SPECIAL_CODES = {
    "POST", "DOT", "M", "C2", "C3", "D", "S", "B", "BANK CHARGES",
    "ADJUST", "ADJUST2", "AMAZONFEE", "CRUK", "TEST001", "TEST002",
}
OUTLIER_COLS = ["Quantity", "Price"]
OUTLIER_K = 3.0  # hệ số IQR (ngoại lai "cực đoan"), áp dụng trên thang log1p


def load_raw(path: Path | str = RAW_PATH) -> pd.DataFrame:
    """Đọc cả 2 sheet của file Excel rồi gộp lại."""
    sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    return pd.concat(sheets.values(), ignore_index=True)


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
    """Làm sạch toàn bộ dữ liệu. Trả về `(clean, log_df)`."""
    log: list[tuple[str, int]] = [("Dữ liệu gốc (đã gộp 2 sheet)", len(raw))]
    df = raw.copy()

    # Bước 1: điền Description thiếu + chuẩn hóa văn bản
    df["Description"] = df["Description"].fillna("Unknown Product")
    df["Description"] = df["Description"].astype(str).str.strip().str.upper()
    df["Invoice"] = df["Invoice"].astype(str).str.strip().str.upper()
    df["StockCode"] = df["StockCode"].astype(str).str.strip().str.upper()
    df["Country"] = df["Country"].astype(str).str.strip().replace({"EIRE": "Ireland"})
    log.append(("Bước 1. Điền Description thiếu, chuẩn hóa văn bản, EIRE → Ireland", len(df)))

    # Bước 2: dòng trùng
    df = df.drop_duplicates()
    log.append(("Bước 2. Bỏ dòng trùng lặp", len(df)))

    # Bước 3: hóa đơn hủy, Quantity/Price không dương, mã hàng đặc biệt
    df = df[~df["Invoice"].str.startswith("C")]
    log.append(("Bước 3a. Bỏ hóa đơn hủy (Invoice bắt đầu bằng C)", len(df)))
    df = df[(df["Quantity"] > 0) & (df["Price"] > 0)]
    log.append(("Bước 3b. Giữ Quantity > 0 và Price > 0", len(df)))
    df = df[~df["StockCode"].isin(SPECIAL_CODES)]
    log.append(("Bước 3c. Bỏ mã hàng đặc biệt (POST, M, BANK CHARGES...)", len(df)))

    # Bước 4: ngoại lai cực đoan
    df = df[~outlier_mask(df)]
    log.append((f"Bước 4. Bỏ ngoại lai cực đoan (IQR x {OUTLIER_K:g} trên log1p)", len(df)))

    # Bước 5: Customer ID thiếu -> "Guest"; đổi kiểu sang chuỗi
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
    """Ghi `data_clean.csv.gz` và `cleaning_log.csv` vào data/processed/."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    clean.to_csv(out / "data_clean.csv.gz", index=False, encoding="utf-8")
    log_df.to_csv(out / "cleaning_log.csv", index=False, encoding="utf-8-sig")
