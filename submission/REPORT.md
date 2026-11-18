# Báo cáo Day 09 — Đoàn Quang Minh, 2A202603228

## 1. Kết luận trước
Pipeline đưa ra quyết định **Hold** (mã thoát 10). Lô dữ liệu đầu vào gồm **224** ảnh; qua bước intake đã sàng lọc và loại bỏ **22** ảnh (ảnh hỏng, trùng lặp, rò rỉ), còn lại **202** ảnh tiếp tục đi qua các vòng kiểm tra chất lượng và được xuất ra thư mục `submission/export/clean_v1` (dưới dạng bản **nháp**, chưa cấp phép phát hành).
Nguyên nhân: Sau khi máy tự sửa và người duyệt thẩm định, dữ liệu đã **hoàn toàn sạch lỗi bắt buộc** (0 lỗi), tuy nhiên vẫn còn **38/202 ảnh (chiếm 18,8%)** tồn đọng cảnh báo chưa được người duyệt, vượt ngưỡng quy định 10%. Hàng đợi thẩm định ghi nhận **125** ảnh cần xử lý, trong khi ngân sách duyệt của dự án bị giới hạn ở mức **80** ảnh.

## 2. Lỗi và phân việc
Số liệu tổng hợp từ `02_error_list_v1` (quét 224 ảnh ở cửa vào và 202 ảnh ở các bước kiểm tra nhãn):

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| `DUP_IMAGE_EXACT` | 8 ảnh | máy (loại) | Trùng lặp chính xác từng byte: loại bỏ để tránh làm lệch phân bố tập train |
| `DUP_IMAGE_NEAR` | 4 ảnh | máy (loại) | Trùng lặp gần đúng qua phash ≤ 10 (ngưỡng sau calibration) |
| `LEAK_TEST` | 5 ảnh | máy (loại) | Trùng lặp với tập test: bắt buộc loại bỏ để tránh hiện tượng rò rỉ dữ liệu làm sai lệch độ đo |
| `BAD_SIZE` / `CORRUPT_IMAGE` | 3 / 2 ảnh | máy (loại) | Ảnh kích thước < 250px hoặc file ảnh hỏng, không giải mã được |
| `BAD_CLASS_ID` | 6 dòng | máy (xoá dòng) | ID lớp nằm ngoài phạm vi 0..3: máy không thể tự suy đoán lớp chuẩn nên chọn phương án xóa an toàn |
| `BAD_FORMAT` | 3 dòng | máy (xoá dòng) | Thiếu cột thuộc tính hoặc chứa giá trị NaN |
| `BOX_ZERO` | 4 dòng | máy (xoá dòng) | Bounding box có diện tích bằng 0 (w hoặc h ≤ 0) |
| `DUP_BOX` | 7 dòng | máy (xoá dòng sau) | Trùng lặp bounding box cùng lớp với IoU > 0.9 |
| `BOX_OUT_OF_IMAGE` | 8 dòng | máy (cắt box) | Lỗi cú pháp hình học: cắt gọt box về phạm vi [0, 1] và giữ nguyên nhãn lớp |
| `BAD_CLASS_NAME` | 2 tên | máy (ghi lại `data.yaml`) | Chuẩn hóa lại các tên lớp viết sai quy ước (`Person`, `Bus`) |
| `MISSING_LABEL_FILE` | 6 ảnh | **người** | Thiếu file nhãn: máy không được tự bịa nhãn, ưu tiên đẩy lên hàng đợi cho chuyên viên (trọng số cao nhất: 10) |
| `POSSIBLE_MISSING` | 53 | **người** | Dự đoán từ mô hình checker lớn, cần con người thẩm định trực quan |
| `POSSIBLE_WRONG_CLASS` | 18 | **người** | Lỗi ngữ nghĩa giữa các lớp gần nhau, quy tắc cú pháp không tự phân xử được |
| `POSSIBLE_LOOSE_BOX` | 28 | **người** | Bounding box lỏng/lệch so với biên vật thể, cần mắt người điều chỉnh |
| `POSSIBLE_FALSE_POS` | 29 | **người** | Nhãn có thể gán nhầm vào nền hoặc vật thể ngoài guideline |
| `EMPTY_LABEL` / `BOX_TINY` / `BOX_HUGE` / `CLASS_RARE` | 12 / 6 / 3 / 4 | **người** | Nhóm cảnh báo thống kê, cần người xác nhận bối cảnh |

