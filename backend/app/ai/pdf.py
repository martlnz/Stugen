"""Trích xuất văn bản PDF bằng PyMuPDF, chia chương (ADR-0009) và bài nhỏ (ADR-0017)."""

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import pymupdf

SCAN_CHARS_PER_PAGE = 100
EQUAL_SPLIT_PAGES = 15
MAX_CHAPTER_CHARS = 36_000  # ~12.000 token
MIN_CHAPTER_CHARS = 1_200  # ngắn hơn ~1/2 trang → gộp với chương kế tiếp
MAX_CHAPTERS = 20
FRONT_MATTER_MIN_CHARS = 2_000

# Bài nhỏ (ADR-0017)
MIN_LESSON_CHARS = 1_500
MAX_LESSON_CHARS = 20_000
MAX_LESSON_PAGES = 8
SINGLE_LESSON_PAGES = 6  # chương ngắn hơn thế mà không có tiêu đề phụ → một bài
FALLBACK_LESSON_PAGES = 4
MAX_LESSONS_PER_CHAPTER = 12
INTRO_MIN_CHARS = 400

HEADING_RE = re.compile(r"^(Chương|CHƯƠNG|Chapter|CHAPTER|Bài|BÀI|Phần|PHẦN)\s+([0-9]+|[IVXLC]+)\b")
SUBHEADING_NUMBER_RE = re.compile(r"^\d+(\.\d+)+\.?\s+\S")
GENERIC_CHAPTER_RE = re.compile(r"^Phần \d+ \(trang ")
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
class ExtractedLesson:
    title: str
    page_start: int
    page_end: int
    text: str
    start: Pos = (1, 0)
    end: Pos = (1, 0)

    @property
    def char_count(self) -> int:
        return len(self.text)


@dataclass
class ExtractedChapter:
    title: str
    page_start: int
    page_end: int
    text: str
    start: Pos = (1, 0)
    end: Pos = (1, 0)  # vị trí bắt đầu của chương kế tiếp (không bao gồm)
    lessons: list[ExtractedLesson] = field(default_factory=list)

    @property
    def char_count(self) -> int:
        return len(self.text)

    @property
    def generic_title(self) -> bool:
        return bool(GENERIC_CHAPTER_RE.match(self.title))


@dataclass
class LessonHint:
    """Gợi ý tách bài từ LLM cho chương không có tiêu đề phụ (ADR-0017)."""

    chapter_title: str | None
    starts: list[tuple[str, int]]  # (tên bài, trang bắt đầu)


Refiner = Callable[[ExtractedChapter], LessonHint | None]


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


def _locate(lines: list[str], title: str) -> int | None:
    key = re.sub(r"\s+", " ", title).strip().lower()[:30]
    for i, line in enumerate(lines):
        if key and line.lower().startswith(key):
            return i
    return None


def _find_line(lines: list[str], title: str) -> int:
    return _locate(lines, title) or 0


@dataclass
class _Doc:
    """Dữ liệu dùng chung khi chia chương/bài."""

    pages: list[list[str]]
    toc: list[tuple[int, str, int]]
    toc_level: int
    sized_lines: list[list[tuple[str, float]]]
    median_size: float


def _sized_lines(doc: pymupdf.Document) -> tuple[list[list[tuple[str, float]]], float]:
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
        return page_lines, 0.0
    # Trung vị cỡ chữ có trọng số theo số ký tự (≈ cỡ chữ thân bài)
    half, acc, median = size_chars.total() / 2, 0, 0.0
    for size in sorted(size_chars):
        acc += size_chars[size]
        if acc >= half:
            median = size
            break
    return page_lines, median


def _toc_starts(d: _Doc) -> list[tuple[str, Pos]]:
    entries = [t for t in d.toc if t[0] == d.toc_level]
    return [(title, (page, _find_line(d.pages[page - 1], title))) for _, title, page in entries]


