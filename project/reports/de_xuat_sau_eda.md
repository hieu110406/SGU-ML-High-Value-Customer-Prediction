# Đề xuất sau EDA từ raw dự án — chờ nhóm thống nhất

Tài liệu này phục vụ thảo luận bước tiếp theo của bài toán **phân cụm khách hàng không giám sát**. Các lựa chọn bên dưới chưa phải quy tắc làm sạch, bộ mã hóa, phép chuẩn hóa hay bộ đặc trưng chính thức. Không có mô hình nào được huấn luyện hoặc so sánh trong đợt EDA này.

Các liên kết bằng chứng mở cùng một workbook; tra tên bảng trong sheet `Danh_muc_bang` để tìm đúng sheet dữ liệu.

Nguồn raw duy nhất là [`data/raw/Online Retail.xlsx`](../data/raw/Online%20Retail.xlsx). Đối chiếu phiên bản, SHA-256, sheet và thời gian chạy tại [sheet Metadata của workbook](../experiments/eda_raw_moi/ket_qua_eda.xlsx); xem kết quả đầy đủ trong [báo cáo EDA](bao_cao_eda.md) và [notebook](../notebooks/01_eda/eda.ipynb). Khảo sát Form 2 từ dữ liệu chọn nhầm không hợp lệ cho dự án và cần được tính lại trước khi dùng.

> **Cập nhật 06/11/2026:** đây là tài liệu lựa chọn chính sách chính thức. Cấu hình thử nghiệm riêng được người dùng cho phép không đồng nghĩa nhóm đã duyệt các lựa chọn này; xem [báo cáo tiến độ](bao_cao_tien_do.md).

## 1. Bằng chứng và phạm vi cần mang sang bước tiếp theo

