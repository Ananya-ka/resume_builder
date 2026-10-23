"""Comprehensive tests for document extraction, structured parsing, and ingestion

Tests cover:
1. Upload and extraction without an OpenAI API key.
2. Standard text PDF extraction and layout preservation.
3. Multi-column PDF extraction preserving column reading order.
4. DOCX containing paragraphs and tables in document order.
5. Image-only document and OCR / fallback behavior.
6. Malformed, corrupted, encrypted, and unsupported files.
7. Preservation of source references, provenance, and achievement attachments.
8. AI features when configured, using mocked provider calls.
"""
from __future__ import annotations

import io
import pytest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from docx import Document
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pypdf import PdfWriter

from app.services.document_extractor import (
    DocumentExtractor,
    DocumentEncryptedError,
    DocumentCorruptedError,
    DocumentEmptyError,
    DocumentExtractionError,
)
from app.services.structured_parser import StructuredResumeParser
from app.services.resume_parser import ResumeParser, validate_resume_parse
from app.core.config import settings


# ------------------------------------------------------------------------------
# Helpers to generate in-memory test documents
# ------------------------------------------------------------------------------

def make_standard_pdf() -> bytes:
    """Generates a standard single-column text PDF."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.drawString(100, 750, "Jane Doe")
    c.drawString(100, 735, "jane.doe@example.com | 555-0199")
    c.drawString(100, 700, "Professional Summary")
    c.drawString(100, 685, "Experienced backend software engineer specializing in Python.")
    c.drawString(100, 650, "Work Experience")
    c.drawString(100, 635, "Acme Corp - Senior Engineer (2021 - Present)")
    c.drawString(120, 620, "- Built distributed microservices handling 10M daily events.")
    c.drawString(120, 605, "- Reduced query latency by 45% using Redis caching.")
    c.drawString(100, 570, "Education")
    c.drawString(100, 555, "Tech University - Bachelor of Science in Computer Science (2017 - 2021)")
    c.drawString(100, 520, "Technical Skills")
    c.drawString(100, 505, "Python, FastAPI, Docker, PostgreSQL, Redis, Kubernetes")
    c.showPage()
    c.save()
    return buffer.getvalue()


def make_multicolumn_pdf() -> bytes:
    """Generates a 2-column PDF where left column is Column 1 and right column is Column 2."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    # Page width is 612pt. Left column: x=72..260, Right column: x=340..540
    # Left column text:
    c.drawString(72, 700, "Work Experience")
    c.drawString(72, 680, "Beta Corp - Backend Lead")
    c.drawString(72, 660, "- Scaled API infrastructure.")
    c.drawString(72, 640, "- Deployed Kubernetes cluster.")
    c.drawString(72, 620, "- Mentored 5 junior developers.")

    # Right column text (vertically overlapping with left column):
    c.drawString(350, 700, "Skills and Tools")
    c.drawString(350, 680, "Python, Go, Docker")
    c.drawString(350, 660, "PostgreSQL, Redis")
    c.drawString(350, 640, "AWS, Terraform, CI/CD")
    c.drawString(350, 620, "Git, Linux, Bash")

    c.showPage()
    c.save()
    return buffer.getvalue()


def make_table_docx() -> bytes:
    """Generates a DOCX with paragraphs and tables interleaved in document order."""
    doc = Document()
    doc.add_heading("Alex Morgan", level=1)
    doc.add_paragraph("Summary: Full Stack Engineer with 4 years experience.")
    doc.add_heading("Work Experience", level=2)

    # Table representing jobs
    table = doc.add_table(rows=3, cols=2)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Company & Role"
    hdr_cells[1].text = "Achievements"

    row1 = table.rows[1].cells
    row1[0].text = "CloudTech | Systems Engineer | 2022 - Present"
    row1[1].text = "- Architected event-driven data pipeline using Kafka and FastAPI."

    row2 = table.rows[2].cells
    row2[0].text = "AppStudio | Developer | 2020 - 2022"
    row2[1].text = "- Developed responsive web interfaces using React and TypeScript."

    doc.add_heading("Education", level=2)
    doc.add_paragraph("State University - B.S. in Software Engineering (2016 - 2020)")
    doc.add_heading("Skills", level=2)
    doc.add_paragraph("Python, React, TypeScript, Kafka, FastAPI, Docker")

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def make_image_only_pdf() -> bytes:
    """Generates a PDF containing an embedded image and zero text."""
    from reportlab.lib.colors import blue
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    # Draw graphics / image rectangle without text strings
    c.setFillColor(blue)
    c.rect(50, 50, 500, 700, fill=1)
    c.showPage()
    c.save()
    return buffer.getvalue()


def make_encrypted_pdf() -> bytes:
    """Generates a password-protected PDF."""
    plain_pdf = make_standard_pdf()
    reader = io.BytesIO(plain_pdf)
    writer = PdfWriter(clone_from=reader)
    writer.encrypt("secret_password")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


# ------------------------------------------------------------------------------
# 1. Upload and extraction with NO OpenAI key
# ------------------------------------------------------------------------------

