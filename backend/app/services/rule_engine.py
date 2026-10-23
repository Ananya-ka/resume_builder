import re
from datetime import datetime
from typing import Dict, Any, List, Set, Optional, Tuple

class RuleEngine:
    ACTION_VERBS = {
        "designed", "developed", "built", "implemented", "scaled", "led", "managed",
        "created", "delivered", "optimized", "reduced", "increased", "orchestrated",
        "engineered", "accelerated", "integrated", "streamlined", "automated", "architected",
        "mentored", "revamped", "monitored", "standardized", "debugged", "formulated"
    }

    MONTHS = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "september": 9, "sept": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12
    }

    _MONTH_NAMES_PATTERN = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Sept|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
    _ENDPOINT_PATTERN = rf"(?:{_MONTH_NAMES_PATTERN}\s+\d{{4}}|\d{{1,2}}/\d{{2,4}}|\b(?:19\d{{2}}|20\d{{2}})\b)"
    _END_ENDPOINT_PATTERN = rf"(?:{_MONTH_NAMES_PATTERN}\s+\d{{4}}|\d{{1,2}}/\d{{2,4}}|\b(?:19\d{{2}}|20\d{{2}})\b|Present|Current|Now|Ongoing)"
    DATE_RANGE_REGEX = re.compile(rf"({_ENDPOINT_PATTERN})\s*(?:[–—\-]+|\bto\b)\s*({_END_ENDPOINT_PATTERN})", re.IGNORECASE)

    def __init__(self):
        from app.services.tenure_matcher import TenureMatcher
        from app.services.ats_matcher import ATSMatchingEngine
        self.tenure_matcher = TenureMatcher()
        self.ats_matcher = ATSMatchingEngine()

    def analyze(self, resume_data: Dict[str, Any], jd_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pure Python multi-dimensional ATS evaluator.
        Evaluates skills, technical competencies, experience relevance, tenure,
        responsibilities, education, domain knowledge, and formatting integrity.
        """
        # 1. Execute deep multi-dimensional matching
        match_eval = self.ats_matcher.evaluate(resume_data, jd_data)

        # 2. Extract full resume text for legacy token-level & formatting checks
        resume_text_parts = []
        if resume_data.get("profile_summary"):
            resume_text_parts.append(resume_data["profile_summary"])
        for exp in resume_data.get("experience", []):
            resume_text_parts.append(exp.get("company", ""))
            resume_text_parts.append(exp.get("role", ""))
            resume_text_parts.append(exp.get("dates", ""))
            resume_text_parts.append(exp.get("duration", ""))
            resume_text_parts.append(exp.get("date_range", ""))
            resume_text_parts.extend(exp.get("bullets", []))
        for proj in resume_data.get("projects", []):
            resume_text_parts.append(proj.get("name", ""))
            resume_text_parts.extend(proj.get("bullets", []))
        resume_text_parts.extend(resume_data.get("skills", []))
        resume_text_parts.extend(resume_data.get("achievements", []))
        resume_text_parts.extend(resume_data.get("certifications", []))
        for edu in resume_data.get("education", []):
            resume_text_parts.append(edu.get("school", ""))
            resume_text_parts.append(edu.get("degree", ""))
        
        full_resume_text = " ".join(resume_text_parts)
        words_resume = self._tokenize(full_resume_text)

        # 3. Keyword Match: Combine literal terms and semantic synonym matches
        jd_keywords = set([k.lower() for k in (jd_data.get("ats_keywords") or [])])
        required_skills = set([s.lower() for s in (jd_data.get("required_skills") or [])])
        preferred_skills = set([s.lower() for s in (jd_data.get("preferred_skills") or [])])
        all_jd_terms = jd_keywords.union(required_skills).union(preferred_skills)

        # Match via lexical check OR semantic evidence ledger
        matched_from_ledger = set([e["term"].lower() for e in match_eval.get("evidence_ledger", [])])
        matched_keywords_set = set()
        for term in all_jd_terms:
            if self._term_exists(term, full_resume_text) or term in matched_from_ledger or self.ats_matcher.canonicalize(term) in matched_from_ledger:
                matched_keywords_set.add(term)

        matched_keywords = list(matched_keywords_set)
        missing_keywords = list(all_jd_terms - matched_keywords_set)
        keyword_match_pct = (len(matched_keywords) / len(all_jd_terms) * 100.0) if all_jd_terms else 100.0

        # 4. Mandatory Skill Match
        all_required_skills = list(required_skills)
        matched_req_skills = [
            s for s in all_required_skills
            if self._term_exists(s, full_resume_text) or s in matched_from_ledger or self.ats_matcher.canonicalize(s) in matched_from_ledger
        ]
        lexical_skill_match = (len(matched_req_skills) / len(all_required_skills) * 100.0) if all_required_skills else 100.0
        # Combine with semantic evidence-weighted score
        semantic_skill_match = match_eval.get("skills_breakdown", {}).get("match_pct", 100.0)
        skill_match_pct = max(lexical_skill_match, semantic_skill_match)

        # 5. Experience Count & Tenure Match using precision TenureMatcher
        tenure_report = match_eval.get("tenure_report") or self.tenure_matcher.match(resume_data, jd_data)
        resume_years = tenure_report["total_years"]
        duration_known = tenure_report["experience_duration_known"]
        exp_match_pct = tenure_report["tenure_score"]
        req_years = tenure_report["required_years"]

        # 6. Section Validation
        core_sections = {
            "Experience": len(resume_data.get("experience", [])) > 0,
            "Education": len(resume_data.get("education", [])) > 0,
            "Skills": len(resume_data.get("skills", [])) > 0,
            "Projects": len(resume_data.get("projects", [])) > 0
        }
        valid_sections_count = sum(1 for v in core_sections.values() if v)
        section_score = (valid_sections_count / len(core_sections)) * 100.0

        # 7. Action Verbs Check
        bullets = []
        for exp in resume_data.get("experience", []):
            bullets.extend(exp.get("bullets", []))
        for proj in resume_data.get("projects", []):
            bullets.extend(proj.get("bullets", []))
            
        action_verb_count = 0
        bullet_grammar_errors = []
        duplicate_bullets_count = 0
        seen_bullets = set()

        for b in bullets:
            b_clean = b.strip().lower()
            if not b_clean:
                continue
            
            first_word = re.sub(r'[^a-zA-Z]', '', b_clean.split()[0]) if b_clean.split() else ""
            if first_word in self.ACTION_VERBS:
                action_verb_count += 1
            
            if not b.endswith('.'):
                bullet_grammar_errors.append(f"Bullet does not end with period: '{b[:30]}...'")
                
            if b_clean in seen_bullets:
                duplicate_bullets_count += 1
            seen_bullets.add(b_clean)

        action_verb_pct = (action_verb_count / len(bullets) * 100.0) if bullets else 100.0
        
        # 8. Resume Length Check
        word_count = len(words_resume)
        length_status = "Optimal"
        if word_count < 200:
            length_status = "Too short (under 200 words)"
        elif word_count > 1000:
            length_status = "Too long (over 1000 words)"

        # 9. Overall ATS Score Calculation
        # Combines deep multi-dimensional fit score with formatting & section hygiene
        fit_score = match_eval.get("overall_fit_score", 0.0)
        ats_score = (fit_score * 0.85) + (section_score * 0.10) + (action_verb_pct * 0.05)
        
        if duplicate_bullets_count > 0:
            ats_score = max(ats_score - (duplicate_bullets_count * 2), 0.0)
        if length_status != "Optimal":
            ats_score = max(ats_score - 5, 0.0)

        ats_score = max(0.0, min(100.0, round(ats_score, 1)))

        return {
            "ats_score": ats_score,
            "overall_fit_score": match_eval.get("overall_fit_score", ats_score),
            "score_label": "Resume–JD match estimate (not an employer ATS score)",
            "experience_duration_known": duration_known,
            "resume_years": round(resume_years, 1),
            "resume_months": round(resume_years * 12),
            "required_years": float(req_years),
            "keyword_match": round(keyword_match_pct, 1),
            "skill_match": round(skill_match_pct, 1),
            "experience_match": round(exp_match_pct, 1),
            "tenure_report": tenure_report,
            "hard_eligibility": match_eval.get("hard_eligibility", {}),
            "dimension_scores": match_eval.get("dimension_scores", {}),
            "skills_breakdown": match_eval.get("skills_breakdown", {}),
            "responsibilities_breakdown": match_eval.get("responsibilities_breakdown", {}),
            "education_breakdown": match_eval.get("education_breakdown", {}),
            "domain_breakdown": match_eval.get("domain_breakdown", {}),
            "evidence_ledger": match_eval.get("evidence_ledger", []),
            "missing_information_report": match_eval.get("missing_information_report", {}),
            "match_recommendations": match_eval.get("recommendations", []),
            "missing_keywords": missing_keywords[:15],
            "matched_keywords": matched_keywords,
            "section_validation": core_sections,
            "formatting_report": {
                "length_status": length_status,
                "word_count": word_count,
                "action_verb_rate": round(action_verb_pct, 1),
                "duplicate_bullets": duplicate_bullets_count,
                "bullet_warnings": bullet_grammar_errors[:5]
            }
        }

    def _parse_date_endpoint(self, ep_str: str, is_end: bool = False) -> Optional[float]:
        """Parses a date endpoint string (e.g., 'Jan 2021', '2018', '03/2019', 'Present') to decimal years."""
        s = ep_str.strip().lower()
        now = datetime.now()
        if s in {"present", "current", "now", "ongoing"}:
            return float(now.year) + (float(now.month - 1) / 12.0)

        # Month YYYY: 'jan 2021', 'january 2021', 'sept. 2022'
        m_match = re.search(r"([a-z]+)\.?\s+(\d{4})", s)
        if m_match:
            m_name = m_match.group(1).rstrip(".")
            year = int(m_match.group(2))
            month = self.MONTHS.get(m_name, 1 if not is_end else 12)
            return float(year) + ((float(month) - (0.0 if is_end else 1.0)) / 12.0)

        # MM/YYYY or M/YYYY: '03/2019', '3/2019'
        m_slash = re.search(r"(\d{1,2})/(\d{4})", s)
        if m_slash:
            month = max(1, min(12, int(m_slash.group(1))))
            year = int(m_slash.group(2))
            return float(year) + ((float(month) - (0.0 if is_end else 1.0)) / 12.0)

        # MM/YY: '03/19' -> 2019
        m_slash2 = re.search(r"(\d{1,2})/(\d{2})\b", s)
        if m_slash2:
            month = max(1, min(12, int(m_slash2.group(1))))
            yr_short = int(m_slash2.group(2))
            year = 2000 + yr_short if yr_short < 70 else 1900 + yr_short
            return float(year) + ((float(month) - (0.0 if is_end else 1.0)) / 12.0)

        # Year alone: '2018'
        y_match = re.search(r"\b(19\d{2}|20\d{2})\b", s)
        if y_match:
            year = int(y_match.group(1))
            return float(year) + (1.0 if is_end else 0.0)

        return None

    def _extract_date_intervals(self, text: str) -> List[Tuple[float, float]]:
        """Finds all start-end date ranges within text and returns list of (start_year, end_year)."""
        intervals = []
        for m in self.DATE_RANGE_REGEX.finditer(text):
            s_val = self._parse_date_endpoint(m.group(1), is_end=False)
            e_val = self._parse_date_endpoint(m.group(2), is_end=True)
            if s_val is not None and e_val is not None and 1970 <= s_val <= 2100 and s_val <= e_val:
                intervals.append((s_val, e_val))
        return intervals

    def _merge_intervals_to_years(self, intervals: List[Tuple[float, float]]) -> float:
        """Merges overlapping date intervals to calculate continuous timeline years without double-counting."""
        if not intervals:
            return 0.0
        sorted_intervals = sorted(intervals, key=lambda x: x[0])
        merged: List[List[float]] = []
        for start, end in sorted_intervals:
            if not merged:
                merged.append([start, end])
            else:
                prev_start, prev_end = merged[-1]
                if start <= prev_end:
                    merged[-1][1] = max(prev_end, end)
                else:
                    merged.append([start, end])
        total_years = sum(end - start for start, end in merged)
        return total_years


    def _tokenize(self, text: str) -> List[str]:
        # Lowercase and split into alphanumeric words
        return re.findall(r'\b[a-z0-9\-]+\b', text.lower())

    def _term_exists(self, term: str, text: str) -> bool:
        # Standard substring or word-boundary check for multi-word or single-word phrases
        pattern = r'\b' + re.escape(term.lower()) + r'\b'
        # Handle cases like "c++" or ".net" where boundaries behave differently
        if not re.match(r'^\w', term) or not re.search(r'\w$', term):
            pattern = re.escape(term.lower())
        return bool(re.search(pattern, text.lower()))
