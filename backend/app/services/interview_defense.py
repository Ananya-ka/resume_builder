import re
from typing import Dict, Any, List, Optional
from enum import Enum


class ProofTier(str, Enum):
    CONCEPTUAL = "conceptual"
    IMPLEMENTATION = "implementation"
    OPERATIONAL = "operational"


class InterviewDefenseEngine:
    """
    Generates personalized interview defense cards and minimum proof blueprints
    grounded directly in the candidate's verified evidence catalog.
    """

    # Common trade-offs and probes mapped to technical patterns
    ARCHITECTURAL_PATTERNS = [
        (
            r"\b(?:rag|vector|embedding|semantic search|retrieval)\b",
            "Retrieval Architecture & Chunking",
            "Why did you choose this vector index/chunking strategy over keyword search (BM25) or hybrid search?",
            "How did you handle embedding latency, out-of-vocabulary terms, and chunk boundary context loss?",
            "Do not claim you fine-tuned foundational models if you only implemented vector retrieval with prompt augmentation."
        ),
        (
            r"\b(?:redis|memcached|caching|cache)\b",
            "Caching Strategy & Invalidation",
            "What eviction policy (LRU/LFU) did you configure and how did you guarantee cache coherency under concurrent writes?",
            "How did your system prevent cache stampedes / thundering herds when keys expired?",
            "Do not claim distributed multi-region replication if Redis was deployed as a single VPC instance."
        ),
        (
            r"\b(?:kafka|rabbitmq|sqs|event-driven|queue|pubsub|streaming)\b",
            "Event-Driven Delivery Guarantees",
            "Did your pipeline provide at-least-once or exactly-once processing, and how were duplicate messages handled?",
            "How did consumers manage backpressure and poison pill message dead-lettering?",
            "Do not claim you managed a multi-broker cluster with partition rebalancing if you only authored producer/consumer application code."
        ),
        (
            r"\b(?:fastapi|flask|django|express|rest|api|grpc)\b",
            "API Reliability & Concurrency",
            "How did your services handle downstream connection pool exhaustion and slow client timeouts?",
            "What rate limiting, schema validation, and error serialization standards did you enforce?",
            "Do not claim 99.99% high availability unless you had automated multi-AZ failover and SLA monitoring in place."
        ),
        (
            r"\b(?:postgresql|mysql|database|sql|indexing)\b",
            "Data Model & Query Optimization",
            "What indexes (B-tree, GIN, composite) did you create, and how did you verify query plans using EXPLAIN ANALYZE?",
            "How did you handle database migration locks and long-running transaction deadlocks?",
            "Do not claim zero-downtime blue/green schema migrations unless you used a dual-write expansion phase."
        ),
        (
            r"\b(?:docker|kubernetes|k8s|container|helm)\b",
            "Container Orchestration & Runtime",
            "How did you manage resource requests/limits, health probes (liveness/readiness), and graceful SIGTERM termination?",
            "What was your container image build strategy (multi-stage builds, non-root users)?",
            "Do not claim cluster administration if your role was limited to deploying Helm charts to an existing namespace."
        )
    ]

    def generate_defense_cards(
        self,
        verified_bullets: List[Dict[str, Any]],
        candidate_profile: Dict[str, Any],
        job_description: Dict[str, Any],
        mode: str = "advance"
    ) -> List[Dict[str, Any]]:
        """
        Generates structured defense cards for each included resume bullet.
        """
        cards = []
        for i, b in enumerate(verified_bullets):
            if not b.get("included", True):
                continue

            bullet_text = b.get("optimized_bullet") or b.get("original_bullet", "")
            company = b.get("company", "Project")
            role = b.get("role", "")
            section = b.get("section", "Experience")

            # Detect pattern and probes
            matched_pattern = self._match_pattern(bullet_text)
            scale_limits = self._extract_scale_limits(bullet_text)
            metrics_mentioned = self._extract_metrics(bullet_text)

            talking_points = (
                [
                    f"Explain the technical problem at {company} that prompted this solution.",
                    f"Walk through your testing suite, runtime debugging, and how you verified correctness.",
                    f"Point directly to your repository commits and live deployment benchmarks rather than tutorial claims."
                ]
                if mode == "launch" else
                [
                    f"Start by describing the business constraint at {company} that necessitated this work.",
                    f"State clearly why you chose {matched_pattern['topic']} rather than simpler alternatives.",
                    f"Conclude with your measurable outcome, and acknowledge team boundaries honestly if asked about cluster/infrastructure ownership."
                ]
            )

            card = {
                "id": f"def_card_{b.get('original_id', i + 1)}",
                "mode": mode,
                "bullet_text": bullet_text,
                "company": company,
                "role": role,
                "section": section,
                "topic": matched_pattern["topic"],
                "technical_probe": matched_pattern["probe"],
                "architecture_tradeoff_question": matched_pattern["tradeoff"],
                "truth_boundary": {
                    "do_not_cross_rule": matched_pattern["boundary"],
                    "verified_scale_limit": scale_limits or ("Single-service/Standard demo scope" if mode == "launch" else "Single-service/Standard enterprise scope"),
                    "metrics_claimed": metrics_mentioned or ["Qualitative feature delivery"]
                },
                "evidence_anchor": {
                    "source_ref": b.get("source_refs") if isinstance(b.get("source_refs"), list) and b.get("source_refs") else [f"evidence:{b.get('original_id', 'unknown')}"],
                    "evidence_id": b.get("original_id")
                },
                "recommended_talking_points": talking_points
            }
            cards.append(card)

        return cards

    def evaluate_defense_explanation(
        self,
        card: Dict[str, Any],
        candidate_explanation: str
    ) -> Dict[str, Any]:
        """
        Evaluates a candidate's verbal or written answer against their truth boundaries.
        Flags exaggerations, unverified claims, or strong technical grounding.
        """
        text = candidate_explanation.lower()
        warnings = []
        strengths = []
        score = 80.0

        # Check for truth boundary violations
        boundary_rule = card.get("truth_boundary", {}).get("do_not_cross_rule", "").lower()
        if "fine-tuned" in boundary_rule and re.search(r"\b(?:fine-tuned|fine tuning|trained foundation model)\b", text):
            warnings.append("Boundary warning: You claimed model fine-tuning when your verified evidence only substantiates retrieval/prompting.")
            score -= 25

        if "multi-region" in boundary_rule and re.search(r"\b(?:multi-region|cross-region replication|global cluster)\b", text):
            warnings.append("Boundary warning: You claimed multi-region infrastructure when verified evidence indicates single VPC deployment.")
            score -= 20

        if "cluster administration" in boundary_rule and re.search(r"\b(?:administered cluster|provisioned control plane|managed master nodes)\b", text):
            warnings.append("Boundary warning: You claimed full cluster administration; ensure you clarify your namespace/application scope.")
            score -= 20

        # Check for trade-off & failure-mode depth
        if re.search(r"\bbecause|chose|instead of|trade-off|latency|concurrency|bottleneck|failure|timeout\b", text):
            strengths.append("Strong technical framing: You justified architectural trade-offs rather than just stating what you built.")
            score += 15

        if re.search(r"\bmonitored|measured|benchmark|verified|datadog|prometheus|metrics\b", text):
            strengths.append("Evidence grounding: You referenced measurement tools and validation methodology.")
            score += 10

        score = max(min(score, 100.0), 30.0)

        status = "solid_defense"
        if warnings:
            status = "overreach_detected"
        elif score < 60:
            status = "needs_depth"

        return {
            "status": status,
            "score": round(score, 1),
            "warnings": warnings,
            "strengths": strengths,
            "feedback": (
                "Your defense is truthful, anchored in your actual contribution, and respects verified scope."
                if not warnings else
                "Careful: Your explanation begins to over-claim beyond what your evidence catalog verifies. Restrict your answer to what you directly measured and implemented."
            )
        }

    def generate_proof_specs(
        self,
        gap_classifications: List[Dict[str, Any]],
        job_description: Dict[str, Any],
        mode: str = "advance"
    ) -> List[Dict[str, Any]]:
        """
        Generates Minimum Proof Task blueprints for Bucket C (True Deficit) skills.
        Never builds toy todo-apps; designs concrete, verifiable implementation specs.
        """
        proof_specs = []
        deficits = [g for g in gap_classifications if g.get("bucket") == "true_deficit" and g.get("is_required", True)]

        for item in deficits[:3]: # Focus on top 3 deficits
            term = item["term"]
            tier = item.get("suggested_proof_tier", ProofTier.IMPLEMENTATION.value)

            spec = self._build_proof_spec_for_term(term, tier, job_description, mode)
            proof_specs.append(spec)

        return proof_specs

    def _build_proof_spec_for_term(
        self,
        term: str,
        tier: str,
        job_description: Dict[str, Any],
        mode: str = "advance"
    ) -> Dict[str, Any]:
        company = job_description.get("company", "Target Employer")
        role = job_description.get("role", "Target Role")

        title = f"Minimum Proof Artifact: {term.upper()} ({tier.capitalize()} Tier)"
        
        deliverables = [
            f"Public GitHub repository named '{term.lower()}-proof-benchmark'.",
            f"Clean README with architecture diagram, local Docker Compose setup, and test commands.",
            f"Automated test suite (unit + integration tests) achieving >80% coverage.",
            "Benchmarking script demonstrating p95/p99 latency under concurrency."
        ]
        if mode == "launch":
            deliverables.insert(1, "Live deployed URL (e.g., Render, Fly.io, or Railway) to verify hands-on deployment.")

        if tier == ProofTier.CONCEPTUAL.value:
            duration = "2–3 hours"
            scope = f"Build an isolated CLI utility demonstrating {term.upper()} core APIs, error propagation, and config management."
        elif tier == ProofTier.OPERATIONAL.value:
            duration = "8–12 hours"
            scope = f"Build a multi-container service with {term.upper()}, automated health checks, Prometheus metrics, and chaos failure testing."
        else: # IMPLEMENTATION
            duration = "4–6 hours"
            scope = f"Build an end-to-end working microservice integrating {term.upper()} with structured logging, retries, and persistence."

        return {
            "term": term,
            "mode": mode,
            "proof_tier": tier,
            "title": title,
            "target_role": f"{role} at {company}",
            "estimated_effort": duration,
            "problem_statement": f"Demonstrate hands-on competency in {term.upper()} to pre-empt interviewer doubts, without fabricating past corporate tenure.",
            "scope": scope,
            "deliverables": deliverables,
            "truth_framing_guidance": f"Label this project explicitly in your resume under 'Key Projects' or 'Technical Proof'. Introduce it to recruiters as: 'To demonstrate hands-on production familiarity with {term}, I architected an end-to-end benchmark service...'"
        }

    def _match_pattern(self, text: str) -> Dict[str, str]:
        for pattern, topic, probe, tradeoff, boundary in self.ARCHITECTURAL_PATTERNS:
            if re.search(pattern, text, re.I):
                return {
                    "topic": topic,
                    "probe": probe,
                    "tradeoff": tradeoff,
                    "boundary": boundary
                }
        return {
            "topic": "Core Implementation & Delivery",
            "probe": "What was the most difficult technical bug or bottleneck you encountered during this work?",
            "tradeoff": "Why was this specific technical architecture chosen over simpler alternatives?",
            "boundary": "Do not claim you led architectural direction if your primary contribution was writing modular feature code."
        }

    def _extract_scale_limits(self, text: str) -> Optional[str]:
        match = re.search(r"(\d+(?:,\d{3})*(?:\.\d+)?(?:k|m|b)?\+?\s*(?:rps|qps|users|requests|records|events|rows|gb|tb))", text, re.I)
        return match.group(1) if match else None

    def _extract_metrics(self, text: str) -> List[str]:
        return re.findall(r"\b(?:\d+(?:\.\d+)?%|\b(?:reduced|increased|improved|scaled|cut)\s+\w+\s+by\s+\d+%?)\b", text, re.I)
