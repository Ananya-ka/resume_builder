import copy
import io
from unittest.mock import Mock
import pytest
from pypdf import PdfWriter
from app.services import pdf_export
from app.services.document_generator import render_latex_resume, DEFAULT_ATS_LATEX_TEMPLATE


def test_readability_rejects_tiny_fonts_and_clipped_content():
    from reportlab.pdfgen.canvas import Canvas
    for x, size in [(1, 10), (60, 5)]:
        stream = io.BytesIO()
        canvas = Canvas(stream, pagesize=(612, 792))
        canvas.setFont("Helvetica", size)
        canvas.drawString(x, 700, "A substantive resume achievement with readable source content")
        canvas.save()
        with pytest.raises(ValueError, match="page edge|below 8 pt"):
            pdf_export.check_readability(stream.getvalue())


def test_page_count_uses_compiled_pdf(monkeypatch):
    writer = PdfWriter()
    for _ in range(2):
        writer.add_blank_page(width=612, height=792)
    stream = io.BytesIO(); writer.write(stream)
    monkeypatch.setattr(pdf_export, "compile_latex_to_pdf", lambda _: stream.getvalue())
    assert pdf_export.compile_export({}, [])[1] == 2


def test_custom_default_template_fills_candidate_not_sample():
    rendered = render_latex_resume("Pat Example", "pat@example.com", {}, [], "custom", DEFAULT_ATS_LATEX_TEMPLATE)
    assert "Pat Example" in rendered
    assert "__NAME__" not in rendered
    assert "Darwix" not in rendered
    with pytest.raises(ValueError, match="dynamic placeholders"):
        render_latex_resume("Pat", "", {}, [], "custom", r"\documentclass{article}\begin{document}Someone Else\end{document}")


def test_selected_profile_keeps_dates_without_unselected_roles():
    profile = {"experience": [{"company": "Acme", "role": "Engineer", "dates": "2020–2024", "location": "Remote"}, {"company": "Unselected", "role": "Other"}]}
    result = pdf_export.selected_profile(profile, [{"section": "Experience", "company": "Acme", "role": "Engineer"}])
    assert len(result["experience"]) == 1
    assert result["experience"][0]["dates"] == "2020–2024"
    assert result["experience"][0]["location"] == "Remote"


def test_compact_keeps_saved_content_and_does_not_remove_entire_roles(monkeypatch):
    bullets = [{"original_id": i, "company": "Acme", "role": "Engineer", "section": "Experience", "optimized_bullet": f"Built service {i}"} for i in range(2)]
    original = copy.deepcopy(bullets)
    optimizer = Mock()
    optimizer.optimize_bullets.return_value = (bullets, [])
    monkeypatch.setattr(pdf_export, "ResumeOptimizer", lambda: optimizer)
    verifier = Mock(); verifier.verify_optimized_bullets.return_value = copy.deepcopy(bullets)
    monkeypatch.setattr(pdf_export, "FactVerifier", lambda: verifier)
    monkeypatch.setattr(pdf_export, "compile_export", lambda profile, selected, *args: (b"PDF", len(selected)))
    _, pages, omitted = pdf_export.concise_export({}, bullets, {})
    assert pages == 1 and omitted == [1]
    assert bullets == original
    assert optimizer.optimize_bullets.call_args.kwargs["compact"] is True
    verifier.verify_optimized_bullets.return_value = copy.deepcopy(bullets)
    monkeypatch.setattr(pdf_export, "compile_export", lambda *args: (b"PDF", 2))
    with pytest.raises(ValueError, match="still exceeds"):
        pdf_export.concise_export({}, bullets, {})
