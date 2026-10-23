"""Document Extraction Service.

Extracts text, layout structure, page boundaries, and block provenance from
PDF, DOCX, and TXT files without requiring external API calls or OpenAI keys.
"""
from __future__ import annotations

import io
import re
import shutil
import zipfile
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

import pdfplumber
from pypdf import PdfReader
from pypdf.errors import PdfReadError, FileNotDecryptedError
from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import Table

logger = logging.getLogger(__name__)


class DocumentExtractionError(Exception):
    """Base error for document extraction failures."""
    pass


class DocumentEncryptedError(DocumentExtractionError):
    """Raised when a document is password-protected or encrypted."""
    pass


class DocumentCorruptedError(DocumentExtractionError):
    """Raised when a document cannot be parsed due to corruption."""
    pass


class DocumentEmptyError(DocumentExtractionError):
    """Raised when an uploaded document contains no content."""
    pass


@dataclass
class TextBlock:
    block_id: str
    page_number: int
    text: str
    bbox: Optional[Tuple[float, float, float, float]] = None
    kind: str = "paragraph"  # heading, paragraph, bullet, table_row, unassigned
    source_ref: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_id": self.block_id,
            "page_number": self.page_number,
            "text": self.text,
            "bbox": self.bbox,
            "kind": self.kind,
            "source_ref": self.source_ref or f"p{self.page_number}:{self.block_id}",
        }


@dataclass
class PageData:
    page_number: int
    text: str
    blocks: List[TextBlock] = field(default_factory=list)
    has_images: bool = False
    is_scanned: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_number": self.page_number,
            "text": self.text,
            "block_count": len(self.blocks),
            "has_images": self.has_images,
            "is_scanned": self.is_scanned,
        }


@dataclass
class ExtractionResult:
    raw_text: str
    pages: List[PageData] = field(default_factory=list)
    blocks: List[TextBlock] = field(default_factory=list)
    needs_ocr: bool = False
    status: str = "extracted"  # extracted, needs_ocr, empty, failed
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def pages_summary(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self.pages]