def test_extraction_and_parsing_without_openai_key(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    pdf_bytes = make_standard_pdf()

    extractor = DocumentExtractor()
    extraction = extractor.extract(pdf_bytes, "standard.pdf")

    assert extraction.status == "extracted"
    assert not extraction.needs_ocr
    assert "Jane Doe" in extraction.raw_text
    assert "Acme Corp" in extraction.raw_text

    parser = StructuredResumeParser()
    parsed = parser.parse(extraction.raw_text, blocks=extraction.blocks)

    assert parsed["parsing_status"] == "ready"
    assert parsed["needs_review"] is True
    assert len(parsed["skills"]) >= 3
    assert any("Python" in s for s in parsed["skills"])
    assert len(parsed["experience"]) >= 1
    assert "Acme Corp" in parsed["experience"][0]["company"]
    assert len(parsed["experience"][0]["bullets"]) == 2
    # Verify bullets are attached to original company
    assert any("45%" in b for b in parsed["experience"][0]["bullets"])


# ------------------------------------------------------------------------------
# 2. Standard text PDF
# ------------------------------------------------------------------------------

def test_standard_text_pdf_preserves_pages_and_blocks():
    pdf_bytes = make_standard_pdf()
    extractor = DocumentExtractor()
    result = extractor.extract(pdf_bytes, "resume.pdf")

    assert len(result.pages) == 1
    assert result.pages[0].page_number == 1
    assert len(result.blocks) >= 5

    # Check block kinds
    bullet_blocks = [b for b in result.blocks if b.kind == "bullet"]
    assert len(bullet_blocks) >= 2
    assert all(b.source_ref.startswith("p1:") for b in result.blocks)


# ------------------------------------------------------------------------------
# 3. Multi-column PDF reading order
# ------------------------------------------------------------------------------

def test_multicolumn_pdf_preserves_column_order():
    pdf_bytes = make_multicolumn_pdf()
    extractor = DocumentExtractor()
    result = extractor.extract(pdf_bytes, "multicolumn.pdf")

    raw = result.raw_text
    # Left column content should appear before right column content
    # (i.e. 'Backend Lead' before 'Skills and Tools')
    pos_exp = raw.find("Work Experience")
    pos_skills = raw.find("Skills and Tools")

    assert pos_exp != -1
    assert pos_skills != -1
    assert pos_exp < pos_skills, "Left column must be read before right column in multi-column layout"

    pos_last_exp_bullet = raw.find("Mentored 5 junior developers")
    assert pos_last_exp_bullet < pos_skills, "All left column items should precede right column items"


# ------------------------------------------------------------------------------
# 4. DOCX containing tables in document order
# ------------------------------------------------------------------------------

def test_docx_table_and_paragraph_document_order():
    docx_bytes = make_table_docx()
    extractor = DocumentExtractor()
    result = extractor.extract(docx_bytes, "experience.docx")

    raw = result.raw_text
    assert "Alex Morgan" in raw
    assert "CloudTech" in raw
    assert "AppStudio" in raw
    assert "State University" in raw

    # Verify document order: Name -> Summary -> Work Experience -> Table rows -> Education -> Skills
    pos_summary = raw.find("Summary:")
    pos_work = raw.find("Work Experience")
    pos_cloudtech = raw.find("CloudTech")
    pos_appstudio = raw.find("AppStudio")
    pos_edu = raw.find("Education")
    pos_skills = raw.find("Skills")

    assert pos_summary < pos_work < pos_cloudtech < pos_appstudio < pos_edu < pos_skills


# ------------------------------------------------------------------------------
# 5. Image-only document and OCR / fallback behavior
# ------------------------------------------------------------------------------

def test_image_only_pdf_triggers_needs_ocr_when_ocr_unavailable():
    pdf_bytes = make_image_only_pdf()
    # Force OCR disabled to test fallback behavior
    extractor = DocumentExtractor(enable_ocr=False)
    result = extractor.extract(pdf_bytes, "scanned.pdf")

    assert result.needs_ocr is True
    assert result.status == "needs_ocr"
    assert any("needs OCR" in w for w in result.warnings)


# ------------------------------------------------------------------------------
# 6. Malformed, corrupted, encrypted, and unsupported files
# ------------------------------------------------------------------------------

def test_empty_file_raises_document_empty_error():
    extractor = DocumentExtractor()
    with pytest.raises(DocumentEmptyError):
        extractor.extract(b"", "empty.pdf")


def test_corrupted_pdf_raises_error():
    extractor = DocumentExtractor()
    with pytest.raises((DocumentCorruptedError, DocumentExtractionError)):
        extractor.extract(b"Not a valid PDF header or content", "corrupted.pdf")


def test_corrupted_docx_raises_error():
    extractor = DocumentExtractor()
    with pytest.raises(DocumentCorruptedError):
        extractor.extract(b"PK\x03\x04corrupted zip stream", "corrupted.docx")


def test_encrypted_pdf_raises_document_encrypted_error():
    enc_pdf = make_encrypted_pdf()
    extractor = DocumentExtractor()
    with pytest.raises(DocumentEncryptedError):
        extractor.extract(enc_pdf, "locked.pdf")


def test_unsupported_extension_raises_error():
    extractor = DocumentExtractor()
    with pytest.raises(DocumentExtractionError, match="Unsupported file format"):
        extractor.extract(b"Some text", "document.exe")


# ------------------------------------------------------------------------------
# 7. Preservation of source references and provenance
# ------------------------------------------------------------------------------

def test_source_references_and_provenance_preserved():
    pdf_bytes = make_standard_pdf()
    extractor = DocumentExtractor()
    extraction = extractor.extract(pdf_bytes, "standard.pdf")

    parser = StructuredResumeParser()
    parsed = parser.parse(extraction.raw_text, blocks=extraction.blocks)

    # Verify provenance on experience entries
    exp = parsed["experience"][0]
    assert exp["company"] == "Acme Corp"
    assert exp["role"] == "Senior Engineer"
    assert len(exp["bullets"]) == 2
    assert len(exp["bullet_provenance"]) == 2
    assert all(ref.startswith("p1:b") for ref in exp["bullet_provenance"])


def test_deterministic_bullet_metadata_extraction():
    parser = StructuredResumeParser()
    bullet = "Scaled real-time data ingestion by 60% using Kafka, Redis, and Python on AWS, saving $15k monthly."
    meta = parser.extract_bullet_metadata(bullet, "Acme", "Senior Engineer")

    assert "Python" in meta["technologies"]
    assert "Kafka" in meta["technologies"]
    assert "Redis" in meta["technologies"]
    assert "Aws" in meta["technologies"] or "AWS" in meta["technologies"]
    assert any("60%" in m for m in meta["metrics"])
    assert any("$15k" in m for m in meta["metrics"])
    assert "scaled" in meta["keywords"]


# ------------------------------------------------------------------------------
# 8. Existing AI features when configured, using mocked provider calls
# ------------------------------------------------------------------------------

def test_ai_parsing_enhancement_with_mocked_provider():
    raw_text = "Acme Corp\nSenior Engineer\nBuilt high throughput APIs.\nSkills: Python, FastAPI"
    ai_json = (
        '{"profile_summary": null, "skills": ["Python", "FastAPI"], '
        '"experience": [{"company": "Acme Corp", "role": "Senior Engineer", "source_quote": "Acme Corp\\nSenior Engineer\\nBuilt high throughput APIs.", "bullets": ["Built high throughput APIs."]}], '
        '"projects": [], "achievements": [], "certifications": [], "education": []}'
    )

    mock_client = Mock()
    mock_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=ai_json))]
    )

    parser = ResumeParser()
    parser.client = mock_client

    result = parser.parse_resume_to_json(raw_text)
    assert result["skills"] == ["Python", "FastAPI"]
    assert result["experience"][0]["company"] == "Acme Corp"
    assert result["experience"][0]["bullets"] == ["Built high throughput APIs."]


