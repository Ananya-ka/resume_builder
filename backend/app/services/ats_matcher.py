import re
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Set, Optional, Tuple

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. SEMANTIC TAXONOMY & SYNONYM CANONICALIZATION DICTIONARY
# ==============================================================================

CANONICAL_SYNONYMS: Dict[str, List[str]] = {
    # Programming Languages
    "python": ["python3", "python 3", "py", "python programming"],
    "javascript": ["js", "ecmascript", "es6", "es2015", "vanilla js", "modern javascript"],
    "typescript": ["ts", "typescript 4", "typescript 5"],
    "golang": ["go lang", "go language", "go"],
    "java": ["java 8", "java 11", "java 17", "java 21", "core java", "j2ee"],
    "c++": ["cpp", "c plus plus", "modern c++", "c++11", "c++17", "c++20"],
    "c#": ["csharp", "c sharp", ".net c#"],
    "rust": ["rustlang", "rust language"],
    "ruby": ["ruby on rails", "mri ruby"],
    "php": ["php 7", "php 8", "modern php"],
    "swift": ["swift 5", "swiftui"],
    "kotlin": ["kotlin android"],
    "sql": ["structured query language", "rdbms", "relational database", "ansi sql"],
    "bash": ["shell", "shell scripting", "bash scripting", "zsh", "sh"],

    # Web & Frameworks
    "react": ["react.js", "reactjs", "react framework"],
    "next.js": ["nextjs", "next js", "next.js framework"],
    "node.js": ["nodejs", "node js", "node runtime", "node"],
    "fastapi": ["fast api", "fastapi framework"],
    "flask": ["flask framework", "python flask"],
    "django": ["django framework", "django rest framework", "drf"],
    "express": ["express.js", "expressjs"],
    "spring": ["spring boot", "spring framework", "spring cloud"],
    "angular": ["angular.js", "angularjs", "angular 2+"],
    "vue": ["vue.js", "vuejs", "vue 3"],
    "graphql": ["graph ql", "apollo graphql"],
    "rest": ["restful", "rest api", "restful apis", "restful web services", "rest endpoints"],
    "grpc": ["g rpc", "protobuf", "protocol buffers"],

    # Cloud & DevOps
    "aws": ["amazon web services", "amazon cloud", "aws cloud"],
    "gcp": ["google cloud platform", "google cloud"],
    "azure": ["microsoft azure", "ms azure"],
    "kubernetes": ["k8s", "kube", "kubernetes cluster", "container orchestration"],
    "docker": ["containerization", "docker containers", "docker-compose", "dockerfile"],
    "ci/cd": ["continuous integration", "continuous deployment", "continuous delivery", "github actions", "gitlab ci", "jenkins", "circleci", "build pipelines"],
    "terraform": ["infrastructure as code", "iac", "terraform modules"],
    "linux": ["unix", "ubuntu", "debian", "redhat", "centos", "amazon linux"],

    # Databases & Caching
    "postgresql": ["postgres", "psql", "postgres database", "postgresql database"],
    "mysql": ["maria db", "mariadb"],
    "mongodb": ["mongo", "mongo db", "document database"],
    "redis": ["redis cache", "redis in-memory"],
    "elasticsearch": ["elastic search", "opensearch", "elk stack"],
    "nosql": ["non-relational database", "document db", "key-value store"],
    "kafka": ["apache kafka", "kafka streaming", "event-driven architecture", "message broker", "pub/sub"],
    "rabbitmq": ["rabbit mq", "amqp", "message queue"],

    # Architecture & Practices
    "microservices": ["microservice architecture", "distributed services", "service-oriented"],
    "distributed systems": ["distributed architecture", "high availability", "fault tolerant", "distributed computing"],
    "system design": ["software architecture", "high level design", "low level design"],
    "agile": ["scrum", "kanban", "sprint planning"],
    "tdd": ["test driven development", "unit testing", "automated testing"],

    # AI / ML / Data
    "machine learning": ["ml", "artificial intelligence", "ai", "predictive modeling"],
    "deep learning": ["neural networks", "dl", "computer vision", "nlp", "natural language processing"],
    "pytorch": ["py torch", "torch"],
    "tensorflow": ["tf", "tensor flow"],
    "llm": ["large language models", "generative ai", "genai", "prompt engineering", "retrieval augmented generation", "rag", "langchain", "llamaindex"],
    "data engineering": ["etl", "elt", "data pipeline", "data warehousing", "data lake"]
}

# Inverted lookup for O(1) canonical resolution
_ALIAS_TO_CANONICAL: Dict[str, str] = {}
for canonical, aliases in CANONICAL_SYNONYMS.items():
    _ALIAS_TO_CANONICAL[canonical.lower()] = canonical.lower()
    for alias in aliases:
        _ALIAS_TO_CANONICAL[alias.lower()] = canonical.lower()

