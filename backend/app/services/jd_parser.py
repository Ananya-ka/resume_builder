import json
import logging
from typing import Dict, Any
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

class JDParser:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=90.0, max_retries=2) if settings.OPENAI_API_KEY else None

    def parse_job_description(self, raw_text: str) -> Dict[str, Any]:
        """
        Uses OpenAI to parse job description into a highly structured object.
        """
        if not self.client:
            raise ValueError("Job description parsing is unavailable. Configure the model service and retry.")

        prompt = f"""
        You are an expert Job Description Analyzer. Parse the following raw job description text into a structured JSON object.
        
        Strictly output JSON with the exact structure:
        {{
            "company": "string (or 'Unknown')",
            "role": "string (or 'Unknown')",
            "department": "string or null",
            "experience_years": "float or null (e.g. 5.0)",
            "responsibilities": ["string"],
            "required_skills": ["string"],
            "preferred_skills": ["string"],
            "cloud": ["string"],
            "languages": ["string"],
            "frameworks": ["string"],
            "databases": ["string"],
            "soft_skills": ["string"],
            "domain": "string or null (e.g. Cloud, FinTech, Web, Healthcare)",
            "industry": "string or null",
            "seniority": "string or null (e.g. Junior, Mid, Senior, Lead, Principal)",
            "ats_keywords": ["string"]
        }}
        
        JOB DESCRIPTION TEXT:
        {raw_text}
        """

        try:
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a precise JSON extractor. Output ONLY valid JSON matching the schema."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            parsed = json.loads(response.choices[0].message.content)
            return parsed
        except Exception as e:
            logger.error("JD LLM parsing failed: %s", type(e).__name__)
            raise ValueError("Job description parsing is unavailable. Configure the model service and retry.")

