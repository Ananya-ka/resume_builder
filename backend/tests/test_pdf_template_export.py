import pytest
from app.services.document_generator import (
    render_latex_resume,
    compile_latex_to_pdf,
    DEFAULT_ATS_LATEX_TEMPLATE,
    latex_escape,
)


def test_escape_preserves_generated_commands():
    assert latex_escape("C:\\work {50%} & x_y") == r"C:\textbackslash{}work \{50\%\} \& x\_y"


def test_identity_and_college_come_from_parsed_resume():
    parsed = {"name": "aLEX de Souza", "email": "alex@college.edu",
              "education": [{"school": "College of Arts & Science", "degree": "BSc", "dates": "2018–2021"}]}
    rendered = render_latex_resume("Account User", "account@example.com", parsed, [])
    assert "aLEX de Souza" in rendered
    assert "alex@college.edu" in rendered
    assert r"College of Arts \& Science" in rendered
    assert "2018–2021" in rendered
    assert "Account User" not in rendered
    assert "account@example.com" not in rendered
    empty = render_latex_resume("", "", {}, [])
    for invented in ("Candidate Name", "example.com", "University", "2022", "mailto:"):
        assert invented not in empty


def test_render_preserves_attribution_and_does_not_invent_dates():
    rendered = render_latex_resume("Candidate", "", {
        "skills": ["Python", "SQL", "Docker", "Redis", "Git", "C++", "Java", "Go"],
        "experience": [{"company": "Other Company", "role": "Engineer", "bullets": ["Original work"]}],
        "projects": [{"name": "Demo", "technologies": ["Python", "SQL"], "bullets": ["Built demo"]}],
        "education": [{"school": "Example University"}],
    }, [{"company": "First Company", "role": "Engineer", "optimized_bullet": "Unrelated work"}])
    assert r"\section{Technical Skills}" in rendered
    assert "Frameworks" not in rendered
    assert "Original work" in rendered
    assert "Unrelated work" not in rendered
    assert "2022 -- 2026" not in rendered
    assert "Python, SQL" in rendered
    assert "['Python'" not in rendered

def test_default_latex_template_contains_structure():
    assert r"\documentclass" in DEFAULT_ATS_LATEX_TEMPLATE
    assert r"\usepackage{charter}" in DEFAULT_ATS_LATEX_TEMPLATE
    assert r"\usepackage{paracol}" in DEFAULT_ATS_LATEX_TEMPLATE
    assert r"\newenvironment{highlights}" in DEFAULT_ATS_LATEX_TEMPLATE
    assert r"\newenvironment{twocolentry}" in DEFAULT_ATS_LATEX_TEMPLATE


def test_render_latex_resume_default():
    parsed = {
        "name": "Ananya Kashyap",
        "email": "ananya@example.com",
        "phone": "+1-555-0199",
        "linkedin": "linkedin.com/in/ananya",
        "github": "github.com/ananya",
        "leetcode": "leetcode.com/u/ananya/",
        "profile_summary": "Seasoned backend and AI systems engineer.",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "PyTorch"],
        "experience": [
            {
                "company": "Darwix AI",
                "role": "SDE-1, AI/ML Engineer",
                "dates": "Feb 2026 -- Present",
                "location": "Gurugram",
                "bullets": ["Engineered high performance inference pipelines."],
            }
        ],
        "projects": [
            {
                "name": "CareerProof",
                "skills": "FastAPI, React, PostgreSQL",
                "bullets": ["Built factual resume optimization engine."],
            }
        ],
        "education": [
            {
                "school": "Malaviya National Institute of Technology Jaipur",
                "degree": "B.Tech, ECE",
                "year": "2022 -- 2026",
            }
        ],
        "certifications": ["Foundations of AI & Machine Learning"],
    }
    optimized_bullets = [
        {
            "section": "Experience",
            "company": "Darwix AI",
            "role": "SDE-1, AI/ML Engineer",
            "optimized_bullet": "Engineered high-throughput AI pipelines serving 1M requests daily with sub-50ms latency.",
        }
    ]

    rendered = render_latex_resume(
        name="Ananya Kashyap",
        email="ananya@example.com",
        parsed_resume=parsed,
        optimized_bullets=optimized_bullets,
        template_choice="default"
    )

    assert "Ananya Kashyap" in rendered
    assert "Darwix AI" in rendered
    assert "Engineered high-throughput AI pipelines" in rendered
    assert "CareerProof" in rendered
    assert "Malaviya National Institute of Technology" in rendered
    assert "FastAPI" in rendered
    assert r"\[1pt\]" not in rendered

    # Test actual compilation to PDF
    pdf_bytes = compile_latex_to_pdf(rendered)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


def test_render_latex_resume_custom_template():
    custom_template = r"""\documentclass{article}
\begin{document}
\section*{{{NAME}}}
Email: {{EMAIL}}
\subsection*{Experience}
\begin{itemize}
{{EXPERIENCE}}
\end{itemize}
\end{document}"""

    optimized_bullets = [
        {
            "section": "Experience",
            "company": "TechCorp",
            "role": "Lead Architect",
            "optimized_bullet": "Designed scalable cloud infrastructure.",
        }
    ]

    rendered = render_latex_resume(
        name="Taylor Swift",
        email="taylor@example.com",
        parsed_resume={},
        optimized_bullets=optimized_bullets,
        template_choice="custom",
        custom_template=custom_template
    )

    assert "Taylor Swift" in rendered
    assert "taylor@example.com" in rendered
    assert r"\item Designed scalable cloud infrastructure." in rendered

    pdf_bytes = compile_latex_to_pdf(rendered)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")
