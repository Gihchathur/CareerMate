from pathlib import Path

import pymupdf
from docx import Document


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


class CVParserError(Exception):
    """Raised when a CV cannot be parsed."""


def extract_pdf_text(file_path: Path) -> str:
    try:
        document = pymupdf.open(file_path)

        pages = []

        for page in document:
            pages.append(page.get_text())

        document.close()

        return "\n".join(pages).strip()

    except Exception as exc:
        raise CVParserError(
            f"Failed to extract text from PDF: {exc}"
        ) from exc


def extract_docx_text(file_path: Path) -> str:
    try:
        document = Document(file_path)

        paragraphs = [
            paragraph.text.strip()
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        ]

        return "\n".join(paragraphs)

    except Exception as exc:
        raise CVParserError(
            f"Failed to extract text from DOCX: {exc}"
        ) from exc


def extract_txt_text(file_path: Path) -> str:
    try:
        return file_path.read_text(
            encoding="utf-8",
            errors="replace",
        ).strip()

    except Exception as exc:
        raise CVParserError(
            f"Failed to read text file: {exc}"
        ) from exc


def extract_cv_text(file_path: Path) -> str:
    extension = file_path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise CVParserError(
            f"Unsupported file type: {extension}"
        )

    if extension == ".pdf":
        return extract_pdf_text(file_path)

    if extension == ".docx":
        return extract_docx_text(file_path)

    if extension == ".txt":
        return extract_txt_text(file_path)

    raise CVParserError("Unsupported CV format")