| Bằng chứng từ raw duy nhất | Kết quả thực tế | Nguồn kiểm tra và hàm ý |
|---|---|---|
| Phiên bản raw | SHA-256 `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`; sheet `Online Retail`; 541.909 dòng, 8 cột | [Metadata](../experiments/eda_raw_moi/ket_qua_eda.xlsx); kết quả tính từ file raw duy nhất |
| Thiếu CustomerID | 135.080 dòng, 24,93%; giá trị có dấu 1.447.682,12 GBP; tổng trị tuyệt đối 2.062.871,16 GBP | [Thiếu - missing_values](../experiments/eda_raw_moi/ket_qua_eda.xlsx), [các cờ chất lượng - quality_issues](../experiments/eda_raw_moi/ket_qua_eda.xlsx). Phần bị tách khỏi cấp khách không nhỏ; trị tuyệt đối khác tổng có dấu |
| Thiếu Description | 1.454 dòng, 0,27%; cùng thiếu CustomerID, UnitPrice = 0 và giá trị dòng = 0 | [Thiếu - missing_values](../experiments/eda_raw_moi/ket_qua_eda.xlsx), [các cờ chất lượng - quality_issues](../experiments/eda_raw_moi/ket_qua_eda.xlsx). Không mặc định thiếu mô tả đồng nghĩa mất giá trị mua |
| Dòng trùng dư trên đủ 8 cột | 5.268 dòng, 0,97%; gắn 1.933 hóa đơn và 960 khách có mã; giá trị có dấu 21.740,98 GBP | [Cờ chất lượng - quality_issues](../experiments/eda_raw_moi/ket_qua_eda.xlsx). “Dư” là các bản sao sau lần xuất hiện đầu, chưa kết luận lỗi nhập |
| C và Quantity âm | C: 9.288 dòng / 3.836 chứng từ / 1.589 khách có mã, giá trị có dấu −896.812,49 GBP; lượng âm: 10.624 dòng, trong đó 1.336 không có C | [Cờ chất lượng - quality_issues](../experiments/eda_raw_moi/ket_qua_eda.xlsx). C là tập con của lượng âm trong raw này; không cộng hai tập |
| Giá và lượng bằng 0/âm | Quantity = 0: 0 dòng; UnitPrice = 0: 2.515 dòng; UnitPrice < 0: 2 dòng | [Cờ chất lượng - quality_issues](../experiments/eda_raw_moi/ket_qua_eda.xlsx). Hai dòng giá âm là dấu hiệu cần đọc chứng từ điều chỉnh, không thay giá tự động |
| Quốc gia và định danh | 38 nhãn Country; United Kingdom 495.478 dòng, 91,43%; 8 khách có nhiều quốc gia | [Quốc gia - country_counts](../experiments/eda_raw_moi/ket_qua_eda.xlsx), [kiểm tra định danh - identifier_conflicts](../experiments/eda_raw_moi/ket_qua_eda.xlsx). One-hot cần cân nhắc lệch nhóm và cách tổng hợp lên khách |
| Mã hàng ↔ mô tả | 650 StockCode có hơn một Description không thiếu theo chuỗi gốc; 172 mô tả xuất hiện với nhiều mã | [Kiểm tra mã–mô tả - stock_description_audit](../experiments/eda_raw_moi/ket_qua_eda.xlsx), [kiểm tra định danh - identifier_conflicts](../experiments/eda_raw_moi/ket_qua_eda.xlsx). Không tự điền theo mã mà chưa có quy tắc tin cậy |
| Phạm vi khách khảo sát | 397.884 dòng, 18.532 hóa đơn, 4.338 khách; giá trị mua tạm tính 8.911.407,904 GBP trước làm tròn | [Phạm vi - analysis_scopes](../experiments/eda_raw_moi/ket_qua_eda.xlsx), [tóm tắt khách - customer_summary](../experiments/eda_raw_moi/ket_qua_eda.xlsx). Giữ dòng trùng, chưa đối soát trả và chưa phân loại mã dịch vụ |
| Khách chỉ một hóa đơn | 1.493 / 4.338 khách = 34,42%; gap chỉ xác định cho 2.845 khách | [Tóm tắt khách - customer_summary](../experiments/eda_raw_moi/ket_qua_eda.xlsx), [số quan sát từng cặp - correlations_customer_pairwise_counts](../experiments/eda_raw_moi/ket_qua_eda.xlsx). Điền gap = 0 sẽ biến thiếu có cấu trúc thành “mua cùng thời điểm” |
| Đuôi phân phối ở cấp dòng | Quantity: median 3, p99 100, min/max −80.995 / 80.995; UnitPrice: median 2,08, p99 18, max 38.970 GBP | [Mô tả số - numeric_summary](../experiments/eda_raw_moi/ket_qua_eda.xlsx). Khoảng cực trị lớn hơn nhiều phần thân phân phối; chưa chứng minh là lỗi |
| Đuôi phân phối ở cấp khách | Số đơn: median 2, p99 30, max 209; tổng giá trị: median 674,485, p99 19.880,9957, max 280.206,02 GBP; AOV: median 293,90, p99 2.031,1612, max 84.236,25 GBP | [Tóm tắt khách - customer_summary](../experiments/eda_raw_moi/ket_qua_eda.xlsx). Scale theo min/max hoặc mean/std cần kiểm tra ảnh hưởng đuôi dài |
| Liên hệ số đơn–tổng giá trị | Trên 4.338 khách: Pearson ≈ 0,554, Spearman ≈ 0,807 | [Pearson - correlations_customer_pearson](../experiments/eda_raw_moi/ket_qua_eda.xlsx), [Spearman - correlations_customer_spearman](../experiments/eda_raw_moi/ket_qua_eda.xlsx). Liên hệ có phần đến từ M = F × AOV; không suy nhân quả |
| Biên thời gian | 01/12/2010 08:26 → 09/12/2011 12:50; tháng 12/2011 chỉ đến ngày 09 | [Theo tháng - monthly_activity](../experiments/eda_raw_moi/ket_qua_eda.xlsx). Không so tổng tháng 12/2011 với tháng đủ dữ liệu như cùng độ dài |

Tỷ lệ làm tròn hai chữ số; giá trị GBP được hiển thị đến hai chữ số khi không cần giữ độ chính xác phân vị. Việc cộng `Quantity × UnitPrice` giữ nguyên độ chính xác tính toán; không làm tròn từng dòng. Các tổng có dấu bên trên là tổng đại số, không gọi là doanh thu thuần đã đối soát.


Các biểu đồ khách hàng dùng **phạm vi khảo sát tạm thời**: có CustomerID và InvoiceDate hợp lệ, InvoiceNo không bắt đầu bằng `C`, Quantity > 0, UnitPrice > 0. Giữ các dòng trùng; chưa áp quy tắc phân loại mã hàng, ghép trả hàng hoặc lọc ngoại lệ. Vì vậy, tổng Quantity và số StockCode là lượng/mã của các dòng đang khảo sát, chưa được khẳng định là số lượng/số sản phẩm thực. Cộng `Quantity × UnitPrice` trong phạm vi này cho **giá trị mua tạm tính**, không phải doanh thu thuần đã đối soát. Đây là điều kiện đọc biểu đồ, không phải quyết định clean của nhóm.

