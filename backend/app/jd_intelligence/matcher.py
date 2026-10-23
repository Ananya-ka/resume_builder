"""Evidence-to-Requirement Mapping Engine.

Matches structured job requirements against verified claims in the Universal Evidence Catalog.
Distinguishes direct, transferable, missing, and unresolved evidence with transparent reasoning.
"""
import re
from typing import Dict, Any, List, Optional, Tuple, Set
from app.services.ats_matcher import CANONICAL_SYNONYMS, _ALIAS_TO_CANONICAL, _stem_token, RESPONSIBILITY_SYNONYM_GROUPS, _tokens_semantically_match
from app.catalog.models import CatalogClaim, CatalogSource, ClaimSource

# Structured transferability clusters: relates sister technologies with architectural parity
TRANSFERABLE_CLUSTERS = {
    "relational_databases": {
        "family": "Relational Databases",
        "members": {"postgresql", "mysql", "sql", "sqlite", "mariadb", "oracle"},
        "note": "Core SQL, relational schema design, indexing, transactions, and query optimization directly transfer."
    },
    "cloud_platforms": {
        "family": "Major Cloud Platforms",
        "members": {"aws", "gcp", "azure"},
        "note": "Infrastructure primitives (IAM, VPC, object storage, managed compute, container registries) share deep operational parity."
    },
    "frontend_frameworks": {
        "family": "Modern Component Frameworks",
        "members": {"react", "next.js", "vue", "angular", "svelte"},
        "note": "Component lifecycles, virtual DOM rendering, state management, and declarative UI patterns transfer directly."
    },
    "python_backends": {
        "family": "Python Web Frameworks",
        "members": {"fastapi", "flask", "django"},
        "note": "Python asynchronous concurrency, WSGI/ASGI patterns, ORM integration, and RESTful API architecture are directly applicable."
    },
    "message_brokers": {
        "family": "Distributed Event & Messaging Brokers",
        "members": {"kafka", "rabbitmq", "sqs", "pubsub"},
        "note": "Publish/subscribe, event streaming, consumer offset management, and decoupling architectures share common design patterns."
    },
    "container_orchestration": {
        "family": "Containerization & Orchestration",
        "members": {"kubernetes", "docker", "docker-compose"},
        "note": "Container packaging, networking, resource declarations, and microservice deployment transfer readily."
    },
    "in_memory_cache": {
        "family": "In-Memory Caching",
        "members": {"redis", "memcached"},
        "note": "In-memory key-value caching, TTL eviction strategies, and distributed caching topologies are equivalent."
    }
}


def find_transferable_match(target_term: str, candidate_technologies: Set[str]) -> Optional[Dict[str, str]]:
    """Checks if a target term has a transferable peer among candidate technologies."""
    target_clean = _ALIAS_TO_CANONICAL.get(target_term.lower(), target_term.lower())
    for cluster_id, cluster in TRANSFERABLE_CLUSTERS.items():
        if target_clean in cluster["members"]:
            for cand_tech in candidate_technologies:
                cand_clean = _ALIAS_TO_CANONICAL.get(cand_tech.lower(), cand_tech.lower())
                if cand_clean in cluster["members"] and cand_clean != target_clean:
                    return {
                        "cluster": cluster["family"],
                        "target_technology": target_clean,
                        "candidate_technology": cand_clean,
                        "rationale": f"Candidate demonstrates {cand_clean.upper()} experience, transferring to {target_clean.upper()} under {cluster['family']}: {cluster['note']}"
                    }
    return None


