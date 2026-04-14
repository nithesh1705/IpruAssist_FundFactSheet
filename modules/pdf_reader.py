"""
PDF reader module: validates the input file, converts PDF pages to high-resolution
images for GPT-4o vision, and also extracts raw embedded text per page.

Hybrid approach:
  - Images (250 DPI) are sent for visual layout understanding and chart/table reading.
  - Embedded text (from the PDF's text layer) is extracted directly — 100% accurate
    for digitally-created PDFs, and used alongside the image so GPT can cross-verify.
"""

import os
import fitz  # PyMuPDF


def is_valid_pdf(file_path: str) -> bool:
    """Check if the given file exists and has a .pdf extension."""
    return os.path.isfile(file_path) and file_path.lower().endswith(".pdf")


def get_pdf_page_images(file_path: str, page_indices: list[int] = None, dpi: int = 250) -> list[bytes]:
    """
    Render specified PDF pages as PNG images (bytes) for GPT-4o vision input.
    If page_indices is None, renders all pages (not recommended for large files).
    Uses 250 DPI — high enough to read small fonts, tables, and footnotes accurately.
    """
    doc = fitz.open(file_path)
    images = []

    if page_indices is None:
        page_indices = range(len(doc))

    for p_idx in page_indices:
        if 0 <= p_idx < len(doc):
            page = doc[p_idx]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            images.append(pix.tobytes("png"))
        else:
            images.append(b"")

    doc.close()
    return images


def get_pdf_page_texts(file_path: str) -> list[str]:
    """
    Extract embedded text from each page of the PDF using PyMuPDF's text layer.
    Returns a list of strings (one per page). Pages with no embedded text return ''.

    This gives 100% accurate numbers/text for digitally-created PDFs.
    For scanned PDFs the strings will be empty — vision takes over.
    """
    doc = fitz.open(file_path)
    texts = []

    for page in doc:
        text = page.get_text("text").strip()
        texts.append(text)

    doc.close()
    return texts


def get_pdf_filename_stem(file_path: str) -> str:
    """Return the filename without extension (used for naming the output .md file)."""
    return os.path.splitext(os.path.basename(file_path))[0]