Phải phân biệt ba đơn vị: **dòng giao dịch**, **hóa đơn** và **khách hàng có mã**. Nhiều cờ lỗi có thể cùng xuất hiện trên một dòng; không cộng tỷ lệ thiếu ID, hủy, lượng âm và giá bất thường như các tập độc lập. Chỉ số hành vi khảo sát không đại diện cho khách vô danh hoặc toàn bộ lịch sử thật của khách hàng.

## 2. Phương án data cleaning

Mỗi hàng dưới đây nêu ít nhất hai hướng có thể thử sau khi nhóm quyết định. “Giữ” cũng là một phương án cần đánh giá; không mặc định ngoại lệ hay dòng trùng là lỗi.

| Vấn đề và bằng chứng cần đọc | Phương án A: ưu điểm / nhược điểm | Phương án B hoặc C: ưu điểm / nhược điểm | Tác động cần đo và câu hỏi bổ sung | Trạng thái |
|---|---|---|---|---|
| Thiếu CustomerID; bảng thiếu và ảnh hưởng tới giá trị dòng trong EDA | Giữ dòng trong thống kê giao dịch, tách khỏi thống kê cấp khách. Bảo toàn bức tranh giao dịch; không thể gán hành vi cho một người cụ thể. | Loại khỏi tập phân cụm nhưng lưu thống kê phần bị loại. Dễ xác định đơn vị khách; có thể gây thiên lệch nếu nhóm vô danh có giỏ hàng khác. Chỉ phục hồi ID khi có khóa nguồn đáng tin cậy. | So sánh phân bố tháng, quốc gia, Quantity và giá trị dòng giữa có/thiếu ID. Không gán tất cả thành một “Guest” và coi đó là khách thật; không suy ID từ quốc gia/mặt hàng. | Chờ nhóm thống nhất |
| Thiếu Description và mã hàng có nhiều mô tả | Giữ thiếu nếu phân tích không dùng mô tả. Ít giả định; hạn chế diễn giải danh mục sản phẩm. | Bổ sung theo StockCode khi quan hệ đủ tin cậy và ghi nguồn/quy tắc; hoặc loại khỏi riêng phân tích cần Description. Có thể tăng độ phủ; mô tả thay đổi, lỗi gõ và mã điều chỉnh có thể làm gán sai. | Kiểm tra một mã → nhiều mô tả và một mô tả → nhiều mã, phân tách theo thời gian; đối chiếu mẫu trước khi lấy mode. Đo số dòng/mã có thể phục hồi và số còn mâu thuẫn. | Chờ nhóm thống nhất |
| Dòng trùng hoàn toàn hoặc lặp InvoiceNo–StockCode | Giữ toàn bộ. Bảo toàn raw và khả năng một mặt hàng xuất hiện nhiều dòng hợp lệ; có thể đếm lặp giá trị/lượng. | Loại riêng bản sao hoàn toàn trên 8 cột; hoặc điều tra theo hóa đơn trước khi loại. Giảm nguy cơ nhập lặp; có thể xóa các dòng mua thật giống nhau. InvoiceNo–StockCode không tự là khóa duy nhất. | Đo chênh lệch dòng, hóa đơn, khách và tổng giá trị khi bỏ trùng; xem số lần lặp và các dòng trong cùng hóa đơn. Xác nhận nghiệp vụ trước khi chọn khóa. | Chờ nhóm thống nhất |
| Chứng từ tiền tố C và Quantity âm | Tách góc nhìn mua và góc nhìn hủy/âm. Dễ giải thích hành vi mua; chưa phản ánh giá trị sau trả hàng. | Giữ giá trị có dấu để khảo sát số dư; hoặc chỉ tính giá trị sau trả hàng khi đã ghép được chứng từ với giao dịch gốc. Phản ánh điều chỉnh tốt hơn; việc ghép có thể thiếu hoặc nhiều kết quả. | Kiểm tra giao chéo C × dấu Quantity, mã/khách/thời điểm của dòng đối ứng, hoàn một phần, giá không khớp và giao dịch gốc ngoài cửa sổ. Không mặc định mọi âm là trả hàng. | Chờ nhóm thống nhất |
| Quantity = 0, UnitPrice = 0 hoặc âm | Giữ và gắn cờ để kiểm tra điều chỉnh/hàng tặng. Bảo toàn ngữ cảnh; một số phép log và tỷ số không dùng được. | Tách khỏi riêng góc nhìn mua có giá trị dương; hoặc loại có điều kiện sau xác minh. Phạm vi mua dễ diễn giải; có thể bỏ hàng tặng/phí hoặc chứng từ kế toán hợp lệ. | Đọc mẫu cực trị, Description/StockCode, ID và hóa đơn; đo ảnh hưởng giá trị dòng thay vì chỉ đếm dòng. Không tự thay giá âm/0 bằng trung bình. | Chờ nhóm thống nhất |
| Thiếu hoặc mâu thuẫn InvoiceNo/CustomerID/Country/InvoiceDate | Giữ cờ và tách các hóa đơn chưa giải quyết khỏi phép tổng hợp cần khóa xác định. Rõ mức độ tin cậy; giảm độ phủ. | Đối chiếu nguồn và sửa có nhật ký; nếu không giải quyết được, giới hạn đơn vị tổng hợp phù hợp. Tăng độ tin cậy; cần bằng chứng ngoài raw. | Kiểm tra một hóa đơn → nhiều khách, nhiều thời điểm/quốc gia; một khách → nhiều quốc gia có thể hợp lệ. Không áp quốc gia đầu tiên hoặc mode vào toàn bộ khách mà không ghi quy tắc. | Chờ nhóm thống nhất |
| Mã dịch vụ/điều chỉnh lẫn sản phẩm | Giữ tất cả mã và gọi đúng là “mã hàng quan sát”. Tránh loại nhầm; chỉ số đa dạng/lượng chưa mang nghĩa sản phẩm. | Lập danh mục vai trò mã đã duyệt, tính chỉ số sản phẩm trên mã được xác nhận; hoặc giữ phí trong giá trị nhưng tách khỏi lượng/độ đa dạng. Dễ diễn giải hơn; danh mục cần bảo trì và xử lý mã chưa phân loại. | Đối chiếu tần suất, mô tả và đóng góp giá trị của từng mã. Regex/mã chứa chữ chỉ là dấu hiệu rà soát, không đủ làm nhãn sản phẩm. | Chờ nhóm thống nhất |
| Ngoại lệ ở dòng hoặc khách hàng | Giữ và gắn cờ theo phân vị/IQR, mô tả nhóm giá trị cao riêng. Bảo toàn khách mua sỉ; khoảng cách và trung bình có thể bị chi phối. | Khảo sát biến đổi phù hợp hoặc winsorize theo ngưỡng được duyệt; chỉ loại khi có bằng chứng sai. Giảm chi phối cực trị; có thể làm mất phân khúc giá trị cao và thay đổi thứ hạng. | Đọc boxplot/phân vị/mẫu cực trị, đo số khách và tỷ trọng giá trị bị tác động ở mỗi ngưỡng. IQR là cờ điều tra, không phải bằng chứng lỗi. | Chờ nhóm thống nhất |
| Tháng đầu/cuối và lịch quan sát không đầy đủ | Giữ cả cửa sổ, gắn nhãn tháng chưa đủ và hạn chế so sánh. Bảo toàn dữ liệu; tổng tháng không có cùng độ phơi nhiễm. | So sánh riêng các tháng đủ ngày hoặc cùng số ngày lịch. Tăng tính tương đương; mất một phần giao dịch và vẫn có mùa vụ. | Kiểm tra ngày/giờ phủ thực tế, ngày không giao dịch và mốc cắt; không tự coi ngày không có dữ liệu là ngày cửa hàng đóng cửa. | Chờ nhóm thống nhất |

