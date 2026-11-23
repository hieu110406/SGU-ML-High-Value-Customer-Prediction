"""Xử lý dữ liệu và dự đoán phía backend cho ứng dụng demo.

Pipeline cuối (B02-KM): log1p cho Frequency, Monetary (giữ Recency)
-> StandardScaler -> PCA giữ 90% phương sai -> K-Means k=3.
Dữ liệu đầu vào: bản tiền xử lý của An (đã loại hủy, giá <= 0, outlier Z-score).
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

# ---------- Đường dẫn & tham số (khớp notebook final) ----------
FINAL_DIR = Path(__file__).resolve().parents[1] / "results" / "final"
CLEAN_PATH = FINAL_DIR / "data" / "online_retail_clean_zscore.csv"

FEATURES = ["Recency", "Frequency", "Monetary"]
LOG_FEATURES = ["Frequency", "Monetary"]  # Recency giữ nguyên
PCA_VAR, K, RANDOM_STATE, N_INIT = 0.90, 3, 42, 20

# Tên cụm gợi ý theo trung vị RFM (xếp theo Monetary giảm dần)
SEGMENT_NAMES = [
    "Giá trị cao",
    "Mua ít, còn gần đây",
    "Mua một lần, lâu chưa quay lại",
]
SEGMENT_ACTIONS = {
    "Giá trị cao": "Giữ chân: ưu đãi thành viên, chăm sóc riêng, ưu tiên hàng mới.",
    "Mua ít, còn gần đây": "Thúc đẩy mua lại: combo, voucher lần mua kế, gợi ý sản phẩm.",
    "Mua một lần, lâu chưa quay lại": "Kích hoạt lại: email nhắc, ưu đãi quay lại; cân nhắc chi phí.",
}


def compute_rfm(df: pd.DataFrame) -> pd.DataFrame:
    """Giao dịch sạch -> bảng RFM theo khách (snapshot = ngày cuối + 1)."""
    df = df.copy()
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    snapshot = df["InvoiceDate"].max() + pd.Timedelta(days=1)
    df["Sales"] = df["Quantity"] * df["UnitPrice"]
    return (
        df.groupby("CustomerID")
        .agg(
            Recency=("InvoiceDate", lambda s: (snapshot - s.max()).days),
            Frequency=("InvoiceNo", "nunique"),
            Monetary=("Sales", "sum"),
        )
        .reset_index()
    )


def make_pipeline() -> Pipeline:
    pre = ColumnTransformer(
        [
            ("recency", "passthrough", ["Recency"]),
            ("log_fm", FunctionTransformer(np.log1p), LOG_FEATURES),
        ]
    )
    return Pipeline(
        [
            ("pre", pre),
            ("scaler", StandardScaler()),
            ("pca", PCA(n_components=PCA_VAR, svd_solver="full", random_state=RANDOM_STATE)),
            ("kmeans", KMeans(n_clusters=K, random_state=RANDOM_STATE, n_init=N_INIT)),
        ]
    )


def load_rfm() -> pd.DataFrame:
    return compute_rfm(pd.read_csv(CLEAN_PATH, dtype={"CustomerID": "string"}))


def fit_model(rfm: pd.DataFrame):
    """Huấn luyện pipeline, đặt tên cụm; trả (model, rfm có nhãn, hồ sơ cụm, map nhãn->tên)."""
    model = make_pipeline().fit(rfm[FEATURES])
    out = rfm.copy()
    out["Cluster"] = model.predict(rfm[FEATURES])

    # Đặt tên theo Monetary trung vị giảm dần: không phụ thuộc nhãn số của K-Means
    order = out.groupby("Cluster")["Monetary"].median().sort_values(ascending=False).index
    name_of = {int(c): SEGMENT_NAMES[i] for i, c in enumerate(order)}
    out["Segment"] = out["Cluster"].map(name_of)

    profile = out.groupby("Segment").agg(
        So_khach=("CustomerID", "size"),
        Recency=("Recency", "median"),
        Frequency=("Frequency", "median"),
        Monetary=("Monetary", "median"),
        Monetary_sum=("Monetary", "sum"),
    )
    profile["Ty_le_khach_%"] = 100 * profile["So_khach"] / profile["So_khach"].sum()
    profile["Ty_trong_Monetary_%"] = 100 * profile["Monetary_sum"] / profile["Monetary_sum"].sum()
    profile = profile.drop(columns="Monetary_sum").reindex(SEGMENT_NAMES)
    return model, out, profile, name_of


def pca_coords(model: Pipeline, rfm: pd.DataFrame) -> np.ndarray:
    """Toạ độ PCA (2 PC) của khách, đúng không gian mô hình được fit."""
    return model[:-1].transform(rfm[FEATURES])


def predict_one(model: Pipeline, name_of: dict, r: float, f: float, m: float):
    """Dự đoán cụm cho 1 khách mới. Trả (tên cụm, toạ độ PCA)."""
    x = pd.DataFrame([[r, f, m]], columns=FEATURES)
    z = model[:-1].transform(x)
    return name_of[int(model["kmeans"].predict(z)[0])], z[0]
