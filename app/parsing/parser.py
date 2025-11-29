from __future__ import annotations

import logging
from pathlib import Path

import pdfplumber

from app.utils.text_utils import clean_text

logger = logging.getLogger(__name__)


class DocumentParser:
    """
    Handle extraction of textual content from supported formats.
    """

    SUPPORTED_EXTENSIONS = (".pdf", ".txt")

    def __init__(self) -> None:
        pass

    def extract_text(self, file_path: Path) -> str:
        """
        Dispatch to the appropriate parser based on file extension.
        """
        suffix = file_path.suffix.lower()
        if suffix not in self.SUPPORTED_EXTENSIONS:
            msg = f"Unsupported file type: {suffix}"
            logger.error(msg)
            raise ValueError(msg)

        if suffix == ".pdf":
            return self._extract_from_pdf(file_path)
        return self._extract_from_txt(file_path)

    def _extract_from_pdf(self, file_path: Path) -> str:
        try:
            with pdfplumber.open(file_path) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                return clean_text(text)
        except Exception as exc:  # pragma: no cover - depends on contents
            logger.exception("PDF parsing failed for %s", file_path)
            raise RuntimeError(f"PDF parsing failed: {exc}") from exc

    @staticmethod
    def _extract_from_txt(file_path: Path) -> str:
        try:
            text = file_path.read_text(encoding="utf-8")
            return clean_text(text)
        except UnicodeDecodeError:
            text = file_path.read_text(encoding="latin-1")
            return clean_text(text)

