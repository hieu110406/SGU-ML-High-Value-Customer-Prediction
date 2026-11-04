"""Tiền xử lý dữ liệu bán lẻ: giá trị thiếu, hóa đơn hủy và ngoại lai.

Các quy tắc ở đây được rút ra từ notebook `notebooks/01_eda/preprocessing_v1.ipynb`
(xem phần "Đề xuất phương án xử lý"). Dữ liệu gốc không bị sửa; mọi hàm trả về
bản sao mới.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

RAW_PATH = Path("data/raw/online_retail_II.xlsx")
PROCESSED_DIR = Path("data/processed")

# Mã hàng không phải sản phẩm (phí, bưu phí, điều chỉnh sổ sách, hàng thử...).
SERVICE_CODES = {
    "POST", "DOT", "M", "C2", "C3", "D", "S", "B", "BANK CHARGES",
    "ADJUST", "ADJUST2", "AMAZONFEE", "CRUK", "TEST001", "TEST002",
}


def load_raw(path: Path | str = RAW_PATH) -> pd.DataFrame:
    """Đọc và gộp các sheet của Online Retail II, thêm cột `Sheet` để truy vết."""
    sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    return pd.concat(
        [frame.assign(Sheet=name) for name, frame in sheets.items()],
        ignore_index=True,
    )


def standardize(df: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn hóa chuỗi: bỏ khoảng trắng, viết hoa mã hàng, đổi tên cột."""
    out = df.copy()
    out["Invoice"] = out["Invoice"].astype(str).str.strip().str.upper()
    out["StockCode"] = out["StockCode"].astype(str).str.strip().str.upper()
    out["Description"] = out["Description"].astype("string").str.strip()
    out["Country"] = out["Country"].astype("string").str.strip()
    return out.rename(columns={"Customer ID": "CustomerID"})


def reversed_sale_mask(sales: pd.DataFrame, cancels: pd.DataFrame) -> pd.Series:
    """Đánh dấu dòng bán đã bị hủy nguyên vẹn (cùng khách, mã hàng, số lượng, đơn giá).

    Khớp theo từng cặp một: mỗi dòng hủy chỉ "triệt tiêu" tối đa một dòng bán
    xảy ra trước nó.
    """
    key = ["CustomerID", "StockCode", "Price"]
    s = sales[key + ["Quantity", "InvoiceDate"]].copy()
    c = cancels[key + ["Quantity", "InvoiceDate"]].copy()
    c["Quantity"] = -c["Quantity"]
    s["rank"] = s.groupby(key + ["Quantity"]).cumcount()
    c["rank"] = c.groupby(key + ["Quantity"]).cumcount()
    merged = s.reset_index().merge(
        c, on=key + ["Quantity", "rank"], how="left", suffixes=("", "_cancel")
    )
    hit = merged["InvoiceDate_cancel"].notna() & (
        merged["InvoiceDate_cancel"] >= merged["InvoiceDate"]
    )
    return pd.Series(hit.to_numpy(), index=merged["index"]).reindex(sales.index).fillna(False)


def clean_transactions(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Áp dụng toàn bộ quy tắc tiền xử lý.

    Trả về `(sales, cancellations, log)`:
    - `sales`: dòng bán hợp lệ có mã khách hàng (đầu vào cho RFM);
    - `cancellations`: dòng hóa đơn hủy có mã khách hàng (dùng cho đặc trưng hoàn trả);
    - `log`: số dòng bị loại ở từng bước.
    """
    log: list[tuple[str, int]] = [("Dữ liệu gốc sau khi gộp sheet", len(raw))]
    df = standardize(raw)

    def step(name: str, frame: pd.DataFrame) -> pd.DataFrame:
        log.append((name, len(frame)))
        return frame

    cols = ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate",
            "Price", "CustomerID", "Country"]
    df = step("Bỏ dòng trùng hoàn toàn", df.drop_duplicates(subset=cols))
    df = step("Bỏ dòng thiếu CustomerID", df.dropna(subset=["CustomerID"]))
    df = df.assign(CustomerID=df["CustomerID"].astype(int))
    df = step("Bỏ mã hàng dịch vụ/phí/thử nghiệm", df[~df["StockCode"].isin(SERVICE_CODES)])

    is_cancel = df["Invoice"].str.startswith("C")
    cancels = df[is_cancel & (df["Quantity"] < 0)]
    sales = df[~is_cancel]
    log.append(("Tách hóa đơn hủy (tiền tố C) sang bảng riêng", len(sales)))
    sales = step("Bỏ dòng bán có Quantity <= 0 hoặc Price <= 0", sales[(sales["Quantity"] > 0) & (sales["Price"] > 0)])
    cancels = cancels[cancels["Price"] > 0]

    sales = sales.assign(LineValue=(sales["Quantity"] * sales["Price"]).round(2))
    cancels = cancels.assign(LineValue=(cancels["Quantity"] * cancels["Price"]).round(2))
    mask = reversed_sale_mask(sales, cancels)
    sales = step("Bỏ dòng bán đã bị hủy nguyên vẹn (đơn lỗi/ngoại lai)", sales[~mask])

    sales = sales.sort_values(["InvoiceDate", "Invoice"]).reset_index(drop=True)
    cancels = cancels.sort_values(["InvoiceDate", "Invoice"]).reset_index(drop=True)
    return sales, cancels, pd.DataFrame(log, columns=["Bước", "Số dòng còn lại"])


def save_processed(sales: pd.DataFrame, cancels: pd.DataFrame, log: pd.DataFrame,
                   out_dir: Path | str = PROCESSED_DIR) -> None:
    """Ghi dữ liệu đã làm sạch vào `data/processed/`."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sales.to_csv(out / "online_retail_clean.csv", index=False, encoding="utf-8")
    cancels.to_csv(out / "online_retail_cancellations.csv", index=False, encoding="utf-8")
    log.to_csv(out / "preprocessing_log.csv", index=False, encoding="utf-8-sig")
