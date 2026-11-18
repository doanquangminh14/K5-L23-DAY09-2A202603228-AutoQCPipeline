# Báo cáo Day 09 — Đoàn Quang Minh, 2A202603228

## 1. Kết luận trước
Pipeline kết luận **Hold** (mã thoát 10). Vào **224** ảnh; loại **22** ở bước nhận dữ liệu → **202** ảnh qua QC và vào bản xuất `submission/export/clean_v1` (bản **nháp**, chưa phát hành).
Lý do: sau tự sửa và người duyệt **không còn lỗi bắt buộc** (0), nhưng **38/202 ảnh (18,8%)** vẫn còn cảnh báo chưa được người duyệt, ≥ ngưỡng 10%. Hàng đợi cần duyệt có **125** ảnh trong khi ngân sách chỉ **80**.

## 2. Lỗi và phân việc
Số liệu từ `02_error_list_v1` (224 ảnh quét ở cửa vào, 202 ảnh ở các check nhãn).

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| `DUP_IMAGE_EXACT` | 8 ảnh | máy (loại) | trùng từng byte: chắc chắn, giữ lại làm lệch phân bố |
| `DUP_IMAGE_NEAR` | 4 ảnh | máy (loại) | phash ≤ 10 (đã calibrate) |
| `LEAK_TEST` | 5 ảnh | máy (loại) | trùng ảnh tập test: giữ lại thì điểm test bị thổi phồng |
| `BAD_SIZE` / `CORRUPT_IMAGE` | 3 / 2 ảnh | máy (loại) | ảnh < 250px hoặc không đọc được |
| `BAD_CLASS_ID` | 6 dòng | máy (xoá dòng) | id ngoài 0..3: không đoán được lớp đúng |
| `BAD_FORMAT` | 3 dòng | máy (xoá dòng) | thiếu cột / nan |
| `BOX_ZERO` | 4 dòng | máy (xoá dòng) | box không có diện tích |
| `DUP_BOX` | 7 dòng | máy (xoá dòng sau) | cùng lớp, IoU > 0.9 |
| `BOX_OUT_OF_IMAGE` | 8 dòng | máy (cắt box) | lỗi cú pháp, giữ nguyên lớp |
| `BAD_CLASS_NAME` | 2 tên | máy (ghi lại `data.yaml`) | `Person`, `Bus` sai chính tả |
| `MISSING_LABEL_FILE` | 6 ảnh | **người** | máy không bịa nhãn; ưu tiên cao nhất (trọng số 10) |
| `POSSIBLE_MISSING` | 53 | **người** | ý kiến model lớn, có thể sai |
| `POSSIBLE_WRONG_CLASS` | 18 | **người** | lỗi ngữ nghĩa |
| `POSSIBLE_LOOSE_BOX` | 28 | **người** | lỗi ngữ nghĩa |
| `POSSIBLE_FALSE_POS` | 29 | **người** | lỗi ngữ nghĩa |
| `EMPTY_LABEL` / `BOX_TINY` / `BOX_HUGE` / `CLASS_RARE` | 12 / 6 / 3 / 4 | **người** | cảnh báo, cần mắt người |

Máy thực hiện **35** thay đổi (`03_fixes.csv`): 20 dòng xoá + 8 box cắt + 1 lần đổi tên lớp + 6 ảnh `needs_label` (không tạo file nhãn).

**Hàng đợi** (`05_review_queue.csv`): điểm ảnh = Σ trọng số mã × (1 + conf). 6 ảnh thiếu nhãn (`NEEDS_LABEL`, trọng số 10) lên đầu; `img_0020` đứng số 1 (11,5) vì cộng dồn dòng bị xoá + `POSSIBLE_MISSING` + `POSSIBLE_WRONG_CLASS`. Với ngân sách 80/125 ảnh, người duyệt giảm `POSSIBLE_MISSING` 53 → 13, `WRONG_CLASS` 18 → 3, `LOOSE_BOX` 28 → 20, `FALSE_POS` 29 → 21 (v1 → v3); 45 ảnh cuối hàng không ai xem.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **10** | NEAR 1.00/0.50 → 1.00/0.67; EXACT 1.00/1.00 giữ nguyên | Cờ trùng = **xoá ảnh**, ưu tiên precision. Precision = 1.00 ở mọi giá trị nên chọn giữa vùng ổn định 4–14, xa vách 20 (EXACT recall rơi 0.33). 16 cho recall 0.83 nhưng chỉ hơn 1 ảnh và sát vách. |
| `second_opinion.conf` | 0.25 | **0.6** | WRONG_CLASS 0.56/0.83 → 0.62/0.83; MISSING 0.50/1.00 → 0.57/1.00; LOOSE_BOX 0.29/0.40 → 0.20/0.20 | Cảnh báo cho người: ưu tiên recall. 0.6 là giá trị cao nhất còn giữ **MISSING recall 1.00**, đồng thời tăng precision để hàng đợi bớt báo động giả. 0.8 có F1 WRONG_CLASS cao nhất nhưng MISSING recall rơi 0.75. Đánh đổi chấp nhận: LOOSE_BOX recall giảm. |

