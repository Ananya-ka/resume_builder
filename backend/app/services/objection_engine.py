import re
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum


class GapBucket(str, Enum):
    UNEXPRESSED = "unexpressed"        # Bucket A: Found in catalog/background, omitted from resume
    TRANSFERABLE = "transferable"      # Bucket B: Relevant adjacent competency, needs honest framing
    TRUE_DEFICIT = "true_deficit"      # Bucket C: Missing competency, requires deliberate proof
    HARD_CONSTRAINT = "hard_constraint"# Bucket D: Legal, degree, visa, or mandatory license requirement


class EvidenceConfidence(str, Enum):
    USER_STATED = "user_stated"                # Tier 1: Claimed in conversation without external proof
    DOCUMENT_SUPPORTED = "document_supported"  # Tier 2: Consistent across multiple uploaded resumes/records
    ARTIFACT_BACKED = "artifact_backed"        # Tier 3: Linked repository, PR, demo, or spec
    MEASUREMENT_BACKED = "measurement_backed"  # Tier 4: Quantified metric with baseline & measurement methodology


class ProofTier(str, Enum):
    CONCEPTUAL = "conceptual"          # Syntax, basic SDK, tutorial comprehension
    IMPLEMENTATION = "implementation"  # End-to-end working service with tests & error handling
    OPERATIONAL = "operational"        # High scale, SLA, incident response, team collaboration


