from pathlib import Path
import tempfile

import fitz

from app.services.pdf_ingestion import PDFIngestionAnalyzer


def make_text_pdf(path: Path):
    doc = fitz.open()
    for i in range(1, 4):
        page = doc.new_page()
        page.insert_text((72, 72), f"Глава {i}. Учебный текст", fontsize=16)
        body = (f"Это тестовая страница {i}. " * 80).strip()
        page.insert_textbox((72, 110, 520, 760), body, fontsize=10)
    doc.set_toc([[1, "Раздел 1", 1], [2, "Тема 1", 1], [2, "Тема 2", 2], [1, "Раздел 2", 3]])
    doc.save(path)
    doc.close()


def make_scan_like_pdf(path: Path):
    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    doc.save(path)
    doc.close()


def main():
    analyzer = PDFIngestionAnalyzer()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        text_pdf = td / 'text.pdf'
        scan_pdf = td / 'scan.pdf'
        make_text_pdf(text_pdf)
        make_scan_like_pdf(scan_pdf)

        text_inspection = analyzer.inspect(text_pdf)
        chunks = analyzer.make_chunks(text_inspection)
        scan_inspection = analyzer.inspect(scan_pdf)

        errors = []
        if text_inspection.page_count != 3:
            errors.append('Text PDF page count mismatch')
        if text_inspection.needs_ocr:
            errors.append('Text PDF incorrectly marked needs_ocr')
        if not chunks:
            errors.append('Text PDF produced no chunks')
        if len(text_inspection.sections) != 4:
            errors.append('TOC extraction mismatch')
        if not scan_inspection.needs_ocr:
            errors.append('Scan-like PDF should require OCR')
        if analyzer.make_chunks(scan_inspection):
            errors.append('Scan-like PDF must not produce text chunks before OCR')

        result = {
            'text_pdf_pages': text_inspection.page_count,
            'text_pdf_chars': text_inspection.text_char_count,
            'toc_sections': len(text_inspection.sections),
            'chunks': len(chunks),
            'scan_needs_ocr': scan_inspection.needs_ocr,
            'errors': errors,
        }
        print(result)
        if errors:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
