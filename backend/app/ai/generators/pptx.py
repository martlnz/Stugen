"""Xuất SlideDeck ra PPTX bằng python-pptx (ADR-0011); LaTeX giữ dạng văn bản thô."""

import io

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Emu, Pt

from app.schemas.llm import Slide, SlideDeck

# Layout của template mặc định python-pptx
LAYOUT_TITLE, LAYOUT_CONTENT, LAYOUT_SECTION = 0, 1, 2
ACCENT = RGBColor(0x1F, 0x4E, 0x79)
MUTED = RGBColor(0x59, 0x59, 0x59)


def _add_notes(pptx_slide, slide: Slide) -> None:  # type: ignore[no-untyped-def]
    notes = slide.notes or ""
    if slide.page_refs:
        refs = ", ".join(str(p) for p in slide.page_refs)
        notes = f"{notes}\n\nTrang tham chiếu: {refs}".strip()
    if notes:
        pptx_slide.notes_slide.notes_text_frame.text = notes


def build_pptx(deck: SlideDeck) -> bytes:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)  # 16:9
    width = prs.slide_width

    for slide in deck.slides:
        if slide.layout == "title":
            s = prs.slides.add_slide(prs.slide_layouts[LAYOUT_TITLE])
            s.shapes.title.text = slide.title
            s.placeholders[1].text = slide.subtitle or ""
        elif slide.layout == "section":
            s = prs.slides.add_slide(prs.slide_layouts[LAYOUT_SECTION])
            s.shapes.title.text = slide.title
            s.placeholders[1].text = slide.subtitle or ""
        else:
            s = prs.slides.add_slide(prs.slide_layouts[LAYOUT_CONTENT])
            s.shapes.title.text = slide.title
            body = s.placeholders[1]
            body.width = width - body.left * 2
            frame = body.text_frame
            frame.clear()
            for i, bullet in enumerate(slide.bullets):
                para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
                para.text = bullet
                para.font.size = Pt(22 if len(slide.bullets) <= 4 else 18)
            if slide.page_refs:
                box = s.shapes.add_textbox(body.left, prs.slide_height - Emu(500000), width, Pt(20))
                run = box.text_frame.paragraphs[0].add_run()
                run.text = "Trang " + ", ".join(str(p) for p in slide.page_refs)
                run.font.size = Pt(12)
                run.font.color.rgb = MUTED
        s.shapes.title.text_frame.paragraphs[0].font.color.rgb = ACCENT
        s.shapes.title.width = width - s.shapes.title.left * 2
        _add_notes(s, slide)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()