Quy trình tự động hóa đã thực hiện tổng cộng **35** thay đổi (`03_fixes.csv`): xóa 20 dòng nhãn hỏng, cắt gọt 8 box tràn viền, cập nhật chuẩn hóa 1 lần tên lớp trong `data.yaml`, và đánh dấu 6 ảnh `needs_label` (chuyển sang hàng đợi, không tạo file nhãn giả).

**Cơ chế hàng đợi duyệt** (`05_review_queue.csv`): Điểm ưu tiên của mỗi ảnh được tính theo công thức: $\text{Điểm} = \sum (\text{trọng số mã lỗi}) \times (1 + \text{conf})$. Trong đó, 6 ảnh chưa có nhãn (`NEEDS_LABEL`, trọng số 10) được xếp ngay đầu danh sách; ảnh `img_0020` có điểm cao nhất (11.5) do cộng dồn nhiều lỗi: có dòng bị xóa + cảnh báo `POSSIBLE_MISSING` + `POSSIBLE_WRONG_CLASS`. Nhờ ngân sách 80 ảnh, người duyệt đã hỗ trợ xử lý giảm mạnh số lượng nghi vấn: `POSSIBLE_MISSING` giảm từ 53 xuống 13, `WRONG_CLASS` từ 18 xuống 3, `LOOSE_BOX` từ 28 xuống 20, `FALSE_POS` từ 29 xuống 21 (so sánh v1 với v3); 45 ảnh còn lại nằm ở cuối hàng đợi chưa thể xử lý do hết định mức thời gian/ngân sách.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Phân tích đánh đổi |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **10** | NEAR 1.00/0.50 → 1.00/0.67; EXACT 1.00/1.00 giữ nguyên | Khi đánh dấu trùng lặp đồng nghĩa với việc **xóa ảnh**, do đó mục tiêu hàng đầu là bảo vệ Precision. Precision đạt 1.00 ở hầu hết các mốc nên tôi chọn giá trị 10 nằm ở khoảng giữa dải ổn định 4–14, tránh vùng rủi ro sát ngưỡng 20 (nơi EXACT recall sụt giảm mạnh còn 0.33). Mốc 16 cho recall 0.83 nhưng thực tế chỉ thu thêm được đúng 1 ảnh trong khi rủi ro xóa nhầm ảnh thật tăng cao. |
| `second_opinion.conf` | 0.25 | **0.6** | WRONG_CLASS 0.56/0.83 → 0.62/0.83; MISSING 0.50/1.00 → 0.57/1.00; LOOSE_BOX 0.29/0.40 → 0.20/0.20 | Với vai trò tạo cảnh báo cho người duyệt, tiêu chí Recall được đặt lên trước. Mốc 0.6 là giá trị tối ưu cao nhất vẫn duy trì được **MISSING recall tuyệt đối 1.00**, đồng thời cải thiện Precision để tinh giản các cảnh báo giả trong hàng đợi. Nếu nâng lên 0.8 thì F1 của WRONG_CLASS đạt đỉnh nhưng MISSING recall lại giảm xuống 0.75 (bỏ sót lỗi nặng). Đánh đổi chấp nhận: Recall của nhóm LOOSE_BOX giảm. |