**Chỗ calibration có thể đánh lừa:** calib chỉ có 9 ảnh trùng (6 gần trùng), mỗi ảnh = 17% recall, và precision = 1.00 ở **mọi** giá trị `phash_dist` — calib không phân biệt được ngưỡng an toàn với ngưỡng xoá nhầm. Trên raw, cặp `img_0186` ↔ `img_0061` có khoảng cách **đúng bằng 10** (ngưỡng đã chọn), hai cặp khác là 0 và 6. Mở xem cả hai cặp: **đều là trùng thật**, ngưỡng 10 không xoá nhầm ảnh trên raw. (1) `img_0061` ↔ `img_0186` (phash 10): cùng một ảnh gốc (người ngồi ghế băng, hàng cây, toà nhà chóp nhọn); `img_0061` (544×361) là bản **crop đều bốn phía** từ `img_0186` (640×425), cùng tỉ lệ khung ~1.51, kèm chỉnh màu ấm/sáng hơn. (2) `img_0077` ↔ `img_0223` (phash 6): cùng khung hình (tháp đồng hồ, xe buýt), `img_0223` bị **thu nhỏ 75%** (500×412 → 375×309), tăng sáng/giảm tương phản (độ sáng TB ~166 → ~188/255) và mềm chi tiết. Cặp crop + chỉnh màu cách nhau đúng 10 — với ngưỡng khởi đầu 2 thì cả hai cặp đều **lọt** vào dataset; ngược lại, biến đổi mạnh hơn một chút (crop sâu hơn) sẽ vượt 10 và lọt, nên ngưỡng "vừa đủ" trên calib không bảo đảm trên raw. Ngoài ra `POSSIBLE_FALSE_POS` không đổi theo `conf` (dùng `fp_conf` cố định) và `LOOSE_BOX` trên calib chỉ có 5 ca, nên số đo của chúng rất nhiễu.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Gate chặn đúng.** Chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt): kết luận **REWORK — còn 6 lỗi bắt buộc (MISSING_LABEL_FILE) trên 6 ảnh**, mã thoát **20**, log `KHÔNG xuất: còn lỗi bắt buộc (Rework)`, và `work/exp_nb` **không tồn tại** (không có dataset nào được xuất).

**(b) Điểm mù có bằng chứng:**
1. **Nhầm truck ↔ car mà model lớn cũng nhầm:** v3 còn `img_0078`, `img_0083`, `img_0220` (nhãn truck, model nói car, IoU > 0.9). Máy không biết bên nào đúng; chỉ người phân xử được.
2. **Box lỏng nhẹ:** với `conf=0.6`, recall `LOOSE_BOX` trên calib chỉ 0.20; v3 vẫn còn 20 cảnh báo box lỏng.
3. **Ảnh trùng biến đổi mạnh:** ngay cả ở `phash_dist=10`, calib còn bỏ sót 2/6 ảnh gần trùng — ảnh crop/thu nhỏ mạnh trong raw sẽ lọt.
4. **Calib khác raw:** lỗi nhầm lớp trong calib chủ yếu person→car, còn raw có thêm truck/car/bus, nên recall trên calib không đại diện cho raw.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Train trên Colab T4: **yolo26n**, 20 epoch, batch 16, imgsz 640, **2 seed (0, 1)** mỗi biến thể, cùng val/test (test 100 ảnh). `clean` = bản xuất nháp của lần chạy **Hold** (202 ảnh); `raw` = 224 ảnh gốc. Bảng từ `submission/results/comparison.md`:

| biến thể | #ảnh train | số seed | mAP50 | mAP50-95 | precision | recall |
|---|---:|---:|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 202 | 2 | 0.701 ± 0.025 | 0.487 ± 0.008 | 0.759 ± 0.003 | 0.625 ± 0.019 |

**Chênh mAP50 (clean − raw) = −0.025**, bằng đúng độ lệch giữa 2 seed của `clean` (0.025; seed 0 = 0.718, seed 1 = 0.683). Với chỉ 2 seed và test 100 ảnh, khác biệt này **nằm trong nhiễu**: **chưa kết luận được** clean tốt hơn hay kém hơn raw. mAP50-95 chênh −0.025 lớn hơn độ lệch seed (0.004–0.008) nên có **dấu hiệu** raw nhỉnh hơn, nhưng 2 seed là quá ít để khẳng định.

