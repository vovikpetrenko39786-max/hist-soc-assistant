from pathlib import Path

import fitz

from app.services.pdf_ingestion import PDFIngestionAnalyzer


def test_text_pdf_is_chunked(tmp_path: Path):
    path = tmp_path / 'book.pdf'
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox((72, 72, 520, 760), 'Учебный текст. ' * 200, fontsize=10)
    doc.save(path)
    doc.close()

    analyzer = PDFIngestionAnalyzer()
    inspection = analyzer.inspect(path)
    assert inspection.page_count == 1
    assert inspection.needs_ocr is False
    chunks = analyzer.make_chunks(inspection)
    assert len(chunks) >= 1
    assert chunks[0].page_pdf_start == 1


def test_blank_pdf_requires_ocr(tmp_path: Path):
    path = tmp_path / 'scan.pdf'
    doc = fitz.open()
    doc.new_page()
    doc.save(path)
    doc.close()

    analyzer = PDFIngestionAnalyzer()
    inspection = analyzer.inspect(path)
    assert inspection.needs_ocr is True
    assert analyzer.make_chunks(inspection) == []
