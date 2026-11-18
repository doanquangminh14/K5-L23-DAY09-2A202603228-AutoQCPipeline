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
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    opt = cfg.get("label_format", {})
    overflow_tol = opt.get("overflow_tol", 0.002)
    min_box_px = opt.get("min_box_px", 12)
    max_box_frac = opt.get("max_box_frac", 0.95)
    dup_box_iou = opt.get("dup_box_iou", 0.9)

    issues: list[Issue] = []
    label_files = ds.label_files()

    for lp in label_files:
        stem = lp.stem
        lines = ds.read_label_lines(stem)
        if lines is None:
            continue

        im_size = ds.image_size(stem)
        valid_boxes: list[tuple[int, int, tuple[float, float, float, float]]] = []

        for line_num, text in lines:
            try:
                c, cx, cy, w, h = parse_yolo_line(text)
            except ValueError as e:
                issues.append(Issue(
                    check="label_format",
                    severity=ERROR,
                    code="BAD_FORMAT",
                    image=stem,
                    message=f"dòng sai định dạng YOLO: {e}",
                    line=line_num,
                ))
                continue

            if not (0 <= c < len(ds.classes)):
                issues.append(Issue(
                    check="label_format",
                    severity=ERROR,
                    code="BAD_CLASS_ID",
                    image=stem,
                    message=f"id lớp {c} ngoài dải 0..{len(ds.classes)-1}",
                    line=line_num,
                    extra={"class_id": c},
                ))
                continue

            if w <= 0 or h <= 0:
                issues.append(Issue(
                    check="label_format",
                    severity=ERROR,
                    code="BOX_ZERO",
                    image=stem,
                    message=f"box kích thước <= 0: w={w}, h={h}",
                    line=line_num,
                    extra={"w": w, "h": h},
                ))
                continue

            # Geometry checks
            x1 = cx - w / 2.0
            y1 = cy - h / 2.0
            x2 = cx + w / 2.0
            y2 = cy + h / 2.0
            overflow = max(0.0, -x1, -y1, x2 - 1.0, y2 - 1.0)
            if overflow > overflow_tol:
                issues.append(Issue(
                    check="label_format",
                    severity=ERROR,
                    code="BOX_OUT_OF_IMAGE",
                    image=stem,
                    message=f"box tràn ảnh: {overflow:.4f} > {overflow_tol}",
                    line=line_num,
                    extra={"overflow": overflow},
                ))

            for prev_line, prev_c, prev_box in valid_boxes:
                if prev_c == c and iou_xywh((cx, cy, w, h), prev_box) > dup_box_iou:
                    issues.append(Issue(
                        check="label_format",
                        severity=ERROR,
                        code="DUP_BOX",
                        image=stem,
                        message=f"box trùng với dòng {prev_line} (cùng lớp {c}, IoU > {dup_box_iou})",
                        line=line_num,
                    ))
                    break

            if im_size is not None:
                img_w, img_h = im_size
                short_px = min(w * img_w, h * img_h)
                if short_px < min_box_px:
                    issues.append(Issue(
                        check="label_format",
                        severity=WARN,
                        code="BOX_TINY",
                        image=stem,
                        message=f"box quá nhỏ: {short_px:.1f}px < {min_box_px}px",
                        line=line_num,
                        extra={"short_px": short_px},
                    ))

            if (w * h) > max_box_frac:
                issues.append(Issue(
                    check="label_format",
                    severity=WARN,
                    code="BOX_HUGE",
                    image=stem,
                    message=f"box quá lớn: diện tích {w*h:.2%} > {max_box_frac:.0%}",
                    line=line_num,
                    extra={"frac": w * h},
                ))

            valid_boxes.append((line_num, c, (cx, cy, w, h)))

    return issues