class EvidenceRequirementMatcher:
    """Evaluates candidate evidence against job requirements."""

    def evaluate_requirement(
        self,
        requirement: Dict[str, Any],
        catalog_claims: List[CatalogClaim],
        open_conflict_claim_ids: Set[int]
    ) -> Dict[str, Any]:
        """Classifies a single requirement into direct, transferable, missing, or unresolved match."""
        category = requirement.get("category", "")
        req_terms = [t.lower() for t in requirement.get("normalized_terms", [])]
        req_title = requirement.get("title", "")
        is_mandatory = requirement.get("is_mandatory", True)

        # Separate approved claims from pending / rejected
        approved_claims = [c for c in catalog_claims if c.approval == "approved"]
        pending_claims = [c for c in catalog_claims if c.approval == "pending" and c.id not in open_conflict_claim_ids]
        conflicted_claims = [c for c in catalog_claims if c.id in open_conflict_claim_ids]

        # 1. Evaluate Direct Matches among Approved Claims
        direct_matches = []
        for claim in approved_claims:
            if self._claim_matches_requirement(claim, requirement):
                direct_matches.append(claim)

        if direct_matches:
            # Determine highest documented depth
            depths = [c.data.get("depth", "unspecified") for c in direct_matches]
            best_depth = "professional" if "professional" in depths else (depths[0] if depths else "unspecified")
            return {
                "status": "direct",
                "matched_claim_ids": [c.id for c in direct_matches],
                "transferable_details": None,
                "candidate_depth": best_depth,
                "score_rationale": f"Candidate has {len(direct_matches)} approved, source-verified claim(s) demonstrating direct competence in '{req_title}'.",
                "clarification_question": None
            }

        # 2. Check for Transferable Matches among Approved Claims
        # Collect all approved candidate technologies
        approved_techs = set()
        for c in approved_claims:
            for t in c.data.get("technologies", []):
                approved_techs.add(t)
            if c.data.get("kind") == "skill":
                approved_techs.add(c.data.get("text", ""))

        for target_term in req_terms:
            transfer = find_transferable_match(target_term, approved_techs)
            if transfer:
                # Find the claims supporting the transferable technology
                supporting_claims = [
                    c for c in approved_claims
                    if any(t.lower() == transfer["candidate_technology"] for t in c.data.get("technologies", []))
                    or (c.data.get("kind") == "skill" and c.data.get("text", "").lower() == transfer["candidate_technology"])
                ]
                return {
                    "status": "transferable",
                    "matched_claim_ids": [c.id for c in supporting_claims],
                    "transferable_details": transfer,
                    "candidate_depth": supporting_claims[0].data.get("depth", "unspecified") if supporting_claims else "unspecified",
                    "score_rationale": transfer["rationale"],
                    "clarification_question": {
                        "prompt": f"This position requires {transfer['target_technology'].upper()}. You have verified experience in {transfer['candidate_technology'].upper()}. Have you also worked with {transfer['target_technology'].upper()} or applied your background to it?",
                        "benefit": "Enables highlighting transferable foundational knowledge while honestly disclosing tool familiarity."
                    }
                }

        # 3. Check for Unresolved / Conflicted / Pending Matches
        unresolved_claims = []
        for claim in conflicted_claims + pending_claims:
            if self._claim_matches_requirement(claim, requirement):
                unresolved_claims.append(claim)

        if unresolved_claims:
            is_conflicted = any(c.id in open_conflict_claim_ids for c in unresolved_claims)
            reason = (
                f"Candidate has matching evidence for '{req_title}', but it has open conflicting sources requiring candidate disambiguation."
                if is_conflicted else
                f"Candidate has extracted evidence for '{req_title}' in the Evidence Catalog, but it remains pending candidate approval."
            )
            return {
                "status": "unresolved",
                "matched_claim_ids": [c.id for c in unresolved_claims],
                "transferable_details": None,
                "candidate_depth": None,
                "score_rationale": reason,
                "clarification_question": {
                    "prompt": f"Review and approve your evidence record for '{req_title}' in the Evidence Vault to apply it to this qualification.",
                    "benefit": "Resolving pending claims provides defensible verified proof for this requirement."
                }
            }

        # 4. Missing Evidence
        question = None
        if is_mandatory:
            question = {
                "prompt": f"This role explicitly requires experience with '{req_title}'. Do you have unlisted projects, employment, or academic work involving this requirement?",
                "benefit": "Identifies omissions from uploaded resumes before drafting, preventing false negative gaps."
            }
        elif requirement.get("is_ambiguous"):
            question = {
                "prompt": f"The job description mentions '{requirement.get('quote')}'. How do you interpret this qualification based on your past accomplishments?",
                "benefit": "Clarifies ambiguous job expectations with concrete personal examples."
            }

        return {
            "status": "missing",
            "matched_claim_ids": [],
            "transferable_details": None,
            "candidate_depth": None,
            "score_rationale": f"No approved or pending evidence in the Evidence Catalog demonstrates '{req_title}'.",
            "clarification_question": question
        }

    def _claim_matches_requirement(self, claim: CatalogClaim, requirement: Dict[str, Any]) -> bool:
        """Determines if a catalog claim grounds a specific requirement."""
        req_category = requirement.get("category", "")
        req_terms = [t.lower() for t in requirement.get("normalized_terms", [])]
        req_title_lower = requirement.get("title", "").lower()
        req_quote_lower = requirement.get("quote", "").lower()

        claim_data = claim.data
        claim_text_lower = claim_data.get("text", "").lower()
        claim_kind = claim_data.get("kind", "")
        claim_techs = [t.lower() for t in claim_data.get("technologies", [])]

        # A. Skills matching
        if req_category in {"mandatory_skill", "preferred_skill"}:
            for term in req_terms:
                canonical_term = _ALIAS_TO_CANONICAL.get(term, term)
                # 1. Match claim technologies
                for tech in claim_techs:
                    if _ALIAS_TO_CANONICAL.get(tech, tech) == canonical_term:
                        return True
                # 2. Match claim text directly
                if re.search(rf"\b{re.escape(term)}\b", claim_text_lower) or re.search(rf"\b{re.escape(canonical_term)}\b", claim_text_lower):
                    return True
                # 3. Match synonyms
                for syn in CANONICAL_SYNONYMS.get(canonical_term, []):
                    if re.search(rf"\b{re.escape(syn)}\b", claim_text_lower):
                        return True

        # B. Responsibility matching (Action verbs and stems)
        elif req_category == "responsibility":
            resp_tokens = [w for w in re.findall(r"\b[a-z0-9+#-]{3,}\b", req_quote_lower) if w not in {"with", "that", "this", "from", "will", "have", "your", "across", "team", "work"}]
            claim_tokens = [w for w in re.findall(r"\b[a-z0-9+#-]{3,}\b", claim_text_lower) if w not in {"with", "that", "this", "from", "will", "have", "your", "across", "team", "work"}]
            if resp_tokens and claim_tokens:
                overlap = sum(1 for rw in resp_tokens if any(_tokens_semantically_match(rw, bw) for bw in claim_tokens))
                if overlap >= 2 or (len(resp_tokens) <= 3 and overlap >= 1):
                    return True

        # C. Education matching
        elif req_category == "education":
            if claim_kind == "education":
                for term in req_terms:
                    if term in claim_text_lower:
                        return True

        # D. Domain matching
        elif req_category == "domain":
            for term in req_terms:
                if term in claim_text_lower or term in claim_data.get("association", "").lower():
                    return True

        # E. Experience / Tenure matching
        elif req_category == "experience":
            if claim_kind in {"experience", "dates"}:
                return True

        return False
