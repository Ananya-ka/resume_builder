"""Compile before checking page limits; create concise exports without editing saved drafts."""
import copy
import io
import pdfplumber
from pypdf import PdfReader
from app.services.document_generator import render_latex_resume, compile_latex_to_pdf
from app.services.resume_optimizer import ResumeOptimizer
from app.services.fact_verifier import FactVerifier


def selected_profile(profile, bullets):
    result = copy.deepcopy(profile)
    for section, label in (("experience", "Experience"), ("projects", "Projects")):
        entries = []
        seen = set()
        for bullet in bullets:
            if not bullet.get("included", True):
                continue
            if bullet.get("section") != label:
                continue
            company, role = bullet.get("company", ""), bullet.get("role", "")
            key = (company, role if section == "experience" else "")
            if key in seen:
                continue
            seen.add(key)
            metadata = next((e for e in profile.get(section, [])
                             if (e.get("company") if section == "experience" else e.get("name")) == company
                             and (section != "experience" or e.get("role", "") == role)), {})
            entry = {k: v for k, v in metadata.items() if k not in {"bullets", "source_quote"}}
            entry.update({"company": company, "role": role} if section == "experience" else {"name": company})
            entries.append(entry)
        result[section] = entries
    return result


def compile_export(profile, bullets, template_choice="default", custom_template=None):
    bullets = [b for b in bullets if b.get("included", True)]
    profile = selected_profile(profile, bullets)
    latex = render_latex_resume(profile.get("name", ""), profile.get("email", ""), profile,
                                bullets, template_choice, custom_template)
    pdf = compile_latex_to_pdf(latex)
    check_readability(pdf)
    return pdf, len(PdfReader(io.BytesIO(pdf)).pages)


def check_readability(pdf):
    """Reject clipping and tiny body text rather than silently shrinking to fit."""
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        for page in document.pages:
            words = page.extract_words()
            if any(w["x0"] < 12 or w["x1"] > page.width - 12 or w["top"] < 8 or w["bottom"] > page.height - 8 for w in words):
                raise ValueError("Text reaches the page edge. Adjust template margins or shorten the content before exporting.")
            body = [c for c in page.chars if str(c.get("text", "")).isalnum()]
            if body and sum(c.get("size", 10) < 8 for c in body) / len(body) > .1:
                raise ValueError("The template uses body text below 8 pt. Use a readable font size instead of shrinking to one page.")


def concise_export(profile, bullets, jd, template_choice="default", custom_template=None):
    bullets = [b for b in bullets if b.get("included", True)]
    if not bullets:
        raise ValueError("There are no achievement bullets to shorten.")
    sources = [{**b, "id": b.get("original_id", i), "content": b.get("optimized_bullet") or b.get("original_bullet", ""),
                "source": b.get("source", "resume")} for i, b in enumerate(bullets)]
    proposed, _ = ResumeOptimizer().optimize_bullets(sources, jd, compact=True)
    shortened = FactVerifier().verify_optimized_bullets(sources, proposed)
    # Source order is relevance-ranked by tailoring. Keep at least one bullet per
    # employer/project; never hide an entire position just to force a page limit.
    omitted = []
    for _ in range(len(shortened) + 1):
        pdf, pages = compile_export(profile, shortened, template_choice, custom_template)
        if pages == 1:
            return pdf, pages, omitted
        counts = {}
        for b in shortened:
            key = (b.get("section"), b.get("company"), b.get("role"))
            counts[key] = counts.get(key, 0) + 1
        index = next((i for i in range(len(shortened) - 1, -1, -1)
                      if counts[(shortened[i].get("section"), shortened[i].get("company"), shortened[i].get("role"))] > 1), None)
        if index is None:
            raise ValueError("The resume still exceeds one page after shortening. Keep the longer version or edit its content/template; no roles or education were removed.")
        omitted.append(shortened.pop(index).get("original_id"))
    raise ValueError("Unable to fit this template on one page.")