def _heading_starts(d: _Doc) -> list[tuple[str, Pos]]:
    """Dòng khớp mẫu 'Chương N', 'Bài N'... và cỡ chữ lớn hơn hẳn trung vị."""
    starts: list[tuple[str, Pos]] = []
    big = d.median_size * 1.2
    for pno, lines in enumerate(d.sized_lines, start=1):
        for i, (text, size) in enumerate(lines):
            if not (HEADING_RE.match(text) and (size >= big or i < 3)):
                continue
            title = text
            # "Chương 1" đứng riêng một dòng → ghép dòng tiêu đề kế tiếp
            if len(title) < 15 and i + 1 < len(lines) and lines[i + 1][1] >= big:
                title = f"{title}. {lines[i + 1][0]}"
            starts.append((title[:200], (pno, _find_line(d.pages[pno - 1], text))))
    return starts


def _build_text(start: Pos, end: Pos, pages: list[list[str]]) -> tuple[int, int, str]:
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
        return start[0], start[0], ""
    text = "\n\n".join(f"[[trang {p}]]\n{body}" for p, body in chunks)
    return chunks[0][0], chunks[-1][0], text


def _build(title: str, start: Pos, end: Pos, pages: list[list[str]]) -> ExtractedChapter:
    first, last, text = _build_text(start, end, pages)
    return ExtractedChapter(title, first, last, text, start, end)


def _build_lesson(title: str, start: Pos, end: Pos, pages: list[list[str]]) -> ExtractedLesson:
    first, last, text = _build_text(start, end, pages)
    return ExtractedLesson(title, first, last, text, start, end)


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


# ---------- Bài nhỏ ----------


def _in_chapter(pos: Pos, ch: ExtractedChapter) -> bool:
    return ch.start < pos < ch.end


def _subheading_starts(ch: ExtractedChapter, d: _Doc) -> list[tuple[str, Pos]]:
    """Điểm bắt đầu bài trong chương: bookmark cấp dưới → tiêu đề phụ theo cỡ chữ/đánh số."""
    sub_level = d.toc_level + 1
    from_toc = [
        (title, (page, _find_line(d.pages[page - 1], title)))
        for lvl, title, page in d.toc
        if lvl == sub_level
    ]
    from_toc = [s for s in from_toc if _in_chapter(s[1], ch)]
    if from_toc:
        return from_toc

    starts: list[tuple[str, Pos]] = []
    sub_min = d.median_size * 1.1
    for pno in range(ch.page_start, ch.page_end + 1):
        for text, size in d.sized_lines[pno - 1]:
            if not 3 <= len(text) <= 80 or text[-1] in ".,;:" or not re.search(r"[^\W\d_]", text):
                continue
            numbered = bool(SUBHEADING_NUMBER_RE.match(text))
            if not (numbered or size >= sub_min) or HEADING_RE.match(text):
                continue
            line = _locate(d.pages[pno - 1], text)
            if line is None:
                continue
            pos = (pno, line)
            if _in_chapter(pos, ch):
                starts.append((text, pos))
    return starts


CHAPTER_PREFIX_RE = re.compile(
    r"^(Chương|CHƯƠNG|Chapter|CHAPTER|Bài|BÀI|Phần|PHẦN)\s+([0-9]+|[IVXLC]+)\s*[.:\-–]?\s*"
)


def core_title(title: str) -> str:
    """'Chương 3. Ngôn ngữ SQL' → 'Ngôn ngữ SQL' (tên bài không lặp tiền tố chương)."""
    return CHAPTER_PREFIX_RE.sub("", title).strip() or title


def _clip_title(text: str, limit: int = 80) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    return cut[: cut.rfind(" ")].rstrip(" ,;:") + "…" if " " in cut else cut + "…"


def _merge_lessons(
    a: ExtractedLesson, b: ExtractedLesson, pages: list[list[str]]
) -> ExtractedLesson:
    title = a.title if b.title in a.title else _clip_title(f"{a.title}; {b.title}")
    return _build_lesson(title, a.start, b.end, pages)