**Rủi ro từ bẫy số liệu Calibration:** Bộ calib chỉ gồm 9 ảnh trùng (trong đó có 6 cặp gần trùng), nên mỗi ảnh đơn lẻ đã chiếm tới ~16.7% recall, và Precision luôn hiển thị 1.00 ở mọi giá trị `phash_dist` — điều này khiến tập calib không phản ánh được nguy cơ xóa nhầm khi triển khai trên dữ liệu thực tế. Trên tập raw, cặp `img_0186` ↔ `img_0061` có khoảng cách Hamming **đúng bằng 10** (trùng với ngưỡng lựa chọn), hai cặp khác có khoảng cách lần lượt là 0 và 6. Kiểm tra trực quan cả hai cặp: **đây đều là ảnh trùng thật**, chứng minh ngưỡng 10 hoạt động an toàn và không xóa nhầm ảnh:
1. Cặp `img_0061` ↔ `img_0186` (phash = 10): Cùng chung một ảnh chụp gốc (người ngồi ghế băng, hàng cây và tòa nhà chóp nhọn phía sau); trong đó `img_0061` (544×361) là bản **cắt cúp (crop) đều bốn phía** từ `img_0186` (640×425) với tỉ lệ khung hình giữ nguyên ~1.51, đồng thời được hậu kỳ màu ấm và sáng hơn.
2. Cặp `img_0077` ↔ `img_0223` (phash = 6): Chung góc máy (tháp đồng hồ, xe buýt); ảnh `img_0223` đã bị **thu nhỏ 75%** kích thước (500×412 → 375×309), tăng độ sáng và giảm tương phản (độ sáng trung bình tăng từ ~166 lên ~188/255) làm mờ chi tiết.

Cặp ảnh bị crop và chỉnh màu có độ lệch vừa vặn chạm mốc 10. Nếu giữ ngưỡng mặc định ban đầu là 2, cả hai cặp ảnh trùng này chắc chắn sẽ bị bỏ lọt vào tập huấn luyện; ngược lại nếu ảnh bị can thiệp biến dạng sâu hơn, khoảng cách sẽ vượt ngưỡng 10, cho thấy việc chọn ngưỡng dựa trên tập calib nhỏ luôn tiềm ẩn sai số trên dữ liệu thực. Bên cạnh đó, `POSSIBLE_FALSE_POS` không chịu ảnh hưởng từ tham số `conf` (do gắn chặt với `fp_conf` cố định), còn `LOOSE_BOX` trên calib chỉ có 5 mẫu nên các chỉ số đo lường mang độ nhiễu khá lớn.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Kiểm chứng cửa chặn (Gate) hoạt động đúng:**
Thử nghiệm chạy pipeline với cờ vô hiệu hóa người duyệt: `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`. Khi không có người xử lý, 6 ảnh thiếu nhãn vẫn tồn tại dưới dạng lỗi bắt buộc. Hệ thống ngay lập tức đưa ra quyết định **REWORK — còn 6 lỗi bắt buộc (MISSING_LABEL_FILE) trên 6 ảnh**, trả về mã thoát **20**, in cảnh báo `KHÔNG xuất: còn lỗi bắt buộc (Rework)`, đồng thời thư mục đích `work/exp_nb` hoàn toàn **không được khởi tạo**, chứng minh cơ chế chốt chặn đã ngăn chặn tuyệt đối việc phát hành dữ liệu lỗi.