Nếu nhóm muốn thử các phương án, mỗi nhánh thử cần có bảng tác động riêng gồm điều kiện, số dòng/hóa đơn/khách trước–sau, tổng giá trị có dấu/giá trị mua tương ứng và số khách giá trị cao bị ảnh hưởng. Không ghi đè raw, processed hay kết quả lịch sử.

## 3. Phương án encoding

Không cần mã hóa mọi cột. CustomerID và InvoiceNo là khóa định danh; StockCode là mã danh mục, không được dùng như số liên tục. Country ở cấp dòng cũng chưa phải thuộc tính duy nhất của khách; cần thống nhất cách tổng hợp nếu một khách xuất hiện ở nhiều quốc gia.

| Lựa chọn | Khi có thể cân nhắc | Ưu điểm | Nhược điểm / tác động cần đánh giá | Việc cần thống nhất |
|---|---|---|---|---|
| Không đưa biến phân loại vào đầu vào phân cụm | Đặc trưng số hành vi đã trả lời mục tiêu; dùng quốc gia/mã hàng để mô tả cụm sau này | Ít chiều, dễ giải thích khoảng cách | Có thể bỏ khác biệt địa lý/sở thích; chưa thể kết luận đủ thông tin chỉ từ EDA | Xác định vai trò biến: đầu vào hay chỉ profiling |
| One-hot cho danh mục đã chọn | Số nhóm vừa phải và có ý nghĩa ở cấp khách | Không giả định thứ tự danh mục; tên cột dễ đọc | Tăng số chiều; nhiều cột có thể tăng trọng số của khối danh mục; cần xử lý nhóm chưa gặp | Quy tắc khách nhiều quốc gia, tập mức hợp lệ, trọng số khối số/danh mục |
| Gộp nhóm hiếm rồi one-hot | Phân bố danh mục lệch và nhiều nhóm rất ít quan sát | Giảm chiều, hạn chế nhóm quá nhỏ | Gộp các nhóm khác nghĩa; kết quả nhạy ngưỡng; nhóm hiếm có thể quan trọng | Mẫu số là khách hay dòng; thử hơn một ngưỡng bằng chứng, giữ mapping có phiên bản |
| Frequency encoding | Tần suất danh mục có ý nghĩa cần khảo sát | Gọn, ít cột | Hai nhóm có tần suất bằng nhau trở nên giống nhau; áp thứ tự tần suất vào khoảng cách; tỷ trọng thay đổi theo cửa sổ | Tính tần suất trên dữ liệu phát triển phù hợp, quy tắc nhóm mới và ổn định qua thời gian |
| Tỷ lệ hành vi theo nhóm sản phẩm/quốc gia | Cần biểu diễn cơ cấu mua của từng khách thay vì một nhãn duy nhất | Giữ hành vi nhiều nhóm, có thể diễn giải trực tiếp | Cần danh mục sản phẩm đáng tin cậy; các tỷ lệ có tổng 1 tạo phụ thuộc; nhiều chiều và mẫu số nhỏ | Tỷ lệ theo dòng/đơn/lượng/giá trị, nhóm hàng, xử lý khách ít đơn và nhóm chưa phân loại |

