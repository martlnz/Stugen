"""Sinh PDF nhỏ cho test: python -m tests.fixtures.make_fixtures (chạy trong container api)."""

from pathlib import Path

import pymupdf

OUT = Path(__file__).parent

CHAPTERS = [
    ("Chương 1. Tổng quan về cơ sở dữ liệu", "Cơ sở dữ liệu là tập hợp dữ liệu có tổ chức. "),
    ("Chương 2. Mô hình quan hệ", "Quan hệ là bảng gồm các bộ và thuộc tính. Khoá chính $K$. "),
    ("Chương 3. Ngôn ngữ SQL", "SQL dùng để truy vấn và thao tác dữ liệu quan hệ. "),
]


def _text(page: pymupdf.Page, rect: tuple[float, float, float, float], text: str, px: int) -> None:
    # insert_htmlbox dùng font Noto có sẵn của MuPDF → giữ được dấu tiếng Việt
    page.insert_htmlbox(pymupdf.Rect(*rect), f'<p style="font-size:{px}px">{text}</p>')


def sample() -> None:
    """6 trang, 3 chương có bookmark, header lặp + footer 'Trang N'."""
    doc = pymupdf.open()
    toc = []
    for title, sentence in CHAPTERS:
        for part in range(2):
            page = doc.new_page()
            n = doc.page_count
            _text(page, (72, 30, 520, 50), "Giáo trình Cơ sở dữ liệu", 9)
            y = 80
            if part == 0:
                _text(page, (72, y, 520, y + 30), title, 18)
                toc.append([1, title, n])
                y += 40
            body = " ".join(f"{i + 1}. {sentence}" for i in range(40))
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
