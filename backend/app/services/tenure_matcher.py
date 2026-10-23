import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12
}

SEASON_MAP = {
    "spring": (3, 5),    # March to May
    "summer": (6, 8),    # June to August
    "fall": (9, 11),     # September to November
    "autumn": (9, 11),   # September to November
    "winter": (12, 2)    # Dec to Feb
}

INTERNSHIP_KEYWORDS = {
    "intern", "internship", "co-op", "coop", "trainee", "traineeship",
    "fellow", "fellowship", "apprentice", "apprenticeship"
}

@dataclass
class RoleSpecificRequirement:
    target: str
    min_years: float
    max_years: Optional[float] = None
    is_preferred: bool = False
    category: str = "technology"  # "technology" or "role_title"

@dataclass
class JDExperienceRequirements:
    min_years: float = 0.0
    max_years: Optional[float] = None
    has_explicit_maximum: bool = False
    preferred_years: Optional[float] = None
    role_specific: List[RoleSpecificRequirement] = field(default_factory=list)
    raw_mentions: List[str] = field(default_factory=list)
    is_entry_level: bool = False

@dataclass
class ParsedRoleExperience:
    company: str
    role: str
    start_date_str: str
    end_date_str: str
    start_decimal: Optional[float]
    end_decimal: Optional[float]
    years: float
    is_internship: bool
    is_current: bool
    dates_missing: bool
    bullets: List[str] = field(default_factory=list)
    matched_skills: List[str] = field(default_factory=list)

@dataclass
class CandidateExperienceProfile:
    total_years: float
    full_time_years: float
    internship_years: float
    duration_known: bool
    roles: List[ParsedRoleExperience]
    merged_timeline_intervals: List[Tuple[float, float]]
    stated_years: float = 0.0

@dataclass
class TenureScoringConfig:
    min_experience_weight: float = 0.75
    preferred_experience_weight: float = 0.15
    role_specific_weight: float = 0.10
    overqualification_penalty_per_year: float = 5.0
    max_overqualification_penalty: float = 20.0
    count_internships: bool = True
    internship_credit_factor: float = 1.0  # Full credit for internships by default