Chưa có nhãn mục tiêu phù hợp nên **không đề xuất target encoding** cho bài toán không giám sát. Không dùng label encoding để tạo khoảng cách tùy ý giữa quốc gia hoặc StockCode. Khi triển khai sau này, mapping và tần suất phải học trên phần dữ liệu phát triển tương ứng, không nhìn sang cửa sổ đánh giá.

## 4. Phương án scaling và biến đổi phân phối

Các phân vị ở phần 1 và hình phân phối khách hàng là bằng chứng để chọn nhánh thử; chưa có scaler nào được fit trong EDA này. Chênh lệch đơn vị GBP, số hóa đơn, ngày và lượng có thể làm thay đổi khoảng cách phân cụm. Trung bình/mức lệch của **mã định danh** không có ý nghĩa nghiệp vụ và không phải đầu vào scaling.

| Lựa chọn | Liên hệ bằng chứng EDA | Ưu điểm | Nhược điểm / câu hỏi cần kiểm tra | Trạng thái |
|---|---|---|---|---|
| Không scaling | Đối chiếu thang đo, IQR và max của giá trị mua với số hóa đơn/ngày | Có đối chứng trên đơn vị gốc | Biến thang lớn dễ chi phối khoảng cách; không mặc định đây là đầu vào phù hợp | Đề xuất, chưa chốt |
| StandardScaler | So sánh mean–median, std và các cực trị | Đưa biến về độ lệch chuẩn để so sánh | Mean/std nhạy ngoại lệ; phân phối vẫn lệch sau chuẩn hóa | Đề xuất, chưa chốt |
| MinMaxScaler | Đối chiếu min–max với p99 và IQR | Khoảng giá trị dễ mô tả | Một cực trị có thể nén phần lớn khách; dữ liệu mới có thể vượt khoảng đã học | Đề xuất, chưa chốt |
| RobustScaler | Đối chiếu median/IQR và tỷ lệ vượt hàng rào IQR | Tâm/thang ít nhạy cực trị hơn mean/std | Không xóa ngoại lệ hoặc làm phân phối thành chuẩn; cần xử lý IQR bằng 0 | Đề xuất, chưa chốt |
| Biến đổi phân phối rồi scaling | Histogram/boxplot có đuôi dài; kiểm tra điều kiện từng biến | `log1p` có thể nén đuôi các biến không âm trước khi scale | Thay đổi ý nghĩa khoảng cách; không áp `log1p` lên dữ liệu có dấu/âm; cần giữ công thức và phép đảo | Đề xuất, chưa chốt |