**(b) Các điểm mù thực tế của pipeline:**
1. **Lỗi nhầm lẫn giữa truck ↔ car mà chính model checker cũng phán đoán sai:** Ở vòng v3 vẫn ghi nhận các ca `img_0078`, `img_0083`, `img_0220` (nhãn gốc gán truck nhưng model dự đoán car với IoU > 0.9). Do cả nhãn và mô hình đều gặp khó khăn trong việc phân biệt ranh giới giữa xe bán tải/xe tải nhỏ và ô tô con, hệ thống tự động không thể tự giải quyết mà bắt buộc phải có mắt người thẩm định.
2. **Sai lệch bounding box mức độ nhẹ:** Tại mốc `conf = 0.6`, Recall đối với `LOOSE_BOX` trên tập calib chỉ đạt 0.20; do đó tại vòng v3 vẫn còn sót lại 20 trường hợp box lỏng chưa được khoanh khít.
3. **Ảnh trùng lặp bị biến dạng mạnh:** Ngay cả khi thiết lập `phash_dist = 10`, tập calib vẫn bỏ sót 2/6 trường hợp gần trùng. Với các ảnh bị xoay, crop quá sâu hoặc biến đổi màu cục bộ trên tập raw, thuật toán pHash hoàn toàn có thể bỏ lọt.
4. **Độ lệch phân bố giữa calib và raw:** Nhóm lỗi nhầm nhãn trên tập calib tập trung chủ yếu vào cặp `person → car`, trong khi dữ liệu raw xuất hiện nhiều ca phức tạp hơn giữa `truck`, `car` và `bus`. Do vậy hiệu năng đo đạc trên calib không phản ánh trọn vẹn độ chính xác trên raw.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Thử nghiệm huấn luyện được thực thi trên môi trường Google Colab (GPU T4): kiến trúc **yolo26n**, 20 epochs, batch size 16, imgsz 640, lặp lại trên **2 seed ngẫu nhiên (seed 0, 1)** cho mỗi biến thể, dùng chung tập kiểm thử (100 ảnh). Biến thể `clean` là bản xuất nháp của phiên chạy **Hold** (202 ảnh); biến thể `raw` là 224 ảnh gốc chưa qua xử lý. Kết quả trích xuất từ `submission/results/comparison.md`:

| Biến thể | Số ảnh train | Số seed | mAP50 | mAP50-95 | Precision | Recall |
|---|---:|---:|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 202 | 2 | 0.701 ± 0.025 | 0.487 ± 0.008 | 0.759 ± 0.003 | 0.625 ± 0.019 |

**Phân tích độ chênh lệch mAP50:** Mức chênh lệch giữa hai biến thể là $\Delta\text{mAP50} = -0.025$, giá trị này tương đương với độ lệch chuẩn nội tại giữa 2 seed của tập `clean` ($\pm 0.025$, cụ thể seed 0 đạt 0.718, seed 1 đạt 0.683). Với quy mô thực nghiệm dừng ở 2 seed và tập test gồm 100 ảnh, sự chênh lệch này **nằm hoàn toàn trong phạm vi nhiễu ngẫu nhiên**: chưa đủ cơ sở thống kê để kết luận tập clean cho chất lượng mô hình tốt hơn hay kém hơn raw. Về chỉ số mAP50-95, mức giảm 0.025 có phần vượt qua độ lệch chuẩn seed (0.004–0.008), mang dấu hiệu cho thấy raw nhỉnh hơn đôi chút, nhưng số lượng seed hiện tại là quá ít để đưa ra khẳng định chắc chắn.

**Khảo sát dữ liệu thực tế mà `raw` sử dụng:** Kiểm tra log cache của Ultralytics (`work/train/raw/train/labels.cache`), hệ thống ghi nhận trạng thái: `(216 có nhãn, 6 thiếu nhãn, 13 nhãn rỗng, 11 hỏng, 224 tổng)`. Theo cơ chế mặc định, Ultralytics **loại bỏ toàn bộ ảnh** nếu phát hiện dòng nhãn lỗi, do đó biến thể `raw` trên thực tế chỉ huấn luyện trên **213 ảnh**, chỉ nhỉnh hơn tập `clean` 11 ảnh thay vì chênh lệch 22 ảnh như số lượng file danh nghĩa. 11 ảnh bị Ultralytics đào thải trùng khớp hoàn toàn với các lỗi mà pipeline đã bắt: 2 ảnh hỏng (`CORRUPT_IMAGE`: img_0010, img_0136), 3 ảnh sai format (`BAD_FORMAT`: img_0014, img_0022 dính NaN; img_0179 thiếu cột), 6 ảnh sai ID lớp (`BAD_CLASS_ID`: img_0020 id 93, img_0099/img_0117 id -1, img_0104 id 7, img_0194/img_0199 id 4). Điểm khác biệt mấu chốt nằm ở chỗ: Ultralytics loại bỏ toàn bộ bức ảnh chỉ vì một dòng hỏng đơn lẻ (chẳng hạn `img_0020` hỏng dòng 3 khiến các box đúng khác bị mất theo), trong khi pipeline AutoQC chỉ bóc tách đúng dòng lỗi (`drop_line`) và bảo toàn các nhãn hợp lệ còn lại. Ngược lại, Ultralytics hoàn toàn không thể phát hiện các lỗi tinh vi: 5 ảnh rò rỉ tập test, 12 ảnh trùng lặp nội dung, 3 ảnh kích thước dưới chuẩn, 4 box rỗng, 7 box chồng lấn, và đặc biệt là 6 ảnh thiếu nhãn bị ngộ nhận thành **ảnh nền** (vô tình huấn luyện cho mô hình tư duy "không có đối tượng" trên vùng ảnh thực tế có đối tượng).

