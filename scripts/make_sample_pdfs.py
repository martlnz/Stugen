"""Sinh 3 PDF mẫu để thử thủ công pipeline Stugen (ADR-0009).

    samples/short-10p.pdf  ~10 trang, không bookmark, tiêu đề chương in đậm cỡ lớn
    samples/toc-50p.pdf    ~50 trang, có bookmark, header/footer lặp lại
    samples/scan.pdf       short-10p.pdf chuyển thành ảnh, không có lớp văn bản

Nội dung lấy từ Wikipedia tiếng Việt (CC BY-SA 4.0), mỗi file có trang ghi nguồn.

Chạy:  python scripts/make_sample_pdfs.py [thư_mục_ra]      (cần: pip install pymupdf)
"""

from __future__ import annotations

import html
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pymupdf

UA = "StugenSampleBuilder/0.1 (https://github.com/martlnz/Stugen; test fixtures)"
FONT_DIR = "C:/Windows/Fonts"
PAGE = pymupdf.paper_rect("a4")
BODY = PAGE + (72, 80, -72, -80)
SKIP_SECTIONS = {"xem thêm", "tham khảo", "liên kết ngoài", "chú thích", "đọc thêm",
                 "ghi chú", "nguồn", "thư mục", "tài liệu tham khảo"}

SHORT = {
    "title": "Nhập môn Cơ sở dữ liệu",
    "chapters": [
        ("Cơ sở dữ liệu quan hệ", "Cơ sở dữ liệu quan hệ"),
        ("Đại số quan hệ", "Đại số quan hệ"),
        ("Ngôn ngữ truy vấn SQL", "SQL"),
        ("Khóa chính và khóa ngoại", "Khóa ngoại"),
        ("Giao dịch và tính chất ACID", "ACID"),
    ],
}
LONG = {
    "title": "Nhập môn Khoa học máy tính",
    "max_chars": 18000,
    "chapters": [
        ("Máy tính", "Máy tính"),
        ("Thuật toán", "Thuật toán"),
        ("Ngôn ngữ lập trình", "Ngôn ngữ lập trình"),
        ("Mạng máy tính", "Mạng máy tính"),
        ("Internet", "Internet"),
        ("Trí tuệ nhân tạo", "Trí tuệ nhân tạo"),
        ("Học máy", "Học máy"),
    ],
}

CSS = f"""
@font-face {{font-family: body; src: url(arial.ttf);}}
@font-face {{font-family: body; src: url(arialbd.ttf); font-weight: bold;}}
* {{font-family: body;}}
body {{font-size: 11pt; line-height: 1.35;}}
p {{text-align: justify; margin: 0 0 6pt 0;}}
h1 {{font-size: 20pt; font-weight: bold; margin: 0 0 14pt 0;}}
h2 {{font-size: 14pt; font-weight: bold; margin: 12pt 0 6pt 0;}}
h3 {{font-size: 12pt; font-weight: bold; margin: 10pt 0 4pt 0;}}
.cover {{font-size: 28pt; font-weight: bold; text-align: center; margin-top: 200pt;}}
.sub {{font-size: 13pt; text-align: center;}}
"""


def fetch(title: str) -> str:
    q = urllib.parse.urlencode({"action": "query", "format": "json", "prop": "extracts",
                                "explaintext": 1, "redirects": 1, "titles": title, "maxlag": 5})
    req = urllib.request.Request("https://vi.wikipedia.org/w/api.php?" + q,
                                 headers={"User-Agent": UA})
    for attempt in range(6):
        try:
            data = json.load(urllib.request.urlopen(req, timeout=30))
            text = next(iter(data["query"]["pages"].values())).get("extract") or ""
            if not text:
                raise RuntimeError(f"Bài '{title}' rỗng hoặc không tồn tại")
            time.sleep(3)
            return text
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            time.sleep(int(e.headers.get("Retry-After") or 0) or 15 * (attempt + 1))
    raise RuntimeError(f"Không lấy được '{title}'")


def merge_math(lines: list[str]) -> list[str]:
    """Wikipedia trả công thức thành các mẩu ký tự rời + '{\\displaystyle ...}'.
    Gộp lại thành LaTeX inline '$...$' nằm trong đoạn văn liền trước."""
    out: list[str] = []
    glue_next = False
    for line in lines:
        if line.startswith("{\\displaystyle") and line.endswith("}"):
            latex = line[len("{\\displaystyle"):-1].strip()
            while out and len(out[-1]) <= 4 and not out[-1].startswith("=="):
                out.pop()  # các mẩu ký tự của công thức đã render
            token = f"${latex}$"
            if out and not out[-1].startswith("=="):
                out[-1] = f"{out[-1]} {token}"
            else:
                out.append(token)
            glue_next = True
            continue
        if glue_next and out and (line[0] in ".,;:)" or line[0].islower()):
            out[-1] = f"{out[-1]}{'' if line[0] in '.,;:)' else ' '}{line}"
        else:
            out.append(line)
        glue_next = False
    return out


def to_html(text: str, max_chars: int | None = None) -> str:
    """Wikipedia plaintext ('== Mục ==') → HTML; bỏ các mục tham khảo/liên kết.
    max_chars: dừng ở ranh giới đoạn khi vượt quá số ký tự."""
    lines = merge_math([ln.strip() for ln in text.splitlines() if ln.strip()])
    out: list[str] = []
    skipping = False
    size = 0
    for line in lines:
        if max_chars and size >= max_chars:
            break
        m = re.fullmatch(r"(={2,})\s*(.*?)\s*\1", line)
        if m:
            level, name = len(m.group(1)), m.group(2)
            if level == 2:
                skipping = name.lower() in SKIP_SECTIONS
            if not skipping:
                tag = "h2" if level == 2 else "h3"
                out.append(f"<{tag}>{html.escape(name)}</{tag}>")
            continue
        if not skipping:
            out.append(f"<p>{html.escape(line)}</p>")
            size += len(line)
    return "\n".join(out)


