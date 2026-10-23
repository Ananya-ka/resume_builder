from app.services.rule_engine import RuleEngine

def test_rule_engine_basic_match():
    engine = RuleEngine()

    resume_data = {
        "profile_summary": "Experienced Python Software Engineer scaling backend microservices.",
        "skills": ["Python", "Docker", "PostgreSQL", "FastAPI"],
        "experience": [
            {
                "company": "Tech Corp",
                "role": "Senior Engineer",
                "bullets": [
                    "Designed and built high-performance APIs using FastAPI, reducing latency by 30%.",
                    "Developed and maintained CI/CD pipelines in AWS."
                ]
            }
        ],
        "projects": [
            {
                "name": "Data Pipe",
                "bullets": [
                    "Optimized database queries in PostgreSQL, improving throughput."
                ]
            }
        ],
        "education": [{"school": "Uni", "degree": "BS CS"}]
    }

    jd_data = {
        "ats_keywords": ["FastAPI", "PostgreSQL", "CI/CD", "AWS", "Python"],
        "required_skills": ["Python", "FastAPI"],
        "preferred_skills": ["Kubernetes"],
        "experience_years": 5.0
    }

    results = engine.analyze(resume_data, jd_data)

    assert "ats_score" in results
    assert results["keyword_match"] > 50.0 # mostly matching
    assert results["skill_match"] == 100.0 # Python, FastAPI are matched
    assert results["formatting_report"]["duplicate_bullets"] == 0
    # "designed", "developed", "optimized" are action verbs
    assert results["formatting_report"]["action_verb_rate"] == 100.0


def test_missing_dates_never_invent_years_of_experience():
    result = RuleEngine().analyze({"experience": [{"company": "Company", "role": "Developer", "bullets": ["Built APIs."]}]}, {"experience_years": 2, "required_skills": None, "preferred_skills": None, "ats_keywords": None})
    assert result["experience_match"] == 0
    assert result["experience_duration_known"] is False
    assert "estimate" in result["score_label"]


def test_experience_tenure_extracted_from_date_ranges():
    engine = RuleEngine()
    resume_data = {
        "experience": [
            {
                "company": "Tech Corp",
                "role": "Senior Engineer",
                "dates": "Jan 2021 – Present",
                "bullets": ["Led development of microservices."]
            },
            {
                "company": "Startup Co",
                "role": "Developer",
                "dates": "2018 – 2020",
                "bullets": ["Built backend services."]
            }
        ]
    }
    jd_data = {"experience_years": 5.0}
    result = engine.analyze(resume_data, jd_data)

    assert result["experience_duration_known"] is True
    assert result["resume_years"] >= 7.0  # 2018-2020 (3 yrs) + Jan 2021-Present (~5.8 yrs)
    assert result["experience_match"] == 100.0
    assert result["required_years"] == 5.0


def test_experience_tenure_merges_overlapping_jobs():
    engine = RuleEngine()
    resume_data = {
        "experience": [
            {
                "company": "Company A",
                "role": "Consultant",
                "dates": "2018 – 2021",
                "bullets": ["Consulting services."]
            },
            {
                "company": "Company B",
                "role": "Full-time Engineer",
                "dates": "2020 – 2022",
                "bullets": ["Core platform engineering."]
            }
        ]
    }
    jd_data = {"experience_years": 6.0}
    result = engine.analyze(resume_data, jd_data)

    # 2018.0 to 2023.0 merged interval = 5.0 years (not 4.0 + 3.0 = 7.0)
    assert result["experience_duration_known"] is True
    assert result["resume_years"] == 5.0
    # Candidate has 5.0 years vs 6.0 years required -> strictly 0.0%
    assert result["experience_match"] == 0.0

    # When requirement is 5.0 years, candidate meets requirement -> 100.0%
    result_met = engine.analyze(resume_data, {"experience_years": 5.0})
    assert result_met["experience_match"] == 100.0


def test_education_dates_never_counted_as_work_tenure():
    engine = RuleEngine()
    resume_data = {
        "experience": [
            {
                "company": "Tech Corp",
                "role": "Engineer",
                "bullets": ["Wrote code."]
            }
        ],
        "education": [
            {
                "school": "University of Tech",
                "degree": "B.S. in Computer Science",
                "dates": "2014 – 2018"
            }
        ]
    }
    jd_data = {"experience_years": 3.0}
    result = engine.analyze(resume_data, jd_data)

    assert result["experience_duration_known"] is False
    assert result["resume_years"] == 0.0
    assert result["experience_match"] == 0.0


