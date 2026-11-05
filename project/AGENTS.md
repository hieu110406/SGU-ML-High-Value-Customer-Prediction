# Phạm vi dữ liệu của dự án

- Nguồn raw duy nhất của dự án là `data/raw/Online Retail.xlsx`, sheet `Online Retail`.
  SHA-256 đã kiểm tra: `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`.
- Kết quả tính từ bộ dữ liệu từng được chọn nhầm không hợp lệ cho dự án. Không dùng
  số liệu, hình, bảng đã xử lý hay kết quả mô hình từ bộ đó làm bằng chứng cho raw hiện tại.
  Một số tệp của thành viên vẫn được giữ để đối chiếu công việc và phải có cảnh báo rõ.
- Trước khi nêu số liệu, tính lại từ raw duy nhất hoặc dùng workbook kết quả EDA đã ghi
  đúng SHA-256. Phân biệt dòng giao dịch, chứng từ và khách có mã; dữ liệu có một sheet.
- Quy tắc cleaning, encoding, scaling và tập đặc trưng chính thức vẫn chờ nhóm thống nhất.
  Không tự áp dụng, huấn luyện mô hình hoặc ghi đè dữ liệu processed để hoàn thành EDA.
- Giữ các hình EDA; kết quả EDA gộp vào một workbook, tránh tạo hàng loạt CSV/JSON.
