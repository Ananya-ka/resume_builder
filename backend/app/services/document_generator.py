import io
from pathlib import Path
import os
import subprocess
import tempfile
import logging
from typing import Optional, List, Dict, Any
from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

logger = logging.getLogger(__name__)


def generate_docx_bytes(name: str, email: str, parsed_resume: dict, optimized_bullets: list) -> bytes:
    name = parsed_resume.get("name") or name or ""
    email = parsed_resume.get("email") or email or ""
    doc = Document()
    
    # 1. Header
    title = doc.add_paragraph()
    run = title.add_run(name)
    run.bold = True
    run.font.size = 24 * 12700 # 24 pt
    title.alignment = 1 # Center
    
    contact = doc.add_paragraph()
    contact.add_run(email or "")
    contact.alignment = 1 # Center

    # Group optimized bullets
    exp_dict = {}
    proj_dict = {}
    for b in optimized_bullets:
        bullet_text = b.get("optimized_bullet", b.get("original_bullet", ""))
        sec = b.get("section", "Experience")
        if sec == "Experience":
            key = (b.get("company", ""), b.get("role", ""))
            if key not in exp_dict:
                exp_dict[key] = []
            exp_dict[key].append(bullet_text)
        elif sec == "Projects":
            key = b.get("company", "")
            if key not in proj_dict:
                proj_dict[key] = []
            proj_dict[key].append(bullet_text)

    # 2. Experience Section
    if exp_dict:
        doc.add_heading("Professional Experience", level=1)
        for (company, role), bullets in exp_dict.items():
            p = doc.add_paragraph()
            r_role = p.add_run(f"{role}")
            r_role.bold = True
            p.add_run(f" — {company}")
            
            for b in bullets:
                doc.add_paragraph(b, style="List Bullet")

    # 3. Projects Section
    if proj_dict:
        doc.add_heading("Key Projects", level=1)
        for name, bullets in proj_dict.items():
            p = doc.add_paragraph()
            r_name = p.add_run(f"{name}")
            r_name.bold = True
            
            for b in bullets:
                doc.add_paragraph(b, style="List Bullet")

    # 4. Education & Skills Section
    skills = parsed_resume.get("skills", [])
    if skills:
        doc.add_heading("Skills", level=1)
        doc.add_paragraph(", ".join(skills))

    edu = parsed_resume.get("education", [])
    if edu:
        doc.add_heading("Education", level=1)
        for item in edu:
            p = doc.add_paragraph()
            school_run = p.add_run(item.get("school", ""))
            school_run.bold = True
            if item.get("degree"):
                p.add_run(f" — {item.get('degree')}")

    # Save to memory buffer
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream.read()