**Chi tiết hiệu năng theo từng lớp đối tượng:** So sánh AP50 trung bình qua 2 seed (raw → clean): `car` giữ nguyên 0.738 → 0.738 (0.000), `person` đạt 0.822 → 0.823 (+0.001), `bus` đạt 0.695 → 0.703 (+0.008), riêng lớp **`truck` sụt giảm mạnh từ 0.648 xuống 0.538 (−0.110)**. Mức giảm −0.110 trên 1 lớp chia đều cho 4 lớp tương đương độ sụt −0.027 trên tổng thể mAP50. Như vậy, các lớp phổ biến gần như không bị ảnh hưởng, toàn bộ sự sụt giảm tập trung vào lớp xe tải (`truck`). Thống kê số lượng box (raw → clean): car giảm 122 → 101, person tăng 537 → 574, truck tăng 32 → 41, bus giảm 35 → 32. Lớp truck được bổ sung thêm box nhưng AP lại giảm và dao động rất mạnh giữa các seed (seed 0 đạt 0.590, seed 1 đạt 0.486). Hiện tượng này tương thích với việc xử lý cảnh báo `POSSIBLE_WRONG_CLASS` đã vô tình hoán đổi một số box giữa car và truck (điểm mù đã phân tích ở §4) trên một tập mẫu vốn dĩ rất thưa thớt (~40 box). Lớp person được bổ sung 37 box hợp lệ thông qua việc người duyệt xử lý `POSSIBLE_MISSING`, giúp nhãn sạch hơn dù AP chưa biến động nhiều do lớp này đã đạt ngưỡng bão hòa cao (>0.82).

**Giả thuyết nguyên nhân và định hướng kiểm chứng:**
1. **Hiện tượng rò rỉ dữ liệu test trong tập `raw`:** Pipeline phát hiện 5 ảnh `LEAK_TEST` trùng lặp với `test_009, 033, 039, 044, 085`. Biến thể `raw` đã vô tình học thuộc lòng 5 ảnh này khiến điểm test bị đội lên ảo, trong khi `clean` đã loại bỏ chúng một cách nghiêm ngặt. *Phương án kiểm chứng:* Đánh giá lại cả hai mô hình trên tập test rút gọn (loại bỏ 5 ảnh rò rỉ, còn 95 ảnh) để đo lường mức độ ảnh hưởng thực tế.
2. **Nhiễu gán nhãn giữa truck và car:** Việc điều chỉnh nhãn ở lớp ít dữ liệu như truck có thể tạo ra tác động tiêu cực cục bộ. *Phương án kiểm chứng:* Rà soát vi sai từng box truck giữa `data/raw` và `clean_v1`, kiểm tra lại các trường hợp `POSSIBLE_WRONG_CLASS` và phân tích AP riêng của truck trên từng ảnh test.
3. **Giới hạn của dữ liệu sạch ở trạng thái Hold:** Do ngân sách duyệt giới hạn ở 80 ảnh, tập clean vẫn còn tồn đọng 38 ảnh có cảnh báo (gồm 13 `POSSIBLE_MISSING`, 20 `LOOSE_BOX`, 21 `FALSE_POS`, 3 `WRONG_CLASS`). *Phương án kiểm chứng:* Cấp thêm ngân sách để duyệt triệt để toàn bộ hàng đợi nhằm đạt chuẩn Release thực thụ, sau đó tiến hành train lại với số lượng seed tăng lên (≥ 5 seed) để triệt tiêu phương sai ngẫu nhiên.

