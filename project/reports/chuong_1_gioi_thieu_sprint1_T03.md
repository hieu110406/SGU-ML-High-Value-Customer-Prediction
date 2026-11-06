# Chương 1: Giới thiệu

**Đề tài:** Phân khúc khách hàng và nhận diện khách hàng có giá trị cao  
**Người thực hiện phần T03:** Ngô Nguyên — MSSV 3124411191  
**Giai đoạn:** Bản thảo Sprint 1, 02–03/11/2026; tiếp tục hoàn thiện trong Sprint 2.

> Phạm vi bản thảo: giới thiệu bài toán, raw duy nhất đã kiểm tra và phương pháp dự kiến.
> Raw của dự án là `data/raw/Online Retail.xlsx`; các kết quả từ dữ liệu từng chọn nhầm
> không hợp lệ. Chưa có kết quả RFM/phân cụm được xác minh từ raw này; các bước liên quan
> trong chương là kế hoạch, không phải kết quả thực nghiệm.

> **Ghi chú phiên bản 06/11/2026:** giữ chức năng bản thảo Sprint 1 của tác giả. Các trạng thái “chưa có kết quả” bên dưới phản ánh thời điểm viết; tiến độ và kết quả baseline thử nghiệm mới ở [báo cáo tiến độ](bao_cao_tien_do.md). Phân công cleaning theo yêu cầu mới: Nguyên phụ trách chính, Thuận kiểm tra chéo; không suy ra Proposal lịch sử đã được sửa hoặc nhóm đã duyệt cấu hình.

## 1.1. Bối cảnh và lý do chọn đề tài

Dữ liệu giao dịch lưu lại thời điểm mua, mặt hàng, số lượng, đơn giá và định danh
khách hàng. Khi được tổ chức ở cấp khách hàng, các thông tin này giúp mô tả
sự khác nhau về mức độ gắn bó và quy mô mua sắm. Chỉ xem tổng số dòng bán hàng
hoặc tổng giá trị giao dịch khó làm rõ một khách hàng mua thường xuyên,
một khách hàng đã lâu không quay lại và một khách hàng có ít lần mua nhưng giá trị lớn.
Vì vậy, phân tích hành vi mua hàng cần kết hợp nhiều khía cạnh thay vì dựa vào một chỉ tiêu.

Phân khúc khách hàng là cách tổ chức các khách hàng có đặc điểm tương đồng
thành những nhóm có thể diễn giải. Trong bối cảnh bán lẻ, cách tiếp cận này
có thể hỗ trợ tìm hiểu nhóm đóng góp giá trị giao dịch lớn, nhóm mua lặp lại
và nhóm cần theo dõi mức độ quay lại. Các nhóm chỉ có ý nghĩa ứng dụng sau khi
được đối chiếu với mục tiêu và quy tắc nghiệp vụ. Một cụm có mức chi tiêu cao
không tự động đồng nghĩa với lợi nhuận cao hoặc giá trị dài hạn cao.