def test_ai_parsing_rejects_hallucinations_with_mocked_provider():
    raw_text = "Acme Corp\nDeveloper\nBuilt basic scripts.\nSkills: Python"
    hallucinated_json = (
        '{"profile_summary": null, "skills": ["Python", "Docker", "Kubernetes", "AWS"], '
        '"experience": [{"company": "Acme Corp", "role": "Developer", "bullets": ["Built basic scripts."]}], '
        '"projects": [], "achievements": [], "certifications": [], "education": []}'
    )

    mock_client = Mock()
    mock_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=hallucinated_json))]
    )

    parser = ResumeParser()
    parser.client = mock_client

    with pytest.raises(ValueError, match="unsupported"):
        parser.parse_resume_to_json(raw_text)


def test_parse_resume_task_succeeds_when_openai_fails(monkeypatch):
    import openai
    from app.worker.tasks import parse_resume_task
    from app.models.schemas import Resume, ResumeBullet

    pdf_bytes = make_standard_pdf()

    # Mock SessionLocal and database
    mock_db = Mock()
    mock_resume = Mock(id=99, parsed_raw={})
    mock_db.query.return_value.filter.return_value.first.return_value = mock_resume
    mock_db.query.return_value.filter.return_value.delete.return_value = None

    added_bullets = []
    mock_db.add.side_effect = lambda item: added_bullets.append(item) if isinstance(item, ResumeBullet) else None

    monkeypatch.setattr("app.worker.tasks.SessionLocal", lambda: mock_db)

    # Force OpenAI client to raise AuthenticationError
    def failing_create(*args, **kwargs):
        raise openai.AuthenticationError(
            message="Invalid API Key",
            response=Mock(status_code=401, headers={}),
            body={"error": {"message": "Invalid API Key"}}
        )

    with patch("app.services.resume_parser.ResumeParser.parse_resume_to_json", side_effect=failing_create):
        parse_resume_task(99, pdf_bytes.hex(), "resume.pdf")

    # Resume must be marked ready and have structured data
    assert mock_resume.parsed_raw.get("parsing_status") == "ready"
    assert "Jane Doe" in mock_resume.parsed_raw.get("name", "")
    assert len(mock_resume.parsed_raw.get("experience", [])) >= 1
    assert len(added_bullets) >= 2
    assert added_bullets[0].section == "Experience"