class DocumentExtractor:
    """Extracts text and layout from PDF, DOCX, and TXT files."""

    def __init__(self, enable_ocr: bool = True):
        self.enable_ocr = enable_ocr
        self.ocr_available = self._check_ocr_available()

    def _check_ocr_available(self) -> bool:
        if not self.enable_ocr:
            return False
        try:
            import pytesseract
            # Check if tesseract binary is in PATH
            return shutil.which("tesseract") is not None
        except ImportError:
            return False

    def extract(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        """Main entrypoint for document extraction."""
        if not file_bytes:
            raise DocumentEmptyError("Uploaded document is empty (0 bytes).")

        name = filename.lower()
        if name.endswith(".pdf"):
            return self.extract_pdf(file_bytes, filename)
        elif name.endswith(".docx"):
            return self.extract_docx(file_bytes, filename)
        elif name.endswith(".txt"):
            return self.extract_txt(file_bytes, filename)
        else:
            raise DocumentExtractionError(f"Unsupported file format: {filename}. Supported: PDF, DOCX, TXT.")

    # --------------------------------------------------------------------------
    # PDF Extraction
    # --------------------------------------------------------------------------

    def extract_pdf(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        # Check for encryption first with pypdf
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            if reader.is_encrypted:
                try:
                    # Attempt empty password decryption
                    if not reader.decrypt(""):
                        raise DocumentEncryptedError("PDF is password-protected. Please upload an unprotected file.")
                except FileNotDecryptedError:
                    raise DocumentEncryptedError("PDF is password-protected. Please upload an unprotected file.")
        except DocumentEncryptedError:
            raise
        except Exception as e:
            if "encrypted" in str(e).lower() or "password" in str(e).lower():
                raise DocumentEncryptedError("PDF is password-protected. Please upload an unprotected file.")
            logger.warning(f"pypdf pre-check failed: {e}")

        pages: List[PageData] = []
        all_blocks: List[TextBlock] = []
        warnings: List[str] = []
        is_any_scanned = False
        total_chars = 0

        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    page_num = page_idx + 1
                    page_images = page.images or []
                    has_images = len(page_images) > 0

                    # 1. Extract words with bounding boxes
                    words = page.extract_words(
                        x_tolerance=2,
                        y_tolerance=2,
                        keep_blank_chars=False,
                        use_text_flow=True
                    )

                    page_text = ""
                    page_blocks: List[TextBlock] = []

                    if words:
                        # Multi-column layout detection and sorting
                        sorted_lines = self._sort_words_layout(words, float(page.width))
                        page_blocks = self._lines_to_blocks(sorted_lines, page_num)
                        page_text = "\n".join(b.text for b in page_blocks)
                        total_chars += len(page_text.strip())

                    # Check if page has no or minimal extractable text but contains graphics/images
                    has_graphics = (
                        has_images
                        or len(getattr(page, "curves", []) or []) > 0
                        or len(getattr(page, "rects", []) or []) > 0
                    )
                    alphanumeric_count = len(re.findall(r"[a-zA-Z0-9]", page_text))
                    page_is_scanned = (alphanumeric_count < 30 and has_graphics) or (alphanumeric_count == 0)

                    if page_is_scanned:
                        is_any_scanned = True
                        if self.ocr_available:
                            try:
                                ocr_text = self._run_ocr(page)
                                if ocr_text.strip():
                                    page_text = ocr_text
                                    page_blocks = [
                                        TextBlock(
                                            block_id=f"p{page_num}-ocr0",
                                            page_number=page_num,
                                            text=ocr_text,
                                            kind="paragraph",
                                            source_ref=f"p{page_num}:ocr"
                                        )
                                    ]
                                    page_is_scanned = False
                            except Exception as ocr_err:
                                logger.warning(f"OCR failed on page {page_num}: {ocr_err}")

                    pages.append(PageData(
                        page_number=page_num,
                        text=page_text,
                        blocks=page_blocks,
                        has_images=has_images,
                        is_scanned=page_is_scanned,
                    ))
                    all_blocks.extend(page_blocks)

        except DocumentEncryptedError:
            raise
        except Exception as e:
            logger.warning(f"pdfplumber failed: {e}. Falling back to pypdf.")
            # Fallback to pypdf
            try:
                reader = PdfReader(io.BytesIO(file_bytes))
                for page_idx, page in enumerate(reader.pages):
                    page_num = page_idx + 1
                    text = page.extract_text() or ""
                    total_chars += len(text.strip())
                    lines = [line.strip() for line in text.split("\n") if line.strip()]
                    page_blocks = [
                        TextBlock(
                            block_id=f"p{page_num}-b{i}",
                            page_number=page_num,
                            text=l,
                            kind="bullet" if re.match(r"^[-*•–\d+\.]", l) else "paragraph",
                            source_ref=f"p{page_num}:b{i}"
                        )
                        for i, l in enumerate(lines)
                    ]
                    pages.append(PageData(page_number=page_num, text=text, blocks=page_blocks))
                    all_blocks.extend(page_blocks)
            except Exception as ex:
                raise DocumentCorruptedError(f"Could not read PDF file: {ex}")

        # Final check: if entire document yielded no text and has scanned pages
        full_text = "\n\n".join(p.text for p in pages if p.text.strip())
        needs_ocr = (len(full_text.strip()) < 30 and is_any_scanned and not self.ocr_available)

        if needs_ocr:
            warnings.append("This document appears to be scanned or image-only and needs OCR.")

        return ExtractionResult(
            raw_text=full_text,
            pages=pages,
            blocks=all_blocks,
            needs_ocr=needs_ocr,
            status="needs_ocr" if needs_ocr else ("empty" if not full_text.strip() else "extracted"),
            warnings=warnings,
            metadata={"format": "pdf", "page_count": len(pages), "filename": filename}
        )

    def _sort_words_layout(self, words: List[Dict[str, Any]], page_width: float) -> List[List[Dict[str, Any]]]:
        """Detects single vs multi-column layout and sorts words in natural reading order."""
        if not words:
            return []

        # Check if there is a vertical gutter around the center with width >= 24pt
        # Search for an x_split in 0.35 * page_width .. 0.65 * page_width
        best_split: Optional[float] = None
        for split_ratio in [0.40, 0.45, 0.50, 0.55, 0.60]:
            split_x = page_width * split_ratio
            gutter_words = [w for w in words if w["x0"] < split_x + 12 and w["x1"] > split_x - 12]
            left_words = [w for w in words if w["x1"] <= split_x - 12]
            right_words = [w for w in words if w["x0"] >= split_x + 12]

            if len(gutter_words) == 0 and len(left_words) >= 4 and len(right_words) >= 4:
                left_y_span = (min(w["top"] for w in left_words), max(w["bottom"] for w in left_words))
                right_y_span = (min(w["top"] for w in right_words), max(w["bottom"] for w in right_words))
                overlap_start = max(left_y_span[0], right_y_span[0])
                overlap_end = min(left_y_span[1], right_y_span[1])
                if overlap_end - overlap_start > 30:
                    best_split = split_x
                    break

        if best_split is not None:
            left_words = [w for w in words if w["x1"] <= best_split]
            right_words = [w for w in words if w["x0"] >= best_split]
            left_lines = self._cluster_lines(left_words)
            right_lines = self._cluster_lines(right_words)
            return left_lines + right_lines

        return self._cluster_lines(words)

    def _cluster_lines(self, words: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Groups words into horizontal lines based on top coordinate proximity."""
        if not words:
            return []
        sorted_words = sorted(words, key=lambda w: (round(w["top"] / 3.0) * 3, w["x0"]))
        lines: List[List[Dict[str, Any]]] = []
        current_line: List[Dict[str, Any]] = []
        current_top: Optional[float] = None

        for w in sorted_words:
            if current_top is None:
                current_top = w["top"]
                current_line.append(w)
            elif abs(w["top"] - current_top) <= 3.5:
                current_line.append(w)
            else:
                lines.append(sorted(current_line, key=lambda item: item["x0"]))
                current_line = [w]
                current_top = w["top"]
        if current_line:
            lines.append(sorted(current_line, key=lambda item: item["x0"]))
        return lines

    def _lines_to_blocks(self, lines: List[List[Dict[str, Any]]], page_num: int) -> List[TextBlock]:
        """Converts grouped word lines into TextBlocks preserving bullets and paragraphs."""
        blocks: List[TextBlock] = []
        bullet_pattern = re.compile(r"^[-*•–—\u2022\u25cf\u25cb\u25aa\u25b8]|\b\d{1,2}\.\s+")

        for idx, line in enumerate(lines):
            line_text = " ".join(w["text"] for w in line).strip()
            if not line_text:
                continue

            # Determine bbox
            x0 = min(w["x0"] for w in line)
            top = min(w["top"] for w in line)
            x1 = max(w["x1"] for w in line)
            bottom = max(w["bottom"] for w in line)

            kind = "paragraph"
            if bullet_pattern.match(line_text):
                kind = "bullet"
            elif len(line_text) < 40 and (line_text.isupper() or line_text.istitle()) and not line_text.endswith("."):
                kind = "heading"

            blocks.append(TextBlock(
                block_id=f"p{page_num}-b{idx}",
                page_number=page_num,
                text=line_text,
                bbox=(x0, top, x1, bottom),
                kind=kind,
                source_ref=f"p{page_num}:b{idx}"
            ))

        return blocks

    def _run_ocr(self, page: Any) -> str:
        """Runs local OCR on a pdfplumber page if tesseract is available."""
        import pytesseract
        pil_image = page.to_image(resolution=200).original
        return pytesseract.image_to_string(pil_image)

    # --------------------------------------------------------------------------
    # DOCX Extraction
    # --------------------------------------------------------------------------

    def extract_docx(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        try:
            doc = Document(io.BytesIO(file_bytes))
        except zipfile.BadZipFile:
            raise DocumentCorruptedError("The uploaded DOCX file is corrupted or not a valid Word document.")
        except Exception as e:
            raise DocumentCorruptedError(f"Failed to open DOCX file: {e}")

        blocks: List[TextBlock] = []
        lines: List[str] = []
        block_idx = 0

        bullet_pattern = re.compile(r"^[-*•–—\u2022\u25cf\u25cb\u25aa\u25b8]|\b\d{1,2}\.\s+")

        # Iterate over doc.element.body children to preserve exact document order
        for child in doc.element.body:
            tag = child.tag.split("}")[-1]
            if tag == "p":
                p = Paragraph(child, doc)
                text = p.text.strip()
                if text:
                    kind = "paragraph"
                    if "Heading" in (p.style.name if p.style else ""):
                        kind = "heading"
                    elif bullet_pattern.match(text) or "List" in (p.style.name if p.style else ""):
                        kind = "bullet"
                    elif len(text) < 50 and text.isupper():
                        kind = "heading"

                    blocks.append(TextBlock(
                        block_id=f"p1-b{block_idx}",
                        page_number=1,
                        text=text,
                        kind=kind,
                        source_ref=f"docx:p1:b{block_idx}"
                    ))
                    lines.append(text)
                    block_idx += 1

            elif tag == "tbl":
                table = Table(child, doc)
                for row_idx, row in enumerate(table.rows):
                    cells = [cell.text.strip() for cell in row.cells]
                    # Filter consecutive duplicate merged cells
                    unique_cells = []
                    for c in cells:
                        if c and (not unique_cells or c != unique_cells[-1]):
                            unique_cells.append(c)
                    if unique_cells:
                        row_text = " | ".join(unique_cells)
                        blocks.append(TextBlock(
                            block_id=f"p1-b{block_idx}",
                            page_number=1,
                            text=row_text,
                            kind="table_row",
                            source_ref=f"docx:table:r{row_idx}:b{block_idx}"
                        ))
                        lines.append(row_text)
                        block_idx += 1

        full_text = "\n".join(lines)
        page = PageData(page_number=1, text=full_text, blocks=blocks)

        return ExtractionResult(
            raw_text=full_text,
            pages=[page],
            blocks=blocks,
            needs_ocr=False,
            status="empty" if not full_text.strip() else "extracted",
            warnings=[] if full_text.strip() else ["Document contains no text"],
            metadata={"format": "docx", "page_count": 1, "filename": filename}
        )

    # --------------------------------------------------------------------------
    # TXT Extraction
    # --------------------------------------------------------------------------

    def extract_txt(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
        text = ""
        for enc in encodings:
            try:
                text = file_bytes.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        bullet_pattern = re.compile(r"^[-*•–—\u2022\u25cf\u25cb\u25aa\u25b8]|\b\d{1,2}\.\s+")
        blocks = []
        for i, l in enumerate(lines):
            kind = "paragraph"
            if bullet_pattern.match(l):
                kind = "bullet"
            elif len(l) < 40 and (l.isupper() or l.istitle()) and not l.endswith("."):
                kind = "heading"
            blocks.append(TextBlock(
                block_id=f"p1-b{i}",
                page_number=1,
                text=l,
                kind=kind,
                source_ref=f"txt:p1:b{i}"
            ))

        full_text = "\n".join(lines)
        page = PageData(page_number=1, text=full_text, blocks=blocks)

        return ExtractionResult(
            raw_text=full_text,
            pages=[page],
            blocks=blocks,
            needs_ocr=False,
            status="empty" if not full_text.strip() else "extracted",
            warnings=[] if full_text.strip() else ["Text file is empty"],
            metadata={"format": "txt", "page_count": 1, "filename": filename}
        )
