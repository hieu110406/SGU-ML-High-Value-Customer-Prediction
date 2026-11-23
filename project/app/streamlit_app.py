"""Giao diện demo Streamlit: phân khúc khách hàng bằng RFM (bản final B02-KM).

Chạy từ thư mục project/:  streamlit run app/streamlit_app.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backend as bk  # noqa: E402

st.set_page_config(page_title="Phân khúc khách hàng RFM", page_icon="🛍️", layout="wide")

# Màu cố định cho từng cụm, dùng chung mọi biểu đồ
COLORS = dict(zip(bk.SEGMENT_NAMES, ["#2CA02C", "#2878B5", "#D62728"]))


# ---------- Nạp dữ liệu & mô hình (cache để không chạy lại mỗi lần bấm) ----------
@st.cache_resource(show_spinner="Đang huấn luyện mô hình B02...")
def load_all():
    rfm = bk.load_rfm()
    model, out, profile, name_of = bk.fit_model(rfm)
    Z = bk.pca_coords(model, out)
    out["PC1"], out["PC2"] = Z[:, 0], Z[:, 1]
    return model, out, profile, name_of


model, data, profile, name_of = load_all()
pca = model["pca"]

# ---------- Đầu trang ----------
st.title("🛍️ Phân khúc khách hàng bằng RFM")
st.caption(
    "Nhóm 15 – DCT124C3 · Online Retail · Mô hình cuối: log1p(F, M) → StandardScaler "
    f"→ PCA 90% ({pca.n_components_} PC) → K-Means k={bk.K}"
)

c1, c2, c3 = st.columns(3)
c1.metric("Số khách hàng", f"{len(data):,}")
c2.metric("Số cụm", bk.K)
c3.metric("Phương sai PCA giữ lại", f"{pca.explained_variance_ratio_.sum():.1%}")

tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 Tổng quan cụm", "🗺️ Bản đồ PCA", "🔮 Dự đoán khách mới", "🔎 Tra cứu khách"]
)

# ---------- Tab 1: hồ sơ cụm ----------
with tab1:
    st.subheader("Hồ sơ trung vị RFM theo cụm")
    show = profile.rename(
        columns={"So_khach": "Số khách", "Ty_le_khach_%": "Tỷ lệ khách (%)",
                 "Ty_trong_Monetary_%": "Tỷ trọng Monetary (%)"}
    )
    st.dataframe(show.round(1), width="stretch")

    left, right = st.columns(2)
    with left:
        fig = px.pie(
            profile.reset_index(), names="Segment", values="So_khach",
            color="Segment", color_discrete_map=COLORS, title="Số khách mỗi cụm",
        )
        st.plotly_chart(fig, width="stretch")
    with right:
        fig = px.bar(
            profile.reset_index(), x="Segment", y="Ty_trong_Monetary_%",
            color="Segment", color_discrete_map=COLORS,
            title="Tỷ trọng tổng Monetary (%)", text_auto=".1f",
        )
        fig.update_layout(showlegend=False, xaxis_title=None)
        st.plotly_chart(fig, width="stretch")

    hi = profile.loc["Giá trị cao"]
    st.info(
        f"**Nhận xét:** nhóm *Giá trị cao* chỉ chiếm {hi['Ty_le_khach_%']:.1f}% khách "
        f"nhưng đóng góp {hi['Ty_trong_Monetary_%']:.1f}% tổng Monetary; hai nhóm còn lại "
        "đóng góp rất ít. Doanh thu tập trung mạnh vào một nhóm nhỏ."
    )
    st.subheader("Gợi ý hành động")
    for seg, action in bk.SEGMENT_ACTIONS.items():
        st.markdown(f"- **{seg}:** {action}")

# ---------- Tab 2: PCA ----------
with tab2:
    st.subheader("Các cụm trong không gian PCA (2 PC)")
    sample = st.slider("Số điểm hiển thị", 500, len(data), len(data), step=500)
    fig = px.scatter(
        data.sample(sample, random_state=42), x="PC1", y="PC2", color="Segment",
        color_discrete_map=COLORS, opacity=0.55,
        hover_data={"CustomerID": True, "Recency": True, "Frequency": True,
                    "Monetary": ":.0f", "PC1": False, "PC2": False},
    )
    fig.update_layout(
        xaxis_title=f"PC1 ({pca.explained_variance_ratio_[0]:.1%})",
        yaxis_title=f"PC2 ({pca.explained_variance_ratio_[1]:.1%})",
        legend_title=None, height=520,
    )
    st.plotly_chart(fig, width="stretch")
    st.info(
        "**Nhận xét:** ba cụm nằm liền kề dọc theo PC1, không có khoảng trống giữa các cụm. "
        "Đây là cách chia một dải liên tục theo mức độ mua hàng, không phải ba nhóm tách bạch."
    )

# ---------- Tab 3: dự đoán khách mới ----------
with tab3:
    st.subheader("Nhập RFM của một khách mới")
    a, b, c = st.columns(3)
    r = a.number_input("Recency (ngày từ lần mua gần nhất)", 1, 400, 30)
    f = b.number_input("Frequency (số hóa đơn)", 1, 100, 3)
    m = c.number_input("Monetary (tổng chi tiêu, GBP)", 1.0, 100000.0, 800.0, step=50.0)

    if st.button("Dự đoán cụm", type="primary"):
        seg, z = bk.predict_one(model, name_of, r, f, m)
        st.success(f"Khách thuộc cụm: **{seg}**")
        st.markdown(f"Gợi ý: {bk.SEGMENT_ACTIONS[seg]}")

        fig = px.scatter(
            data.sample(2000, random_state=42), x="PC1", y="PC2", color="Segment",
            color_discrete_map=COLORS, opacity=0.35,
        )
        fig.add_scatter(
            x=[z[0]], y=[z[1]], mode="markers", name="Khách mới",
            marker=dict(size=16, color="black", symbol="x"),
        )
        fig.update_layout(height=420, legend_title=None)
        st.plotly_chart(fig, width="stretch")
        st.caption(
            "Lưu ý: mô hình mô tả hành vi mua lịch sử, không dự báo giá trị tương lai. "
            "Giá trị nhập nên nằm trong khoảng dữ liệu huấn luyện."
        )

# ---------- Tab 4: tra cứu ----------
with tab4:
    st.subheader("Tra cứu khách theo CustomerID")
    cid = st.text_input("CustomerID", value=str(data["CustomerID"].iloc[0]))
    row = data[data["CustomerID"].astype(str) == cid.strip()]
    if row.empty:
        st.warning("Không tìm thấy CustomerID này trong 4.323 khách đã phân cụm.")
    else:
        row = row.iloc[0]
        st.success(f"Cụm: **{row['Segment']}**")
        x, y, z_ = st.columns(3)
        x.metric("Recency (ngày)", int(row["Recency"]))
        y.metric("Frequency (hóa đơn)", int(row["Frequency"]))
        z_.metric("Monetary", f"{row['Monetary']:,.0f}")
        st.markdown(f"Gợi ý: {bk.SEGMENT_ACTIONS[row['Segment']]}")

    st.divider()
    st.download_button(
        "⬇️ Tải toàn bộ kết quả phân cụm (CSV)",
        data[["CustomerID", "Recency", "Frequency", "Monetary", "Segment"]]
        .to_csv(index=False).encode("utf-8"),
        file_name="phan_cum_khach_hang_b02.csv", mime="text/csv",
    )
