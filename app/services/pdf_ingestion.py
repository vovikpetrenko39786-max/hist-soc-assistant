from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
import re

import fitz  # PyMuPDF


@dataclass
class PageExtract:
    page_number_pdf: int
    page_label: str | None
    printed_page: int | None
    text: str
    char_count: int
    has_text: bool
    text_hash: str | None
    width: float
    height: float


@dataclass
class SectionExtract:
    level: int
    title: str
    start_page_pdf: int
    end_page_pdf: int | None
    order_index: int
    parent_order_index: int | None = None


@dataclass
class ChunkExtract:
    chunk_index: int
    text: str
    page_pdf_start: int
    page_pdf_end: int
    page_print_start: int | None
    page_print_end: int | None
    text_hash: str
    char_count: int
    section_order_index: int | None = None


@dataclass
class PDFInspection:
    file_hash: str
    file_size_bytes: int
    page_count: int
    text_char_count: int
    pages_with_text: int
    has_text_layer: bool
    needs_ocr: bool
    metadata: dict
    pages: list[PageExtract] = field(default_factory=list)
    sections: list[SectionExtract] = field(default_factory=list)


class PDFIngestionAnalyzer:
    """Deterministic PDF extraction for the source-ingestion pipeline.

    Rules:
    - PDF page numbers stored here are 1-based.
    - Printed page is only populated from an embedded PDF page label when it is purely numeric.
      We do not infer a printed page number from headers/footers.
    - A scan with too little extractable text is marked `needs_ocr`; OCR is a separate operation.
    - Exact quotes/pages should later be grounded in SourcePage rows, not model memory.
    """

    MIN_TEXT_CHARS_PER_TEXT_PAGE = 40
    MIN_TEXT_PAGE_RATIO = 0.60

    @staticmethod
    def sha256_file(path: str | Path) -> str:
        h = sha256()
        with open(path, 'rb') as fh:
            for block in iter(lambda: fh.read(1024 * 1024), b''):
                h.update(block)
        return h.hexdigest()

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.replace('\u00ad', '')
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    @staticmethod
    def _numeric_page_label(label: str | None) -> int | None:
        if not label:
            return None
        value = label.strip()
        return int(value) if value.isdigit() else None

    def inspect(self, path: str | Path) -> PDFInspection:
        path = Path(path)
        if path.suffix.lower() != '.pdf':
            raise ValueError('Only PDF files are accepted by PDFIngestionAnalyzer')

        file_hash = self.sha256_file(path)
        doc = fitz.open(path)
        try:
            pages: list[PageExtract] = []
            total_chars = 0
            pages_with_text = 0

            for i, page in enumerate(doc):
                raw = page.get_text('text', sort=True) or ''
                text = self._normalize_text(raw)
                char_count = len(text)
                has_text = char_count >= self.MIN_TEXT_CHARS_PER_TEXT_PAGE
                if has_text:
                    pages_with_text += 1
                total_chars += char_count
                try:
                    label = page.get_label() or None
                except Exception:
                    label = None
                rect = page.rect
                pages.append(
                    PageExtract(
                        page_number_pdf=i + 1,
                        page_label=label,
                        printed_page=self._numeric_page_label(label),
                        text=text,
                        char_count=char_count,
                        has_text=has_text,
                        text_hash=sha256(text.encode('utf-8')).hexdigest() if text else None,
                        width=float(rect.width),
                        height=float(rect.height),
                    )
                )

            page_count = len(pages)
            ratio = (pages_with_text / page_count) if page_count else 0.0
            has_text_layer = page_count > 0 and pages_with_text > 0
            needs_ocr = page_count > 0 and (
                not has_text_layer or ratio < self.MIN_TEXT_PAGE_RATIO
            )

            sections = self._extract_toc(doc, page_count)
            metadata = {k: v for k, v in (doc.metadata or {}).items() if v}

            return PDFInspection(
                file_hash=file_hash,
                file_size_bytes=path.stat().st_size,
                page_count=page_count,
                text_char_count=total_chars,
                pages_with_text=pages_with_text,
                has_text_layer=has_text_layer,
                needs_ocr=needs_ocr,
                metadata=metadata,
                pages=pages,
                sections=sections,
            )
        finally:
            doc.close()

    def _extract_toc(self, doc: fitz.Document, page_count: int) -> list[SectionExtract]:
        raw = doc.get_toc(simple=True) or []
        result: list[SectionExtract] = []
        stack: list[tuple[int, int]] = []  # (level, order_index)
        for idx, item in enumerate(raw):
            if len(item) < 3:
                continue
            level, title, page_no = int(item[0]), str(item[1]).strip(), int(item[2])
            if not title or page_no <= 0 or page_no > max(page_count, 1):
                continue
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent_order_index = stack[-1][1] if stack else None
            order_index = len(result)
            result.append(
                SectionExtract(
                    level=level,
                    title=title,
                    start_page_pdf=page_no,
                    end_page_pdf=None,
                    order_index=order_index,
                    parent_order_index=parent_order_index,
                )
            )
            stack.append((level, order_index))

        # End page is the page before the next heading of the same or higher hierarchy.
        for i, section in enumerate(result):
            end_page = page_count
            for nxt in result[i + 1:]:
                if nxt.level <= section.level:
                    end_page = max(section.start_page_pdf, nxt.start_page_pdf - 1)
                    break
            section.end_page_pdf = end_page
        return result

    def make_chunks(
        self,
        inspection: PDFInspection,
        target_chars: int = 1800,
        max_chars: int = 2600,
    ) -> list[ChunkExtract]:
        if inspection.needs_ocr:
            return []

        section_by_page: dict[int, int] = {}
        # Prefer the most specific (highest level number) section covering a page.
        for section in sorted(inspection.sections, key=lambda s: s.level):
            for page_no in range(section.start_page_pdf, (section.end_page_pdf or section.start_page_pdf) + 1):
                section_by_page[page_no] = section.order_index

        pieces: list[tuple[str, int, int | None, int | None]] = []
        for page in inspection.pages:
            if not page.text:
                continue
            paragraphs = [p.strip() for p in re.split(r'\n\s*\n', page.text) if p.strip()]
            if not paragraphs:
                paragraphs = [page.text]
            for paragraph in paragraphs:
                # Split pathological huge paragraphs without inventing structure.
                if len(paragraph) <= max_chars:
                    pieces.append((paragraph, page.page_number_pdf, page.printed_page, section_by_page.get(page.page_number_pdf)))
                else:
                    for start in range(0, len(paragraph), target_chars):
                        part = paragraph[start:start + target_chars].strip()
                        if part:
                            pieces.append((part, page.page_number_pdf, page.printed_page, section_by_page.get(page.page_number_pdf)))

        chunks: list[ChunkExtract] = []
        buffer: list[str] = []
        page_start = page_end = None
        print_start = print_end = None
        section_idx = None

        def flush():
            nonlocal buffer, page_start, page_end, print_start, print_end, section_idx
            if not buffer or page_start is None or page_end is None:
                return
            text = '\n\n'.join(buffer).strip()
            if text:
                chunks.append(
                    ChunkExtract(
                        chunk_index=len(chunks),
                        text=text,
                        page_pdf_start=page_start,
                        page_pdf_end=page_end,
                        page_print_start=print_start,
                        page_print_end=print_end,
                        text_hash=sha256(text.encode('utf-8')).hexdigest(),
                        char_count=len(text),
                        section_order_index=section_idx,
                    )
                )
            buffer = []
            page_start = page_end = None
            print_start = print_end = None
            section_idx = None

        for text, pdf_page, printed_page, piece_section in pieces:
            current_len = sum(len(x) for x in buffer) + max(0, len(buffer) - 1) * 2
            section_changed = buffer and piece_section is not None and section_idx is not None and piece_section != section_idx
            would_overflow = buffer and current_len + len(text) + 2 > max_chars
            if section_changed or would_overflow or (buffer and current_len >= target_chars):
                flush()

            if not buffer:
                page_start = pdf_page
                print_start = printed_page
                section_idx = piece_section
            buffer.append(text)
            page_end = pdf_page
            print_end = printed_page

        flush()
        return chunks