# Degree hierarchy mapping: maps degree strings to numeric level
DEGREE_LEVELS: Dict[str, int] = {
    "high school": 1,
    "associate": 2,
    "bachelor": 3,
    "bs": 3, "ba": 3, "b.s.": 3, "b.a.": 3, "b.tech": 3, "btech": 3, "b.e.": 3, "be": 3, "undergraduate": 3,
    "master": 4,
    "ms": 4, "ma": 4, "m.s.": 4, "m.a.": 4, "m.tech": 4, "mtech": 4, "mba": 4, "postgraduate": 4,
    "phd": 5, "ph.d.": 5, "doctorate": 5, "doctoral": 5
}

# Domain & Industry taxonomy
INDUSTRY_DOMAINS: Dict[str, List[str]] = {
    "fintech": ["payments", "banking", "trading", "financial services", "lending", "credit", "ledger", "pci", "fraud detection"],
    "healthcare": ["healthtech", "hipaa", "ehr", "emr", "clinical", "biotech", "medical devices", "telehealth"],
    "ecommerce": ["retail", "shopping cart", "marketplace", "inventory", "checkout", "order management", "logistics"],
    "cloud_infrastructure": ["devops", "sre", "platform engineering", "infrastructure", "observability", "monitoring"],
    "cybersecurity": ["security", "soc2", "penetration testing", "encryption", "auth0", "oauth", "identity", "zero trust"],
    "b2b_saas": ["enterprise software", "multi-tenant", "crm", "billing", "subscriptions"]
}

# Responsibility synonym groups for semantic matching across synonymous action verbs and workplace concepts
RESPONSIBILITY_SYNONYM_GROUPS: List[Set[str]] = [
    {"partner", "collaborate", "collaborated", "partnered", "stakeholder", "stakeholders", "team", "teams", "cross-functional", "liaise", "align", "interact"},
    {"architect", "architected", "design", "designed", "scale", "scaled", "build", "built", "develop", "developed", "create", "created", "engineer", "implement"},
    {"mentor", "mentored", "lead", "leading", "coach", "coached", "guide", "guided", "train", "trained", "supervise", "supervised", "advise"},
    {"drive", "driven", "deliver", "delivered", "execute", "executed", "ship", "shipped", "launch", "launched", "roadmap", "release"},
    {"manage", "managed", "operate", "operated", "support", "supported", "maintain", "maintained", "administer", "troubleshoot"},
    {"standardize", "standardized", "review", "reviewed", "excellence", "quality", "guidelines", "best-practices", "governance"}
]

RESPONSIBILITY_STOPWORDS: Set[str] = {
    "with", "that", "this", "from", "will", "have", "your", "across", "responsibilities", "duties", "such", "into", "through", "using"
}

def _stem_token(token: str) -> str:
    """Lightweight English stemmer for ATS semantic token matching."""
    token = token.lower().strip()
    token = re.sub(r"[^\w-]", "", token)
    if not token:
        return ""
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("ing") and len(token) > 4:
        return token[:-3]
    if token.endswith("ed") and len(token) > 4:
        return token[:-2]
    if token.endswith("es") and len(token) > 4:
        return token[:-2]
    if token.endswith("s") and len(token) > 3 and not token.endswith("ss"):
        return token[:-1]
    if token.endswith("tion") and len(token) > 6:
        return token[:-4]
    if token.endswith("ment") and len(token) > 6:
        return token[:-4]
    return token

def _tokens_semantically_match(w1: str, w2: str) -> bool:
    """Checks if two tokens match directly, via stem, or via responsibility synonym groups."""
    if w1 == w2:
        return True
    s1, s2 = _stem_token(w1), _stem_token(w2)
    if s1 and s2 and s1 == s2:
        return True
    for group in RESPONSIBILITY_SYNONYM_GROUPS:
        g_stems = {_stem_token(g) for g in group}
        if (w1 in group or s1 in g_stems) and (w2 in group or s2 in g_stems):
            return True
    return False


# ==============================================================================
# 2. DATA STRUCTURES & CONFIGURATION
# ==============================================================================

@dataclass
class EvidenceMatch:
    term: str
    canonical: str
    category: str  # "mandatory_skill", "preferred_skill", "responsibility", "domain", "education"
    evidence_level: str  # "strong", "moderate", "listed_only", "none"
    evidence_snippet: str
    source_section: str  # "Experience", "Projects", "Skills", "Summary", "Education"
    confidence: float  # 0.0 to 1.0


@dataclass
class HardEligibilityGate:
    gate_name: str  # "minimum_tenure", "education_level", "mandatory_certifications", "maximum_tenure_cap"
    required_value: Any
    candidate_value: Any
    is_passed: bool
    status: str  # "passed", "failed", "unverifiable"
    reason: str
    remediation: Optional[str] = None


@dataclass
class ATSMatcherConfig:
    """Configurable weights and thresholds for ATS matching engine."""
    mandatory_skills_weight: float = 0.30
    preferred_skills_weight: float = 0.10
    experience_relevance_weight: float = 0.20
    tenure_weight: float = 0.15
    responsibilities_weight: float = 0.10
    education_weight: float = 0.10
    domain_weight: float = 0.05

    strong_evidence_multiplier: float = 1.0
    moderate_evidence_multiplier: float = 0.85
    listed_only_multiplier: float = 0.60
    strict_binary_tenure: bool = True


