import pytest
from app.services.claim_analytics import ClaimAnalyticsEngine


def test_claim_analytics_win_rate_and_tiers():
    engine = ClaimAnalyticsEngine()

    all_evidence = [
        {
            "id": 1,
            "data": {
                "content": "Built high-throughput Redis pipeline handling 10k rps with p99 < 10ms",
                "company": "Payment Gateway",
                "role": "Backend Engineer",
                "section": "Experience"
            }
        },
        {
            "id": 2,
            "data": {
                "content": "Assisted team in maintaining legacy Jenkins CI scripts",
                "company": "Old Corp",
                "role": "Junior Dev",
                "section": "Experience"
            }
        },
        {
            "id": 3,
            "data": {
                "content": "Implemented ChromaDB vector similarity search with 95% precision",
                "company": "AI Project",
                "role": "Creator",
                "section": "Projects"
            }
        }
    ]

    all_optimizations = [
        {
            "id": 101,
            "optimized_content": [
                {"original_id": 1, "included": True, "optimized_bullet": "Built high-throughput Redis pipeline..."},
                {"original_id": 2, "included": True, "optimized_bullet": "Assisted team in Jenkins..."}
            ]
        },
        {
            "id": 102,
            "optimized_content": [
                {"original_id": 1, "included": True, "optimized_bullet": "Built high-throughput Redis pipeline..."},
                {"original_id": 2, "included": True, "optimized_bullet": "Assisted team in Jenkins..."}
            ]
        },
        {
            "id": 103,
            "optimized_content": [
                {"original_id": 2, "included": True, "optimized_bullet": "Assisted team in Jenkins..."}
            ]
        }
    ]

    tracked_applications = [
        {
            "id": 1,
            "optimization_id": 101,
            "status": "Interview",
            "company": "Stripe",
            "role": "Backend Architect"
        },
        {
            "id": 2,
            "optimization_id": 102,
            "status": "OA",
            "company": "Datadog",
            "role": "Systems Engineer"
        },
        {
            "id": 3,
            "optimization_id": 103,
            "status": "Rejected",
            "company": "Legacy Corp",
            "role": "DevOps Engineer"
        }
    ]

    report = engine.analyze_claims(all_evidence, tracked_applications, all_optimizations)
    
    assert report["summary"]["total_claims"] == 3
    assert report["summary"]["total_applications_tracked"] == 3
    assert report["summary"]["total_interviews"] == 2
    assert report["summary"]["overall_interview_rate"] == 66.7

    cards_by_id = {c["evidence_id"]: c for c in report["heatmap"]}

    # Claim 1: Used in apps 101 and 102 (both resulted in Interview/OA) -> 2/2 = 100% win rate -> high_performer
    c1 = cards_by_id[1]
    assert c1["application_count"] == 2
    assert c1["interview_count"] == 2
    assert c1["win_rate"] == 100.0
    assert c1["win_tier"] == "high_performer"
    assert "High Performer" in c1["market_signal"]

    # Claim 2: Used in apps 101 (Interview), 102 (OA), 103 (Rejected) -> 2/3 = 66.7% win rate -> high_performer (>= 35%)
    c2 = cards_by_id[2]
    assert c2["application_count"] == 3
    assert c2["interview_count"] == 2
    assert c2["win_rate"] == 66.7

    # Claim 3: Not included in any tracked application -> untested
    c3 = cards_by_id[3]
    assert c3["application_count"] == 0
    assert c3["win_rate"] == 0.0
    assert c3["win_tier"] == "untested"


def test_claim_analytics_underperforming_alert():
    engine = ClaimAnalyticsEngine()

    all_evidence = [
        {
            "id": 99,
            "data": {
                "content": "Worked on ad-hoc scripting tasks using Bash and Perl",
                "company": "Old Tech",
                "role": "Admin",
                "section": "Experience"
            }
        }
    ]
    all_optimizations = [
        {"id": 201, "optimized_content": [{"original_id": 99, "included": True}]},
        {"id": 202, "optimized_content": [{"original_id": 99, "included": True}]},
        {"id": 203, "optimized_content": [{"original_id": 99, "included": True}]},
    ]
    tracked_applications = [
        {"id": 1, "optimization_id": 201, "status": "Rejected"},
        {"id": 2, "optimization_id": 202, "status": "Rejected"},
        {"id": 3, "optimization_id": 203, "status": "Applied"}, # No callback
    ]

    report = engine.analyze_claims(all_evidence, tracked_applications, all_optimizations)
    c99 = report["heatmap"][0]
    assert c99["application_count"] == 3
    assert c99["interview_count"] == 0
    assert c99["win_rate"] == 0.0
    assert c99["win_tier"] == "underperforming"
    assert "Underperforming" in c99["market_signal"]
    assert "Consider reframing" in c99["market_signal"]