def test_candidate_exceeding_minimum_is_never_penalized():
    """Candidates exceeding minimum experience should receive 100% score and never be penalized."""
    engine = RuleEngine()
    resume_data = {
        "experience": [
            {
                "company": "Enterprise Corp",
                "role": "Staff Engineer",
                "dates": "2015 – 2023", # 9 years
                "bullets": ["Architected distributed systems."]
            }
        ]
    }
    jd_data = {
        "experience_years": 3.0,
        "raw_text": "We are seeking a Software Engineer with at least 3+ years of experience."
    }
    result = engine.analyze(resume_data, jd_data)

    assert result["resume_years"] == 9.0
    assert result["experience_match"] == 100.0
    tenure_rep = result["tenure_report"]
    assert tenure_rep["is_eligible"] is True
    assert tenure_rep["eligibility_status"] == "meets_requirements"
    assert len(tenure_rep["penalties"]) == 0
    assert any("meets or exceeds minimum requirement" in e["reason"].lower() for e in tenure_rep["evidence"])


def test_candidate_exceeding_explicit_maximum_is_penalized():
    """Candidates exceeding an explicit maximum cap are penalized with explainable penalty."""
    engine = RuleEngine()
    resume_data = {
        "experience": [
            {
                "company": "Corp",
                "role": "Senior Engineer",
                "dates": "2017 – 2023", # 7 years
                "bullets": ["Managed platforms."]
            }
        ]
    }
    jd_data = {
        "raw_text": "Junior Software Engineer position. Requirements: 1-3 years of experience. Maximum 3 years."
    }
    result = engine.analyze(resume_data, jd_data)

    tenure_rep = result["tenure_report"]
    assert tenure_rep["has_explicit_maximum"] is True
    assert tenure_rep["max_years"] == 3.0
    assert tenure_rep["eligibility_status"] == "exceeds_maximum"
    assert any(p["code"] == "OVERQUALIFICATION_EXPLICIT_MAX" for p in tenure_rep["penalties"])
    assert result["experience_match"] < 100.0


def test_preferred_experience_scoring_bonus():
    """Differentiates minimum hard eligibility from preferred bonus experience."""
    engine = RuleEngine()
    jd_data = {
        "raw_text": "Backend Engineer. Requirements: 3+ years experience required. 5+ years preferred."
    }

    # Candidate 1: Exactly meets minimum (3 yrs)
    res_min = {
        "experience": [{"company": "A", "role": "Dev", "dates": "2020 – 2022", "bullets": ["APIs."]}] # 3 yrs (2020-2023)
    }
    res_1 = engine.analyze(res_min, jd_data)

    # Candidate 2: Meets preferred (6 yrs)
    res_pref = {
        "experience": [{"company": "B", "role": "Dev", "dates": "2017 – 2022", "bullets": ["APIs."]}] # 6 yrs (2017-2023)
    }
    res_2 = engine.analyze(res_pref, jd_data)

    # Candidate 3: Below minimum (2 yrs vs 3 yrs req)
    res_deficit = {
        "experience": [{"company": "C", "role": "Dev", "dates": "2021 – 2022", "bullets": ["APIs."]}] # 2 yrs (2021-2023)
    }
    res_3 = engine.analyze(res_deficit, jd_data)

    assert res_1["tenure_report"]["is_eligible"] is True
    assert res_2["tenure_report"]["is_eligible"] is True
    assert res_3["tenure_report"]["is_eligible"] is False
    # Meeting requirement gives 100.0%
    assert res_1["experience_match"] == 100.0
    assert res_2["experience_match"] == 100.0
    # Lesser YOE gives strictly 0.0%
    assert res_3["experience_match"] == 0.0


