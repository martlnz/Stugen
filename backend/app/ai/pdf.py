"""Trích xuất văn bản và chia chương PDF bằng PyMuPDF (ADR-0009)."""

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

import pymupdf

SCAN_CHARS_PER_PAGE = 100
EQUAL_SPLIT_PAGES = 15
MAX_CHAPTER_CHARS = 36_000  # ~12.000 token
MIN_CHAPTER_CHARS = 1_200  # ngắn hơn ~1/2 trang → gộp với chương kế tiếp
MAX_CHAPTERS = 20
FRONT_MATTER_MIN_CHARS = 2_000

HEADING_RE = re.compile(r"^(Chương|CHƯƠNG|Chapter|CHAPTER|Bài|BÀI|Phần|PHẦN)\s+([0-9]+|[IVXLC]+)\b")
NON_CONTENT_TITLES = re.compile(
    r"^(mục lục|table of contents|contents|tài liệu tham khảo|references|bibliography|index|"
    r"nguồn( nội dung)?|chỉ mục)\b",
    re.IGNORECASE,
)

Pos = tuple[int, int]  # (số trang bắt đầu từ 1, chỉ số dòng trong trang đã làm sạch)


class PdfError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class ExtractedChapter:
    title: str
    page_start: int
    page_end: int
    text: str
    start: Pos = (1, 0)
    end: Pos = (1, 0)  # vị trí bắt đầu của chương kế tiếp (không bao gồm)

    @property
    def char_count(self) -> int:
        return len(self.text)


