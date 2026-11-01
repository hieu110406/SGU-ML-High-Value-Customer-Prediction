# Dự án phân cụm khách hàng giá trị cao

Dự án phân tích Online Retail II, xây dựng đặc trưng RFM và thử nghiệm các
thuật toán phân cụm. Dữ liệu gốc trong `data/raw/` được giữ nguyên; các bước
tiền xử lý và kết quả được lưu ở những thư mục riêng.

## Bắt đầu

```bash
python -m pip install -r requirements.txt
```

Đặt dữ liệu Online Retail II vào `data/raw/`. Chưa có dữ liệu hoặc cấu hình
thực nghiệm mặc định nào được tạo trong bộ khung này.

## Cấu trúc

- `data/`: dữ liệu gốc, trung gian và đã xử lý.
- `configs/`: cấu hình YAML cho từng thực nghiệm.
- `notebooks/`: notebook EDA, phân cụm, đánh giá và profiling.
- `src/`: các module tiền xử lý, đặc trưng, mô hình và đánh giá.
- `experiments/`: đầu ra riêng của từng lần chạy, không ghi đè.
- `results/`: nhật ký Excel và kết quả dùng trong báo cáo.
- `app/`: ứng dụng demo Streamlit.
- `reports/`: báo cáo và slide.

Các module và notebook hiện là bộ khung; chưa triển khai pipeline phân tích.