def test_role_specific_tenure_matching():
    """Tests evaluation of technology or role-specific experience requirements."""
    engine = RuleEngine()
    jd_data = {
        "raw_text": "Senior Python Developer. Requirements: 5+ years experience total. 3+ years of experience with Python."
    }

    # Candidate with 5 yrs total, all in Python
    res_python = {
        "experience": [
            {
                "company": "PyCorp",
                "role": "Python Backend Engineer",
                "dates": "2018 – 2022", # 5 yrs
                "bullets": ["Developed services using Python and FastAPI."]
            }
        ]
    }
    result_python = engine.analyze(res_python, jd_data)
    assert result_python["experience_match"] == 100.0
    assert any(e["type"] == "ROLE_SPECIFIC_MET" for e in result_python["tenure_report"]["evidence"])

    # Candidate with 5 yrs total, but only Java (no Python)
    res_java = {
        "experience": [
            {
                "company": "JavaCorp",
                "role": "Java Enterprise Developer",
                "dates": "2018 – 2022", # 5 yrs
                "bullets": ["Developed services using Java and Spring Boot."]
            }
        ]
    }
    result_java = engine.analyze(res_java, jd_data)
    assert result_java["experience_match"] < 100.0
    assert any(p["code"] == "ROLE_SPECIFIC_MISSING" for p in result_java["tenure_report"]["penalties"])


def test_internship_categorization_and_separation():
    """Verifies that internships are identified, categorized, and separated from full-time tenure."""
    engine = RuleEngine()
    resume_data = {
        "experience": [
            {
                "company": "BigTech",
                "role": "Software Engineering Intern",
                "dates": "May 2020 – Aug 2020",
                "bullets": ["Built analytics dashboard."]
            },
            {
                "company": "BigTech",
                "role": "Software Engineer",
                "dates": "Jan 2021 – Present",
                "bullets": ["Full-time backend engineer."]
            }
        ]
    }
    jd_data = {"experience_years": 2.0}
    result = engine.analyze(resume_data, jd_data)

    tenure_rep = result["tenure_report"]
    assert tenure_rep["internship_years"] > 0
    assert tenure_rep["full_time_years"] >= 2.0
    assert tenure_rep["total_years"] >= tenure_rep["full_time_years"]
    assert result["experience_match"] == 100.0


def test_complex_overlapping_jobs_no_double_counting():
    """Three overlapping/nested jobs must be merged into continuous timeline without double-counting."""
    engine = RuleEngine()
    resume_data = {
        "experience": [
            {
                "company": "Primary Employer",
                "role": "Full-time Engineer",
                "dates": "2019 – 2022", # 2019.0 to 2023.0 = 4.0 yrs
                "bullets": ["Core platform."]
            },
            {
                "company": "Side Startup",
                "role": "Co-founder / Part-time",
                "dates": "2020 – 2021", # 2020.0 to 2022.0 = 2.0 yrs (nested)
                "bullets": ["Startup."]
            },
            {
                "company": "Contract Client",
                "role": "Consultant",
                "dates": "2022 – 2023", # 2022.0 to 2024.0 = 2.0 yrs (overlaps tail)
                "bullets": ["Consulting."]
            }
        ]
    }
    jd_data = {"experience_years": 5.0}
    result = engine.analyze(resume_data, jd_data)

    # 2019.0 to 2024.0 merged = exactly 5.0 continuous years (NOT 4.0 + 2.0 + 2.0 = 8.0)
    assert result["resume_years"] == 5.0
    assert result["experience_match"] == 100.0


def test_seasons_date_parsing():
    """Tests season-based dates like 'Summer 2021' to 'Fall 2021'."""
    from app.services.tenure_matcher import TenureMatcher
    matcher = TenureMatcher()
    intervals = matcher.extract_date_intervals("Summer 2021 – Fall 2021")
    assert len(intervals) == 1
    start, end, _, _ = intervals[0]
    # Summer start: month 6 -> ~2021.417. Fall end: month 11 -> ~2021.917
    assert 2021.4 <= start <= 2021.5
    assert 2021.8 <= end <= 2022.0
    assert 0.3 <= (end - start) <= 0.7


def test_entry_level_and_zero_experience_required():
    """Entry-level or zero-experience requirements should give 100% score."""
    engine = RuleEngine()
    jd_data = {
        "raw_text": "Entry level Software Engineer. New graduates welcome. No prior experience required."
    }
    resume_data = {
        "experience": [
            {
                "company": "College Project",
                "role": "Developer",
                "dates": "2023 – 2023",
                "bullets": ["Built app."]
            }
        ]
    }
    result = engine.analyze(resume_data, jd_data)
    assert result["experience_match"] == 100.0
    assert result["tenure_report"]["is_eligible"] is True


