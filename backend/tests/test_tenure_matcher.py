import pytest
from app.services.tenure_matcher import (
    TenureMatcher,
    TenureScoringConfig,
    JDExperienceRequirements,
    CandidateExperienceProfile,
)
from app.services.ats_checker import ATSCheckerEngine
from app.services.rule_engine import RuleEngine

def test_extract_jd_requirements_ranges_and_caps():
    matcher = TenureMatcher()

    # Range
    r1 = matcher.extract_jd_requirements("We are looking for someone with 3-5 years of experience in backend development.")
    assert r1.min_years == 3.0
    assert r1.max_years == 5.0
    assert r1.has_explicit_maximum is True

    # "between X and Y"
    r2 = matcher.extract_jd_requirements("Seeking between 2 and 4 years of experience.")
    assert r2.min_years == 2.0
    assert r2.max_years == 4.0
    assert r2.has_explicit_maximum is True

    # Explicit maximum / cap
    r3 = matcher.extract_jd_requirements("Junior Associate role. Maximum 2 years experience. Up to 2 years.")
    assert r3.max_years == 2.0
    assert r3.has_explicit_maximum is True

    # Open-ended minimum
    r4 = matcher.extract_jd_requirements("Senior Platform Engineer: requires at least 5+ years of experience.")
    assert r4.min_years == 5.0
    assert r4.max_years is None
    assert r4.has_explicit_maximum is False

    # Preferred vs required
    r5 = matcher.extract_jd_requirements("Qualifications: 3+ years required. 5+ years preferred.")
    assert r5.min_years == 3.0
    assert r5.preferred_years == 5.0
    assert r5.has_explicit_maximum is False

    # Entry-level / new grad
    r6 = matcher.extract_jd_requirements("Entry level Software Engineer. New graduates welcome.")
    assert r6.min_years == 0.0
    assert r6.is_entry_level is True

def test_extract_jd_role_and_tech_specific_requirements():
    matcher = TenureMatcher()
    jd = """
    Full Stack Developer
    Requirements:
    - 5+ years of software engineering experience
    - 3+ years of experience with Python and FastAPI
    - 2+ years working with React
    - 1+ year in Kubernetes
    """
    reqs = matcher.extract_jd_requirements(jd)
    assert reqs.min_years == 5.0
    targets = [r.target for r in reqs.role_specific]
    assert any("python" in t for t in targets)
    assert any("react" in t for t in targets)

def test_timeline_interval_merging_prevents_double_counting():
    matcher = TenureMatcher()
    # 2 concurrent jobs occurring during exactly the same 2-year period
    # Job A: Jan 2020 – Dec 2021 (2.0 yrs)
    # Job B: Jan 2020 – Dec 2021 (2.0 yrs)
    resume = {
        "experience": [
            {"company": "Company A", "role": "Engineer", "dates": "Jan 2020 – Dec 2021"},
            {"company": "Company B", "role": "Consultant", "dates": "Jan 2020 – Dec 2021"}
        ]
    }
    profile = matcher.extract_candidate_profile(resume)
    # Total merged tenure must be ~2.0 years, NEVER 4.0 years
    assert 1.9 <= profile.total_years <= 2.1
    assert len(profile.merged_timeline_intervals) == 1

def test_timeline_chained_and_nested_jobs():
    matcher = TenureMatcher()
    resume = {
        "experience": [
            {"company": "Main", "role": "Dev", "dates": "2018 – 2022"},  # 2018.0 to 2023.0 = 5.0 yrs
            {"company": "Side 1", "role": "Advisor", "dates": "2019 – 2020"}, # 2019.0 to 2021.0 = 2.0 yrs (inside Main)
            {"company": "Side 2", "role": "Contract", "dates": "2021 – 2023"}  # 2021.0 to 2024.0 = 3.0 yrs (extends Main by 1 yr)
        ]
    }
    profile = matcher.extract_candidate_profile(resume)
    # 2018.0 to 2024.0 = exactly 6.0 years
    assert profile.total_years == 6.0
    assert len(profile.merged_timeline_intervals) == 1

def test_ongoing_current_roles():
    matcher = TenureMatcher()
    resume = {
        "experience": [
            {"company": "Current Employer", "role": "Lead", "dates": "Jan 2022 – Present"}
        ]
    }
    profile = matcher.extract_candidate_profile(resume)
    assert profile.duration_known is True
    assert profile.total_years >= 2.0
    assert profile.roles[0].is_current is True