def normalize(text: str) -> str:
    """NFC (bắt buộc với tiếng Việt), bỏ NBSP, soft hyphen, zero-width space."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\xa0", " ").replace("\xad", "").replace("​", "")
    return re.sub(r"[ \t]+", " ", text)


def _line_key(line: str) -> str:
    return re.sub(r"\d+", "#", line.strip().lower())


def strip_headers_footers(pages: list[list[str]]) -> list[list[str]]:
    """Bỏ dòng lặp ở đầu/cuối trang (≥ 50% số trang); chữ số được thay ký tự đại diện."""
    if len(pages) < 3:
        return pages
    zone = 2

    def zone_indices(lines: list[str]) -> set[int]:
        n = len(lines)
        return set(range(min(zone, n))) | set(range(max(0, n - zone), n))

    counts: Counter[str] = Counter()
    for lines in pages:
        counts.update({_line_key(lines[i]) for i in zone_indices(lines)})
    repeated = {k for k, c in counts.items() if c >= len(pages) * 0.5}
    if not repeated:
        return pages
    result = []
    for lines in pages:
        drop = {i for i in zone_indices(lines) if _line_key(lines[i]) in repeated}
        result.append([x for i, x in enumerate(lines) if i not in drop])
    return result


def _page_lines(doc: pymupdf.Document) -> list[list[str]]:
    pages = []
    for page in doc:
        text = normalize(page.get_text("text", sort=True))
        pages.append([line.strip() for line in text.splitlines() if line.strip()])
    return pages


def _find_line(lines: list[str], title: str) -> int:
    key = re.sub(r"\s+", " ", title).strip().lower()[:30]
    for i, line in enumerate(lines):
        if key and line.lower().startswith(key):
            return i
    return 0


def _toc_starts(doc: pymupdf.Document, pages: list[list[str]]) -> list[tuple[str, Pos]]:
    toc = [(lvl, normalize(title).strip(), page) for lvl, title, page, *_ in doc.get_toc()]
    toc = [t for t in toc if 1 <= t[2] <= doc.page_count and t[1]]
    level1 = [t for t in toc if t[0] == 1]
    level2 = [t for t in toc if t[0] == 2]
    entries = level2 if len(level1) <= 2 and len(level2) > len(level1) else level1
    return [(title, (page, _find_line(pages[page - 1], title))) for _, title, page in entries]


def _heading_starts(doc: pymupdf.Document, pages: list[list[str]]) -> list[tuple[str, Pos]]:
    """Dòng khớp mẫu 'Chương N', 'Bài N'... và cỡ chữ lớn hơn hẳn trung vị."""
    size_chars: Counter[float] = Counter()
    page_lines: list[list[tuple[str, float]]] = []
    for page in doc:
        lines = []
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                for span in spans:
                    size_chars[round(span["size"], 1)] += len(span["text"])
                text = normalize("".join(s["text"] for s in spans)).strip()
                lines.append((text, max(s["size"] for s in spans)))
        page_lines.append(lines)
    if not size_chars:
        return []
    # Trung vị cỡ chữ có trọng số theo số ký tự (≈ cỡ chữ thân bài)
    half, acc, median = size_chars.total() / 2, 0, 0.0
    for size in sorted(size_chars):
        acc += size_chars[size]
        if acc >= half:
            median = size
            break
    starts: list[tuple[str, Pos]] = []
    for pno, lines in enumerate(page_lines, start=1):
        for i, (text, size) in enumerate(lines):
            if not (HEADING_RE.match(text) and (size >= median * 1.2 or i < 3)):
                continue
            title = text
            # "Chương 1" đứng riêng một dòng → ghép dòng tiêu đề kế tiếp
            if len(title) < 15 and i + 1 < len(lines) and lines[i + 1][1] >= median * 1.2:
                title = f"{title}. {lines[i + 1][0]}"
            starts.append((title[:200], (pno, _find_line(pages[pno - 1], text))))
    return starts


def _build(title: str, start: Pos, end: Pos, pages: list[list[str]]) -> ExtractedChapter:
    """Ghép văn bản từ `start` tới trước `end`, đánh dấu [[trang N]] ở đầu mỗi trang."""
    chunks: list[tuple[int, str]] = []
    for p in range(start[0], min(end[0], len(pages)) + 1):
        lines = pages[p - 1]
        lo = start[1] if p == start[0] else 0
        hi = end[1] if p == end[0] else len(lines)
        body = "\n".join(lines[lo:hi]).strip()
        if body:
            chunks.append((p, body))
    if not chunks:
        return ExtractedChapter(title, start[0], start[0], "", start, end)
    text = "\n\n".join(f"[[trang {p}]]\n{body}" for p, body in chunks)
    return ExtractedChapter(title, chunks[0][0], chunks[-1][0], text, start, end)


def _chapters_from_starts(
    starts: list[tuple[str, Pos]], pages: list[list[str]]
) -> list[ExtractedChapter]:
    starts = sorted(starts, key=lambda s: s[1])
    deduped: list[tuple[str, Pos]] = []
    for title, pos in starts:
        if deduped and deduped[-1][1] == pos:
            continue
        deduped.append((title, pos))
    doc_end: Pos = (len(pages) + 1, 0)
    chapters = []
    first = deduped[0][1]
    if first > (1, 0):
        front = _build("Mở đầu", (1, 0), first, pages)
        if front.char_count >= FRONT_MATTER_MIN_CHARS:
            chapters.append(front)
    for i, (title, start) in enumerate(deduped):
        end = deduped[i + 1][1] if i + 1 < len(deduped) else doc_end
        chapters.append(_build(title, start, end, pages))
    return [c for c in chapters if c.text and not NON_CONTENT_TITLES.match(c.title)]


def _equal_split(pages: list[list[str]]) -> list[ExtractedChapter]:
    page_count = len(pages)
    parts = max(1, math.ceil(page_count / EQUAL_SPLIT_PAGES))
    size = math.ceil(page_count / parts)
    chapters = []
    for i in range(parts):
        start, end = i * size + 1, min(page_count, (i + 1) * size)
        if start <= end:
            title = f"Phần {i + 1} (trang {start}–{end})"
            chapters.append(_build(title, (start, 0), (end + 1, 0), pages))
    return [c for c in chapters if c.text]


def _split_long(chapter: ExtractedChapter, pages: list[list[str]]) -> list[ExtractedChapter]:
    if chapter.char_count <= MAX_CHAPTER_CHARS or chapter.page_start == chapter.page_end:
        return [chapter]
    cuts: list[Pos] = [chapter.start]
    acc = 0
    for p in range(chapter.page_start, chapter.page_end + 1):
        acc += sum(len(x) for x in pages[p - 1])
        if acc >= MAX_CHAPTER_CHARS * 0.8 and p < chapter.page_end:
            cuts.append((p + 1, 0))
            acc = 0
    cuts.append(chapter.end)
    if len(cuts) == 2:
        return [chapter]
    return [
        _build(f"{chapter.title} (phần {i + 1})", cuts[i], cuts[i + 1], pages)
        for i in range(len(cuts) - 1)
    ]


def _merge(a: ExtractedChapter, b: ExtractedChapter, pages: list[list[str]]) -> ExtractedChapter:
    title = a.title if a.char_count >= b.char_count else b.title
    return _build(title, a.start, b.end, pages)


def _normalize_sizes(
    chapters: list[ExtractedChapter], pages: list[list[str]]
) -> list[ExtractedChapter]:
    result: list[ExtractedChapter] = []
    for ch in chapters:
        result.extend(_split_long(ch, pages))
    # Gộp chương quá ngắn với chương kế tiếp (chương cuối gộp với chương trước)
    i = 0
    while len(result) > 1 and i < len(result):
        if result[i].char_count < MIN_CHAPTER_CHARS:
            if i + 1 < len(result):
                result[i : i + 2] = [_merge(result[i], result[i + 1], pages)]
            else:
                result[i - 1 : i + 1] = [_merge(result[i - 1], result[i], pages)]
            continue
        i += 1
    # Tối đa 20 chương: gộp cặp liền kề có tổng ngắn nhất
    while len(result) > MAX_CHAPTERS:
        j = min(
            range(len(result) - 1),
            key=lambda k: result[k].char_count + result[k + 1].char_count,
        )
        result[j : j + 2] = [_merge(result[j], result[j + 1], pages)]
    return result


def extract_chapters(data: bytes) -> list[ExtractedChapter]:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        raise PdfError("PDF_CORRUPTED") from None
    with doc:
        if doc.page_count < 1:
            raise PdfError("PDF_CORRUPTED")
        raw_lines = _page_lines(doc)
        total_chars = sum(len(re.sub(r"\s", "", " ".join(lines))) for lines in raw_lines)
        if total_chars < SCAN_CHARS_PER_PAGE * doc.page_count:
            raise PdfError("PDF_NO_TEXT")
        pages = strip_headers_footers(raw_lines)

        starts = _toc_starts(doc, pages)
        if len(starts) < 2:
            starts = _heading_starts(doc, pages)
        chapters = _chapters_from_starts(starts, pages) if len(starts) >= 2 else []
    if not chapters:
        chapters = _equal_split(pages)
    if not chapters:
        raise PdfError("PDF_NO_TEXT")
    return _normalize_sizes(chapters, pages)
