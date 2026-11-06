"""Tiền xử lý dữ liệu Online Retail cho bài toán phân cụm RFM.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

RAW_PATH = Path(__file__).resolve().parents[1] / "data/raw/Online Retail.xlsx"
PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data/processed"
RAW_SHA256 = "43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d"


RENAME = {"InvoiceNo": "Invoice", "UnitPrice": "Price", "CustomerID": "Customer ID"}


SPECIAL_CODES = {
    "POST", "DOT", "M", "C2", "C3", "D", "S", "B", "BANK CHARGES",
    "ADJUST", "ADJUST2", "AMAZONFEE", "CRUK", "TEST001", "TEST002",
}
OUTLIER_COLS = ["Quantity", "Price"]
OUTLIER_K = 3.0  


def load_raw(path: Path | str = RAW_PATH) -> pd.DataFrame:
    """Đọc workbook vào bộ nhớ, không đổi tên cột và không làm sạch."""
    sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    return pd.concat(sheets.values(), ignore_index=True)


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
    """Làm sạch toàn bộ dữ liệu. Trả về `(clean, log_df)`."""
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
    """Ghi `data_clean.csv.gz` và `cleaning_log.csv` vào data/processed/."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    clean.to_csv(out / "data_clean.csv.gz", index=False, encoding="utf-8")
    log_df.to_csv(out / "cleaning_log.csv", index=False, encoding="utf-8-sig")
