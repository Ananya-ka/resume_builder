"""Intelligent Job Description Parsing and Requirement Extraction.

Extracts structured requirements with verbatim source quotes, exact start/end offsets,
mandatory vs preferred qualification gating, ambiguity detection, and skill-duty dependencies.
"""
import re
import json
import hashlib
import logging
from typing import Dict, Any, List, Tuple, Optional
from openai import OpenAI
from app.core.config import settings
from app.services.ats_matcher import CANONICAL_SYNONYMS, _ALIAS_TO_CANONICAL, DEGREE_LEVELS, INDUSTRY_DOMAINS

logger = logging.getLogger(__name__)

AMBIGUOUS_PATTERNS = [
    (r"\b(fast[- ]learner|quick learner|self[- ]starter)\b", "Subjective soft trait without measurable criteria"),
    (r"\b(strong|good|excellent)\s+(communication|interpersonal|teamwork)\b", "Subjective interpersonal expectation; verify during interview, not factual vetting"),
    (r"\b(modern\s+(?:[\w-]+\s+)*(?:tech\s+stack|technologies|tools)|cutting[- ]edge)\b", "Vague technological scope; specific tools should be confirmed"),
    (r"\b(familiarity\s+with\s+(?:[\w-]+\s+)*(?:ai|cloud|data|systems|tools|workflows|llm))\b", "Ambiguous depth; unclear if production experience or high-level familiarity is expected"),
    (r"\b(big\s+data|deep\s+knowledge)\b", "Unquantified scale or expertise standard"),
]


def locate_quote(raw_text: str, quote: str) -> Tuple[Optional[int], Optional[int], str]:
    """Finds verbatim or whitespace-normalized quote inside raw_text with character offsets."""
    if not quote or not quote.strip():
        return None, None, quote
    clean_quote = quote.strip()
    idx = raw_text.find(clean_quote)
    if idx != -1:
        return idx, idx + len(clean_quote), clean_quote

    # Whitespace-tolerant search
    pattern = r"\s+".join(re.escape(w) for w in clean_quote.split())
    match = re.search(pattern, raw_text, re.IGNORECASE)
    if match:
        return match.start(), match.end(), match.group()

    # Search for first sentence / subsegment if composite
    for segment in clean_quote.split("\n"):
        seg = segment.strip().rstrip(".,;")
        if len(seg) > 15:
            m = re.search(r"\s+".join(re.escape(w) for w in seg.split()), raw_text, re.IGNORECASE)
            if m:
                return m.start(), m.end(), m.group()

    return None, None, clean_quote


def canonicalize_skill(term: str) -> str:
    """Resolves technical abbreviations or synonyms to their canonical index."""
    cleaned = term.strip().lower()
    return _ALIAS_TO_CANONICAL.get(cleaned, cleaned)


def check_ambiguity(text: str) -> Tuple[bool, Optional[str]]:
    """Identifies ambiguous or subjective qualification phrases."""
    for pattern, reason in AMBIGUOUS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True, reason
    return False, None