def _split_long_lesson(lesson: ExtractedLesson, pages: list[list[str]]) -> list[ExtractedLesson]:
    pages_n = lesson.page_end - lesson.page_start + 1
    if (lesson.char_count <= MAX_LESSON_CHARS and pages_n <= MAX_LESSON_PAGES) or pages_n == 1:
        return [lesson]
    parts = max(
        math.ceil(pages_n / MAX_LESSON_PAGES), math.ceil(lesson.char_count / MAX_LESSON_CHARS)
    )
    step = math.ceil(pages_n / parts)
    cuts: list[Pos] = [lesson.start]
    cuts += [(lesson.page_start + step * i, 0) for i in range(1, parts)]
    cuts.append(lesson.end)
    return [
        _build_lesson(f"{lesson.title} (phần {i + 1})", cuts[i], cuts[i + 1], pages)
        for i in range(len(cuts) - 1)
        if cuts[i] < cuts[i + 1]
    ]


def _lessons_from_starts(
    ch: ExtractedChapter, starts: list[tuple[str, Pos]], pages: list[list[str]]
) -> list[ExtractedLesson]:
    starts = sorted({pos: (title, pos) for title, pos in starts}.values(), key=lambda s: s[1])
    bounds: list[tuple[str, Pos]] = []
    if not starts or starts[0][1] > ch.start:
        intro = _build_lesson("", ch.start, starts[0][1] if starts else ch.end, pages)
        if starts and len(intro.text) < INTRO_MIN_CHARS:
            # Mở đầu chỉ có dòng tiêu đề chương → bài đầu tiên bắt đầu từ đầu chương
            starts[0] = (starts[0][0], ch.start)
        else:
            bounds.append((core_title(ch.title), ch.start))
    bounds += starts
    lessons = []
    for i, (title, start) in enumerate(bounds):
        end = bounds[i + 1][1] if i + 1 < len(bounds) else ch.end
        lesson = _build_lesson(title, start, end, pages)
        # "Tài liệu tham khảo", "Nguồn"... không phải nội dung học
        if lesson.text and not NON_CONTENT_TITLES.match(title):
            lessons.append(lesson)
    return lessons


def _normalize_lessons(
    lessons: list[ExtractedLesson], pages: list[list[str]]
) -> list[ExtractedLesson]:
    result: list[ExtractedLesson] = []
    for lesson in lessons:
        result.extend(_split_long_lesson(lesson, pages))
    i = 0
    while len(result) > 1 and i < len(result):
        if result[i].char_count < MIN_LESSON_CHARS:
            if i + 1 < len(result):
                result[i : i + 2] = [_merge_lessons(result[i], result[i + 1], pages)]
            else:
                result[i - 1 : i + 1] = [_merge_lessons(result[i - 1], result[i], pages)]
            continue
        i += 1
    while len(result) > MAX_LESSONS_PER_CHAPTER:
        j = min(
            range(len(result) - 1),
            key=lambda k: result[k].char_count + result[k + 1].char_count,
        )
        result[j : j + 2] = [_merge_lessons(result[j], result[j + 1], pages)]
    return result


def _page_chunks(ch: ExtractedChapter, pages: list[list[str]]) -> list[ExtractedLesson]:
    n = ch.page_end - ch.page_start + 1
    parts = max(1, round(n / FALLBACK_LESSON_PAGES))
    step = math.ceil(n / parts)
    cuts: list[Pos] = [ch.start] + [(ch.page_start + step * i, 0) for i in range(1, parts)]
    cuts.append(ch.end)
    return [
        _build_lesson(f"{core_title(ch.title)} (phần {i + 1})", cuts[i], cuts[i + 1], pages)
        for i in range(len(cuts) - 1)
    ]


def _apply_hint(
    ch: ExtractedChapter, hint: LessonHint, pages: list[list[str]]
) -> list[ExtractedLesson]:
    starts: list[tuple[str, Pos]] = []
    seen: set[int] = set()
    for title, page in sorted(hint.starts, key=lambda s: s[1]):
        page = min(max(page, ch.page_start), ch.page_end)
        if page in seen:
            continue
        seen.add(page)
        pos = ch.start if page == ch.page_start else (page, 0)
        starts.append((title, pos))
    if not starts:
        return []
    # Bài đầu tiên luôn bắt đầu từ đầu chương
    starts[0] = (starts[0][0], ch.start)
    return _lessons_from_starts(ch, starts, pages)