def render(parts: list[str]) -> tuple[pymupdf.Document, list[int]]:
    """Mỗi phần bắt đầu ở trang mới; trả về tài liệu và trang bắt đầu (1-based) của từng phần."""
    archive = pymupdf.Archive(FONT_DIR)
    stream = io.BytesIO()
    writer = pymupdf.DocumentWriter(stream)
    starts: list[int] = []
    page_no = 0
    for part in parts:
        starts.append(page_no + 1)
        story = pymupdf.Story(html=part, user_css=CSS, archive=archive)
        more = True
        while more:
            dev = writer.begin_page(PAGE)
            more, _ = story.place(BODY)
            story.draw(dev)
            writer.end_page()
            page_no += 1
    writer.close()
    return pymupdf.open("pdf", stream.getvalue()), starts


def decorate(doc: pymupdf.Document, header: str) -> None:
    """Header/footer lặp lại trên mọi trang trừ bìa (để thử bộ lọc header/footer)."""
    font = pymupdf.Font(fontfile=f"{FONT_DIR}/arial.ttf")
    for i, page in enumerate(doc):
        if i == 0:
            continue
        page.wrap_contents()  # cô lập ma trận biến đổi của Story, tránh chữ bị lật
        tw = pymupdf.TextWriter(page.rect)
        tw.append((72, 50), header, font=font, fontsize=9)
        tw.append((page.rect.width / 2 - 15, page.rect.height - 40), f"Trang {i + 1}",
                  font=font, fontsize=9)
        tw.write_text(page, color=(0.4, 0.4, 0.4))


def attribution(book: dict) -> str:
    items = "".join(
        f"<p>• {html.escape(art)} – https://vi.wikipedia.org/wiki/"
        f"{html.escape(urllib.parse.quote(art.replace(' ', '_')))}</p>"
        for _, art in book["chapters"])
    return ("<h2>Nguồn nội dung</h2><p>Tài liệu mẫu dùng để thử nghiệm Stugen, ghép từ các bài viết "
            "Wikipedia tiếng Việt, phát hành theo giấy phép Creative Commons Ghi công – Chia sẻ tương "
            "tự 4.0 (CC BY-SA 4.0). Nội dung có thể đã được rút gọn (bỏ phần tham khảo).</p>" + items)


def build_long(book: dict, out: Path) -> None:
    texts = [to_html(fetch(art), book.get("max_chars")) for _, art in book["chapters"]]
    cover = f'<p class="cover">{html.escape(book["title"])}</p><p class="sub">Tài liệu mẫu</p>'
    toc = "<h1>Mục lục</h1>" + "".join(
        f"<p>Chương {i}. {html.escape(name)}</p>" for i, (name, _) in enumerate(book["chapters"], 1))
    chapters = [f"<h1>Chương {i}. {html.escape(name)}</h1>{body}"
                for i, ((name, _), body) in enumerate(zip(book["chapters"], texts), 1)]
    doc, starts = render([cover, toc, *chapters, attribution(book)])
    decorate(doc, book["title"])
    bookmarks = [[1, "Mục lục", starts[1]]]
    bookmarks += [[1, f"Chương {i}. {name}", starts[i + 1]]
                  for i, (name, _) in enumerate(book["chapters"], 1)]
    bookmarks.append([1, "Nguồn nội dung", starts[-1]])
    doc.set_toc(bookmarks)
    doc.set_metadata({"title": book["title"], "author": "Wikipedia (CC BY-SA 4.0)"})
    doc.save(out, garbage=3, deflate=True)
    print(f"{out.name}: {doc.page_count} trang, {len(bookmarks)} bookmark")


def build_short(book: dict, out: Path) -> None:
    body = f'<p class="cover">{html.escape(book["title"])}</p><p class="sub">Tài liệu mẫu</p>'
    parts = [body]
    chapters = "".join(
        f"<h1>Chương {i}. {html.escape(name)}</h1>{to_html(fetch(art))}"
        for i, (name, art) in enumerate(book["chapters"], 1))
    parts.append(chapters + attribution(book))
    doc, _ = render(parts)
    decorate(doc, book["title"])
    doc.set_metadata({"title": book["title"], "author": "Wikipedia (CC BY-SA 4.0)"})
    doc.save(out, garbage=3, deflate=True)
    print(f"{out.name}: {doc.page_count} trang, không bookmark")


def build_scan(src: Path, out: Path) -> None:
    """Mỗi trang → ảnh xám JPEG; tài liệu kết quả không có lớp văn bản."""
    with pymupdf.open(src) as doc, pymupdf.open() as scan:
        for page in doc:
            pix = page.get_pixmap(dpi=120, colorspace=pymupdf.csGRAY)
            new = scan.new_page(width=page.rect.width, height=page.rect.height)
            new.insert_image(new.rect, stream=pix.tobytes("jpg", jpg_quality=70))
        scan.save(out, garbage=3, deflate=True)
        print(f"{out.name}: {scan.page_count} trang ảnh, không có văn bản")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "samples")
    out_dir.mkdir(parents=True, exist_ok=True)
    build_short(SHORT, out_dir / "short-10p.pdf")
    build_scan(out_dir / "short-10p.pdf", out_dir / "scan.pdf")
    build_long(LONG, out_dir / "toc-50p.pdf")


if __name__ == "__main__":
    main()