**Đánh giá thực nghiệm:** Kết quả huấn luyện sau pipeline **chưa thể hiện sự vượt trội về mặt điểm số** so với dữ liệu thô: mức chênh lệch mAP50 nằm trọn trong khoảng dao động seed và phần lớn xuất phát từ biến động đơn lẻ của lớp truck. Kế hoạch tiếp theo cần tập trung vào việc đánh giá lại trên tập test sạch rò rỉ, chuẩn hóa lại quy tắc gán nhãn cho lớp truck, và mở rộng quy mô duyệt ảnh trước khi đưa ra kết luận cuối cùng.

## 6. Quyết định và ghi chú AI
**(a) Quyết định nghiệm thu: Hold.** Lô dữ liệu đã sạch lỗi bắt buộc nhưng vẫn còn 18.8% ảnh tồn đọng cảnh báo chưa được xử lý. Để chuyển trạng thái sang **Release**, tỉ lệ này bắt buộc phải hạ xuống dưới 10% (tương đương không quá 20 ảnh còn cảnh báo). Biện pháp khả thi là cấp thêm ngân sách để thẩm định thêm tối thiểu **18** ảnh trong nhóm 45 ảnh còn lại, hoặc tối ưu mô hình checker để giảm thiểu cảnh báo giả. Tuyệt đối **không** áp dụng giải pháp nâng ngưỡng `conf` nhằm ép hàng đợi co lại, vì hành động này sẽ làm tê liệt khả năng phát hiện lỗi bỏ sót vật thể (sụt giảm Recall của MISSING) và tạo ra kết quả Release ảo.

**(b) Ghi nhận hỗ trợ từ AI (Claude Code):**
- **Nội dung câu lệnh (Prompt chính):** Cung cấp docstring và các kịch bản kiểm thử mẫu của từng module (`label_format`, `gate`, `autofix`, `second_opinion`); yêu cầu sinh code đáp ứng chuẩn xác giao diện vào/ra, trích xuất cấu hình động từ tham số `cfg`, bắt buộc xử lý ngoại lệ an toàn đối với các dòng dữ liệu hỏng để không làm dừng đột ngột pipeline, và tuyệt đối không xâm phạm cấu trúc thư mục `data/raw`.
- **Phương pháp thẩm tra code:** Trực tiếp đọc và rà soát từng dòng logic; chạy kiểm thử đơn vị độc lập trên từng module và kiểm tra tích hợp toàn hệ thống (đạt 79/79 test); kích hoạt pipeline thực tế `python -m pipeline.run` để đối soát sự tương thích giữa danh sách phát hiện `02_error_list_v1` và nhật ký khắc phục `03_fixes.csv` (khớp hoàn toàn 35 thao tác sửa đổi); thực hiện kịch bản giả định `--budget 0` để kiểm chứng năng lực ngăn chặn của Gate.
- **Tình huống AI phát sinh lỗi:** Trong quá trình thiết lập môi trường, AI đã tự động kích hoạt trình thông dịch tại `.venv\Scripts\python.exe` vốn chưa được đồng bộ thư viện thay vì môi trường Conda (base) sẵn có trên máy dẫn tới lỗi thực thi; tôi đã nhận diện nguyên nhân và chuyển hướng gọi lệnh trực tiếp qua môi trường Python chuẩn của hệ thống.