def split_lessons(
    ch: ExtractedChapter, d: _Doc, refine: Refiner | None = None
) -> list[ExtractedLesson]:
    pages = d.pages
    n_pages = ch.page_end - ch.page_start + 1
    starts = [] if ch.generic_title else _subheading_starts(ch, d)
    if starts:
        lessons = _lessons_from_starts(ch, starts, pages)
    elif n_pages <= SINGLE_LESSON_PAGES and not ch.generic_title:
        lessons = [_build_lesson(core_title(ch.title), ch.start, ch.end, pages)]
    else:
        lessons = []
        hint = refine(ch) if refine else None
        if hint:
            if hint.chapter_title and ch.generic_title:
                ch.title = hint.chapter_title
            lessons = _apply_hint(ch, hint, pages)
        if not lessons:
            lessons = _page_chunks(ch, pages)
    lessons = _normalize_lessons(lessons, pages)
    if len(lessons) == 1:
        lessons[0].title = core_title(ch.title)
    return lessons


def page_snippets(text: str, lines_per_page: int = 6) -> str:
    """Vài dòng đầu mỗi trang (kèm [[trang N]]) – đủ để LLM nhận ra ranh giới bài, ít token."""
    out = []
    for block in re.split(r"(?=\[\[trang \d+\]\])", text):
        if block.strip():
            out.append("\n".join(block.strip().splitlines()[: lines_per_page + 1]))
    return "\n\n".join(out)


# ---------- Điểm vào ----------


def _open(data: bytes) -> pymupdf.Document:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        raise PdfError("PDF_CORRUPTED") from None
    if doc.page_count < 1:
        raise PdfError("PDF_CORRUPTED")
    return doc


def _analyze(doc: pymupdf.Document) -> tuple[_Doc, list[ExtractedChapter]]:
    raw_lines = _page_lines(doc)
    total_chars = sum(len(re.sub(r"\s", "", " ".join(lines))) for lines in raw_lines)
    if total_chars < SCAN_CHARS_PER_PAGE * doc.page_count:
        raise PdfError("PDF_NO_TEXT")
    pages = strip_headers_footers(raw_lines)
    toc = [(lvl, normalize(title).strip(), page) for lvl, title, page, *_ in doc.get_toc()]
    toc = [t for t in toc if 1 <= t[2] <= doc.page_count and t[1]]
    level1 = [t for t in toc if t[0] == 1]
    level2 = [t for t in toc if t[0] == 2]
    toc_level = 2 if len(level1) <= 2 and len(level2) > len(level1) else 1
    sized, median = _sized_lines(doc)
    d = _Doc(pages, toc, toc_level, sized, median)

    starts = _toc_starts(d)
    if len(starts) < 2:
        starts = _heading_starts(d)
    chapters = _chapters_from_starts(starts, pages) if len(starts) >= 2 else []
    if not chapters:
        chapters = _equal_split(pages)
    if not chapters:
        raise PdfError("PDF_NO_TEXT")
    return d, _normalize_sizes(chapters, pages)


def extract_chapters(data: bytes) -> list[ExtractedChapter]:
    with _open(data) as doc:
        return _analyze(doc)[1]


def extract_outline(
    data: bytes, refine: Refiner | None = None, workers: int = 4
) -> list[ExtractedChapter]:
    """Chương kèm danh sách bài nhỏ (ADR-0017). `refine` gọi LLM cho chương cần tách bài;
    các chương được xử lý song song để mục lục sẵn sàng trong vài giây."""
    with _open(data) as doc:
        d, chapters = _analyze(doc)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        results = list(pool.map(lambda ch: split_lessons(ch, d, refine), chapters))
    for ch, lessons in zip(chapters, results, strict=True):
        ch.lessons = lessons
    return chapters
