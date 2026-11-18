"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


NAME = "label_format"


def run(ds, cfg):
    c = cfg["label_format"]
    tol, dup_iou = c["overflow_tol"], c["dup_box_iou"]
    min_px, max_frac = c["min_box_px"], c["max_box_frac"]
    n_cls = len(ds.classes)
    issues = []

    for p in ds.label_files():
        stem = p.stem
        size = ds.image_size(stem)          # (W, H) hoặc None nếu không mở được ảnh
        seen = []                           # box hợp lệ ở các dòng trước: (cls, x, y, w, h)

        for n, text in ds.read_label_lines(stem) or []:
            # 1. định dạng: phải đúng 5 cột số
            try:
                cls, x, y, w, h = parse_yolo_line(text)
            except ValueError as e:
                issues.append(Issue(NAME, ERROR, "BAD_FORMAT", stem, f"dòng sai định dạng: {e}", line=n))
                continue

            # 2. id lớp
            if not 0 <= cls < n_cls:
                issues.append(Issue(NAME, ERROR, "BAD_CLASS_ID", stem, f"id lớp {cls} ngoài 0..{n_cls - 1}", line=n))
                continue

            # 3. box rỗng
            if w <= 0 or h <= 0:
                issues.append(Issue(NAME, ERROR, "BOX_ZERO", stem, f"box rỗng w={w} h={h}", line=n))
                continue

            # 4. tràn ảnh: mức tràn lớn nhất trong 4 mép
            overflow = max(0 - (x - w / 2), (x + w / 2) - 1, 0 - (y - h / 2), (y + h / 2) - 1)
            if overflow > tol:
                issues.append(Issue(NAME, ERROR, "BOX_OUT_OF_IMAGE", stem, f"box tràn ảnh {overflow:.4f}",
                                    line=n, extra={"overflow": round(overflow, 6)}))

            # 5. box lặp: cùng lớp với một dòng trước, IoU cao -> báo ở dòng sau
            box = (x, y, w, h)
            if any(sc == cls and iou_xywh(sb, box) > dup_iou for sc, sb in seen):
                issues.append(Issue(NAME, ERROR, "DUP_BOX", stem, "box lặp với một dòng trước (cùng lớp)", line=n))
            seen.append((cls, box))

            # 6. box quá nhỏ (theo px, cần kích thước ảnh)
            if size:
                short = min(w * size[0], h * size[1])
                if short < min_px:
                    issues.append(Issue(NAME, WARN, "BOX_TINY", stem, f"cạnh ngắn {short:.1f}px < {min_px}px",
                                        line=n, extra={"short_px": round(short, 1)}))

            # 7. box quá to
            if w * h > max_frac:
                issues.append(Issue(NAME, WARN, "BOX_HUGE", stem, f"box chiếm {w * h:.2f} diện tích ảnh", line=n))

    return issues