So sánh tối thiểu hai nhánh hợp lý, chẳng hạn StandardScaler trên biến gốc và `log1p` rồi RobustScaler trên biến không âm, chỉ sau khi thống nhất phạm vi và bộ biến. Không mặc định biến đổi mọi biến. Với giá trị có dấu, phải nghiên cứu phép biến đổi khác hoặc giữ nguyên, không dịch hằng số tùy tiện để dùng log. Gap của khách một đơn vẫn thiếu; chọn phương án dùng riêng/tách chỉ báo/không đưa vào bộ biến, không tự điền 0.

Khi triển khai thí nghiệm ở giai đoạn sau, tham số scaler, ngưỡng nhóm hiếm, phép điền thiếu và ngưỡng ngoại lệ phải fit trên phần dữ liệu phát triển tương ứng. Các biến lịch sử phải được tổng hợp đến cùng mốc cắt đã xác định để hạn chế leakage. EDA toàn bộ raw hiện tại không tự biến thành thiết kế đánh giá tương lai.

## 5. Feature engineering: bắt đầu từ hành vi thủ công

Gọi `P` là tập dòng mua đủ điều kiện sau **quy tắc được nhóm duyệt trong tương lai**; `I_c` là tập hóa đơn khác nhau của khách `c` trong cửa sổ `[t_start, t_ref)`, `N_c = |I_c|`, `v_l = Quantity_l × UnitPrice_l`, `V_i = Σv_l`. Thời điểm hóa đơn `t_i` phải được xác định khi một hóa đơn có nhiều thời điểm. Bảng dưới là **công thức dự kiến**, chưa phải bảng đặc trưng chính thức. Tên trong ngoặc là biến tương ứng chỉ phục vụ khảo sát trong notebook mới.

### 5.1. Đặc trưng hành vi thủ công

| Tên biến dự kiến | Đơn vị | Công thức dự kiến / điều kiện | Ý nghĩa | Nguồn dữ liệu | Rủi ro / trùng thông tin | Trạng thái |
|---|---|---|---|---|---|---|
| Số hóa đơn (`n_invoices`) | Hóa đơn/khách/cửa sổ | `N_c = nunique(InvoiceNo)` trên P | Tần suất mua quan sát được | CustomerID, InvoiceNo, InvoiceDate và điều kiện P | Trùng trực tiếp Frequency; không đếm dòng thành đơn; đơn hủy không tự là mua | Đề xuất, chưa chốt |
| Số ngày mua (`active_days`) | Ngày lịch/khách | Số ngày `date(t_i)` khác nhau | Mức phân bố hoạt động theo ngày | InvoiceDate, InvoiceNo, CustomerID | Phụ thuộc múi giờ chưa cung cấp; liên quan số hóa đơn, không phải số ngày theo dõi | Đề xuất, chưa chốt |
| Tổng giá trị mua (`monetary`) | GBP/khách/cửa sổ | `Σ_i V_i` theo quy tắc giá trị đã duyệt | Quy mô mua lịch sử | Quantity, UnitPrice, InvoiceNo, CustomerID | Trùng Monetary; tổng gộp khác giá trị sau trả hàng; có thể gồm phí nếu giữ | Đề xuất, chưa chốt |
| Giá trị trung bình hóa đơn (`avg_order_value`) | GBP/hóa đơn | `Σ_i V_i / N_c`, N_c > 0 | Mức chi trên mỗi đơn đủ điều kiện | Cùng nguồn tổng giá trị và số hóa đơn | Quan hệ công thức với M và F, không phải thông tin độc lập | Đề xuất, chưa chốt |
| Số mã sản phẩm khác nhau (`n_stock_codes` trong khảo sát chỉ là mã) | Mã sản phẩm/khách | `nunique(StockCode)` sau đối chiếu danh mục vai trò mã | Độ đa dạng danh mục mua | StockCode, Description, CustomerID | Mã dịch vụ/chưa phân loại làm sai ý nghĩa; nhiều mã chưa chắc nhiều sản phẩm thực | Đề xuất, chưa chốt |
| Tổng lượng sản phẩm (`total_quantity` trong khảo sát gồm mã chưa phân loại) | Đơn vị sản phẩm/khách | `ΣQuantity_l` trên dòng được xác nhận là sản phẩm | Quy mô số lượng mua | Quantity, StockCode và danh mục vai trò mã | Không cộng đơn vị phí với hàng; liên hệ số đơn và lượng/đơn | Đề xuất, chưa chốt |
| Lượng trung bình mỗi hóa đơn | Đơn vị sản phẩm/hóa đơn | Tổng lượng sản phẩm / N_c với mẫu số đã duyệt | Quy mô giỏ hàng theo lượng | Quantity, InvoiceNo, CustomerID, vai trò mã | Hóa đơn chỉ có phí có thể ảnh hưởng mẫu số; trùng thông tin lượng/F | Đề xuất, chưa chốt |
| Khoảng hoạt động quan sát (`observed_span_days`) | Ngày | `(max(t_i) − min(t_i))/86.400 giây` | Độ dài giữa lần mua đầu/cuối trong cửa sổ | InvoiceDate, InvoiceNo, CustomerID | Khách một đơn = 0 có căn cứ; không phải tuổi thật của quan hệ khách hàng; chịu cắt trái/phải | Đề xuất, chưa chốt |
| Thời gian từ lần mua đầu quan sát | Ngày | `(t_ref − min(t_i))/86.400 giây` | Mức phơi nhiễm quan sát từ lần đầu thấy | InvoiceDate và mốc tham chiếu | Khác observed_span; không biết thời điểm trở thành khách thật; liên quan recency | Đề xuất, chưa chốt |
| Khoảng cách mua trung bình (`avg_purchase_gap_days`) | Ngày/khoảng | Trung bình các `t_(j)−t_(j−1)` sau sắp xếp hóa đơn; N_c < 2 → thiếu | Nhịp mua quan sát được | InvoiceDate, InvoiceNo, CustomerID | Hai hóa đơn cùng thời điểm có gap 0 thật; khách một đơn không có gap; liên hệ span/(F−1) khi cùng quy tắc | Đề xuất, chưa chốt |
| Tỷ lệ dòng có tiền tố C / tỷ lệ lượng âm | Tỷ lệ, mẫu số phải công bố | Số dòng thỏa cờ / tổng dòng thuộc phạm vi của khách | Dấu hiệu điều chỉnh cần khảo sát | Raw trước khi bỏ C/âm | Không tự gọi là return_rate; C và âm chồng lấn; cần chọn mẫu số dòng/đơn/lượng | Đề xuất, chưa chốt |
| Tỷ lệ trả hàng đã đối soát | Tỷ lệ theo đơn/lượng/giá trị | Chỉ tính sau ghép trả với giao dịch gốc và duyệt mẫu số | Hành vi hoàn trả xác minh được | Chứng từ trả, giao dịch gốc, khách, mã, thời gian | Giao dịch gốc ngoài cửa sổ; ghép mơ hồ; chưa đủ bằng chứng thì giữ thiếu, không gán 0 | Đề xuất, chưa chốt |
| Tỷ trọng mua theo nhóm | Tỷ lệ/khách | Giá trị hoặc số đơn nhóm / mẫu số tương ứng đã chọn | Cơ cấu sở thích/địa lý | Country hoặc danh mục sản phẩm đã duyệt | Tỷ lệ tổng 1, mẫu nhỏ, phụ thuộc quy tắc nhóm và giá trị gộp/thuần | Đề xuất, chưa chốt |