class TenureMatcher:
    """
    Precision ATS Tenure & Experience Matcher.
    Extracts structured requirements from JDs, builds non-overlapping candidate employment timelines,
    and calculates deterministic, explainable tenure scores (0-100).
    """

    MONTH_REGEX_STR = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Sept|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
    SEASON_REGEX_STR = r"(?:Spring|Summer|Fall|Autumn|Winter)"
    ENDPOINT_PATTERN = rf"(?:{MONTH_REGEX_STR}\s+\d{{4}}|{SEASON_REGEX_STR}\s+\d{{4}}|\d{{1,2}}/\d{{2,4}}|\b(?:19\d{{2}}|20\d{{2}})\b)"
    END_ENDPOINT_PATTERN = rf"(?:{MONTH_REGEX_STR}\s+\d{{4}}|{SEASON_REGEX_STR}\s+\d{{4}}|\d{{1,2}}/\d{{2,4}}|\b(?:19\d{{2}}|20\d{{2}})\b|Present|Current|Now|Ongoing|To\s+Date)"
    DATE_RANGE_REGEX = re.compile(
        rf"({ENDPOINT_PATTERN})\s*(?:[–—\-]+|\bto\b|\bthrough\b|\buntil\b)\s*({END_ENDPOINT_PATTERN})",
        re.IGNORECASE
    )

    def __init__(self, config: Optional[TenureScoringConfig] = None):
        self.config = config or TenureScoringConfig()

    # ==========================================
    # 1. JD EXPERIENCE EXTRACTION
    # ==========================================

    def extract_jd_requirements(
        self,
        jd_text: Optional[str] = None,
        structured_data: Optional[Dict[str, Any]] = None
    ) -> JDExperienceRequirements:
        """
        Extracts minimum, maximum, range-based, preferred, and role-specific experience
        requirements from raw JD text and/or structured database attributes.
        """
        reqs = JDExperienceRequirements()
        text = (jd_text or "").strip()
        text_lower = text.lower()

        # Check explicit structured overrides first if passed
        if structured_data:
            for k in ("experience_years", "required_years", "min_years"):
                if structured_data.get(k) is not None:
                    try:
                        exp_val = float(structured_data[k])
                        if exp_val >= 0:
                            reqs.min_years = exp_val
                            break
                    except (ValueError, TypeError):
                        pass

        if not text:
            return reqs

        # 1. Check for entry-level / new-grad markers
        entry_level_patterns = [
            r"\b(?:entry\s*level|new\s*grad(?:uate)?|recent\s*graduate|internship|intern\s*role|no\s*prior\s*experience\s*required|0\s*years?\s*experience)\b"
        ]
        for p in entry_level_patterns:
            if re.search(p, text_lower):
                reqs.is_entry_level = True
                reqs.min_years = 0.0
                reqs.raw_mentions.append("Entry-level / no experience required")
                break

        # 2. Preferred experience patterns
        preferred_regexes = [
            r"(?:preferred|nice\s+to\s+have|ideally|is\s+a\s+plus|plus|bonus|desired)[\s\:\-]+.*?(\d+(?:\.\d+)?)\s*(?:\+)?\s*(?:years?|yrs)\b",
            r"(\d+(?:\.\d+)?)\s*(?:\+)?\s*(?:years?|yrs)\b\s*(?:of\s+experience\s*)?(?:preferred|is\s+a\s+plus|is\s+desired|recommended|ideal)"
        ]
        for pref_pat in preferred_regexes:
            for m in re.finditer(pref_pat, text_lower):
                val = float(m.group(1))
                if reqs.preferred_years is None or val > reqs.preferred_years:
                    reqs.preferred_years = val
                    reqs.raw_mentions.append(f"Preferred: {val}+ years ({m.group(0).strip()})")

        # 3. Explicit Range patterns ("3-5 years", "3 to 5 years", "between 2 and 4 years")
        range_regexes = [
            r"\bbetween\s+(\d+(?:\.\d+)?)\s+(?:and|to)\s+(\d+(?:\.\d+)?)\s*(?:years?|yrs)\b",
            r"\b(\d+(?:\.\d+)?)\s*(?:-|–|—|\bto\b)\s*(\d+(?:\.\d+)?)\s*(?:\+)?\s*(?:years?|yrs)\b"
        ]
        for r_pat in range_regexes:
            for m in re.finditer(r_pat, text_lower):
                low = float(m.group(1))
                high = float(m.group(2))
                if low < high and high <= 30:  # reasonable year bounds
                    # If this range is in a "preferred" sentence, don't overwrite hard requirements
                    context_snippet = text_lower[max(0, m.start() - 30):min(len(text_lower), m.end() + 30)]
                    if any(pw in context_snippet for pw in ["preferred", "plus", "bonus", "nice to have"]):
                        if reqs.preferred_years is None:
                            reqs.preferred_years = low
                        continue

                    reqs.min_years = low
                    reqs.max_years = high
                    reqs.has_explicit_maximum = True
                    reqs.raw_mentions.append(f"Range requirement: {low}–{high} years")
                    break
            if reqs.has_explicit_maximum:
                break

        # 4. Explicit Maximum / Cap patterns ("up to 3 years", "maximum 4 years", "no more than 3 years")
        if not reqs.has_explicit_maximum:
            max_regexes = [
                r"\b(?:maximum(?:\s+of)?|max|up\s+to|no\s+more\s+than|at\s+most|not\s+to\s+exceed)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs)\b",
                r"(?:<=|<)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs)\b"
            ]
            for m_pat in max_regexes:
                m = re.search(m_pat, text_lower)
                if m:
                    max_val = float(m.group(1))
                    reqs.max_years = max_val
                    reqs.has_explicit_maximum = True
                    reqs.raw_mentions.append(f"Explicit maximum: up to {max_val} years")
                    break

        # 5. Explicit Minimum patterns ("3+ years", "at least 3 years", "minimum 4 years")
        if reqs.min_years == 0.0 and not reqs.is_entry_level:
            min_regexes = [
                r"\b(?:at\s+least|minimum(?:\s+of)?|min|more\s+than|>)\s*(\d+(?:\.\d+)?)\s*(?:\+)?\s*(?:years?|yrs)\b",
                r"(\d+(?:\.\d+)?)\s*(?:\+)\s*(?:years?|yrs)\b",
                r"(\d+(?:\.\d+)?)\s*(?:or\s+more)\s*(?:years?|yrs)\b",
                r"(\d+(?:\.\d+)?)\s*(?:years?|yrs)\b(?:\s+of\s+experience|\s+experience|\s+background)"
            ]
            for min_pat in min_regexes:
                for m in re.finditer(min_pat, text_lower):
                    context_snippet = text_lower[max(0, m.start() - 30):min(len(text_lower), m.end() + 30)]
                    if any(pw in context_snippet for pw in ["preferred", "plus", "bonus", "nice to have"]):
                        continue
                    val = float(m.group(1))
                    if 0.5 <= val <= 30:
                        reqs.min_years = val
                        reqs.raw_mentions.append(f"Minimum required: {val}+ years")
                        break
                if reqs.min_years > 0.0:
                    break

        # Fallback if text has standard "X years" and nothing was detected
        if reqs.min_years == 0.0 and not reqs.is_entry_level:
            general_match = re.findall(r"(\d+(?:\.\d+)?)\s*(?:\+)?\s*(?:years?|yrs)", text_lower)
            if general_match:
                reqs.min_years = float(general_match[0])
                reqs.raw_mentions.append(f"Stated requirement: {reqs.min_years} years")

        # 6. Role-specific & Technology-specific requirements
        # e.g., "3+ years of experience with Python", "2+ years in React"
        role_spec_patterns = [
            r"(\d+(?:\.\d+)?)\s*(?:\+)?\s*(?:years?|yrs)\b(?:\s+of\s+experience)?\s+(?:in|with|using|working\s+with|as\s+a|as\s+an)\s+([A-Za-z0-9\+\#\.\s\/\-]{2,30}?)(?:[\.,;\n]|\band\b|$)",
            r"(?:in|with|using|working\s+with)\s+([A-Za-z0-9\+\#\.\-]{2,25})\s*[\:\-]?\s*(\d+(?:\.\d+)?)\s*(?:\+)?\s*(?:years?|yrs)\b"
        ]
        seen_targets = set()

        for m in re.finditer(role_spec_patterns[0], text, re.IGNORECASE):
            yrs = float(m.group(1))
            tgt = m.group(2).strip().strip(".,;:").lower()
            # Clean common filler words
            tgt_clean = re.sub(r"^(?:hands-on|proven|demonstrated|solid|deep|extensive)\s+", "", tgt).strip()
            if tgt_clean and len(tgt_clean) >= 2 and tgt_clean not in seen_targets and tgt_clean not in {"experience", "work", "software"}:
                seen_targets.add(tgt_clean)
                is_pref = "prefer" in m.group(0).lower() or "plus" in m.group(0).lower()
                reqs.role_specific.append(RoleSpecificRequirement(
                    target=tgt_clean,
                    min_years=yrs,
                    is_preferred=is_pref,
                    category="role_or_tech"
                ))

        for m in re.finditer(role_spec_patterns[1], text, re.IGNORECASE):
            tgt = m.group(1).strip().strip(".,;:").lower()
            yrs = float(m.group(2))
            if tgt and len(tgt) >= 2 and tgt not in seen_targets and tgt not in {"experience", "work"}:
                seen_targets.add(tgt)
                is_pref = "prefer" in m.group(0).lower() or "plus" in m.group(0).lower()
                reqs.role_specific.append(RoleSpecificRequirement(
                    target=tgt,
                    min_years=yrs,
                    is_preferred=is_pref,
                    category="role_or_tech"
                ))

        return reqs

    # ==========================================
    # 2. CANDIDATE EXPERIENCE EXTRACTION
    # ==========================================

    def parse_date_endpoint(self, ep_str: str, is_end: bool = False) -> Optional[float]:
        """
        Parses a date endpoint string to decimal years.
        Supports Month-Year, Season-Year, Slash formats, Year-only, and Ongoing markers.
        """
        if not ep_str or not isinstance(ep_str, str):
            return None
        s = ep_str.strip().lower()
        now = datetime.now()

        # Ongoing / Current
        if s in {"present", "current", "now", "ongoing", "to date"}:
            return float(now.year) + (float(now.month - 1) / 12.0 if not is_end else float(now.month) / 12.0)

        # Seasons: "Summer 2022", "Spring 2021"
        season_match = re.search(r"\b(spring|summer|fall|autumn|winter)\s+(\d{4})\b", s)
        if season_match:
            season = season_match.group(1)
            year = int(season_match.group(2))
            start_m, end_m = SEASON_MAP[season]
            if not is_end:
                return float(year) + (float(start_m - 1) / 12.0)
            else:
                return float(year) + (float(end_m) / 12.0)

        # Month YYYY: 'jan 2021', 'january 2021', 'sept. 2022'
        m_match = re.search(r"([a-z]+)\.?\s+(\d{4})", s)
        if m_match:
            m_name = m_match.group(1).rstrip(".")
            year = int(m_match.group(2))
            month = MONTH_MAP.get(m_name, 1 if not is_end else 12)
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
        # Convention: start is 2018.0 (Jan 1), end is 2019.0 (Dec 31 inclusive)
        y_match = re.search(r"\b(19\d{2}|20\d{2})\b", s)
        if y_match:
            year = int(y_match.group(1))
            return float(year) + (1.0 if is_end else 0.0)

        return None

    def extract_date_intervals(self, text: str) -> List[Tuple[float, float, str, str]]:
        """
        Finds all start-end date ranges within text and returns list of
        (start_year, end_year, raw_start, raw_end).
        """
        intervals = []
        if not text or not isinstance(text, str):
            return intervals

        for m in self.DATE_RANGE_REGEX.finditer(text):
            raw_s = m.group(1)
            raw_e = m.group(2)
            s_val = self.parse_date_endpoint(raw_s, is_end=False)
            e_val = self.parse_date_endpoint(raw_e, is_end=True)
            if s_val is not None and e_val is not None and 1970 <= s_val <= 2100 and s_val <= e_val:
                intervals.append((s_val, e_val, raw_s, raw_e))
        return intervals

    def merge_intervals(self, intervals: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        Merges overlapping or contiguous date intervals to prevent double-counting.
        """
        if not intervals:
            return []
        sorted_intervals = sorted(intervals, key=lambda x: (x[0], x[1]))
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
        return [(s, e) for s, e in merged]

    def calculate_merged_years(self, intervals: List[Tuple[float, float]]) -> float:
        """Calculates total continuous years across intervals with zero overlap."""
        merged = self.merge_intervals(intervals)
        return sum(end - start for start, end in merged)

    def extract_candidate_profile(
        self,
        resume_data: Dict[str, Any]
    ) -> CandidateExperienceProfile:
        """
        Parses candidate experience, roles, internships, and builds non-overlapping timelines.
        """
        parsed_roles: List[ParsedRoleExperience] = []
        all_intervals: List[Tuple[float, float]] = []
        ft_intervals: List[Tuple[float, float]] = []
        intern_intervals: List[Tuple[float, float]] = []

        # 1. Stated years extraction from summary (explicit career tenure)
        summary_text = str(resume_data.get("profile_summary", "") or "").lower()
        stated_years = 0.0
        # Check explicit experience claims like "5+ years of experience", "4 years experience"
        summary_matches = re.findall(
            r"\b(\d+(?:\.\d+)?)\s*(?:\+)?\s*(?:years?|yrs)\b(?:\s+of)?\s+(?:professional\s+|relevant\s+|work\s+|industry\s+|hands-on\s+)?experience",
            summary_text
        )
        if summary_matches:
            stated_years = max([float(y) for y in summary_matches if float(y) <= 40])
        elif summary_text:
            short_matches = re.findall(r"\b(\d+(?:\.\d+)?)\s*(?:\+)?\s*(?:years?|yrs)\b", summary_text)
            if short_matches:
                stated_years = max([float(y) for y in short_matches if float(y) <= 40])

        # 2. Iterate each experience entry
        for exp in resume_data.get("experience", []):
            comp = exp.get("company", "")
            role_title = exp.get("role", "")
            bullets = exp.get("bullets", [])

            # Check internship status
            comb_title = f"{comp} {role_title}".lower()
            is_intern = any(re.search(rf"\b{kw}\b", comb_title) for kw in INTERNSHIP_KEYWORDS)

            # Extract date ranges
            role_intervals: List[Tuple[float, float, str, str]] = []

            for date_key in ("dates", "duration", "date_range"):
                val = exp.get(date_key)
                if val and isinstance(val, str):
                    role_intervals.extend(self.extract_date_intervals(val))

            for header_key in ("company", "role"):
                val = exp.get(header_key)
                if val and isinstance(val, str):
                    role_intervals.extend(self.extract_date_intervals(val))

            # Explicit start_date / end_date
            if exp.get("start_date"):
                s_ep = self.parse_date_endpoint(str(exp["start_date"]), is_end=False)
                e_ep = self.parse_date_endpoint(str(exp.get("end_date", "Present")), is_end=True)
                if s_ep is not None and e_ep is not None and s_ep <= e_ep:
                    role_intervals.append((s_ep, e_ep, str(exp["start_date"]), str(exp.get("end_date", "Present"))))

            # Check bullets if still no dates found
            if not role_intervals:
                for b in bullets:
                    if isinstance(b, str) and len(b) > 4:
                        role_intervals.extend(self.extract_date_intervals(b))

            if role_intervals:
                # Use earliest start and latest end for this specific role
                s_val = min(r[0] for r in role_intervals)
                e_val = max(r[1] for r in role_intervals)
                raw_s = role_intervals[0][2]
                raw_e = role_intervals[0][3]
                role_yrs = max(0.0, e_val - s_val)
                is_curr = any(r[3].strip().lower() in {"present", "current", "now", "ongoing", "to date"} for r in role_intervals)

                parsed_role = ParsedRoleExperience(
                    company=comp,
                    role=role_title,
                    start_date_str=raw_s,
                    end_date_str=raw_e,
                    start_decimal=s_val,
                    end_decimal=e_val,
                    years=role_yrs,
                    is_internship=is_intern,
                    is_current=is_curr,
                    dates_missing=False,
                    bullets=bullets
                )
                parsed_roles.append(parsed_role)
                all_intervals.append((s_val, e_val))
                if is_intern:
                    intern_intervals.append((s_val, e_val))
                else:
                    ft_intervals.append((s_val, e_val))
            else:
                # Role has no verifiable dates
                parsed_roles.append(ParsedRoleExperience(
                    company=comp,
                    role=role_title,
                    start_date_str="",
                    end_date_str="",
                    start_decimal=None,
                    end_decimal=None,
                    years=0.0,
                    is_internship=is_intern,
                    is_current=False,
                    dates_missing=True,
                    bullets=bullets
                ))

        timeline_years = self.calculate_merged_years(all_intervals)
        full_time_years = self.calculate_merged_years(ft_intervals)
        internship_years = self.calculate_merged_years(intern_intervals)

        total_years = max(stated_years, timeline_years)
        duration_known = bool(all_intervals) or (stated_years > 0.0)

        merged_timeline = self.merge_intervals(all_intervals)

        return CandidateExperienceProfile(
            total_years=round(total_years, 2),
            full_time_years=round(full_time_years, 2),
            internship_years=round(internship_years, 2),
            duration_known=duration_known,
            roles=parsed_roles,
            merged_timeline_intervals=merged_timeline,
            stated_years=stated_years
        )

    # ==========================================
    # 3. DETERMINISTIC TENURE SCORER
    # ==========================================

    def calculate_tenure_score(
        self,
        candidate_profile: CandidateExperienceProfile,
        jd_reqs: JDExperienceRequirements,
        config: Optional[TenureScoringConfig] = None
    ) -> Dict[str, Any]:
        """
        Calculates a deterministic 0–100 tenure match score with explainable penalties and evidence.
        Distinguishes hard eligibility criteria from scoring preferences.
        NEVER penalizes candidates for exceeding minimum experience unless an explicit maximum applies.
        """
        cfg = config or self.config
        penalties: List[Dict[str, Any]] = []
        evidence: List[Dict[str, Any]] = []
        recommendations: List[str] = []

        total_candidate_years = candidate_profile.total_years
        min_years = jd_reqs.min_years
        max_years = jd_reqs.max_years
        has_explicit_max = jd_reqs.has_explicit_maximum
        preferred_years = jd_reqs.preferred_years

        # ----------------------------------------------------
        # CASE A: Missing dates / Unverifiable tenure
        # ----------------------------------------------------
        if not candidate_profile.duration_known:
            penalties.append({
                "code": "MISSING_DATES",
                "points": 100.0,
                "reason": "No verifiable employment dates or tenure found in experience section."
            })
            recommendations.append("Add clear employment date ranges (e.g., 'Jan 2021 – Present' or '2019 – 2023') to each role.")
            return {
                "tenure_score": 0.0,
                "is_eligible": False,
                "eligibility_status": "unverifiable",
                "experience_duration_known": False,
                "candidate_years": 0.0,
                "total_years": 0.0,
                "full_time_years": 0.0,
                "internship_years": 0.0,
                "required_years": min_years,
                "max_years": max_years,
                "has_explicit_maximum": has_explicit_max,
                "preferred_years": preferred_years,
                "penalties": penalties,
                "evidence": evidence,
                "scoring_breakdown": {
                    "base_eligibility_score": 0.0,
                    "preferred_score": 0.0,
                    "role_specific_score": 0.0,
                    "overqualification_penalty": 0.0,
                    "final_score": 0.0
                },
                "recommendations": recommendations,
                "timeline_intervals": []
            }

        # ----------------------------------------------------
        # CASE B: No experience required (Entry-level / zero req)
        # ----------------------------------------------------
        if min_years == 0.0 and not has_explicit_max and not preferred_years and not jd_reqs.role_specific:
            evidence.append({
                "type": "ENTRY_LEVEL_ELIGIBLE",
                "credit": 100.0,
                "reason": "Position has no minimum experience requirement; full tenure credit awarded."
            })
            return {
                "tenure_score": 100.0,
                "is_eligible": True,
                "eligibility_status": "meets_requirements",
                "experience_duration_known": True,
                "candidate_years": total_candidate_years,
                "total_years": total_candidate_years,
                "full_time_years": candidate_profile.full_time_years,
                "internship_years": candidate_profile.internship_years,
                "required_years": 0.0,
                "max_years": max_years,
                "has_explicit_maximum": False,
                "preferred_years": None,
                "penalties": [],
                "evidence": evidence,
                "scoring_breakdown": {
                    "base_eligibility_score": 100.0,
                    "preferred_score": 0.0,
                    "role_specific_score": 0.0,
                    "overqualification_penalty": 0.0,
                    "final_score": 100.0
                },
                "recommendations": [],
                "timeline_intervals": [
                    {"start": round(s, 2), "end": round(e, 2), "years": round(e - s, 2)}
                    for s, e in candidate_profile.merged_timeline_intervals
                ]
            }

        # ----------------------------------------------------
        # DYNAMIC WEIGHT ALLOCATION
        # Distinguish Hard Eligibility from Preferences
        # ----------------------------------------------------
        has_preferred = preferred_years is not None and preferred_years > min_years
        has_role_specific = bool(jd_reqs.role_specific)

        # Allocate weights dynamically so components sum to 100.0
        w_min = 1.0
        w_pref = 0.0
        w_role = 0.0

        if has_preferred and has_role_specific:
            w_min = 0.70
            w_pref = 0.15
            w_role = 0.15
        elif has_preferred:
            w_min = 0.80
            w_pref = 0.20
        elif has_role_specific:
            w_min = 0.80
            w_role = 0.20

        base_max_points = 100.0 * w_min

        # ----------------------------------------------------
        # ----------------------------------------------------
        # HARD MINIMUM ELIGIBILITY (BINARY 100% OR 0%)
        # Rule: If JD has a YOE requirement and resume has lesser YOE, allocate 0%
        # (strictly 0%, not 30% or 50%). It should be either 100% or 0%.
        # ----------------------------------------------------
        if min_years > 0.0 and total_candidate_years < min_years:
            penalties.append({
                "code": "TENURE_DEFICIT",
                "points": 100.0,
                "reason": (
                    f"Tenure deficit: candidate has {total_candidate_years} yrs vs {min_years} yrs required. "
                    "Position minimum experience not met (allocated 0%)."
                )
            })
            recommendations.append(
                f"Position requires at least {min_years} years of experience (detected {total_candidate_years} yrs). "
                "Highlight earlier roles, contract work, or additional relevant projects."
            )
            return {
                "tenure_score": 0.0,
                "is_eligible": False,
                "eligibility_status": "below_minimum",
                "experience_duration_known": True,
                "candidate_years": total_candidate_years,
                "total_years": total_candidate_years,
                "full_time_years": candidate_profile.full_time_years,
                "internship_years": candidate_profile.internship_years,
                "required_years": min_years,
                "max_years": max_years,
                "has_explicit_maximum": has_explicit_max,
                "preferred_years": preferred_years,
                "penalties": penalties,
                "evidence": evidence,
                "scoring_breakdown": {
                    "base_eligibility_score": 0.0,
                    "preferred_score": 0.0,
                    "role_specific_score": 0.0,
                    "overqualification_penalty": 0.0,
                    "final_score": 0.0
                },
                "recommendations": recommendations,
                "timeline_intervals": [
                    {"start": round(s, 2), "end": round(e, 2), "years": round(e - s, 2)}
                    for s, e in candidate_profile.merged_timeline_intervals
                ]
            }

        # Candidate meets or exceeds minimum requirement (Base 100% eligibility)
        base_score = 100.0
        is_eligible = True
        evidence.append({
            "type": "MIN_TENURE_MET",
            "credit": 100.0,
            "reason": (
                f"Candidate tenure ({total_candidate_years} yrs) meets or exceeds minimum requirement "
                f"({min_years} yrs). Full eligibility credit awarded."
            )
        })

        # ----------------------------------------------------
        # COMPONENT 2: PREFERRED EXPERIENCE BONUS
        # ----------------------------------------------------
        if has_preferred and preferred_years:
            if total_candidate_years >= preferred_years:
                evidence.append({
                    "type": "PREFERRED_TENURE_MET",
                    "credit": 0.0,
                    "reason": f"Candidate satisfies preferred experience target ({total_candidate_years} yrs >= {preferred_years} yrs)."
                })
            elif total_candidate_years > min_years:
                evidence.append({
                    "type": "PREFERRED_TENURE_PARTIAL",
                    "credit": 0.0,
                    "reason": (
                        f"Partial progress toward preferred experience target "
                        f"({total_candidate_years} yrs of {preferred_years} preferred yrs)."
                    )
                })

        # ----------------------------------------------------
        # COMPONENT 3: ROLE-SPECIFIC / TECH-SPECIFIC EXPERIENCE
        # ----------------------------------------------------
        role_spec_penalty = 0.0
        if has_role_specific:
            penalty_per_target = 20.0 / len(jd_reqs.role_specific)

            for req in jd_reqs.role_specific:
                # Find candidate roles containing this skill/role
                target_intervals: List[Tuple[float, float]] = []
                target_lower = req.target.lower()

                for role in candidate_profile.roles:
                    if role.start_decimal is not None and role.end_decimal is not None:
                        combined_role_text = f"{role.company} {role.role} {' '.join(role.bullets)}".lower()
                        if target_lower in combined_role_text:
                            target_intervals.append((role.start_decimal, role.end_decimal))

                target_years = self.calculate_merged_years(target_intervals)

                if target_years >= req.min_years:
                    evidence.append({
                        "type": "ROLE_SPECIFIC_MET",
                        "credit": round(penalty_per_target, 1),
                        "reason": f"Meets role requirement for '{req.target}': {round(target_years, 1)} yrs (required {req.min_years} yrs)."
                    })
                elif target_years > 0.0:
                    fraction = 1.0 - (target_years / req.min_years)
                    pts = penalty_per_target * fraction
                    role_spec_penalty += pts
                    penalties.append({
                        "code": "ROLE_SPECIFIC_DEFICIT",
                        "points": round(pts, 1),
                        "reason": f"Partial tenure in '{req.target}': {round(target_years, 1)} yrs vs {req.min_years} yrs required (-{round(pts, 1)} pts)."
                    })
                else:
                    role_spec_penalty += penalty_per_target
                    penalties.append({
                        "code": "ROLE_SPECIFIC_MISSING",
                        "points": round(penalty_per_target, 1),
                        "reason": f"No explicit employment tenure detected for required domain '{req.target}' ({req.min_years} yrs needed) (-{round(penalty_per_target, 1)} pts)."
                    })
                    recommendations.append(f"Add bullets explicitly demonstrating experience with {req.target}.")

        # ----------------------------------------------------
        # COMPONENT 4: EXPLICIT MAXIMUM (OVERQUALIFICATION) PENALTY
        # Apply ONLY IF explicit maximum applies
        # ----------------------------------------------------
        overqual_penalty = 0.0
        eligibility_status = "meets_requirements" if is_eligible else "below_minimum"

        if has_explicit_max and max_years is not None:
            if total_candidate_years > max_years:
                excess_years = total_candidate_years - max_years
                overqual_penalty = min(
                    excess_years * cfg.overqualification_penalty_per_year,
                    cfg.max_overqualification_penalty
                )
                penalties.append({
                    "code": "OVERQUALIFICATION_EXPLICIT_MAX",
                    "points": round(overqual_penalty, 1),
                    "reason": (
                        f"Candidate experience ({total_candidate_years} yrs) exceeds explicit position maximum "
                        f"({max_years} yrs) by {round(excess_years, 1)} yrs (-{round(overqual_penalty, 1)} pts)."
                    )
                })
                eligibility_status = "exceeds_maximum"
                recommendations.append(
                    f"Position explicitly seeks up to {max_years} years. Emphasize hands-on execution rather than senior management."
                )
            else:
                evidence.append({
                    "type": "WITHIN_MAX_CAP",
                    "credit": 0.0,
                    "reason": f"Candidate tenure ({total_candidate_years} yrs) is within explicit maximum bracket (<= {max_years} yrs)."
                })

        # Calculate final score: 100% base minus overqualification and domain deficit
        raw_final = base_score - role_spec_penalty - overqual_penalty
        final_score = max(0.0, min(100.0, round(raw_final, 1)))

        # Format timeline intervals for output
        timeline_report = [
            {
                "start": round(s, 2),
                "end": round(e, 2),
                "years": round(e - s, 2)
            }
            for s, e in candidate_profile.merged_timeline_intervals
        ]

        return {
            "tenure_score": final_score,
            "is_eligible": is_eligible,
            "eligibility_status": eligibility_status,
            "experience_duration_known": True,
            "candidate_years": total_candidate_years,
            "total_years": total_candidate_years,
            "full_time_years": candidate_profile.full_time_years,
            "internship_years": candidate_profile.internship_years,
            "required_years": min_years,
            "max_years": max_years,
            "has_explicit_maximum": has_explicit_max,
            "preferred_years": preferred_years,
            "penalties": penalties,
            "evidence": evidence,
            "scoring_breakdown": {
                "base_eligibility_score": round(base_score, 1),
                "preferred_score": 0.0,
                "role_specific_score": round(max(0.0, 20.0 - role_spec_penalty), 1),
                "overqualification_penalty": round(overqual_penalty, 1),
                "final_score": final_score
            },
            "recommendations": recommendations,
            "timeline_intervals": timeline_report
        }

    # ==========================================
    # 4. END-TO-END MATCH HELPER
    # ==========================================

    def match(
        self,
        resume_data: Dict[str, Any],
        jd_data: Dict[str, Any],
        config: Optional[TenureScoringConfig] = None
    ) -> Dict[str, Any]:
        """
        Runs complete tenure matching between resume and job description.
        """
        jd_text = jd_data.get("raw_text") or jd_data.get("jd_text") or ""
        jd_reqs = self.extract_jd_requirements(jd_text=jd_text, structured_data=jd_data)

        # Allow structured override if experience_years was explicitly provided
        for k in ("experience_years", "required_years", "min_years"):
            if jd_data.get(k) is not None:
                try:
                    exp_flt = float(jd_data[k])
                    if exp_flt > 0 and jd_reqs.min_years == 0.0:
                        jd_reqs.min_years = exp_flt
                        break
                except (ValueError, TypeError):
                    pass

        candidate_profile = self.extract_candidate_profile(resume_data)
        return self.calculate_tenure_score(candidate_profile, jd_reqs, config)