class ObjectionEngine:
    """
    Evidence-grounded Hiring Objection Engine.
    Identifies recruiter/manager hesitations as testable hypotheses grounded in evidence.
    """

    # Common hard constraint keywords
    HARD_CONSTRAINT_PATTERNS = [
        (r"\b(?:us citizenship|u\.s\. citizen|security clearance|top secret|ts/sci)\b", "Security Clearance / Citizenship"),
        (r"\b(?:phd|master'?s|bachelor'?s|degree in computer science)\b", "Mandatory Academic Degree"),
        (r"\b(?:pe license|cpa|pmp|bar admission|licensed attorney)\b", "Mandatory Professional License"),
        (r"\b(?:must be legally authorized to work|no visa sponsorship|greencard|permanent resident)\b", "Work Authorization / Visa"),
    ]

    # Adjacent technology mappings for Bucket B (Transferable)
    ADJACENT_DOMAINS = {
        "kafka": ["rabbitmq", "sqs", "sns", "redis streams", "pubsub", "activemq", "pulsar", "zeromq"],
        "kubernetes": ["docker", "docker compose", "ecs", "nomad", "helm", "openshift", "containerization"],
        "aws": ["gcp", "azure", "cloud computing", "digitalocean", "openstack"],
        "gcp": ["aws", "azure", "google cloud platform"],
        "azure": ["aws", "gcp"],
        "graphql": ["rest", "restful apis", "grpc", "openapi", "trpc"],
        "grpc": ["rest", "graphql", "protobuf"],
        "postgresql": ["mysql", "sqlite", "mariadb", "sql server", "oracle", "sql"],
        "mysql": ["postgresql", "sqlite", "mariadb", "sql"],
        "redis": ["memcached", "caching", "in-memory datastore"],
        "react": ["vue", "angular", "svelte", "next.js", "frontend development"],
        "vue": ["react", "angular", "svelte"],
        "fastapi": ["flask", "django", "tornado", "aiohttp", "express", "gin"],
        "django": ["fastapi", "flask", "ruby on rails", "spring boot", "express"],
        "pytorch": ["tensorflow", "keras", "jax", "scikit-learn", "deep learning"],
        "tensorflow": ["pytorch", "keras", "jax"],
        "rag": ["vector database", "semantic search", "embeddings", "faiss", "pinecone", "chroma", "langchain"],
        "vector database": ["pinecone", "chroma", "faiss", "weaviate", "qdrant", "milvus", "rag"],
        "spark": ["hadoop", "flink", "big data", "pyspark", "databricks"],
        "golang": ["rust", "c++", "c", "java", "backend concurrency"],
        "rust": ["golang", "c++", "c", "systems programming"],
    }

    def analyze(
        self,
        candidate_profile: Dict[str, Any],
        reconstructed_resume: Dict[str, Any],
        job_description: Dict[str, Any],
        all_catalog_evidence: Optional[List[Dict[str, Any]]] = None,
        mode: str = "advance"
    ) -> Dict[str, Any]:
        """
        Runs comprehensive objection simulation across 3 hiring personas:
        - Recruiter Screen (6-second scan, hard eligibility, YOE floor)
        - Hiring Manager (Impact, scope, team leadership vs individual execution)
        - Technical Interviewer (Depth, architectural trade-offs, production reliability)
        """
        jd_text = (job_description.get("raw_text") or "").lower()
        required_skills = [s.strip().lower() for s in (job_description.get("required_skills") or []) if s.strip()]
        preferred_skills = [s.strip().lower() for s in (job_description.get("preferred_skills") or []) if s.strip()]
        req_years = float(job_description.get("experience_years") or 0.0)

        # 1. Map candidate text
        resume_text, resume_bullets = self._extract_resume_content(reconstructed_resume)
        catalog_text = self._extract_catalog_content(all_catalog_evidence or [])
        profile_skills = set(s.lower() for s in candidate_profile.get("skills", []))
        education_list = candidate_profile.get("education", [])

        # 2. Identify Hard Constraints (Bucket D)
        hard_constraints = self._check_hard_constraints(jd_text, candidate_profile, education_list)

        # 3. Categorize Gaps into 4 Buckets
        all_target_terms = list(dict.fromkeys(required_skills + preferred_skills))
        gap_classifications = []
        dual_axis_map = []

        for term in all_target_terms:
            is_required = term in required_skills
            relevance_score = 90.0 if is_required else 65.0
            
            # Check presence in active resume
            in_resume = self._term_matches(term, resume_text)
            in_catalog = in_resume or self._term_matches(term, catalog_text) or (term in profile_skills)

            # Determine confidence tier
            confidence_tier, confidence_score = self._determine_confidence(
                term, in_resume, in_catalog, resume_bullets, all_catalog_evidence or []
            )

            if in_resume:
                bucket = GapBucket.UNEXPRESSED if confidence_tier == EvidenceConfidence.USER_STATED else None
            elif in_catalog:
                bucket = GapBucket.UNEXPRESSED
            else:
                # Check for transferable adjacent technology (Bucket B)
                transferable_match = self._find_transferable_match(term, resume_text + " " + catalog_text)
                if transferable_match:
                    bucket = GapBucket.TRANSFERABLE
                else:
                    bucket = GapBucket.TRUE_DEFICIT

            gap_item = {
                "term": term,
                "is_required": is_required,
                "in_resume": in_resume,
                "in_catalog": in_catalog,
                "bucket": bucket.value if bucket else "verified_present",
                "confidence_tier": confidence_tier.value,
                "confidence_score": confidence_score,
                "relevance_score": relevance_score,
                "transferable_from": transferable_match if bucket == GapBucket.TRANSFERABLE else None,
                "suggested_proof_tier": self._recommend_proof_tier(term) if bucket == GapBucket.TRUE_DEFICIT else None,
            }
            gap_classifications.append(gap_item)
            dual_axis_map.append({
                "name": term,
                "evidence_confidence": confidence_score,
                "hiring_relevance": relevance_score,
                "bucket": gap_item["bucket"],
                "is_required": is_required
            })

        # 4. Generate 3-Persona Objection Hypotheses
        objections = []
        
        # Persona 1: Recruiter Screen
        objections.extend(self._simulate_recruiter_screen(
            job_description, req_years, hard_constraints, gap_classifications, reconstructed_resume, mode
        ))

        # Persona 2: Hiring Manager
        objections.extend(self._simulate_hiring_manager(
            job_description, reconstructed_resume, resume_bullets, gap_classifications, mode
        ))

        # Persona 3: Technical Interviewer
        objections.extend(self._simulate_technical_interviewer(
            job_description, resume_bullets, gap_classifications, mode
        ))

        return {
            "mode": mode,
            "hard_constraints": hard_constraints,
            "objections": objections,
            "gap_classifications": gap_classifications,
            "dual_axis_map": dual_axis_map,
            "summary": {
                "mode": mode,
                "total_objections": len(objections),
                "high_priority_objections": len([o for o in objections if o["confidence"] == "High"]),
                "hard_constraints_count": len(hard_constraints),
                "unexpressed_gaps": len([g for g in gap_classifications if g["bucket"] == GapBucket.UNEXPRESSED.value]),
                "transferable_gaps": len([g for g in gap_classifications if g["bucket"] == GapBucket.TRANSFERABLE.value]),
                "true_deficits": len([g for g in gap_classifications if g["bucket"] == GapBucket.TRUE_DEFICIT.value]),
            }
        }

    def _simulate_recruiter_screen(
        self,
        jd: Dict[str, Any],
        req_years: float,
        hard_constraints: List[Dict[str, Any]],
        gaps: List[Dict[str, Any]],
        reconstructed_resume: Dict[str, Any],
        mode: str = "advance"
    ) -> List[Dict[str, Any]]:
        objections = []
        
        # Hard constraints first
        for hc in hard_constraints:
            objections.append({
                "id": f"obj_rec_{len(objections) + 1}",
                "persona": "Recruiter Screen",
                "jd_trigger": hc["requirement"],
                "evidence_state": hc["current_state"],
                "hypothesis": f"Recruiter will immediately filter out this profile due to unverified {hc['type'].lower()}.",
                "confidence": "High",
                "gap_bucket": GapBucket.HARD_CONSTRAINT.value,
                "resolution_action": {
                    "type": "Explicit Eligibility Declaration",
                    "action": hc["action_guidance"],
                    "cannot_fix_via_rewrite": True
                }
            })

        # Launch mode early-career objection
        if mode == "launch":
            objections.append({
                "id": f"obj_rec_{len(objections) + 1}",
                "persona": "Recruiter Screen",
                "jd_trigger": "Candidate is applying via CareerProof Launch (0–2 YOE profile)",
                "evidence_state": "Projects may be viewed as non-commercial academic exercises or tutorial clones",
                "hypothesis": "Recruiter may hesitate that portfolio projects are boilerplate clones without real production or deployment rigor.",
                "confidence": "High",
                "gap_bucket": GapBucket.TRUE_DEFICIT.value if not any(g["bucket"] == GapBucket.UNEXPRESSED.value for g in gaps) else GapBucket.UNEXPRESSED.value,
                "resolution_action": {
                    "type": "Verifiable Production Proof",
                    "action": "Include live deployed application URLs, public GitHub repository commits, and k6/Locust load benchmark figures to prove non-tutorial authenticity."
                }
            })

        # Required years floor
        years_found = self._estimate_resume_years(reconstructed_resume)
        if req_years > 0 and years_found < req_years:
            deficit = round(req_years - years_found, 1)
            objections.append({
                "id": f"obj_rec_{len(objections) + 1}",
                "persona": "Recruiter Screen",
                "jd_trigger": f"Position requires {req_years}+ years of experience",
                "evidence_state": f"Calculated duration from resume text shows ~{years_found} years",
                "hypothesis": f"Recruiter may screen out resume on the 6-second scan assuming seniority deficit ({deficit} years under requirement).",
                "confidence": "High" if deficit >= 2 else "Medium",
                "gap_bucket": GapBucket.UNEXPRESSED.value if deficit <= 1.5 else GapBucket.HARD_CONSTRAINT.value,
                "resolution_action": {
                    "type": "Experience Horizon Clarification",
                    "action": "Ensure all relevant internships, contract work, or founding experience have clear start/end dates so full tenure is transparently visible."
                }
            })

        # Required skills completely absent
        missing_reqs = [g["term"] for g in gaps if g["is_required"] and g["bucket"] in (GapBucket.TRUE_DEFICIT.value, GapBucket.UNEXPRESSED.value)]
        if missing_reqs:
            top_missing = missing_reqs[:3]
            objections.append({
                "id": f"obj_rec_{len(objections) + 1}",
                "persona": "Recruiter Screen",
                "jd_trigger": f"Required stack includes: {', '.join(top_missing)}",
                "evidence_state": f"Terms are absent from the active resume text",
                "hypothesis": f"Recruiter scanning for core buzzwords won't see {', '.join(top_missing)} and will assume zero exposure.",
                "confidence": "High",
                "gap_bucket": GapBucket.UNEXPRESSED.value if any(g["in_catalog"] for g in gaps if g["term"] in top_missing) else GapBucket.TRUE_DEFICIT.value,
                "resolution_action": {
                    "type": "Targeted Discovery / Proof",
                    "action": f"If you have used {top_missing[0]}, incorporate the verified project into the resume. If not, do not fabricate it."
                }
            })

        return objections

    def _simulate_hiring_manager(
        self,
        jd: Dict[str, Any],
        reconstructed_resume: Dict[str, Any],
        resume_bullets: List[str],
        gaps: List[Dict[str, Any]],
        mode: str = "advance"
    ) -> List[Dict[str, Any]]:
        objections = []
        
        # Launch mode team SDLC objection
        if mode == "launch":
            objections.append({
                "id": f"obj_hm_{len(objections) + 1}",
                "persona": "Hiring Manager",
                "jd_trigger": "Values fast onboarding and professional team SDLC collaboration",
                "evidence_state": "Profile lacks evidence of enterprise team git collaboration, code review, or agile sprint workflows",
                "hypothesis": "Hiring manager wonders whether you can integrate into a professional agile engineering team without high mentoring overhead.",
                "confidence": "Medium",
                "gap_bucket": GapBucket.UNEXPRESSED.value,
                "resolution_action": {
                    "type": "Collaborative SDLC Highlighting",
                    "action": "Highlight any open-source PRs, collaborative projects, pair programming, or documented CI/CD automated deployment workflows."
                }
            })

        # Check for individual ownership ambiguity
        passive_bullets = [b for b in resume_bullets if re.search(r"\b(?:assisted with|participated in|helped|contributed to|involved in|worked with team to)\b", b.lower())]
        if passive_bullets:
            objections.append({
                "id": f"obj_hm_{len(objections) + 1}",
                "persona": "Hiring Manager",
                "jd_trigger": "Expects autonomous technical ownership and individual contribution",
                "evidence_state": f"Found phrasing suggesting secondary support: '{passive_bullets[0][:80]}...'",
                "hypothesis": "Hiring manager will hesitate over your individual impact, wondering if you merely assisted while senior engineers did the heavy lifting.",
                "confidence": "Medium",
                "gap_bucket": GapBucket.UNEXPRESSED.value,
                "resolution_action": {
                    "type": "Ownership Clarification",
                    "action": "Specify the exact component, module, or schema decision you personally authored and verified."
                }
            })

        # Check for missing quantified impact metrics
        quantified_bullets = [b for b in resume_bullets if re.search(r"\d+[%kKmMbB]?|\b(?:increased|reduced|decreased|accelerated|optimized by)\b", b.lower())]
        quantified_ratio = (len(quantified_bullets) / len(resume_bullets)) if resume_bullets else 0
        if quantified_ratio < 0.35 and len(resume_bullets) >= 4:
            objections.append({
                "id": f"obj_hm_{len(objections) + 1}",
                "persona": "Hiring Manager",
                "jd_trigger": "Values data-driven delivery, efficiency improvements, and business outcomes",
                "evidence_state": f"Only {round(quantified_ratio * 100)}% of bullets include measurable metrics or concrete outcomes",
                "hypothesis": "Manager will see feature execution but lack evidence that your code moved business or latency metrics.",
                "confidence": "Medium",
                "gap_bucket": GapBucket.UNEXPRESSED.value,
                "resolution_action": {
                    "type": "Impact Metric Anchor",
                    "action": "Add baseline vs measured outcome numbers (e.g., latency, throughput, cost, query time, users served) where truthful records exist."
                }
            })

        # Transferable skills check
        transferable = [g for g in gaps if g["bucket"] == GapBucket.TRANSFERABLE.value]
        if transferable:
            first_t = transferable[0]
            objections.append({
                "id": f"obj_hm_{len(objections) + 1}",
                "persona": "Hiring Manager",
                "jd_trigger": f"Role specifies {first_t['term'].upper()}",
                "evidence_state": f"You have strong adjacent experience with {first_t['transferable_from'].upper()} but not native {first_t['term'].upper()}",
                "hypothesis": f"Manager will question whether your {first_t['transferable_from']} experience transfers seamlessly to their {first_t['term']} stack without onboarding friction.",
                "confidence": "Medium",
                "gap_bucket": GapBucket.TRANSFERABLE.value,
                "resolution_action": {
                    "type": "Transferable Architecture Framing",
                    "action": f"Frame your {first_t['transferable_from']} architecture around core engineering patterns (concurrency, data models, state) and prepare to speak to how they map to {first_t['term']}."
                }
            })

        return objections

    def _simulate_technical_interviewer(
        self,
        jd: Dict[str, Any],
        resume_bullets: List[str],
        gaps: List[Dict[str, Any]],
        mode: str = "advance"
    ) -> List[Dict[str, Any]]:
        objections = []

        # Launch mode foundational understanding objection
        if mode == "launch":
            objections.append({
                "id": f"obj_tech_{len(objections) + 1}",
                "persona": "Technical Bar-Raiser",
                "jd_trigger": "Underlying CS fundamentals and runtime execution comprehension",
                "evidence_state": "Bullets focus on using high-level frameworks and libraries",
                "hypothesis": "Interviewer will grill on foundational execution (e.g. event loop, memory leaks, data structures, network protocols) to ensure you didn't just copy boilerplate.",
                "confidence": "Medium",
                "gap_bucket": GapBucket.UNEXPRESSED.value,
                "resolution_action": {
                    "type": "Foundational Defense Preparation",
                    "action": "Be ready to explain how your framework runs under the hood, how async I/O operates, and how you debugged runtime exceptions."
                }
            })

        # Check for scale/failure mode depth
        advanced_reliability_terms = re.findall(
            r"\b(?:concurrency|latency|throughput|caching|fault tolerance|retry|partition|failover|clustering|load balancing|sharding|distributed|deadlock)\b",
            " ".join(resume_bullets).lower()
        )
        if len(advanced_reliability_terms) < 2 and len(resume_bullets) >= 3:
            objections.append({
                "id": f"obj_tech_{len(objections) + 1}",
                "persona": "Technical Bar-Raiser",
                "jd_trigger": "Core engineering focus on production reliability and architecture trade-offs",
                "evidence_state": "Bullets focus on API creation/happy path with few references to reliability, caching, or latency bounds",
                "hypothesis": "Interviewer will test whether you have dealt with real-world edge cases (concurrency bottlenecks, retry backoff, out-of-memory limits).",
                "confidence": "Medium",
                "gap_bucket": GapBucket.UNEXPRESSED.value,
                "resolution_action": {
                    "type": "Failure-Mode Defense Preparation",
                    "action": "Be ready to explain how your services handled downstream failures, timeouts, and boundary validation in production."
                }
            })

        # Check for True Deficits requiring proof building
        deficits = [g for g in gaps if g["bucket"] == GapBucket.TRUE_DEFICIT.value and g["is_required"]]
        if deficits:
            target_def = deficits[0]
            proof_tier = target_def.get("suggested_proof_tier", ProofTier.IMPLEMENTATION.value)
            objections.append({
                "id": f"obj_tech_{len(objections) + 1}",
                "persona": "Technical Bar-Raiser",
                "jd_trigger": f"Must demonstrate competency in {target_def['term'].upper()}",
                "evidence_state": f"Zero historical record or adjacent exposure found in profile for {target_def['term']}",
                "hypothesis": f"Interviewer will immediately uncover that you have not worked hands-on with {target_def['term']}.",
                "confidence": "High",
                "gap_bucket": GapBucket.TRUE_DEFICIT.value,
                "resolution_action": {
                    "type": f"Minimum Proof Building ({proof_tier.capitalize()} Tier)",
                    "action": f"Build a focused, end-to-end {target_def['term']} project demonstrating {proof_tier} competence with working test coverage. Never present it as past corporate tenure."
                }
            })

        return objections

    def _determine_confidence(
        self,
        term: str,
        in_resume: bool,
        in_catalog: bool,
        resume_bullets: List[str],
        catalog_items: List[Dict[str, Any]]
    ) -> Tuple[EvidenceConfidence, float]:
        """
        Determines evidence confidence tier (Tier 1-4) and normalized confidence score (0-100).
        """
        if not in_catalog and not in_resume:
            return EvidenceConfidence.USER_STATED, 10.0

        all_text = " ".join(resume_bullets) + " " + " ".join(str(c.get("data", {})) for c in catalog_items)
        term_matches = [b for b in resume_bullets if self._term_matches(term, b)]

        # Check for Measurement-Backed (Tier 4)
        for b in term_matches:
            if re.search(r"\d+(?:\.\d+)?%|\b(?:reduced by|increased by|latency from \d+|p99|qps|rps|benchmark)\b", b.lower()):
                return EvidenceConfidence.MEASUREMENT_BACKED, 95.0

        # Check for Artifact-Backed (Tier 3)
        if re.search(r"github\.com|gitlab\.com|http[s]?://|pr #|repository|open source", all_text.lower()):
            return EvidenceConfidence.ARTIFACT_BACKED, 80.0

        # Check for Document-Supported (Tier 2)
        if len(term_matches) >= 2 or (in_resume and in_catalog):
            return EvidenceConfidence.DOCUMENT_SUPPORTED, 65.0

        # User-Stated (Tier 1)
        return EvidenceConfidence.USER_STATED, 40.0

    def _find_transferable_match(self, term: str, text: str) -> Optional[str]:
        adjacent = self.ADJACENT_DOMAINS.get(term.lower(), [])
        for candidate in adjacent:
            if self._term_matches(candidate, text):
                return candidate
        return None

    def _recommend_proof_tier(self, term: str) -> str:
        # High-complexity distributed systems or architecture items need Implementation or Operational proof
        if term in {"kubernetes", "kafka", "distributed systems", "spark", "system design"}:
            return ProofTier.IMPLEMENTATION.value
        # Programming languages or toolkits can start with Conceptual or Implementation
        return ProofTier.IMPLEMENTATION.value

    def _check_hard_constraints(
        self,
        jd_text: str,
        candidate_profile: Dict[str, Any],
        education_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        hard_constraints = []
        for pattern, label in self.HARD_CONSTRAINT_PATTERNS:
            match = re.search(pattern, jd_text)
            if match:
                matched_phrase = match.group(0)
                # Check if candidate has degree when degree is requested
                has_substantiation = False
                if "degree" in label.lower() and education_list:
                    has_substantiation = True
                
                if not has_substantiation:
                    hard_constraints.append({
                        "type": label,
                        "requirement": f"Job requirement explicitly mentions: '{matched_phrase}'",
                        "current_state": "No explicit matching verification found in your profile records",
                        "action_guidance": f"Verify whether you legally/institutionally satisfy '{matched_phrase}'. Resume edits cannot replace hard compliance requirements."
                    })
        return hard_constraints

    def _extract_resume_content(self, reconstructed: Dict[str, Any]) -> Tuple[str, List[str]]:
        parts = []
        bullets = []
        for exp in reconstructed.get("experience", []):
            parts.append(exp.get("company", ""))
            parts.append(exp.get("role", ""))
            b_list = exp.get("bullets", [])
            parts.extend(b_list)
            bullets.extend(b_list)
        for proj in reconstructed.get("projects", []):
            parts.append(proj.get("name", ""))
            b_list = proj.get("bullets", [])
            parts.extend(b_list)
            bullets.extend(b_list)
        parts.extend(reconstructed.get("skills", []))
        return " ".join(parts).lower(), bullets

    def _extract_catalog_content(self, catalog: List[Dict[str, Any]]) -> str:
        parts = []
        for item in catalog:
            data = item.get("data", {})
            parts.append(data.get("content", ""))
            parts.append(data.get("company", ""))
            parts.append(data.get("role", ""))
            parts.append(data.get("ownership", ""))
        return " ".join(parts).lower()

    def _term_matches(self, term: str, text: str) -> bool:
        pattern = r"\b" + re.escape(term.lower()) + r"\b"
        if not re.match(r"^\w", term) or not re.search(r"\w$", term):
            pattern = re.escape(term.lower())
        return bool(re.search(pattern, text.lower()))

    def _estimate_resume_years(self, reconstructed: Dict[str, Any]) -> float:
        text, _ = self._extract_resume_content(reconstructed)
        years_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:\+)?\s*years?", text)
        if years_matches:
            return max(float(y) for y in years_matches)
        # Estimate based on experience entries
        return len(reconstructed.get("experience", [])) * 1.5
