"""Mã tiền xử lý đang chờ nhóm rà soát cho raw Online Retail của dự án.

Các hàm clean hiện dùng tên cột nội bộ Invoice/Price/Customer ID, chưa tương thích
trực tiếp với schema raw InvoiceNo/UnitPrice/CustomerID và chưa được phê duyệt.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RAW_PATH = Path(__file__).resolve().parents[1] / "data/raw/Online Retail.xlsx"
PROCESSED_DIR = Path("data/processed")


SPECIAL_CODES = {
    "POST", "DOT", "M", "C2", "C3", "D", "S", "B", "BANK CHARGES",
    "ADJUST", "ADJUST2", "AMAZONFEE", "CRUK", "TEST001", "TEST002",
}
OUTLIER_COLS = ["Quantity", "Price"]
OUTLIER_K = 3.0  


def load_raw(path: Path | str = RAW_PATH) -> pd.DataFrame:
    """Đọc workbook vào bộ nhớ; raw hiện tại có một sheet và chưa được làm sạch."""
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
    """Chính sách thử nghiệm cũ, chưa phê duyệt cho raw của dự án."""
    if {"InvoiceNo", "UnitPrice", "CustomerID"}.issubset(raw.columns):
        raise ValueError("clean_data chưa tương thích schema raw InvoiceNo/UnitPrice/CustomerID; "
                         "nhóm cần thống nhất chính sách và cập nhật pipeline trước khi chạy.")
    log: list[tuple[str, int]] = [("Dữ liệu nguồn đầu vào", len(raw))]
    df = raw.copy()

   
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
    """Ghi `data_clean.csv.gz` và `cleaning_log.csv` vào data/processed/."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    clean.to_csv(out / "data_clean.csv.gz", index=False, encoding="utf-8")
    log_df.to_csv(out / "cleaning_log.csv", index=False, encoding="utf-8-sig")