def test_missing_dates_flagged_without_inventing_tenure():
    matcher = TenureMatcher()
    resume = {
        "experience": [
            {"company": "Secret Corp", "role": "Developer", "bullets": ["Wrote code."]}
        ]
    }
    profile = matcher.extract_candidate_profile(resume)
    assert profile.duration_known is False
    assert profile.total_years == 0.0
    assert profile.roles[0].dates_missing is True

    # Scoring should output 0.0 with explainable penalty
    jd_reqs = JDExperienceRequirements(min_years=3.0)
    score_res = matcher.calculate_tenure_score(profile, jd_reqs)
    assert score_res["tenure_score"] == 0.0
    assert score_res["is_eligible"] is False
    assert score_res["eligibility_status"] == "unverifiable"
    assert any(p["code"] == "MISSING_DATES" for p in score_res["penalties"])

def test_candidate_exceeding_minimum_never_penalized_without_max():
    matcher = TenureMatcher()
    # Candidate with 10 years experience applying for 3+ years role
    resume = {
        "experience": [
            {"company": "Enterprise", "role": "Senior Architect", "dates": "2013 – 2023"} # 11 yrs
        ]
    }
    profile = matcher.extract_candidate_profile(resume)
    jd_reqs = matcher.extract_jd_requirements("Requires 3+ years of experience.")

    score_res = matcher.calculate_tenure_score(profile, jd_reqs)
    assert score_res["tenure_score"] == 100.0
    assert score_res["is_eligible"] is True
    assert score_res["eligibility_status"] == "meets_requirements"
    assert len(score_res["penalties"]) == 0

def test_candidate_exceeding_explicit_maximum_penalized():
    matcher = TenureMatcher()
    # Candidate with 7 years experience applying for a position capped at 3 years
    resume = {
        "experience": [
            {"company": "Company", "role": "Engineer", "dates": "2016 – 2022"} # 7 yrs
        ]
    }
    profile = matcher.extract_candidate_profile(resume)
    jd_reqs = matcher.extract_jd_requirements("Associate role. Experience: 1-3 years. Maximum 3 years.")

    score_res = matcher.calculate_tenure_score(profile, jd_reqs)
    assert score_res["is_eligible"] is True
    assert score_res["eligibility_status"] == "exceeds_maximum"
    assert score_res["has_explicit_maximum"] is True
    assert score_res["max_years"] == 3.0
    # Overqualification penalty applied
    assert any(p["code"] == "OVERQUALIFICATION_EXPLICIT_MAX" for p in score_res["penalties"])
    assert score_res["tenure_score"] < 100.0

def test_deterministic_scoring_configuration():
    # Test configurable penalty weights
    custom_cfg = TenureScoringConfig(
        overqualification_penalty_per_year=10.0,
        max_overqualification_penalty=30.0
    )
    matcher = TenureMatcher(config=custom_cfg)

    resume = {
        "experience": [
            {"company": "Company", "role": "Engineer", "dates": "2017 – 2022"} # 6 yrs
        ]
    }
    profile = matcher.extract_candidate_profile(resume)
    jd_reqs = JDExperienceRequirements(min_years=1.0, max_years=3.0, has_explicit_maximum=True)

    score_res = matcher.calculate_tenure_score(profile, jd_reqs)
    # Excess is 6 - 3 = 3 yrs. At 10 pts/yr, penalty is 30.0
    assert score_res["scoring_breakdown"]["overqualification_penalty"] == 30.0
    assert score_res["tenure_score"] == 70.0

def test_ats_checker_engine_tenure_report_integration():
    engine = ATSCheckerEngine()
    resume_text = """
    Jane Developer
    jane@example.com

    EXPERIENCE
    Stripe | Senior Engineer | Jan 2020 – Present
    - Built payments microservices using FastAPI, Python, and PostgreSQL.
    - Scaled distributed transaction architecture.

    Shopify | Software Engineer | Jan 2017 – Dec 2019
    - Developed merchant services with Python and Ruby.

    EDUCATION
    BS Computer Science, Stanford University
    """

    jd_text = """
    Principal Platform Engineer
    Requirements:
    - 5+ years of software engineering experience
    - 3+ years experience with Python
    - 8+ years preferred
    """

    # Pure text check match
    result = engine.rule_engine.analyze(
        engine._parse_raw_resume_text(resume_text),
        engine._parse_raw_jd_text(jd_text)
    )

    assert "tenure_report" in result
    tenure_rep = result["tenure_report"]
    assert tenure_rep["is_eligible"] is True
    assert tenure_rep["candidate_years"] >= 7.0
    assert tenure_rep["required_years"] == 5.0
    assert tenure_rep["preferred_years"] == 8.0
    assert tenure_rep["tenure_score"] >= 80.0
    assert len(tenure_rep["timeline_intervals"]) >= 1