class IntelligentJDParser:
    """Parses raw job descriptions into structured, source-quoted requirements."""

    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=90.0, max_retries=2) if settings.OPENAI_API_KEY else None

    def parse(self, raw_text: str, role_hint: str = "", company_hint: str = "") -> Dict[str, Any]:
        """Orchestrates parsing: attempts LLM extraction with deterministic validation and fallback."""
        if self.client:
            try:
                llm_res = self._llm_extract(raw_text, role_hint, company_hint)
                validated = self._validate_and_anchor(llm_res, raw_text)
                if validated["requirements"]:
                    return validated
            except Exception as e:
                logger.warning("LLM JD extraction failed or incomplete, using deterministic engine: %s", e)

        # Deterministic rule-based extraction
        return self._deterministic_extract(raw_text, role_hint, company_hint)

    def _llm_extract(self, raw_text: str, role_hint: str, company_hint: str) -> Dict[str, Any]:
        prompt = f"""
        You are a principal hiring engineer and rigorous parser. Analyze this job description.
        Every extracted item MUST include an exact 'quote' matching text in the job description. Do not paraphrase.
        
        Extract:
        1. mandatory_skills: explicitly required technical skills/tools
        2. preferred_skills: bonus/plus/preferred qualifications
        3. responsibilities: core duties, day-to-day engineering tasks
        4. education: degree level and field (is_mandatory: bool)
        5. experience: required years of experience, min_years, max_years
        6. seniority: Junior, Mid, Senior, Lead, Staff, Principal
        7. domain: business/tech domain (Fintech, Health, etc.)
        8. constraints: location, work authorization, clearance
        
        Strict JSON schema:
        {{
            "role": "string",
            "company": "string",
            "experience_years": float or null,
            "seniority": "string or null",
            "domain": "string or null",
            "requirements": [
                {{
                    "category": "mandatory_skill" | "preferred_skill" | "responsibility" | "education" | "experience" | "domain" | "constraint",
                    "title": "Clean concise title",
                    "quote": "EXACT verbatim quote from text",
                    "is_mandatory": boolean,
                    "importance": "critical" | "high" | "medium" | "preferred",
                    "normalized_terms": ["canonical_term"],
                    "dependencies": ["related responsibility or tool if linked in text"]
                }}
            ]
        }}
        
        RAW TEXT:
        {raw_text[:12000]}
        """
        response = self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a precise JSON extractor. Output ONLY valid JSON where every quote is verbatim from the source."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        return json.loads(response.choices[0].message.content)

    def _validate_and_anchor(self, extracted: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
        """Validates quotes against raw_text, locates character offsets, and checks ambiguity."""
        anchored_reqs = []
        seen_keys = set()

        for item in extracted.get("requirements", []):
            quote = item.get("quote", "").strip()
            title = item.get("title", "").strip()
            if not title or not quote:
                continue

            start, end, real_quote = locate_quote(raw_text, quote)
            if start is None:
                # If LLM quote drifted, attempt to find title in raw text
                start, end, real_quote = locate_quote(raw_text, title)
                if start is None:
                    continue

            category = item.get("category", "mandatory_skill")
            is_mand = item.get("is_mandatory", category not in {"preferred_skill"})
            terms = [canonicalize_skill(t) for t in item.get("normalized_terms", []) if t.strip()]
            if not terms and category in {"mandatory_skill", "preferred_skill"}:
                terms = [canonicalize_skill(title)]

            req_key = hashlib.sha256(f"{category}:{title.lower()}".encode()).hexdigest()[:16]
            if req_key in seen_keys:
                continue
            seen_keys.add(req_key)

            ambig, reason = check_ambiguity(quote + " " + title)

            anchored_reqs.append({
                "requirement_key": req_key,
                "category": category,
                "title": title,
                "quote": real_quote,
                "start_offset": start,
                "end_offset": end,
                "is_mandatory": is_mand,
                "importance": item.get("importance", "high" if is_mand else "preferred"),
                "normalized_terms": terms,
                "dependencies": item.get("dependencies", []),
                "is_ambiguous": ambig,
                "ambiguity_reason": reason
            })

        return {
            "role": extracted.get("role") or "",
            "company": extracted.get("company") or "",
            "experience_years": extracted.get("experience_years"),
            "seniority": extracted.get("seniority"),
            "domain": extracted.get("domain"),
            "requirements": anchored_reqs
        }

    def _deterministic_extract(self, raw_text: str, role_hint: str = "", company_hint: str = "") -> Dict[str, Any]:
        """Robust deterministic rule-based parser that guarantees source-grounded quotes."""
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        text_lower = raw_text.lower()
        requirements = []
        seen_keys = set()

        # 1. Experience Years extraction
        exp_years = None
        yoe_match = re.search(r"(\d+(?:\.\d+)?)\+?\s*(?:to\s*(\d+))?\s*(?:years|yrs)(?:\s+of)?(?:\s+experience|\s+work)?", raw_text, re.IGNORECASE)
        if yoe_match:
            try:
                exp_years = float(yoe_match.group(1))
            except ValueError:
                exp_years = None
            start, end, quote = locate_quote(raw_text, yoe_match.group(0))
            req_key = "req_exp_years"
            requirements.append({
                "requirement_key": req_key,
                "category": "experience",
                "title": f"Minimum {exp_years}+ years experience",
                "quote": quote,
                "start_offset": start,
                "end_offset": end,
                "is_mandatory": True,
                "importance": "critical",
                "normalized_terms": [f"{exp_years}_yoe"],
                "dependencies": [],
                "is_ambiguous": False,
                "ambiguity_reason": None
            })
            seen_keys.add(req_key)

        # 2. Education extraction
        for deg_name, level in sorted(DEGREE_LEVELS.items(), key=lambda x: -x[1]):
            pattern = rf"\b{re.escape(deg_name)}\b(?:\s+(?:degree|in\s+[\w\s]+))?"
            deg_match = re.search(pattern, raw_text, re.IGNORECASE)
            if deg_match:
                start, end, quote = locate_quote(raw_text, deg_match.group(0))
                # Check surrounding context for preferred / required
                surrounding = raw_text[max(0, (start or 0) - 50):min(len(raw_text), (end or 0) + 50)].lower()
                is_pref = bool(re.search(r"\b(preferred|plus|bonus|nice to have)\b", surrounding))
                req_key = f"req_edu_{deg_name.replace(' ', '_')}"
                if req_key not in seen_keys:
                    seen_keys.add(req_key)
                    requirements.append({
                        "requirement_key": req_key,
                        "category": "education",
                        "title": f"{deg_name.capitalize()} degree",
                        "quote": quote,
                        "start_offset": start,
                        "end_offset": end,
                        "is_mandatory": not is_pref,
                        "importance": "medium" if is_pref else "high",
                        "normalized_terms": [deg_name],
                        "dependencies": [],
                        "is_ambiguous": False,
                        "ambiguity_reason": None
                    })
                break

        # 3. Section-Aware Extraction (Responsibilities vs Requirements vs Preferred)
        current_section = "general"
        for line in lines:
            line_clean = line.lstrip("•-*# ").strip()
            line_lower = line.lower()

            # Section header detection
            if re.search(r"\b(responsibilities|what you('ll| will) do|duties|the role)\b", line_lower):
                current_section = "responsibilities"
                continue
            elif re.search(r"\b(preferred|nice to have|bonus|plus qualifications)\b", line_lower):
                current_section = "preferred"
                continue
            elif re.search(r"\b(requirements|qualifications|what you('ll| will) bring|must have)\b", line_lower):
                current_section = "mandatory"
                continue

            if len(line_clean) < 8 or len(line_clean) > 300:
                continue

            # Responsibilities
            if current_section == "responsibilities" or (line.startswith(("-", "•", "*")) and any(v in line_lower for v in ["architect", "build", "design", "develop", "lead", "manage", "collaborate", "deliver"])):
                start, end, quote = locate_quote(raw_text, line_clean)
                req_key = hashlib.sha256(f"resp:{line_clean.lower()}".encode()).hexdigest()[:16]
                if req_key not in seen_keys:
                    seen_keys.add(req_key)
                    # Find any technology mentioned in this responsibility to establish dependencies
                    linked_tech = [canonicalize_skill(t) for t in _ALIAS_TO_CANONICAL if re.search(rf"\b{re.escape(t)}\b", line_lower)]
                    ambig, reason = check_ambiguity(line_clean)
                    requirements.append({
                        "requirement_key": req_key,
                        "category": "responsibility",
                        "title": line_clean[:80] + ("..." if len(line_clean) > 80 else ""),
                        "quote": quote,
                        "start_offset": start,
                        "end_offset": end,
                        "is_mandatory": True,
                        "importance": "high",
                        "normalized_terms": [],
                        "dependencies": linked_tech,
                        "is_ambiguous": ambig,
                        "ambiguity_reason": reason
                    })

        # 4. Canonical Technology / Skills Scanning across entire text
        for term, canonical in _ALIAS_TO_CANONICAL.items():
            if len(term) < 2 or term in {"c", "r", "go", "it"}:  # Protect short tokens with strict word boundary
                pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
            else:
                pattern = rf"\b{re.escape(term)}\b"

            m = re.search(pattern, raw_text, re.IGNORECASE)
            if m:
                start, end, quote = locate_quote(raw_text, m.group(0))
                surrounding = raw_text[max(0, (start or 0) - 80):min(len(raw_text), (end or 0) + 80)].lower()
                is_preferred = bool(re.search(r"\b(preferred|plus|bonus|nice to have|optional)\b", surrounding))
                category = "preferred_skill" if is_preferred else "mandatory_skill"
                req_key = f"skill_{canonical}"

                if req_key not in seen_keys:
                    seen_keys.add(req_key)
                    # Extract surrounding sentence as quote context if available
                    sentence_m = re.search(rf"([^.\n;]*{re.escape(m.group(0))}[^.\n;]*)", raw_text, re.IGNORECASE)
                    ctx_quote = sentence_m.group(1).strip() if sentence_m else quote
                    s_idx, e_idx, final_quote = locate_quote(raw_text, ctx_quote)

                    # Look for responsibilities mentioning this skill
                    linked_duties = [r["title"] for r in requirements if r["category"] == "responsibility" and canonical in r["normalized_terms"]]

                    ambig, reason = check_ambiguity(final_quote or quote)
                    requirements.append({
                        "requirement_key": req_key,
                        "category": category,
                        "title": canonical.replace("_", " ").title(),
                        "quote": final_quote or quote,
                        "start_offset": s_idx if s_idx is not None else start,
                        "end_offset": e_idx if e_idx is not None else end,
                        "is_mandatory": not is_preferred,
                        "importance": "preferred" if is_preferred else "high",
                        "normalized_terms": [canonical],
                        "dependencies": linked_duties,
                        "is_ambiguous": ambig,
                        "ambiguity_reason": reason
                    })

        # 5. Domain Knowledge Identification
        detected_domain = None
        for dom, kws in INDUSTRY_DOMAINS.items():
            for kw in kws:
                m = re.search(rf"\b{re.escape(kw)}\b", text_lower)
                if m:
                    start, end, quote = locate_quote(raw_text, m.group(0))
                    detected_domain = dom.replace("_", " ").title()
                    req_key = f"domain_{dom}"
                    if req_key not in seen_keys:
                        seen_keys.add(req_key)
                        requirements.append({
                            "requirement_key": req_key,
                            "category": "domain",
                            "title": f"{detected_domain} Domain Experience",
                            "quote": quote,
                            "start_offset": start,
                            "end_offset": end,
                            "is_mandatory": False,
                            "importance": "medium",
                            "normalized_terms": [dom],
                            "dependencies": [],
                            "is_ambiguous": False,
                            "ambiguity_reason": None
                        })
                    break

        # 6. Seniority Identification
        seniority = None
        for lvl in ["Principal", "Staff", "Lead", "Senior", "Mid", "Junior", "Associate", "Entry"]:
            if re.search(rf"\b{lvl}\b", role_hint + " " + raw_text[:500], re.IGNORECASE):
                seniority = lvl
                break

        return {
            "role": role_hint or "Target Role",
            "company": company_hint or "Target Company",
            "experience_years": exp_years,
            "seniority": seniority,
            "domain": detected_domain,
            "requirements": requirements
        }