Đề tài sử dụng Online Retail vì bộ dữ liệu có các trường giao dịch cần thiết
để liên kết hoạt động mua với mã khách hàng và thời gian. Theo
[mô tả của UCI](https://archive.ics.uci.edu/dataset/352/online+retail), dữ liệu
đến từ một nhà bán lẻ trực tuyến đăng ký tại Anh và đơn giá được ghi bằng GBP.
Trong dự án này, số liệu phân tích được tính trực tiếp từ tệp Excel lưu trong repository.

RFM được lựa chọn làm hướng tạo đặc trưng vì có thể diễn giải từ lịch sử giao dịch:
Recency phản ánh khoảng thời gian từ lần mua gần nhất đến ngày tham chiếu;
Frequency phản ánh số lần mua trong cửa sổ quan sát; Monetary phản ánh giá trị
giao dịch của khách hàng trong cùng cửa sổ. Ba chiều này phù hợp với những cột
đang có, đồng thời tạo một biểu diễn gọn hơn so với dữ liệu từng mặt hàng.
Việc tính RFM vẫn cần thống nhất thế nào là một lần mua và cách xử lý hoàn trả,
hủy hoặc điều chỉnh trước khi tiến hành mô hình hóa.

## 1.2. Phát biểu bài toán

Bài toán của đề tài là chuyển dữ liệu giao dịch ở cấp dòng hóa đơn thành
đặc trưng ở cấp khách hàng, sau đó thử nghiệm phân cụm để nhận diện các nhóm
có hành vi mua khác nhau và mô tả nhóm có giá trị giao dịch lịch sử cao.
Một dòng dữ liệu không phải một khách hàng và cũng không phải một hóa đơn
hoàn chỉnh: nhiều dòng mặt hàng có thể thuộc một hóa đơn, còn một khách hàng
có thể phát sinh nhiều hóa đơn.

**Đầu vào duy nhất** là tệp `data/raw/Online Retail.xlsx`, sheet `Online Retail`,
gồm `InvoiceNo`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`, `UnitPrice`,
`CustomerID` và `Country`. Những dòng thiếu mã khách hàng, hóa đơn hủy, giá trị không
dương và dòng trùng là vấn đề cần xử lý có quy tắc, không phải dữ liệu được mặc
định loại bỏ ngay khi đọc.

**Đầu ra dự kiến** gồm bảng đặc trưng RFM theo khách hàng đủ điều kiện,
nhãn cụm của từng khách hàng, bảng/biểu đồ mô tả các cụm và kết quả đánh giá
các phương án phân cụm. Tiêu chí gọi một nhóm là “khách hàng có giá trị cao”
cần nhóm xác nhận trên cơ sở hồ sơ RFM và mục tiêu nghiệp vụ; chưa có ngưỡng
Monetary, số cụm hay tỷ lệ khách hàng giá trị cao được chốt trong repository.

Cần phân biệt hai bài toán. **Phân cụm dựa trên lịch sử** là học không giám sát,
nhóm khách hàng theo các đặc trưng đã quan sát mà không cần nhãn giá trị tương lai.
**Dự đoán giá trị tương lai** đòi hỏi xác định biến mục tiêu và kỳ dự báo,
tạo đặc trưng chỉ từ dữ liệu có trước thời điểm dự báo, đồng thời đánh giá
trên giai đoạn tiếp theo. Phân cụm RFM không tự chứng minh khả năng dự báo.
Dù tên repository có từ “Prediction”, hướng triển khai hiện được mô tả trong
README là RFM và phân cụm; mở rộng sang dự báo phải được nhóm xác nhận riêng.

## 1.3. Mục tiêu nghiên cứu

### 1.3.1. Mục tiêu tổng quát

Xây dựng và đánh giá một quy trình phân tích khách hàng từ lịch sử giao dịch,
nhằm tạo các phân khúc có thể diễn giải và hỗ trợ nhận diện nhóm có giá trị
giao dịch lịch sử cao trong phạm vi dữ liệu. Mục tiêu này hướng đến chất lượng
phân tích và khả năng tái lập, chưa đặt ra cam kết hiệu quả kinh doanh hoặc
độ chính xác dự báo khi chưa có thực nghiệm tương ứng.

### 1.3.2. Mục tiêu cụ thể

1. Khảo sát cấu trúc và phạm vi của toàn bộ workbook; thống kê giá trị thiếu,
   trùng lặp, dấu hiệu hủy, lượng/giá không dương và phân phối các biến số.
2. Dự kiến thống nhất tập giao dịch đủ điều kiện, ngày tham chiếu và cửa sổ
   quan sát; tạo đặc trưng RFM ở cấp khách hàng với định nghĩa nhất quán.
3. Dự kiến thử nghiệm KMeans, phân cụm phân cấp Ward và DBSCAN theo các hướng
   đã có tên notebook/module trong repository; lựa chọn tham số bằng thực nghiệm.
4. Dự kiến đánh giá cấu trúc cụm và mức độ phân tách, sử dụng Elbow và Silhouette
   ở những trường hợp phù hợp; diễn giải đặc điểm khách hàng trong từng cụm.
5. Dự kiến trực quan hóa kết quả, đối chiếu độ nhạy với chính sách tiền xử lý
   và tổng hợp các giới hạn khi nhận diện nhóm khách hàng giá trị cao.

Khám phá dữ liệu hiện được thể hiện trong [notebook EDA](../notebooks/01_eda/eda.ipynb).
Các mục tiêu còn lại là hướng thực hiện tiếp theo; chưa có kết quả mô hình được
xác minh từ raw duy nhất để báo cáo.

## 1.4. Đối tượng và phạm vi nghiên cứu

### 1.4.1. Đối tượng nghiên cứu

Đối tượng nghiên cứu là hành vi giao dịch được ghi nhận của khách hàng trong
Online Retail và các nhóm khách hàng có thể hình thành từ đặc trưng RFM.
Đơn vị dữ liệu đầu vào là dòng hóa đơn; đơn vị dự kiến phân cụm là khách hàng
có mã định danh đáp ứng quy tắc được nhóm thống nhất.

### 1.4.2. Phạm vi dữ liệu đã kiểm tra

Raw duy nhất có một sheet và được đọc trực tiếp để kiểm kê:

| Sheet | Số dòng dữ liệu | Số cột | Thời điểm đầu | Thời điểm cuối |
|---|---:|---:|---|---|
| Online Retail | 541.909 | 8 | 2010-12-01 08:26:00 | 2011-12-09 12:50:00 |

Workbook có **541.909 dòng và 8 cột nguồn**,
trong khoảng **2010-12-01 08:26:00 đến 2011-12-09 12:50:00**. Quan sát được
**4.372 mã khách hàng**, **25.900 mã chứng từ duy nhất** (gồm chứng từ C)
và **38 nhãn quốc gia**. Đây là thống kê phạm vi dữ liệu thô,
chưa phải quy mô tập huấn luyện hoặc số khách hàng sau tiền xử lý.

EDA phát hiện **5.268 dòng trùng dư trên 8 cột nguồn**. Các dòng này được giữ
trong khảo sát và ghi nhận để nhóm quyết định chính sách. Có **135.080 dòng thiếu CustomerID**;
không thể tự gán các dòng này về một khách hàng đã biết chỉ từ dữ liệu hiện có.

### 1.4.3. Giới hạn nghiên cứu

Phạm vi thời gian nêu trên là lịch sử giao dịch giai đoạn 12/2010–12/2011, không phải
hoạt động kinh doanh năm 2026. Tháng cuối chỉ có quan sát đến ngày 09/12/2011,
nên mức giao dịch tháng đó không thể được so trực tiếp với một tháng đầy đủ.
Thông tin múi giờ không có trong workbook; EDA giữ thời gian nguồn.

Dữ liệu hiện có không cung cấp chi phí, biên lợi nhuận, đặc điểm nhân khẩu học
hay toàn bộ hành vi ngoài giao dịch. Vì vậy, Monetary dự kiến biểu diễn giá trị
giao dịch theo chính sách đã chốt, không phải lợi nhuận hoặc giá trị vòng đời
được xác thực. Các mã hàng có thể bao gồm bút toán dịch vụ/điều chỉnh nên cần
phân loại trước khi diễn giải tất cả là hàng hóa. Giá trị âm hoặc cực lớn cần
xét ngữ cảnh nghiệp vụ; EDA chưa áp dụng chính sách xóa ngoại lai.

Phạm vi phân tích hiện tại là notebook EDA và bản thảo Chương 1.
Các công việc tiền xử lý, tạo RFM, mô hình hóa, đánh giá và ứng dụng demo
thuộc bước tiếp theo theo phân công của nhóm; bản thảo này không coi chúng
là sản phẩm đã hoàn thành. Kế hoạch chi tiết và tiêu chí nghiệm thu các bước
đó chưa được tìm thấy trong tài liệu cục bộ đã kiểm tra, cần nhóm xác nhận.

## 1.5. Phương pháp thực hiện

Quy trình dự kiến đi từ xác minh dữ liệu đến tạo biểu diễn khách hàng,
thử nghiệm phân cụm, đánh giá và diễn giải. Trạng thái của từng bước được phân biệt như sau:

1. **Kiểm tra nguồn và khám phá ban đầu — đã thực hiện trên raw duy nhất.**
   Đọc sheet `Online Retail`, thống kê cấu trúc/chất lượng,
   tính mô tả số và phân tích số hóa đơn theo tháng/quốc gia. Phép đếm hóa đơn
   sử dụng mã duy nhất thay vì số dòng. Tạo `Quantity × UnitPrice` chỉ để khảo sát
   giá trị đại số của dòng; dữ liệu gốc được giữ nguyên.
2. **Tiền xử lý — dự kiến.** Thống nhất cách xử lý mã khách hàng thiếu,
   dòng trùng, hóa đơn hủy, lượng/giá không dương,
   mã dịch vụ và ngoại lai. Mỗi điều kiện cần có số dòng bị ảnh hưởng và
   lý do nghiệp vụ; chưa mặc định rằng mọi dòng có dấu hiệu bất thường phải xóa.
3. **Tạo đặc trưng RFM — dự kiến.** Chốt ngày tham chiếu sau cửa sổ quan sát;
   tính Recency từ lần mua đủ điều kiện gần nhất, Frequency bằng số hóa đơn
   mua duy nhất của khách hàng và Monetary bằng tổng giá trị giao dịch đủ
   điều kiện. Cách đối trừ hoàn/hủy, đơn vị Recency và cửa sổ quan sát cần
   nhóm xác nhận trước khi triển khai.
4. **Biến đổi và phân cụm — dự kiến.** Khảo sát độ lệch để cân nhắc biến đổi
   và chuẩn hóa đặc trưng, vì các chiều RFM có thang đo khác nhau. Bộ khung
   hiện gợi ý KMeans, Ward và DBSCAN. Các tên cấu hình `kmeans_k4.yaml`
   và `dbscan_eps05.yaml` hiện là TODO, không chứng minh rằng k = 4 hoặc
   eps = 0,5 là tham số tối ưu hay đã được chạy.
5. **Đánh giá và diễn giải — dự kiến.** Khảo sát Elbow/Silhouette theo các
   notebook đã có tên, kết hợp quy mô cụm và hồ sơ RFM; không chọn mô hình
   chỉ từ một con số. Dự kiến dùng PCA để hỗ trợ trực quan hóa và profiling
   để mô tả cụm. Chính sách đánh giá nhiễu của DBSCAN và tiêu chí ổn định
   cần được nhóm xác định; chưa có điểm đánh giá hoặc nhãn cụm thực nghiệm.
6. **Tổng hợp báo cáo và minh họa — dự kiến.** Trình bày các lựa chọn,
   kết quả và giới hạn theo bằng chứng thực thi. Thư mục `app/` hiện chỉ
   có bộ khung; demo Streamlit chưa phải chức năng đã hoàn thành.

Phương pháp trên bám vào README, tên notebook, module và cấu hình hiện có.
Các quyết định thiết kế chưa được mô tả trong kế hoạch chính thức chỉ là
đề xuất làm việc, cần thống nhất trong nhóm trước Sprint 2.

## 1.6. Ý nghĩa của đề tài

### 1.6.1. Ý nghĩa học thuật

Đề tài tạo điều kiện vận dụng học không giám sát trên dữ liệu giao dịch thực tế,
từ xác định đơn vị phân tích, kiểm tra chất lượng và thiết kế đặc trưng đến
đánh giá/diễn giải cụm. RFM giúp kết nối kiến thức máy học với các chỉ tiêu
có thể giải thích ở cấp khách hàng. Việc phân biệt dòng hóa đơn với lần mua,
giữ dấu vết dữ liệu và nêu rõ các quyết định chưa chốt giúp kết quả có thể
kiểm tra và tái lập, đồng thời làm rõ giới hạn giữa phân khúc lịch sử và dự báo.

### 1.6.2. Ý nghĩa ứng dụng

Nếu quy trình được kiểm chứng, các phân khúc có thể cung cấp một góc nhìn
hỗ trợ ưu tiên chăm sóc, theo dõi khách hàng mua lặp lại hoặc xây dựng giả
thuyết về mức độ gắn bó. Hồ sơ cụm giúp trao đổi với người sử dụng thông qua
thời gian quay lại, tần suất và giá trị giao dịch thay vì chỉ có nhãn số.
Đây là khả năng ứng dụng dự kiến; T03 chưa chứng minh cải thiện doanh thu,
lợi nhuận, duy trì khách hàng hoặc hiệu quả của một chiến dịch. Mọi ứng dụng
thực tế cần dữ liệu phù hợp bối cảnh, tiêu chí nghiệp vụ và đánh giá bổ sung.

## 1.7. Cấu trúc báo cáo

Theo yêu cầu, báo cáo được tổ chức thành 5 chương. Repository chưa có đề cương
5 chương chính thức; **tên và phân bổ dưới đây là đề xuất cho bản thảo,
cần nhóm xác nhận** trước khi ghép báo cáo chung:

1. **Chương 1 — Giới thiệu:** bối cảnh, phát biểu bài toán, mục tiêu,
   đối tượng/phạm vi, phương pháp dự kiến và ý nghĩa của đề tài.
2. **Chương 2 — Cơ sở lý thuyết và phương pháp:** RFM, biến đổi/chuẩn hóa,
   KMeans, phân cụm phân cấp Ward, DBSCAN và các khái niệm đánh giá liên quan.
3. **Chương 3 — Dữ liệu và quy trình thực nghiệm:** nguồn dữ liệu, EDA,
   chính sách tiền xử lý được thống nhất, tạo đặc trưng và thiết kế thí nghiệm.
4. **Chương 4 — Kết quả và thảo luận:** dự kiến trình bày kết quả thực thi,
   so sánh các phương án, trực quan hóa và hồ sơ cụm cùng những giới hạn.
5. **Chương 5 — Kết luận và hướng phát triển:** dự kiến tổng hợp mức độ đạt
   mục tiêu, hạn chế và hướng mở rộng phù hợp với bằng chứng đã có.

## Nguồn đối chiếu và các điểm cần nhóm xác nhận

- Chen, D. *Online Retail* [Dataset]. UCI Machine Learning Repository.
  [https://doi.org/10.24432/C5BW33](https://doi.org/10.24432/C5BW33).
  Dùng để đối chiếu bối cảnh và quy ước biến; các số đếm trong chương tính từ raw duy nhất.
- [README dự án](../README.md), [requirements.txt](../requirements.txt),
  thư mục `src/`, `configs/` và các notebook hiện có: căn cứ cho trạng thái
  triển khai và các hướng phương pháp; chưa có kế hoạch chi tiết hoàn chỉnh.
- [EDA từ raw duy nhất](../notebooks/01_eda/eda.ipynb): cấu trúc,
  chất lượng, phép đếm và kiểm tra nhất quán. SHA-256 nguồn:
  `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`.

Trước Sprint 2, nhóm cần xác nhận đề cương 5 chương; tiêu chí khách hàng giá trị cao;
chính sách trùng, hoàn/hủy và ngoại lai; định nghĩa RFM/cửa sổ/ngày tham chiếu;
thiết kế đánh giá mô hình; và có mở rộng từ phân cụm sang dự đoán tương lai hay không.
