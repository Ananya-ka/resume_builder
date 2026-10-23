import re
from typing import Dict, Any, List, Optional
from collections import defaultdict


class ClaimAnalyticsEngine:
    """
    Evidence-grounded Claim Heatmap and Win Rate Engine.
    Tracks actual conversion (interview callbacks, offers, screening pass rate)
    rather than mere vanity usage counts.
    """

    def analyze_claims(
        self,
        all_evidence: List[Dict[str, Any]],
        tracked_applications: List[Dict[str, Any]],
        all_optimizations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculates conversion metrics and win rates for every candidate evidence claim.
        """
        # Map optimization_id -> list of included bullets/evidence_ids
        opt_claims_map: Dict[int, List[Dict[str, Any]]] = {}
        for opt in all_optimizations:
            opt_id = opt.get("id")
            if not opt_id:
                continue
            bullets = opt.get("optimized_content") or []
            included = [
                b for b in bullets
                if b.get("included", True) and (b.get("optimized_bullet") or b.get("original_bullet") or b.get("original_id"))
            ]
            opt_claims_map[opt_id] = included

        # Accumulators per evidence_id or claim key
        claim_stats = defaultdict(lambda: {
            "application_count": 0,
            "interview_count": 0,
            "offer_count": 0,
            "rejection_count": 0,
            "companies_applied": [],
            "roles_applied": [],
        })

        for app in tracked_applications:
            opt_id = app.get("optimization_id")
            status = (app.get("status") or "Applied").strip()
            company = app.get("company", "Company")
            role = app.get("role", "Role")

            # Status classification
            is_interview = status in ("OA", "Screening", "Interview", "Offer")
            is_offer = status == "Offer"
            is_rejection = status == "Rejected"

            if opt_id and opt_id in opt_claims_map:
                for b in opt_claims_map[opt_id]:
                    ev_id = b.get("original_id") or b.get("evidence_id")
                    if ev_id:
                        stats = claim_stats[ev_id]
                        stats["application_count"] += 1
                        if company not in stats["companies_applied"]:
                            stats["companies_applied"].append(company)
                        if role not in stats["roles_applied"]:
                            stats["roles_applied"].append(role)
                        if is_interview:
                            stats["interview_count"] += 1
                        if is_offer:
                            stats["offer_count"] += 1
                        if is_rejection:
                            stats["rejection_count"] += 1

        # Build detailed heatmap cards for every evidence item
        heatmap_cards = []
        for ev in all_evidence:
            ev_id = ev.get("id")
            data = ev.get("data") or {}
            content = data.get("content") or data.get("ownership") or ""
            company = data.get("company", "Project")
            role = data.get("role", "Engineer")
            section = data.get("section", "Experience")

            stats = claim_stats[ev_id]
            apps_count = stats["application_count"]
            int_count = stats["interview_count"]
            offer_count = stats["offer_count"]
            rej_count = stats["rejection_count"]

            win_rate = round((int_count / apps_count * 100), 1) if apps_count > 0 else 0.0

            # Win Tier classification
            if apps_count >= 3 and win_rate == 0.0:
                win_tier = "underperforming"
                signal = (
                    f"Underperforming: Used in {apps_count} tracked applications with 0 callbacks. "
                    "The impact metric may be unverified or unclear to recruiters. Consider reframing."
                )
            elif apps_count >= 2 and win_rate >= 35.0:
                win_tier = "high_performer"
                signal = (
                    f"High Performer: {win_rate}% interview callback rate across {apps_count} applications. "
                    "Keep as an anchor claim for similar roles."
                )
            elif apps_count >= 1:
                win_tier = "tested"
                signal = (
                    f"Tested: Applied to {apps_count} role(s) with {int_count} callback(s). "
                    "Gaining empirical market validation."
                )
            else:
                win_tier = "untested"
                signal = "Untested: Not yet submitted in tracked applications."

            heatmap_cards.append({
                "evidence_id": ev_id,
                "content": content,
                "company": company,
                "role": role,
                "section": section,
                "application_count": apps_count,
                "interview_count": int_count,
                "offer_count": offer_count,
                "rejection_count": rej_count,
                "win_rate": win_rate,
                "win_tier": win_tier,
                "market_signal": signal,
                "companies_applied": stats["companies_applied"],
                "roles_applied": stats["roles_applied"]
            })

        # Sort: High performers first, then tested, then underperforming, then untested
        tier_order = {"high_performer": 0, "tested": 1, "underperforming": 2, "untested": 3}
        heatmap_cards.sort(key=lambda x: (tier_order.get(x["win_tier"], 4), -x["win_rate"], -x["application_count"]))

        # Aggregate summary
        total_apps = len(tracked_applications)
        total_interviews = sum(1 for a in tracked_applications if (a.get("status") or "") in ("OA", "Screening", "Interview", "Offer"))
        overall_interview_rate = round((total_interviews / total_apps * 100), 1) if total_apps > 0 else 0.0

        top_converter = next((c for c in heatmap_cards if c["win_tier"] == "high_performer"), None)

        return {
            "heatmap": heatmap_cards,
            "summary": {
                "total_claims": len(heatmap_cards),
                "total_applications_tracked": total_apps,
                "total_interviews": total_interviews,
                "overall_interview_rate": overall_interview_rate,
                "high_performing_count": len([c for c in heatmap_cards if c["win_tier"] == "high_performer"]),
                "tested_count": len([c for c in heatmap_cards if c["win_tier"] == "tested"]),
                "underperforming_count": len([c for c in heatmap_cards if c["win_tier"] == "underperforming"]),
                "untested_count": len([c for c in heatmap_cards if c["win_tier"] == "untested"]),
                "top_converting_claim": top_converter["content"] if top_converter else (heatmap_cards[0]["content"] if heatmap_cards else None)
            }
        }