Không dùng tương quan cao như quy tắc tự động loại biến. Trước tiên đọc Pearson, Spearman, số quan sát từng cặp và scatter; sau đó đối chiếu công thức. Ví dụ M = F × AOV và gap trung bình liên hệ span/(F−1) làm một phần quan hệ xuất phát từ cấu tạo biến. Khách một đơn tạo thiếu có cấu trúc ở gap; không chỉ chọn complete-case mà bỏ qua thay đổi dân số.

### 5.2. RFM

| Tên biến | Đơn vị | Công thức dự kiến | Ý nghĩa | Nguồn dữ liệu | Rủi ro / trùng thông tin | Trạng thái |
|---|---|---|---|---|---|---|
| Recency (`recency_days`) | Ngày | `(t_ref − max(t_i))/86.400 giây`, thống nhất dùng thời điểm hay ngày lịch | Khoảng cách từ lần mua cuối đến mốc chung | InvoiceDate, InvoiceNo, CustomerID và t_ref | Không dùng ngày cuối riêng của từng khách; nhạy mốc cắt và múi giờ; khác churn | Đề xuất, chưa chốt |
| Frequency | Hóa đơn/khách/cửa sổ | `N_c` trên tập mua đủ điều kiện | Tần suất mua | InvoiceNo, CustomerID | Trùng n_invoices; không thay bằng số dòng; khách vào muộn có cửa sổ quan sát ngắn | Đề xuất, chưa chốt |
| Monetary | GBP/khách/cửa sổ | `Σ_i V_i` theo quy tắc gộp hoặc sau trả đã duyệt | Quy mô giá trị mua lịch sử | Quantity, UnitPrice, InvoiceNo, CustomerID | Trùng monetary; không đồng nghĩa lợi nhuận hoặc giá trị tương lai | Đề xuất, chưa chốt |

