"""Sinh PDF nhỏ cho test: python -m tests.fixtures.make_fixtures (chạy trong container api).

sample.pdf (14 trang, bookmark cấp 1, header lặp + footer "Trang N"):
- Chương 1 (tr. 1–4): bookmark cấp 2 "1.1" (tr. 1), "1.2" (tr. 3) → 2 bài
- Chương 2 (tr. 5–6): tiêu đề phụ cỡ chữ lớn ở tr. 6, không có bookmark → 2 bài
- Chương 3 (tr. 7–14): không tiêu đề phụ, dài 8 trang → LLM tách bài (ADR-0017)
"""

from pathlib import Path

import pymupdf

OUT = Path(__file__).parent

# (tiêu đề chương, câu mẫu, [(tiêu đề phụ, có bookmark cấp 2)] theo từng trang)
CHAPTERS = [
    (
        "Chương 1. Tổng quan về cơ sở dữ liệu",
        "Cơ sở dữ liệu là tập hợp dữ liệu có tổ chức. ",
        [
            ("1.1 Khái niệm cơ sở dữ liệu", True),
            None,
            ("1.2 Hệ quản trị cơ sở dữ liệu", True),
            None,
        ],
    ),
    (
        "Chương 2. Mô hình quan hệ",
        "Quan hệ là bảng gồm các bộ và thuộc tính. Khoá chính $K$. ",
        [None, ("Khoá chính và khoá ngoại", False)],
    ),
    (
        "Chương 3. Ngôn ngữ SQL",
        "SQL dùng để truy vấn và thao tác dữ liệu quan hệ. ",
        [None] * 8,
    ),
]


def _text(page: pymupdf.Page, rect: tuple[float, float, float, float], text: str, px: int) -> None:
    # insert_htmlbox dùng font Noto có sẵn của MuPDF → giữ được dấu tiếng Việt
    page.insert_htmlbox(pymupdf.Rect(*rect), f'<p style="font-size:{px}px">{text}</p>')


def sample() -> None:
    doc = pymupdf.open()
    toc = []
    for title, sentence, page_specs in CHAPTERS:
        for part, sub in enumerate(page_specs):
            page = doc.new_page()
            n = doc.page_count
            _text(page, (72, 30, 520, 50), "Giáo trình Cơ sở dữ liệu", 9)
            y = 80
            if part == 0:
                _text(page, (72, y, 520, y + 30), title, 18)
                toc.append([1, title, n])
                y += 40
            if sub:
                _text(page, (72, y, 520, y + 28), sub[0], 16)
                if sub[1]:
                    toc.append([2, sub[0], n])
                y += 30
            body = " ".join(f"{i + 1}. {sentence}" for i in range(32))
            _text(page, (72, y, 520, 780), body, 11)
            _text(page, (270, 800, 340, 820), f"Trang {n}", 9)
    doc.set_toc(toc)
    doc.set_metadata({"title": "Nhập môn Cơ sở dữ liệu"})
    doc.subset_fonts()
    doc.save(OUT / "sample.pdf", garbage=3, deflate=True)


def scan() -> None:
    """2 trang chỉ có ảnh, không có lớp văn bản."""
    src = pymupdf.open(OUT / "sample.pdf")
    doc = pymupdf.open()
    for i in range(2):
        jpeg = src[i].get_pixmap(dpi=50).tobytes("jpeg")
        page = doc.new_page()
        page.insert_image(page.rect, stream=jpeg)
    doc.save(OUT / "scan.pdf", garbage=3, deflate=True)


def encrypted() -> None:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Bí mật")
    doc.save(
        OUT / "encrypted.pdf",
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw="secret",
        owner_pw="owner",
    )


if __name__ == "__main__":
    sample()
    scan()
    encrypted()
