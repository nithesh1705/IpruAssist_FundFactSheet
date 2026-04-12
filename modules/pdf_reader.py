"""
PDF reader module: validates the input file and converts PDF pages to images for AI processing.
"""

import os
import fitz  # PyMuPDF


def is_valid_pdf(file_path: str) -> bool:
    """Check if the given file exists and has a .pdf extension."""
    return os.path.isfile(file_path) and file_path.lower().endswith(".pdf")


def get_pdf_page_images(file_path: str, dpi: int = 150) -> list[bytes]:
    """
    Render each PDF page as a PNG image (bytes) for GPT-4o vision input.
    Uses 150 DPI for a good balance between quality and token efficiency.
    """
    doc = fitz.open(file_path)
    images = []

    for page in doc:
        mat = fitz.Matrix(dpi / 72, dpi / 72)  # scale factor relative to 72 dpi base
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        images.append(pix.tobytes("png"))

    doc.close()
    return images


def get_pdf_filename_stem(file_path: str) -> str:
    """Return the filename without extension (used for naming the output .md file)."""
    return os.path.splitext(os.path.basename(file_path))[0]