**`raw` thật sự train trên bao nhiêu ảnh?** Cache của Ultralytics (`work/train/raw/train/labels.cache`) ghi `(216 có nhãn, 6 thiếu nhãn, 13 nhãn rỗng, 11 hỏng, 224 tổng)`: Ultralytics **bỏ cả ảnh** ở 11 ảnh, nên `raw` thực tế chỉ dùng **213 ảnh**, chỉ hơn `clean` 11 ảnh (không phải 22). 11 ảnh này khớp đúng các lỗi pipeline đã bắt: `CORRUPT_IMAGE` 2 (img_0010, img_0136), `BAD_FORMAT` 3 (img_0014, img_0022 nan; img_0179 4 cột), `BAD_CLASS_ID` 6 (img_0020 id 93, img_0099/img_0117 id −1, img_0104 id 7, img_0194/img_0199 id 4). Khác biệt: Ultralytics vứt cả ảnh vì **một** dòng hỏng (img_0020 sai dòng 3 mà mất mọi box đúng), còn autofix chỉ xoá đúng dòng đó. Ultralytics **không** bắt: 5 ảnh rò rỉ test, 12 ảnh trùng, 3 ảnh quá nhỏ, 4 box rỗng, 7 box lặp, box tràn nhẹ (img_0078 tới 1.000018 vẫn được nhận); và 6 ảnh thiếu file nhãn bị coi là **ảnh nền** (dạy model "không có vật" trên ảnh có vật).

**Lớp nào được lợi?** AP50 trung bình 2 seed, raw → clean: car 0.738 → 0.738 (0.000), person 0.822 → 0.823 (+0.001), bus 0.695 → 0.703 (+0.008), **truck 0.648 → 0.538 (−0.110)**. −0.110 / 4 lớp ≈ −0.027 ≈ toàn bộ chênh mAP50: **không lớp nào được lợi rõ rệt**, khác biệt đến gần hết từ truck. Số box theo lớp (raw → clean): car 122 → 101, person 537 → 574, truck 32 → 41, bus 35 → 32. Truck **tăng** box nhưng AP tụt và dao động mạnh giữa 2 seed (0.590 / 0.486): khớp với việc một số box car bị đổi sang truck khi xử lý `POSSIBLE_WRONG_CLASS` (nhầm truck ↔ car là điểm mù ở §4), trên một lớp ít dữ liệu (~40 box). Person tăng 37 box là các box `POSSIBLE_MISSING` được người duyệt thêm vào, nhưng AP person không đổi.

**Giả thuyết và cách kiểm:**
1. **Rò rỉ test trong `raw`:** pipeline phát hiện 5 ảnh `LEAK_TEST` (trùng `test_009, 033, 039, 044, 085`); `raw` train trên chính 5 ảnh test này nên điểm test bị thổi phồng, `clean` đã loại chúng. Chưa đo được mức thổi phồng. *Kiểm:* đánh giá lại cả hai trên test bỏ 5 ảnh đó (95 ảnh) và so chênh lệch.
2. **Đổi lớp truck ↔ car làm hại lớp truck:** *Kiểm:* so từng box truck giữa `data/raw` và `clean_v1` (box nào đổi lớp), mở các ảnh `POSSIBLE_WRONG_CLASS` truck/car, xem AP truck trên test theo từng ảnh.
3. **`clean` chưa phải chặn trên của "dữ liệu sạch":** hàng đợi 125 ảnh > ngân sách 80, nên còn 38 ảnh có cảnh báo chưa duyệt; v3 vẫn còn 13 `POSSIBLE_MISSING`, 20 `LOOSE_BOX`, 21 `FALSE_POS`, 3 `WRONG_CLASS`. *Kiểm:* duyệt đủ hàng đợi (Release) rồi train lại; chạy ≥ 5 seed để thu hẹp nhiễu.

**Kết luận trung thực:** dữ liệu sau pipeline **chưa cho thấy** model tốt hơn: mAP50 chênh −0.025, nằm trong nhiễu seed, và gần như toàn bộ đến từ một lớp ít dữ liệu (truck). Việc tiếp theo: đánh giá trên test bỏ 5 ảnh rò rỉ, kiểm tra các box truck bị đổi lớp, duyệt đủ hàng đợi và chạy ≥ 5 seed trước khi kết luận.

## 6. Quyết định và ghi chú AI
**(a) Quyết định cuối: Hold.** Không có lỗi bắt buộc, nhưng 18,8% ảnh còn cảnh báo chưa duyệt. Để thành **Release** cần tỉ lệ < 10%, tức còn ≤ 20 ảnh cảnh báo chưa duyệt: duyệt thêm ít nhất **18** ảnh trong 45 ảnh cuối hàng (ngân sách ~98+ ảnh), hoặc giảm báo động giả bằng checker tốt hơn. **Không** tăng `conf` để thu nhỏ hàng đợi, vì sẽ làm mù check (MISSING recall giảm) và tạo Release giả.

**(b) Dùng AI (Claude Code):**
- Prompt chính: đưa docstring + file test của từng module (`label_format`, `gate`, `autofix`, `second_opinion`), yêu cầu viết đúng đầu vào/đầu ra, đọc ngưỡng từ `cfg`, không làm chết script với dòng hỏng, không sửa `data/raw`.
- Cách kiểm: đọc từng dòng; chạy `pytest` từng module rồi toàn bộ (79 test); chạy `python -m pipeline.run` và đối chiếu số trong `02_error_list_v1` với `03_fixes.csv` (35 thay đổi khớp tổng các mã); thử `--budget 0` để chắc gate chặn.
- 1 lần AI sai: AI chạy test bằng `.venv\Scripts\python.exe` trong khi máy dùng môi trường conda (base) nên lệnh lỗi; phải chạy lại bằng `python`.