Khảo sát hiện tại dùng `t_ref = 2011-12-10 00:00`, là nửa đêm kế tiếp sau ngày lớn nhất của raw; thời gian nguồn chưa cung cấp múi giờ. Với mỗi hóa đơn, khảo sát dùng thời điểm sớm nhất để tính khoảng cách giữa các hóa đơn khác nhau; khách một hóa đơn giữ gap thiếu. Đây là lựa chọn EDA cần được đọc cùng [phạm vi/công thức - analysis_scopes](../experiments/eda_raw_moi/ket_qua_eda.xlsx). Khi xây bộ RFM chính thức, nhóm cần chốt một `t_ref` chung, cửa sổ lịch sử, quy tắc hóa đơn mua, giá trị gộp/sau trả và điều kiện ID. Không tự dùng những công thức này để ghi ra bộ feature chính thức trong đợt EDA.

### 5.3. Ba hướng bộ biến để nhóm cân nhắc

| Hướng | Ví dụ phạm vi đề xuất | Ưu điểm | Nhược điểm / việc cần kiểm tra |
|---|---|---|---|
| Chỉ một số hành vi thủ công | Số đơn, AOV, đa dạng sản phẩm đã xác minh, active_days; gap chỉ khi có cách xử lý thiếu phù hợp | Linh hoạt, bám hành vi cần diễn giải | Dễ trùng công thức/thông tin; cần kiểm soát số chiều, thiếu và vai trò mã |
| Chỉ RFM | Recency, Frequency, Monetary | Gọn, dễ giải thích lịch sử mua | Có thể bỏ cơ cấu sản phẩm, nhịp mua và hoàn trả; chịu ảnh hưởng cửa sổ, ngoại lệ |
| RFM + hành vi được chọn | RFM cùng AOV/đa dạng/nhịp mua hoặc tỷ lệ đã xác minh | Bổ sung chiều hành vi có lý do nghiệp vụ | Không thêm bản sao Frequency/Monetary; cân nhắc trọng số khối biến và quan hệ công thức |

EDA chưa xác định hướng nào tốt hơn. Việc so sánh bộ biến, phép scale và mô hình thuộc giai đoạn tiếp theo sau khi nhóm thống nhất chính sách dữ liệu và cách đánh giá.

## 6. Danh sách quyết định chờ nhóm

1. Xác nhận phiên bản raw duy nhất, cửa sổ phân tích, mốc tham chiếu và hạn chế múi giờ; chốt cách so sánh tháng chưa đủ.
2. Chốt cách tách khách vô danh và đối chiếu thiên lệch giữa có/thiếu CustomerID; không gom thành một khách thật.
3. Chọn giữ, điều tra hay bỏ bản sao hoàn toàn; xác nhận khóa hóa đơn và cách xử lý nhiều thời điểm/quốc gia.
4. Phân biệt tập mua, tập hủy/điều chỉnh và giá trị sau trả; chốt bằng chứng ghép giao dịch, mẫu số tỷ lệ hoàn trả.
5. Duyệt cách xử lý Quantity/UnitPrice 0 hoặc âm, Description thiếu và các mã dịch vụ; lập danh mục vai trò mã nếu cần chỉ số sản phẩm.
6. Chọn giữ/gắn cờ/biến đổi/điều tra ngoại lệ; đánh giá khách mua sỉ và phần giá trị bị tác động ở nhiều ngưỡng.
7. Quyết định biến phân loại là đầu vào hay chỉ mô tả cụm; nếu đưa vào, chọn ít nhất hai hướng encoding để thảo luận cùng số chiều và trọng số.
8. Chọn nhánh scaling dựa trên phân vị thực tế; thống nhất cách xử lý thiếu ở gap mà không biến “chưa xác định” thành 0.
9. Chọn hành vi thủ công, RFM hoặc kết hợp; công bố công thức, đơn vị, cửa sổ, biến trùng và trạng thái từng biến.
10. Trước khi triển khai chính thức, thống nhất thiết kế đánh giá, nơi fit tham số và quy tắc dữ liệu theo thời điểm để hạn chế leakage.

Các quyết định chính thức trên vẫn **chờ nhóm thống nhất**. Văn bản này lưu phương án EDA ngày 05/11/2026. Ngày 06/11/2026, người dùng cho phép cấu hình baseline thử nghiệm riêng; cấu hình, tác động và kết quả ở [báo cáo tiến độ](bao_cao_tien_do.md). Mã `src/` đã được cập nhật cho luồng thử nghiệm; raw, processed cũ và khảo sát Form 2 được giữ nguyên.
