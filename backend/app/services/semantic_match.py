import logging
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from app.models.schemas import ResumeBullet, KnowledgeBase
from app.services.resume_parser import ResumeParser

logger = logging.getLogger(__name__)

class SemanticMatchEngine:
    def __init__(self, db: Session):
        self.db = db
        self.parser = ResumeParser()

    def retrieve_relevant_bullets(
        self, 
        user_id: str, 
        resume_id: int, 
        jd_text: str, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Retrieves the top 20 most semantically relevant resume bullets + knowledge base facts
        relative to the job description using pgvector cosine similarity.
        """
        # If no OpenAI key or zero embedding, use lexical relevance fallback
        from app.core.config import settings
        if not settings.OPENAI_API_KEY or not self.parser.client:
            return self._lexical_retrieve(user_id, resume_id, jd_text, limit)

        # 1. Generate embedding for the Job Description
        jd_embedding = self.parser.get_embedding(jd_text)
        if not jd_embedding or all(v == 0.0 for v in jd_embedding):
            return self._lexical_retrieve(user_id, resume_id, jd_text, limit)

        # 2. Query ResumeBullet table
        # We select the fields and the cosine distance
        bullet_query = (
            self.db.query(
                ResumeBullet,
                ResumeBullet.embedding.cosine_distance(jd_embedding).label("distance")
            )
            .filter(ResumeBullet.resume_id == resume_id)
            .order_by("distance")
            .limit(limit)
        )
        
        bullets_with_dist = bullet_query.all()

        # 3. Query KnowledgeBase table
        kb_query = (
            self.db.query(
                KnowledgeBase,
                KnowledgeBase.embedding.cosine_distance(jd_embedding).label("distance")
            )
            .filter(KnowledgeBase.user_id == user_id)
            .order_by("distance")
            .limit(10)
        )
        kb_with_dist = kb_query.all()

        # 4. Merge results and format
        merged = []
        for bullet, dist in bullets_with_dist:
            similarity = 1.0 - float(dist) if dist is not None else 0.0
            merged.append({
                "source": "resume",
                "id": bullet.id,
                "section": bullet.section,
                "company": bullet.company,
                "role": bullet.role,
                "content": bullet.bullet,
                "technologies": bullet.technologies or [],
                "keywords": bullet.keywords or [],
                "metrics": bullet.metrics or [],
                "domain": bullet.domain,
                "similarity": round(similarity, 3)
            })

        for kb, dist in kb_with_dist:
            similarity = 1.0 - float(dist) if dist is not None else 0.0
            merged.append({
                "source": "knowledge_base",
                "id": kb.id,
                "section": kb.category,
                "company": "Knowledge Base",
                "role": kb.category,
                "content": kb.content,
                "technologies": kb.technologies or [],
                "keywords": kb.keywords or [],
                "metrics": kb.metrics or [],
                "domain": "Knowledge Base",
                "similarity": round(similarity, 3)
            })

        # Sort merged by similarity descending
        merged.sort(key=lambda x: x["similarity"], reverse=True)

        # Keep top 'limit' entries
        return merged[:limit]

    def _lexical_retrieve(
        self,
        user_id: str,
        resume_id: int,
        jd_text: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Lexical/keyword overlap retrieval fallback when vector embeddings are unavailable."""
        import re
        jd_words = set(re.findall(r"[a-z0-9+#]+", jd_text.lower()))

        bullets = self.db.query(ResumeBullet).filter(ResumeBullet.resume_id == resume_id).all()
        kb_items = self.db.query(KnowledgeBase).filter(KnowledgeBase.user_id == user_id).limit(10).all()

        scored = []
        for b in bullets:
            content_words = set(re.findall(r"[a-z0-9+#]+", b.bullet.lower()))
            overlap = len(jd_words & content_words)
            # Add bonus for matched technologies or keywords
            tech_overlap = len(set(t.lower() for t in (b.technologies or [])) & jd_words)
            score = overlap + (tech_overlap * 2)
            similarity = min(round(score / (len(content_words) or 1), 3), 1.0)
            scored.append({
                "source": "resume",
                "id": b.id,
                "section": b.section,
                "company": b.company,
                "role": b.role,
                "content": b.bullet,
                "technologies": b.technologies or [],
                "keywords": b.keywords or [],
                "metrics": b.metrics or [],
                "domain": b.domain,
                "similarity": similarity,
                "_raw_score": score
            })

        for kb in kb_items:
            content_words = set(re.findall(r"[a-z0-9+#]+", kb.content.lower()))
            overlap = len(jd_words & content_words)
            tech_overlap = len(set(t.lower() for t in (kb.technologies or [])) & jd_words)
            score = overlap + (tech_overlap * 2)
            similarity = min(round(score / (len(content_words) or 1), 3), 1.0)
            scored.append({
                "source": "knowledge_base",
                "id": kb.id,
                "section": kb.category,
                "company": "Knowledge Base",
                "role": kb.category,
                "content": kb.content,
                "technologies": kb.technologies or [],
                "keywords": kb.keywords or [],
                "metrics": kb.metrics or [],
                "domain": "Knowledge Base",
                "similarity": similarity,
                "_raw_score": score
            })

        scored.sort(key=lambda x: (x["_raw_score"], x["similarity"]), reverse=True)
        for item in scored:
            del item["_raw_score"]
        return scored[:limit]