# ==============================================================================
# 3. PRODUCTION ATS RESUME–JOB DESCRIPTION MATCHING ENGINE
# ==============================================================================

class ATSMatchingEngine:
    """
    Industrial-strength ATS Resume–Job Description Matching System.
    Evaluates candidate-job fit across:
      1. Mandatory Skills & Technical Competencies
      2. Preferred / Bonus Qualifications
      3. Relevant Work Experience & Seniority Alignment
      4. Professional Tenure (Strict deterministic binary gating)
      5. Core Job Responsibilities Coverage
      6. Educational Qualifications & Field of Study
      7. Industry & Domain Knowledge Alignment
    """

    def __init__(self, config: Optional[ATSMatcherConfig] = None):
        from app.services.tenure_matcher import TenureMatcher
        self.config = config or ATSMatcherConfig()
        self.tenure_matcher = TenureMatcher()

    # --------------------------------------------------------------------------
    # Helper: Canonicalize Terms
    # --------------------------------------------------------------------------

    @staticmethod
    def canonicalize(term: str) -> str:
        """Resolves a skill/term to its canonical dictionary form."""
        clean = term.strip().lower()
        clean = re.sub(r"[\.,;:!\(\)]", "", clean)
        return _ALIAS_TO_CANONICAL.get(clean, clean)

    # --------------------------------------------------------------------------
    # 1. JD Requirement Extraction & Dimensional Parsing
    # --------------------------------------------------------------------------

    def parse_jd_requirements(self, jd_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Interprets raw and structured JD requirements, cleanly separating:
        - Mandatory skills vs Preferred skills (anti-double-counting)
        - Core responsibilities
        - Education requirements (degree level & field)
        - Industry domain context
        - Experience tenure targets
        """
        raw_text = jd_data.get("raw_text") or jd_data.get("jd_text") or ""
        text_lower = raw_text.lower()

        # A. Tenure Requirements
        tenure_reqs = self.tenure_matcher.extract_jd_requirements(raw_text, structured_data=jd_data)

        # B. Skills Extraction & Categorization
        all_req_skills: Set[str] = set()
        all_pref_skills: Set[str] = set()

        # Structured fields if available
        if jd_data.get("required_skills"):
            all_req_skills.update([s.strip().lower() for s in jd_data["required_skills"] if s])
        if jd_data.get("languages"):
            all_req_skills.update([s.strip().lower() for s in jd_data["languages"] if s])
        if jd_data.get("frameworks"):
            all_req_skills.update([s.strip().lower() for s in jd_data["frameworks"] if s])
        if jd_data.get("databases"):
            all_req_skills.update([s.strip().lower() for s in jd_data["databases"] if s])
        if jd_data.get("cloud"):
            all_req_skills.update([s.strip().lower() for s in jd_data["cloud"] if s])

        if jd_data.get("preferred_skills"):
            all_pref_skills.update([s.strip().lower() for s in jd_data["preferred_skills"] if s])

        # If ats_keywords present, add them without duplicate counting
        if jd_data.get("ats_keywords"):
            for kw in jd_data["ats_keywords"]:
                kw_clean = kw.strip().lower()
                if kw_clean and kw_clean not in all_pref_skills:
                    all_req_skills.add(kw_clean)

        # Text-based Section Scanning for Mandatory vs Preferred if raw text is provided
        if raw_text:
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
            in_preferred_section = False
            in_required_section = False

            for line in lines:
                l_lower = line.lower()
                if any(h in l_lower for h in ["preferred", "nice to have", "bonus", "plus", "desired", "what gives you an edge"]):
                    in_preferred_section = True
                    in_required_section = False
                    continue
                elif any(h in l_lower for h in ["requirements", "required", "qualifications", "must have", "what you need", "what you'll bring"]):
                    in_required_section = True
                    in_preferred_section = False
                    continue
                elif any(h in l_lower for h in ["about us", "benefits", "perks", "equal opportunity", "who we are"]):
                    in_preferred_section = False
                    in_required_section = False

                # Scan technical terms mentioned in preferred lines
                if in_preferred_section:
                    for canonical, aliases in CANONICAL_SYNONYMS.items():
                        all_terms = [canonical] + aliases
                        for t in all_terms:
                            if re.search(rf"\b{re.escape(t)}\b", l_lower):
                                all_pref_skills.add(canonical)

        # Anti-double counting rule: Mandatory takes absolute precedence over Preferred
        all_pref_skills = all_pref_skills - all_req_skills

        # C. Responsibilities Extraction
        responsibilities = []
        if jd_data.get("responsibilities") and isinstance(jd_data["responsibilities"], list):
            responsibilities = [r.strip() for r in jd_data["responsibilities"] if len(r.strip()) > 10]
        elif raw_text:
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
            in_resp = False
            for line in lines:
                l_lower = line.lower()
                if any(h in l_lower for h in ["responsibilities", "what you'll do", "what you will do", "duties", "the role", "your impact"]):
                    in_resp = True
                    continue
                elif in_resp and any(h in l_lower for h in ["requirements", "qualifications", "preferred", "benefits", "about us"]):
                    in_resp = False

                if in_resp and (line.startswith(("-", "*", "•", "–")) or len(line) > 25):
                    clean_line = line.lstrip("-*•–> \t")
                    if len(clean_line) > 15:
                        responsibilities.append(clean_line)

        # D. Education Requirements Extraction
        req_degree_level = 0
        req_degree_name = "None"
        req_field = None

        if "ph.d" in text_lower or "phd" in text_lower or "doctorate" in text_lower:
            req_degree_level = 5
            req_degree_name = "Ph.D. / Doctorate"
        elif any(k in text_lower for k in ["master's", "masters degree", "m.s.", "ms in", "m.tech"]):
            req_degree_level = 4
            req_degree_name = "Master's Degree"
        elif any(k in text_lower for k in ["bachelor's", "bachelors degree", "b.s.", "bs in", "b.tech", "b.e.", "undergraduate degree", "4-year degree"]):
            req_degree_level = 3
            req_degree_name = "Bachelor's Degree"
        elif any(k in text_lower for k in ["associate's", "associates degree"]):
            req_degree_level = 2
            req_degree_name = "Associate Degree"

        if any(f in text_lower for f in ["computer science", "software engineering", "computer engineering"]):
            req_field = "Computer Science"
        elif any(f in text_lower for f in ["data science", "statistics", "mathematics", "math"]):
            req_field = "Data Science / Math"
        elif any(f in text_lower for f in ["stem", "engineering", "technical field", "related field"]):
            req_field = "STEM / Technical Field"

        # E. Domain & Industry Extraction
        detected_domains = []
        if jd_data.get("domain"):
            detected_domains.append(str(jd_data["domain"]).lower())
        if jd_data.get("industry"):
            detected_domains.append(str(jd_data["industry"]).lower())

        for domain, keywords in INDUSTRY_DOMAINS.items():
            if any(re.search(rf"\b{re.escape(k)}\b", text_lower) for k in keywords):
                if domain not in detected_domains:
                    detected_domains.append(domain)

        return {
            "tenure_reqs": tenure_reqs,
            "mandatory_skills": sorted(list(all_req_skills)),
            "preferred_skills": sorted(list(all_pref_skills)),
            "responsibilities": responsibilities[:10],
            "required_degree_level": req_degree_level,
            "required_degree_name": req_degree_name,
            "required_field": req_field,
            "detected_domains": detected_domains,
            "role": jd_data.get("role") or "",
            "company": jd_data.get("company") or ""
        }

    # --------------------------------------------------------------------------
    # 2. Candidate Evidence Harvester & Semantic Search
    # --------------------------------------------------------------------------

    def harvest_candidate_evidence(self, resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Structures candidate resume into searchable semantic units with provenance.
        """
        roles_with_evidence = []
        projects_with_evidence = []
        raw_skills: Set[str] = set()

        for s in resume_data.get("skills", []):
            if isinstance(s, str):
                raw_skills.add(s.strip().lower())

        # Extract Experience
        for exp in resume_data.get("experience", []):
            comp = exp.get("company", "")
            role = exp.get("role", "")
            bullets = [b for b in exp.get("bullets", []) if isinstance(b, str)]
            roles_with_evidence.append({
                "company": comp,
                "role": role,
                "bullets": bullets,
                "combined_text": f"{comp} {role} {' '.join(bullets)}".lower()
            })

        # Extract Projects
        for proj in resume_data.get("projects", []):
            p_name = proj.get("name", "")
            p_bullets = [b for b in proj.get("bullets", []) if isinstance(b, str)]
            projects_with_evidence.append({
                "name": p_name,
                "bullets": p_bullets,
                "combined_text": f"{p_name} {' '.join(p_bullets)}".lower()
            })

        # Extract Education
        candidate_degree_level = 0
        candidate_degree_title = "None"
        candidate_field = ""
        edu_entries = resume_data.get("education", [])

        for edu in edu_entries:
            deg_text = f"{edu.get('degree', '')} {edu.get('school', '')}".lower()
            for deg_kw, level in DEGREE_LEVELS.items():
                if re.search(rf"\b{re.escape(deg_kw)}\b", deg_text):
                    if level > candidate_degree_level:
                        candidate_degree_level = level
                        candidate_degree_title = edu.get("degree", deg_kw.capitalize())

            if any(f in deg_text for f in ["computer science", "cs", "software"]):
                candidate_field = "Computer Science"
            elif any(f in deg_text for f in ["data science", "statistics", "math"]):
                candidate_field = "Data Science / Math"
            elif any(f in deg_text for f in ["engineering", "information technology", "electrical"]):
                candidate_field = "Engineering"

        summary = str(resume_data.get("profile_summary", "") or "").lower()

        return {
            "roles": roles_with_evidence,
            "projects": projects_with_evidence,
            "skills": raw_skills,
            "education_level": candidate_degree_level,
            "education_degree": candidate_degree_title,
            "education_field": candidate_field,
            "education_entries_count": len(edu_entries),
            "summary": summary
        }

    def find_term_evidence(
        self,
        target_term: str,
        candidate_profile: Dict[str, Any]
    ) -> Optional[EvidenceMatch]:
        """
        Searches for target term or any of its canonical aliases across candidate profile.
        Determines evidence level:
          - 'strong': demonstrated in an active work experience bullet with execution context
          - 'moderate': demonstrated in a project or summary
          - 'listed_only': only found in the raw skills list
        """
        term_clean = target_term.strip().lower()
        canonical = self.canonicalize(term_clean)

        # Collect search variants
        variants = {term_clean, canonical}
        if canonical in CANONICAL_SYNONYMS:
            variants.update(CANONICAL_SYNONYMS[canonical])

        # 1. Search Work Experience Bullets (Strong Evidence)
        for role_entry in candidate_profile["roles"]:
            for bullet in role_entry["bullets"]:
                b_lower = bullet.lower()
                for v in variants:
                    # Match on word boundary (allowing punctuation like c++, .net)
                    pattern = rf"\b{re.escape(v)}\b" if re.match(r"^\w", v) and re.search(r"\w$", v) else re.escape(v)
                    if re.search(pattern, b_lower):
                        return EvidenceMatch(
                            term=target_term,
                            canonical=canonical,
                            category="mandatory_skill",
                            evidence_level="strong",
                            evidence_snippet=bullet,
                            source_section="Experience",
                            confidence=1.0
                        )

        # 2. Search Projects (Moderate Evidence)
        for proj in candidate_profile["projects"]:
            for bullet in proj["bullets"]:
                b_lower = bullet.lower()
                for v in variants:
                    pattern = rf"\b{re.escape(v)}\b" if re.match(r"^\w", v) and re.search(r"\w$", v) else re.escape(v)
                    if re.search(pattern, b_lower):
                        return EvidenceMatch(
                            term=target_term,
                            canonical=canonical,
                            category="mandatory_skill",
                            evidence_level="moderate",
                            evidence_snippet=bullet,
                            source_section="Projects",
                            confidence=0.85
                        )

        # 3. Search Summary (Moderate Evidence)
        if candidate_profile["summary"]:
            for v in variants:
                pattern = rf"\b{re.escape(v)}\b" if re.match(r"^\w", v) and re.search(r"\w$", v) else re.escape(v)
                if re.search(pattern, candidate_profile["summary"]):
                    return EvidenceMatch(
                        term=target_term,
                        canonical=canonical,
                        category="mandatory_skill",
                        evidence_level="moderate",
                        evidence_snippet=candidate_profile["summary"][:120],
                        source_section="Summary",
                        confidence=0.80
                    )

        # 4. Search Skills List (Listed Only)
        for sk in candidate_profile["skills"]:
            sk_canonical = self.canonicalize(sk)
            if sk in variants or sk_canonical in variants:
                return EvidenceMatch(
                    term=target_term,
                    canonical=canonical,
                    category="mandatory_skill",
                    evidence_level="listed_only",
                    evidence_snippet=f"Listed under skills: '{sk}'",
                    source_section="Skills",
                    confidence=0.60
                )

        return None

    # --------------------------------------------------------------------------
    # 3. Dimensional Evaluation Modules
    # --------------------------------------------------------------------------

    def evaluate_skills(
        self,
        skills_list: List[str],
        candidate_profile: Dict[str, Any],
        is_mandatory: bool
    ) -> Tuple[float, List[EvidenceMatch], List[str]]:
        """
        Evaluates skills alignment, scaling credit based on evidence quality.
        """
        if not skills_list:
            return 100.0, [], []

        matched_evidence: List[EvidenceMatch] = []
        missing_skills: List[str] = []
        total_points = 0.0

        for skill in skills_list:
            ev = self.find_term_evidence(skill, candidate_profile)
            if ev:
                ev.category = "mandatory_skill" if is_mandatory else "preferred_skill"
                matched_evidence.append(ev)
                if ev.evidence_level == "strong":
                    total_points += self.config.strong_evidence_multiplier
                elif ev.evidence_level == "moderate":
                    total_points += self.config.moderate_evidence_multiplier
                else:
                    total_points += self.config.listed_only_multiplier
            else:
                missing_skills.append(skill)

        max_possible = len(skills_list) * self.config.strong_evidence_multiplier
        score = (total_points / max_possible * 100.0) if max_possible > 0 else 100.0
        return round(score, 1), matched_evidence, missing_skills

    def evaluate_responsibilities(
        self,
        jd_responsibilities: List[str],
        candidate_profile: Dict[str, Any]
    ) -> Tuple[float, List[Dict[str, str]], List[str]]:
        """
        Evaluates coverage of JD responsibilities against candidate experience bullets.
        Matches each duty to the best evidence bullet.
        """
        if not jd_responsibilities:
            return 100.0, [], []

        all_candidate_bullets = []
        for r in candidate_profile["roles"]:
            all_candidate_bullets.extend(r["bullets"])
        for p in candidate_profile["projects"]:
            all_candidate_bullets.extend(p["bullets"])

        covered: List[Dict[str, str]] = []
        uncovered: List[str] = []

        for resp in jd_responsibilities:
            resp_tokens = [w for w in re.findall(r"\b[a-z0-9+#-]{3,}\b", resp.lower()) if w not in RESPONSIBILITY_STOPWORDS]
            if not resp_tokens:
                covered.append({"responsibility": resp, "matched_bullet": "General professional alignment"})
                continue

            best_bullet = ""
            best_overlap = 0

            for bullet in all_candidate_bullets:
                b_tokens = [w for w in re.findall(r"\b[a-z0-9+#-]{3,}\b", bullet.lower()) if w not in RESPONSIBILITY_STOPWORDS]
                # Count distinct resp_tokens that find a semantic or stem match in b_tokens
                overlap = sum(1 for rw in resp_tokens if any(_tokens_semantically_match(rw, bw) for bw in b_tokens))
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_bullet = bullet

            # Require at least 2 significant keyword overlaps or >= 30% of content words
            if best_overlap >= 2 or (len(resp_tokens) <= 3 and best_overlap >= 1):
                covered.append({
                    "responsibility": resp,
                    "matched_bullet": best_bullet
                })
            else:
                uncovered.append(resp)

        score = (len(covered) / len(jd_responsibilities) * 100.0) if jd_responsibilities else 100.0
        return round(score, 1), covered, uncovered

    def evaluate_education(
        self,
        jd_reqs: Dict[str, Any],
        candidate_profile: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any], Optional[HardEligibilityGate]]:
        """
        Evaluates educational credentials and field of study.
        Handles missing education transparently.
        """
        req_level = jd_reqs["required_degree_level"]
        cand_level = candidate_profile["education_level"]
        cand_degree = candidate_profile["education_degree"]
        has_edu_section = candidate_profile["education_entries_count"] > 0

        # Case 1: No education requirement stated in JD
        if req_level == 0:
            return 100.0, {
                "required_degree": "None",
                "candidate_degree": cand_degree,
                "status": "not_required",
                "is_met": True
            }, None

        # Case 2: Candidate did not include education section on resume
        if not has_edu_section or cand_level == 0:
            gate = HardEligibilityGate(
                gate_name="education_level",
                required_value=jd_reqs["required_degree_name"],
                candidate_value="Not stated on resume",
                is_passed=False,
                status="unverifiable",
                reason=f"Position requires {jd_reqs['required_degree_name']}, but no education details were detected on the resume.",
                remediation="Add an Education section specifying your highest degree, institution, and graduation year."
            )
            return 0.0, {
                "required_degree": jd_reqs["required_degree_name"],
                "candidate_degree": "Not stated",
                "status": "unverifiable",
                "is_met": False
            }, gate

        # Case 3: Candidate degree meets or exceeds required degree
        if cand_level >= req_level:
            return 100.0, {
                "required_degree": jd_reqs["required_degree_name"],
                "candidate_degree": cand_degree,
                "status": "meets_requirement",
                "is_met": True
            }, HardEligibilityGate(
                gate_name="education_level",
                required_value=jd_reqs["required_degree_name"],
                candidate_value=cand_degree,
                is_passed=True,
                status="passed",
                reason=f"Candidate education ({cand_degree}) meets or exceeds required level ({jd_reqs['required_degree_name']})."
            )

        # Case 4: Candidate degree is below requirement (e.g. Associate vs Bachelor's)
        gate = HardEligibilityGate(
            gate_name="education_level",
            required_value=jd_reqs["required_degree_name"],
            candidate_value=cand_degree,
            is_passed=False,
            status="failed",
            reason=f"Candidate degree ({cand_degree}) does not satisfy required {jd_reqs['required_degree_name']}.",
            remediation="Highlight relevant professional certifications and equivalent work tenure."
        )
        return 40.0, {
            "required_degree": jd_reqs["required_degree_name"],
            "candidate_degree": cand_degree,
            "status": "below_requirement",
            "is_met": False
        }, gate

    def evaluate_domain(
        self,
        jd_domains: List[str],
        candidate_profile: Dict[str, Any]
    ) -> Tuple[float, List[str], List[str]]:
        """
        Evaluates industry domain knowledge alignment.
        """
        if not jd_domains:
            return 100.0, [], []

        all_text = []
        for r in candidate_profile["roles"]:
            all_text.append(r["combined_text"])
        for p in candidate_profile["projects"]:
            all_text.append(p["combined_text"])
        all_text.append(candidate_profile["summary"])
        full_cand_text = " ".join(all_text).lower()

        matched_domains = []
        missing_domains = []

        for d in jd_domains:
            kw_list = INDUSTRY_DOMAINS.get(d, [d])
            if any(re.search(rf"\b{re.escape(k)}\b", full_cand_text) for k in kw_list):
                matched_domains.append(d)
            else:
                missing_domains.append(d)

        score = (len(matched_domains) / len(jd_domains) * 100.0) if jd_domains else 100.0
        return round(score, 1), matched_domains, missing_domains

    # --------------------------------------------------------------------------
    # 4. Master Evaluation Pipeline
    # --------------------------------------------------------------------------

    def evaluate(
        self,
        resume_data: Dict[str, Any],
        jd_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executes full multi-dimensional ATS evaluation between Resume and JD.
        """
        # 1. Parse JD and Harvest Candidate Evidence
        jd_reqs = self.parse_jd_requirements(jd_data)
        cand_profile = self.harvest_candidate_evidence(resume_data)

        # 2. Evaluate Professional Tenure with precision TenureMatcher
        tenure_report = self.tenure_matcher.match(resume_data, jd_data)
        tenure_score = tenure_report["tenure_score"]

        # 3. Evaluate Skills (Mandatory vs Preferred)
        mandatory_score, mandatory_evidence, mandatory_missing = self.evaluate_skills(
            jd_reqs["mandatory_skills"], cand_profile, is_mandatory=True
        )
        preferred_score, preferred_evidence, preferred_missing = self.evaluate_skills(
            jd_reqs["preferred_skills"], cand_profile, is_mandatory=False
        )

        # 4. Evaluate Core Responsibilities Alignment
        resp_score, resp_covered, resp_uncovered = self.evaluate_responsibilities(
            jd_reqs["responsibilities"], cand_profile
        )

        # 5. Evaluate Education
        edu_score, edu_report, edu_gate = self.evaluate_education(jd_reqs, cand_profile)

        # 6. Evaluate Domain Knowledge
        domain_score, matched_domains, missing_domains = self.evaluate_domain(
            jd_reqs["detected_domains"], cand_profile
        )

        # 7. Experience Relevance Assessment (Role title alignment & bullet complexity)
        exp_relevance_score = 100.0
        raw_role = (jd_reqs.get("role") or "").strip().lower()
        if raw_role and raw_role not in {"target role", "role", "unknown", "n/a", "none"}:
            role_words = set(re.findall(r"\b[a-z0-9]+\b", raw_role)) - {
                "engineer", "developer", "senior", "lead", "junior", "staff", "principal", "manager", "role", "target"
            }
            if role_words:
                cand_roles_str = " ".join([r["role"].lower() + " " + r["combined_text"] for r in cand_profile["roles"]])
                matched_role_words = sum(1 for rw in role_words if rw in cand_roles_str or _stem_token(rw) in cand_roles_str)
                if matched_role_words == 0 and len(cand_profile["roles"]) > 0:
                    exp_relevance_score = 75.0

        # 8. Hard Eligibility Checks
        gates: List[HardEligibilityGate] = []

        # Gate A: Minimum Tenure Check
        req_years = tenure_report["required_years"]
        cand_years = tenure_report["total_years"]
        if req_years > 0:
            if not tenure_report["experience_duration_known"]:
                gates.append(HardEligibilityGate(
                    gate_name="minimum_tenure",
                    required_value=f"{req_years} yrs",
                    candidate_value="Unverifiable dates",
                    is_passed=False,
                    status="unverifiable",
                    reason="No verifiable employment dates were detected in experience section.",
                    remediation="Add clear date ranges (e.g., 'Jan 2021 – Present') to each experience role."
                ))
            elif cand_years < req_years:
                gates.append(HardEligibilityGate(
                    gate_name="minimum_tenure",
                    required_value=f"{req_years} yrs",
                    candidate_value=f"{cand_years} yrs",
                    is_passed=False,
                    status="failed",
                    reason=f"Candidate has {cand_years} yrs vs {req_years} yrs minimum required.",
                    remediation=f"Position requires {req_years}+ years. Highlight earlier roles or contract projects."
                ))
            else:
                gates.append(HardEligibilityGate(
                    gate_name="minimum_tenure",
                    required_value=f"{req_years} yrs",
                    candidate_value=f"{cand_years} yrs",
                    is_passed=True,
                    status="passed",
                    reason=f"Candidate experience ({cand_years} yrs) meets or exceeds requirement ({req_years} yrs)."
                ))

        # Gate B: Maximum Tenure Cap
        if tenure_report.get("has_explicit_maximum") and tenure_report.get("max_years"):
            max_y = tenure_report["max_years"]
            if cand_years > max_y:
                gates.append(HardEligibilityGate(
                    gate_name="maximum_tenure_cap",
                    required_value=f"<= {max_y} yrs",
                    candidate_value=f"{cand_years} yrs",
                    is_passed=False,
                    status="failed",
                    reason=f"Candidate experience ({cand_years} yrs) exceeds position maximum cap ({max_y} yrs).",
                    remediation="Emphasize direct individual contribution rather than high-level management."
                ))
            else:
                gates.append(HardEligibilityGate(
                    gate_name="maximum_tenure_cap",
                    required_value=f"<= {max_y} yrs",
                    candidate_value=f"{cand_years} yrs",
                    is_passed=True,
                    status="passed",
                    reason=f"Candidate experience ({cand_years} yrs) is within position cap (<= {max_y} yrs)."
                ))

        # Gate C: Education Gate
        if edu_gate:
            gates.append(edu_gate)

        is_overall_eligible = all(g.is_passed for g in gates)
        failed_gates = [g.gate_name for g in gates if not g.is_passed and g.status == "failed"]
        unverifiable_gates = [g.gate_name for g in gates if g.status == "unverifiable"]
        passed_gates = [g.gate_name for g in gates if g.is_passed]

        eligibility_status = "eligible" if is_overall_eligible else ("unverifiable" if unverifiable_gates and not failed_gates else "ineligible")

        # 9. Dynamic Weight Re-normalization & Overall Match Score
        # Re-balance weights across active dimensions so scores are never deflated when a JD omits optional fields
        active_weights = {}
        active_scores = {}

        if jd_reqs["mandatory_skills"]:
            active_weights["mandatory_skills"] = self.config.mandatory_skills_weight
            active_scores["mandatory_skills"] = mandatory_score
        else:
            # Fallback if no mandatory skills specified
            active_weights["mandatory_skills"] = 0.20
            active_scores["mandatory_skills"] = 100.0

        if jd_reqs["preferred_skills"]:
            active_weights["preferred_skills"] = self.config.preferred_skills_weight
            active_scores["preferred_skills"] = preferred_score

        active_weights["experience_relevance"] = self.config.experience_relevance_weight
        active_scores["experience_relevance"] = exp_relevance_score

        active_weights["tenure"] = self.config.tenure_weight
        active_scores["tenure"] = tenure_score

        if jd_reqs["responsibilities"]:
            active_weights["responsibilities"] = self.config.responsibilities_weight
            active_scores["responsibilities"] = resp_score

        if jd_reqs["required_degree_level"] > 0:
            active_weights["education"] = self.config.education_weight
            active_scores["education"] = edu_score

        if jd_reqs["detected_domains"]:
            active_weights["domain"] = self.config.domain_weight
            active_scores["domain"] = domain_score

        # Normalize weights to sum exactly to 1.0
        total_weight = sum(active_weights.values()) or 1.0
        normalized_weights = {k: v / total_weight for k, v in active_weights.items()}

        overall_fit = sum(active_scores[k] * normalized_weights[k] for k in active_weights)
        overall_fit = max(0.0, min(100.0, round(overall_fit, 1)))

        # 10. Generate Prioritized Actionable Recommendations
        recommendations = []
        if failed_gates:
            for g in gates:
                if not g.is_passed:
                    recommendations.append({
                        "type": "hard_eligibility",
                        "title": f"Eligibility Gate Issue: {g.gate_name.replace('_', ' ').title()}",
                        "description": g.reason,
                        "action": g.remediation or "Review requirement"
                    })

        if mandatory_missing:
            top_missing = mandatory_missing[:5]
            recommendations.append({
                "type": "skills_mandatory",
                "title": f"Missing Core Mandatory Skills ({len(mandatory_missing)} missing)",
                "description": f"Key required competencies not demonstrated: {', '.join(top_missing)}. ATS screeners heavily weight these requirements.",
                "action": "Add Experience Bullets Demonstrating Missing Skills"
            })

        if resp_uncovered:
            recommendations.append({
                "type": "responsibilities",
                "title": f"Unaddressed Target Responsibilities ({len(resp_uncovered)} uncovered)",
                "description": f"Target duties unaddressed in resume: '{resp_uncovered[0][:80]}...'",
                "action": "Tailor Project & Experience Bullets"
            })

        if preferred_missing and len(mandatory_missing) <= 2:
            top_pref = preferred_missing[:3]
            recommendations.append({
                "type": "skills_preferred",
                "title": f"Bonus Alignment Booster: Preferred Skills",
                "description": f"Incorporate preferred technologies if experienced: {', '.join(top_pref)}.",
                "action": "Add Preferred Skills"
            })

        # 11. Compile Evidence Ledger
        evidence_ledger = [asdict(e) for e in mandatory_evidence + preferred_evidence]

        return {
            "overall_fit_score": overall_fit,
            "hard_eligibility": {
                "is_eligible": is_overall_eligible,
                "status": eligibility_status,
                "passed_gates": passed_gates,
                "failed_gates": failed_gates,
                "unverifiable_gates": unverifiable_gates,
                "gates": [asdict(g) for g in gates]
            },
            "dimension_scores": {
                "mandatory_skills": mandatory_score,
                "preferred_skills": preferred_score,
                "experience_relevance": exp_relevance_score,
                "tenure": tenure_score,
                "responsibilities": resp_score,
                "education": edu_score,
                "domain": domain_score
            },
            "skills_breakdown": {
                "mandatory_matched": [asdict(e) for e in mandatory_evidence],
                "mandatory_missing": mandatory_missing,
                "preferred_matched": [asdict(e) for e in preferred_evidence],
                "preferred_missing": preferred_missing,
                "match_pct": mandatory_score
            },
            "responsibilities_breakdown": {
                "covered": resp_covered,
                "uncovered": resp_uncovered,
                "coverage_pct": resp_score
            },
            "education_breakdown": edu_report,
            "domain_breakdown": {
                "detected_domains": jd_reqs["detected_domains"],
                "matched_domains": matched_domains,
                "missing_domains": missing_domains,
                "match_pct": domain_score
            },
            "evidence_ledger": evidence_ledger,
            "tenure_report": tenure_report,
            "missing_information_report": {
                "missing_dates": not tenure_report["experience_duration_known"],
                "missing_education": not cand_profile["education_entries_count"],
                "notes": [g.reason for g in gates if g.status == "unverifiable"]
            },
            "recommendations": recommendations
        }