def generate_pdf_bytes(name: str, email: str, parsed_resume: dict, optimized_bullets: list) -> bytes:
    name = parsed_resume.get("name") or name or ""
    email = parsed_resume.get("email") or email or ""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        alignment=1, # Center
        textColor=colors.HexColor("#1A202C")
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        alignment=1, # Center
        textColor=colors.HexColor("#4A5568")
    )

    heading_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        spaceBefore=14,
        spaceAfter=6,
        textColor=colors.HexColor("#2B6CB0")
    )

    job_title_style = ParagraphStyle(
        'JobTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        spaceBefore=6,
        spaceAfter=2,
        textColor=colors.HexColor("#2D3748")
    )

    bullet_style = ParagraphStyle(
        'BulletPoint',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3,
        textColor=colors.HexColor("#2D3748")
    )

    normal_style = ParagraphStyle(
        'NormalText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#2D3748")
    )

    story = []
    
    # Header
    story.append(Paragraph(name, title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(email or "", subtitle_style))
    story.append(Spacer(1, 10))

    # Group optimized bullets
    exp_dict = {}
    proj_dict = {}
    for b in optimized_bullets:
        bullet_text = b.get("optimized_bullet", b.get("original_bullet", ""))
        sec = b.get("section", "Experience")
        if sec == "Experience":
            key = (b.get("company", ""), b.get("role", ""))
            if key not in exp_dict:
                exp_dict[key] = []
            exp_dict[key].append(bullet_text)
        elif sec == "Projects":
            key = b.get("company", "")
            if key not in proj_dict:
                proj_dict[key] = []
            proj_dict[key].append(bullet_text)

    # Experience Section
    if exp_dict:
        story.append(Paragraph("Professional Experience", heading_style))
        for (company, role), bullets in exp_dict.items():
            story.append(Paragraph(f"<b>{role}</b> — {company}", job_title_style))
            for b in bullets:
                story.append(Paragraph(f"&bull; {b}", bullet_style))

    # Projects Section
    if proj_dict:
        story.append(Paragraph("Key Projects", heading_style))
        for name, bullets in proj_dict.items():
            story.append(Paragraph(f"<b>{name}</b>", job_title_style))
            for b in bullets:
                story.append(Paragraph(f"&bull; {b}", bullet_style))

    # Skills Section
    skills = parsed_resume.get("skills", [])
    if skills:
        story.append(Paragraph("Skills", heading_style))
        story.append(Paragraph(", ".join(skills), normal_style))

    # Education Section
    edu = parsed_resume.get("education", [])
    if edu:
        story.append(Paragraph("Education", heading_style))
        for item in edu:
            degree_str = f" — {item.get('degree')}" if item.get('degree') else ""
            story.append(Paragraph(f"<b>{item.get('school', '')}</b>{degree_str}", normal_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()

def generate_optimized_latex(original_latex: str, optimized_bullets: list) -> str:
    """
    Substitutes original bullets with optimized bullets in the LaTeX source text,
    maintaining 100% of the original formatting.
    """
    latex_out = original_latex
    for b in optimized_bullets:
        orig_bullet = b.get("original_bullet", "").strip()
        opt_bullet = b.get("optimized_bullet", "").strip()
        
        if not orig_bullet or orig_bullet == opt_bullet:
            continue
            
        # Standard replacements
        if orig_bullet in latex_out:
            latex_out = latex_out.replace(orig_bullet, opt_bullet)
        else:
            # Try to match without final period/spaces or slight LaTeX formatting cleanups
            orig_clean = orig_bullet.rstrip(". ")
            if orig_clean in latex_out:
                latex_out = latex_out.replace(orig_clean, opt_bullet.rstrip(". "))
            else:
                # Also try replacing matching phrases or parts of the bullet
                pass
    return latex_out

def latex_escape(text: str) -> str:
    """Escapes special LaTeX characters in plain text."""
    if not text:
        return ""
    s = str(text)
    replacements = [
        ('\\', r'\textbackslash{}'),
        ('&', r'\&'),
        ('%', r'\%'),
        ('$', r'\$'),
        ('#', r'\#'),
        ('_', r'\_'),
        ('{', r'\{'),
        ('}', r'\}'),
        ('~', r'\textasciitilde{}'),
        ('^', r'\textasciicircum{}'),
    ]
    # Escape input characters once; do not escape braces introduced by commands.
    mapping = dict(replacements)
    return "".join(mapping.get(char, char) for char in s)


DEFAULT_ATS_LATEX_TEMPLATE = (Path(__file__).resolve().parent.parent / "templates" / "resume_default.tex").read_text(encoding="utf-8")


def render_latex_resume(
    name: str,
    email: str,
    parsed_resume: dict,
    optimized_bullets: list,
    template_choice: str = "default",
    custom_template: Optional[str] = None
) -> str:
    """
    Renders LaTeX code for the resume.
    If template_choice is 'custom' and custom_template is supplied:
      - Uses template placeholders ({{NAME}}, {{EMAIL}}, etc.) if present.
      - Otherwise substitutes bullet points in the raw custom LaTeX source.
    If template_choice is 'default':
      - Renders using the ATS-friendly default template.
    """
    parsed_resume = parsed_resume or {}
    optimized_bullets = optimized_bullets or []

    full_template = None
    if template_choice == "custom" and not (custom_template or "").strip():
        raise ValueError("Provide a custom template or choose the default.")
    # If custom template requested
    if template_choice == "custom" and custom_template and custom_template.strip():
        template_str = custom_template.strip()
        if "__NAME__" in template_str and "__EXPERIENCE_BLOCK__" in template_str:
            full_template = template_str
        elif "{{NAME}}" in template_str:
            candidate_name = parsed_resume.get("name") or name or ""
            candidate_email = parsed_resume.get("email") or email or ""
            candidate_phone = parsed_resume.get("phone", "")

            exp_lines = []
            proj_lines = []
            for b in optimized_bullets:
                txt = b.get("optimized_bullet", b.get("original_bullet", ""))
                sec = b.get("section", "Experience")
                if sec == "Experience":
                    exp_lines.append(f"\\item {latex_escape(txt)}")
                else:
                    proj_lines.append(f"\\item {latex_escape(txt)}")

            skills = parsed_resume.get("skills", [])
            if isinstance(skills, list):
                skills_str = ", ".join(latex_escape(s) for s in skills)
            else:
                skills_str = str(skills)

            edu = parsed_resume.get("education", [])
            edu_str = " \\\\\n".join(
                f"{latex_escape(e.get('school', ''))} -- {latex_escape(e.get('degree', ''))}"
                for e in edu
            )

            replacements = {
                "{{NAME}}": latex_escape(candidate_name),
                "{{EMAIL}}": latex_escape(candidate_email),
                "{{PHONE}}": latex_escape(candidate_phone),
                "{{SKILLS}}": skills_str,
                "{{EXPERIENCE}}": "\n".join(exp_lines),
                "{{PROJECTS}}": "\n".join(proj_lines),
                "{{EDUCATION}}": edu_str,
                "{{SUMMARY}}": latex_escape(parsed_resume.get("profile_summary", "") or parsed_resume.get("summary", "")),
            }
            for k, v in replacements.items():
                template_str = template_str.replace(k, v)
            return template_str
        else:
            raise ValueError("Custom templates must use dynamic placeholders. Start with the default template and edit its layout; filled example resumes cannot be used as candidate content.")

    # Default ATS template generation
    candidate_name = parsed_resume.get("name") or name or ""
    candidate_email = parsed_resume.get("email") or email or ""
    candidate_phone = parsed_resume.get("phone")

    contact_parts = []
    if candidate_phone:
        contact_parts.append(rf"\faPhone\ {latex_escape(candidate_phone)}")
    if candidate_email:
        clean_email = latex_escape(candidate_email)
        contact_parts.append(rf"\href{{mailto:{candidate_email}}}{{\faEnvelope\ {clean_email}}}")

    linkedin = parsed_resume.get("linkedin")
    github = parsed_resume.get("github")
    leetcode = parsed_resume.get("leetcode")

    for link in parsed_resume.get("links", []):
        low = link.lower()
        if "linkedin.com" in low and not linkedin:
            linkedin = link
        elif "github.com" in low and not github:
            github = link
        elif "leetcode.com" in low and not leetcode:
            leetcode = link

    if linkedin:
        url = linkedin if linkedin.startswith("http") else f"https://{linkedin}"
        contact_parts.append(rf"\href{{{url}}}{{\faLinkedin\ LinkedIn}}")
    if github:
        url = github if github.startswith("http") else f"https://{github}"
        contact_parts.append(rf"\href{{{url}}}{{\faGithub\ GitHub}}")
    if leetcode:
        url = leetcode if leetcode.startswith("http") else f"https://{leetcode}"
        contact_parts.append(rf"\href{{{url}}}{{\faCode\ LeetCode}}")


    header_contact_str = "        " + "\n        \\enspace|\\enspace\n        ".join(contact_parts)

    # 1. Profile Summary
    summary_text = parsed_resume.get("profile_summary") or parsed_resume.get("summary", "")
    if summary_text:
        summary_block = (
            "% =========================================================\n"
            "% PROFILE SUMMARY\n"
            "% =========================================================\n\n"
            "\\section{Profile Summary}\n\n\n"
            "\\begin{onecolentry}\n"
            f"{latex_escape(summary_text.strip())}\n"
            "\\end{onecolentry}\n\n\n"
            "\\vspace{-3pt}"
        )
    else:
        summary_block = ""

    # 2. Technical Skills
    skills = parsed_resume.get("skill_categories") or parsed_resume.get("skills", [])
    if skills:
        if isinstance(skills, dict):
            skill_lines = []
            for cat, items in skills.items():
                items_str = ", ".join(latex_escape(x) for x in items)
                skill_lines.append(rf"\textbf{{{latex_escape(cat)}:}} {items_str}")
            skills_content = " \\\\\n".join(skill_lines)
        else:
            skills_content = ", ".join(latex_escape(x) for x in skills) if isinstance(skills, list) else latex_escape(skills)

        skills_block = (
            "% =========================================================\n"
            "% TECHNICAL SKILLS\n"
            "% =========================================================\n\n"
            "\\section{Technical Skills}\n\n"
            "\\begin{onecolentry}\n"
            f"{skills_content}\n"
            "\\end{onecolentry}\n"
        )
    else:
        skills_block = ""

    # Group optimized bullets
    exp_bullets_dict = {}
    proj_bullets_dict = {}
    for b in optimized_bullets:
        bullet_text = b.get("optimized_bullet", b.get("original_bullet", ""))
        sec = b.get("section", "Experience")
        if sec == "Experience":
            comp = b.get("company", "")
            role = b.get("role", "")
            key = (comp, role)
            if key not in exp_bullets_dict:
                exp_bullets_dict[key] = []
            exp_bullets_dict[key].append(bullet_text)
        elif sec == "Projects":
            proj = b.get("company", "")
            if proj not in proj_bullets_dict:
                proj_bullets_dict[proj] = []
            proj_bullets_dict[proj].append(bullet_text)

    # 3. Experience
    exp_list = parsed_resume.get("experience", [])
    exp_entries = []

    if exp_list:
        for job in exp_list:
            comp = job.get("company", "")
            role = job.get("role", "")
            dates = job.get("dates") or job.get("date_range", "")
            location = job.get("location", "")
            loc_str = f" -- {latex_escape(location)}" if location else ""

            bullets = exp_bullets_dict.get((comp, role))
            if not bullets:
                for (c, r), b_list in exp_bullets_dict.items():
                    if c.casefold().strip() == comp.casefold().strip() and r.casefold().strip() == role.casefold().strip():
                        bullets = b_list
                        break
            if not bullets:
                bullets = job.get("bullets", [])

            bullet_items = "\n".join(f"    \\item {latex_escape(b)}" for b in bullets if b.strip())

            entry_tex = (
                f"\\begin{{twocolentry}}{{\n"
                f"    \\textit{{{latex_escape(dates)}}}\n"
                f"}}\n"
                f"    \\textbf{{{latex_escape(role)}}}, {latex_escape(comp)}{loc_str}\n"
                f"\\end{{twocolentry}}\n\n"
                f"\\vspace{{2pt}}\n\n"
                f"\\begin{{onecolentry}}\n"
                f"\\begin{{highlights}}\n\n"
                f"{bullet_items}\n"
                f"\\end{{highlights}}\n"
                f"\\end{{onecolentry}}"
            )
            exp_entries.append(entry_tex)
    elif exp_bullets_dict:
        for (comp, role), bullets in exp_bullets_dict.items():
            bullet_items = "\n".join(f"    \\item {latex_escape(b)}" for b in bullets if b.strip())
            entry_tex = (
                f"\\begin{{twocolentry}}{{\n"
                f"    \\textit{{}}\n"
                f"}}\n"
                f"    \\textbf{{{latex_escape(role)}}}, {latex_escape(comp)}\n"
                f"\\end{{twocolentry}}\n\n"
                f"\\vspace{{2pt}}\n\n"
                f"\\begin{{onecolentry}}\n"
                f"\\begin{{highlights}}\n\n"
                f"{bullet_items}\n"
                f"\\end{{highlights}}\n"
                f"\\end{{onecolentry}}"
            )
            exp_entries.append(entry_tex)

    if exp_entries:
        exp_block = (
            "% =========================================================\n"
            "% EXPERIENCE\n"
            "% =========================================================\n\n"
            "\\vspace{-3pt}\n"
            "\\section{Experience}\n\n" +
            "\n\n\\vspace{4pt}\n\n".join(exp_entries)
        )
    else:
        exp_block = ""

    # 4. Projects
    proj_list = parsed_resume.get("projects", [])
    proj_entries = []
    if proj_list:
        for p in proj_list:
            p_name = p.get("name") or p.get("company", "")
            p_skills = p.get("skills") or p.get("technologies", "")
            if isinstance(p_skills, list):
                p_skills = ", ".join(str(skill) for skill in p_skills)
            bullets = proj_bullets_dict.get(p_name)
            if not bullets:
                bullets = p.get("bullets", [])

            skills_tag = f" \\textbar{{}} \\textit{{{latex_escape(p_skills)}}}" if p_skills else ""
            bullet_items = "\n".join(f"    \\item {latex_escape(b)}" for b in bullets if b.strip())

            entry_tex = (
                f"\\begin{{onecolentry}}\n"
                f"    \\textbf{{{latex_escape(p_name)}}}{skills_tag}\n"
                f"\\end{{onecolentry}}\n\n"
                f"\\begin{{onecolentry}}\n"
                f"\\begin{{highlights}}\n\n"
                f"{bullet_items}\n\n"
                f"\\end{{highlights}}\n"
                f"\\end{{onecolentry}}"
            )
            proj_entries.append(entry_tex)
    elif proj_bullets_dict:
        for p_name, bullets in proj_bullets_dict.items():
            bullet_items = "\n".join(f"    \\item {latex_escape(b)}" for b in bullets if b.strip())
            entry_tex = (
                f"\\begin{{onecolentry}}\n"
                f"    \\textbf{{{latex_escape(p_name)}}}\n"
                f"\\end{{onecolentry}}\n\n"
                f"\\begin{{onecolentry}}\n"
                f"\\begin{{highlights}}\n\n"
                f"{bullet_items}\n\n"
                f"\\end{{highlights}}\n"
                f"\\end{{onecolentry}}"
            )
            proj_entries.append(entry_tex)

    if proj_entries:
        proj_block = (
            "% =========================================================\n"
            "% PROJECTS\n"
            "% =========================================================\n\n"
            "\\vspace{-3pt}\n"
            "\\section{Projects}\n\n" +
            "\n\n\\vspace{4pt}\n\n".join(proj_entries)
        )
    else:
        proj_block = ""

    # 5. Education
    edu_list = parsed_resume.get("education", [])
    edu_entries = []
    if edu_list:
        for e in edu_list:
            school = e.get("school", "")
            degree = e.get("degree", "")
            years = e.get("year") or e.get("dates") or e.get("graduation_year", "")
            deg_part = f" -- {latex_escape(degree)}" if degree else ""
            years_str = latex_escape(years) if years else ""

            entry_tex = (
                f"\\begin{{twocolentry}}{{{years_str}}}\n"
                f"\\textbf{{{latex_escape(school)}}}{deg_part}\n"
                f"\\end{{twocolentry}}"
            )
            edu_entries.append(entry_tex)

    if edu_entries:
        edu_block = (
            "% =========================================================\n"
            "% EDUCATION\n"
            "% =========================================================\n\n"
            "\\vspace{-3pt}\n"
            "\\section{Education}\n\n" +
            "\n\n".join(edu_entries)
        )
    else:
        edu_block = ""

    # 6. Certifications & Coding Profile
    certs = parsed_resume.get("certifications", [])
    if certs or leetcode:
        cert_items = [latex_escape(c) for c in certs if c]
        certs_line = " \\quad $|$ \\quad ".join(cert_items) if cert_items else ""
        profile_line = ""
        if leetcode:
            handle = leetcode.rstrip("/").split("/")[-1]
            url = leetcode if leetcode.startswith("http") else f"https://{leetcode}"
            profile_line = (
                f"LeetCode:\n"
                f"\\href{{{url}}}{{\n"
                f"\\underline{{{latex_escape(handle)}}}\n"
                f"}}\n"
                f"\\quad $|$ \\quad Coding Profile"
            )
        combined = []
        if certs_line:
            combined.append(certs_line)
        if profile_line:
            combined.append(profile_line)

        cert_content = "\n\\par\\vspace{1pt}\n".join(combined)
        cert_block = (
            "% =========================================================\n"
            "% CERTIFICATIONS & CODING PROFILE\n"
            "% =========================================================\n\n"
            "\\vspace{-4pt}\n"
            "\\section{Certifications \\& Coding Profile}\n\n"
            "\\begin{onecolentry}\n\n"
            f"{cert_content}\n\n"
            "\\end{onecolentry}\n"
        )
    else:
        cert_block = ""

    # Assemble document
    doc = full_template or DEFAULT_ATS_LATEX_TEMPLATE
    doc = doc.replace("__NAME__", latex_escape(candidate_name))
    doc = doc.replace("__HEADER_CONTACT__", header_contact_str)
    doc = doc.replace("__PROFILE_SUMMARY_BLOCK__", summary_block)
    doc = doc.replace("__SKILLS_BLOCK__", skills_block)
    doc = doc.replace("__EXPERIENCE_BLOCK__", exp_block)
    doc = doc.replace("__PROJECTS_BLOCK__", proj_block)
    doc = doc.replace("__EDUCATION_BLOCK__", edu_block)
    doc = doc.replace("__CERTIFICATIONS_BLOCK__", cert_block)

    return doc


def compile_latex_to_pdf(latex_code: str) -> bytes:
    """
    Compiles LaTeX code into PDF using tectonic or pdflatex.
    """
    env = os.environ.copy()
    env["PATH"] = f"/opt/homebrew/bin:/usr/local/bin:/Library/TeX/texbin:{env.get('PATH', '')}"

    with tempfile.TemporaryDirectory(dir=".") as temp_dir:
        tex_path = os.path.join(temp_dir, "resume.tex")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_code)

        # 1. Try tectonic
        tectonic_res = subprocess.run(["which", "tectonic"], env=env, capture_output=True, text=True)
        tectonic_bin = tectonic_res.stdout.strip()
        if tectonic_bin and os.path.exists(tectonic_bin):
            try:
                res = subprocess.run(
                    [tectonic_bin, "-o", temp_dir, tex_path],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=90
                )
                pdf_path = os.path.join(temp_dir, "resume.pdf")
                if res.returncode == 0 and os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        return f.read()
                logger.warning(f"tectonic compilation failed (exit code {res.returncode}): {res.stderr or res.stdout}")
            except Exception as e:
                logger.warning(f"tectonic execution exception: {e}")

        # 2. Try pdflatex
        pdflatex_res = subprocess.run(["which", "pdflatex"], env=env, capture_output=True, text=True)
        pdflatex_bin = pdflatex_res.stdout.strip()
        if pdflatex_bin and os.path.exists(pdflatex_bin):
            try:
                res = subprocess.run(
                    [pdflatex_bin, "-no-shell-escape", "-halt-on-error", "-interaction=nonstopmode", "-output-directory", temp_dir, tex_path],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=45
                )
                pdf_path = os.path.join(temp_dir, "resume.pdf")
                if res.returncode == 0 and os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        return f.read()
                logger.warning(f"pdflatex compilation failed: {res.stderr or res.stdout}")
            except Exception as e:
                logger.warning(f"pdflatex execution exception: {e}")

        raise ValueError("Neither tectonic nor pdflatex could compile the LaTeX document to PDF.")