def test_candidate_with_lesser_yoe_allocated_zero_percent():
    """If JD has YOE requirement and resume has lesser YOE, allocate strictly 0%."""
    matcher = TenureMatcher()
    resume = {
        "experience": [
            {"company": "Company", "role": "Junior Dev", "dates": "2021 – 2022"} # 2.0 yrs
        ]
    }
    profile = matcher.extract_candidate_profile(resume)
    jd_reqs = matcher.extract_jd_requirements("Requires 4+ years of experience.")

    score_res = matcher.calculate_tenure_score(profile, jd_reqs)
    # Must be strictly 0.0%, never 30% or 50%
    assert score_res["tenure_score"] == 0.0
    assert score_res["is_eligible"] is False
    assert score_res["eligibility_status"] == "below_minimum"
    assert any(p["code"] == "TENURE_DEFICIT" for p in score_res["penalties"])
    assert score_res["scoring_breakdown"]["final_score"] == 0.0


def test_binary_yoe_scoring_never_returns_intermediate_percentage():
    """Confirms that tenure scoring is strictly binary (0% or 100%), never 30%, 50%, or 75%."""
    matcher = TenureMatcher()
    jd_reqs = matcher.extract_jd_requirements("Seeking Software Engineer with 4+ years of experience.")

    # 1. Candidate with 1 year (previously ~25% proportional) -> MUST be 0%
    res_1 = {"experience": [{"company": "A", "role": "Dev", "dates": "2022 – 2022"}]} # 1 yr
    score_1 = matcher.calculate_tenure_score(matcher.extract_candidate_profile(res_1), jd_reqs)
    assert score_1["tenure_score"] == 0.0
    assert score_1["is_eligible"] is False

    # 2. Candidate with 2 years (previously ~50% proportional) -> MUST be 0%
    res_2 = {"experience": [{"company": "A", "role": "Dev", "dates": "2021 – 2022"}]} # 2 yrs
    score_2 = matcher.calculate_tenure_score(matcher.extract_candidate_profile(res_2), jd_reqs)
    assert score_2["tenure_score"] == 0.0
    assert score_2["is_eligible"] is False

    # 3. Candidate with 3 years (previously ~75% proportional) -> MUST be 0%
    res_3 = {"experience": [{"company": "A", "role": "Dev", "dates": "2020 – 2022"}]} # 3 yrs
    score_3 = matcher.calculate_tenure_score(matcher.extract_candidate_profile(res_3), jd_reqs)
    assert score_3["tenure_score"] == 0.0
    assert score_3["is_eligible"] is False

    # 4. Candidate with exactly 4 years -> MUST be 100%
    res_4 = {"experience": [{"company": "A", "role": "Dev", "dates": "2019 – 2022"}]} # 4 yrs
    score_4 = matcher.calculate_tenure_score(matcher.extract_candidate_profile(res_4), jd_reqs)
    assert score_4["tenure_score"] == 100.0
    assert score_4["is_eligible"] is True

    # 5. Candidate with 6 years (exceeding minimum) -> MUST be 100%
    res_6 = {"experience": [{"company": "A", "role": "Dev", "dates": "2017 – 2022"}]} # 6 yrs
    score_6 = matcher.calculate_tenure_score(matcher.extract_candidate_profile(res_6), jd_reqs)
    assert score_6["tenure_score"] == 100.0
    assert score_6["is_eligible"] is True


def test_bullets_with_years_do_not_inflate_tenure():
    """Accomplishment bullets containing mentions of years must not falsely inflate candidate timeline."""
    matcher = TenureMatcher()
    resume = {
        "experience": [
            {
                "company": "Startup",
                "role": "Software Engineer",
                "dates": "2022 – 2022", # 1 year actual timeline
                "bullets": [
                    "Managed analytics pipeline processing 5 years of historical financial transactions.",
                    "Reduced 3 years of technical debt in modernizing legacy database."
                ]
            }
        ]
    }
    profile = matcher.extract_candidate_profile(resume)
    assert profile.total_years == 1.0  # Must be 1.0 year, NOT 5.0 or 3.0

    jd_reqs = matcher.extract_jd_requirements("Requires 3+ years of experience.")
    score = matcher.calculate_tenure_score(profile, jd_reqs)
    # 1 year vs 3 years required must be strictly 0.0%
    assert score["tenure_score"] == 0.0
    assert score["is_eligible"] is False


def test_rule_engine_experience_match_strictly_binary():
    """End-to-end check: RuleEngine returns 0.0% for lesser YOE and 100.0% for met YOE."""
    engine = RuleEngine()
    jd = {"experience_years": 5.0, "raw_text": "Senior Developer requiring 5+ years experience."}

    # Deficit: 2 years -> strictly 0.0%
    res_deficit = {"experience": [{"company": "C", "role": "Dev", "dates": "2021 – 2022", "bullets": ["Built API."]}]}
    res_deficit_out = engine.analyze(res_deficit, jd)
    assert res_deficit_out["experience_match"] == 0.0

    # Met: 5 years -> strictly 100.0%
    res_met = {"experience": [{"company": "C", "role": "Dev", "dates": "2018 – 2022", "bullets": ["Built API."]}]}
    res_met_out = engine.analyze(res_met, jd)
    assert res_met_out["experience_match"] == 100.0

