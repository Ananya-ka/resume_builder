"""Conservative Structured Resume Parser.

Identifies sections, roles, organizations, projects, skills, education, and dates
using layout, headings, and pattern analysis without requiring an external AI provider.
Treats output as a reviewable draft and preserves ambiguous text as unassigned.
"""
from __future__ import annotations

import re
from typing import List, Dict, Any, Optional, Tuple
from app.services.document_extractor import TextBlock, ExtractionResult


class StructuredResumeParser:
    """Rule-based, conservative parser for extracted resume blocks."""

    HEADING_PATTERNS = {
        "summary": re.compile(
            r"^(?:professional\s+summary|profile\s+summary|summary|profile|about\s+me|career\s+objective|objective)\b",
            re.IGNORECASE
        ),
        "experience": re.compile(
            r"^(?:work\s+experience|professional\s+experience|employment\s+history|experience|work\s+history|career\s+history)\b",
            re.IGNORECASE
        ),
        "projects": re.compile(
            r"^(?:personal\s+projects|academic\s+projects|key\s+projects|selected\s+projects|projects)\b",
            re.IGNORECASE
        ),
        "education": re.compile(
            r"^(?:education|academic\s+background|educational\s+qualifications|academics)\b",
            re.IGNORECASE
        ),
        "skills": re.compile(
            r"^(?:technical\s+skills|core\s+competencies|skills\s*(?:&|and)\s*tools|skills|technologies|proficiencies|tools\s*(?:&|and)\s*technologies)\b",
            re.IGNORECASE
        ),
        "certifications": re.compile(
            r"^(?:certifications|licenses|certificates|accreditations|credentials)\b",
            re.IGNORECASE
        ),
        "achievements": re.compile(
            r"^(?:achievements|awards|honors|accomplishments|publications)\b",
            re.IGNORECASE
        ),
    }

    DATE_PATTERN = re.compile(
        r"(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|\b\d{4}\b)[^–—\-\n]*(?:[–—\-]|to)\s*(?:Present|Current|\d{4}|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[^–—\-\n]*)|(?:\b\d{4}\s*[–—\-]\s*\d{4}\b)|(?:\b\d{4}\s*[–—\-]\s*Present\b)",
        re.IGNORECASE
    )

    BULLET_PREFIX_PATTERN = re.compile(
        r"^[-*•–—\u2022\u25cf\u25cb\u25aa\u25b8]\s*|\b\d{1,2}\.\s+"
    )

    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
    PHONE_PATTERN = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
    LINK_PATTERN = re.compile(r"(?:https?://\S+|linkedin\.com/\S+|github\.com/\S+|leetcode\.com/\S+)", re.IGNORECASE)

    KNOWN_TECH = {
        "python", "javascript", "typescript", "java", "c++", "c#", "go", "golang", "rust", "ruby", "php", "swift", "kotlin",
        "react", "react.js", "next.js", "vue", "vue.js", "angular", "node.js", "nodejs", "fastapi", "flask", "django", "spring", "express",
        "sql", "postgresql", "postgres", "mysql", "mongodb", "redis", "elasticsearch", "cassandra", "dynamodb", "snowflake",
        "aws", "gcp", "azure", "docker", "kubernetes", "k8s", "terraform", "ansible", "jenkins", "git", "github", "gitlab", "ci/cd",
        "kafka", "rabbitmq", "celery", "graphql", "rest", "restful", "grpc", "linux", "bash",
        "pytorch", "tensorflow", "keras", "scikit-learn", "pandas", "numpy", "opencv", "spacy", "huggingface", "transformers",
        "llm", "rag", "langchain", "llamaindex", "mcp", "agentic ai", "claude code", "openai", "embeddings"
    }

    def parse(self, raw_text: str, blocks: Optional[List[TextBlock]] = None) -> Dict[str, Any]:
        """Parses raw text and optional structured blocks into sections and fields."""
        if not blocks:
            # Build basic blocks from lines if blocks were not provided
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
            blocks = [
                TextBlock(
                    block_id=f"b{i}",
                    page_number=1,
                    text=l,
                    kind="bullet" if self.BULLET_PREFIX_PATTERN.match(l) else "paragraph",
                    source_ref=f"line:{i}"
                )
                for i, l in enumerate(lines)
            ]

        # 1. Segment blocks into labeled sections
        section_blocks = self._segment_sections(blocks)

        # 1b. Extract candidate header details (name, email, phone, links)
        header_blocks = section_blocks.get("header", [])
        contact_info = self._extract_contact_info(header_blocks, raw_text)

        # 2. Extract profile summary
        summary = self._extract_summary(section_blocks.get("summary", []))

        # 3. Extract skills
        skills = self._extract_skills(section_blocks.get("skills", []))

        # 4. Extract experience
        experience, unassigned_exp = self._extract_experience(section_blocks.get("experience", []))

        # 5. Extract projects
        projects, unassigned_proj = self._extract_projects(section_blocks.get("projects", []))

        # 6. Extract education
        education, unassigned_edu = self._extract_education(section_blocks.get("education", []))

        # 7. Extract certifications and achievements
        certifications = self._extract_flat_list(section_blocks.get("certifications", []))
        achievements = self._extract_flat_list(section_blocks.get("achievements", []))

        # 8. Collect all unassigned text
        unassigned_all = (
            [b.text for b in section_blocks.get("header", [])[3:]] +  # Skip first 3 lines (typically candidate name/contact)
            unassigned_exp +
            unassigned_proj +
            unassigned_edu +
            [b.text for b in section_blocks.get("unassigned", [])]
        )

        return {
            "name": contact_info["name"],
            "email": contact_info["email"],
            "phone": contact_info["phone"],
            "links": contact_info["links"],
            "linkedin": contact_info["linkedin"],
            "github": contact_info["github"],
            "leetcode": contact_info["leetcode"],
            "profile_summary": summary,
            "skills": skills,
            "experience": experience,
            "projects": projects,
            "education": education,
            "certifications": certifications,
            "achievements": achievements,
            "unassigned_text": [t for t in unassigned_all if t.strip()],
            "parsing_status": "ready",
            "needs_review": True,
            "provenance_blocks_count": len(blocks),
        }

    def _extract_contact_info(self, header_blocks: List[TextBlock], raw_text: str) -> Dict[str, Any]:
        header_text = " \n ".join(b.text.strip() for b in header_blocks if b.text.strip())
        search_text = header_text or raw_text[:1500]

        name = ""
        for b in header_blocks:
            t = b.text.strip()
            if t and len(t) < 60 and not self.EMAIL_PATTERN.search(t) and not self.LINK_PATTERN.search(t) and not self.DATE_PATTERN.search(t):
                clean_name = self.BULLET_PREFIX_PATTERN.sub("", t).strip()
                if clean_name and not any(clean_name.lower().startswith(p) for p in ["resume", "curriculum", "cv"]):
                    name = clean_name
                    break

        email_match = self.EMAIL_PATTERN.search(search_text)
        email = email_match.group(0) if email_match else None

        phone_match = self.PHONE_PATTERN.search(search_text)
        phone = phone_match.group(0) if phone_match else None

        raw_links = self.LINK_PATTERN.findall(search_text)
        links = []
        for l in raw_links:
            clean_l = l.strip(" ,|;()[]")
            if clean_l and clean_l not in links:
                links.append(clean_l)

        linkedin = next((l for l in links if "linkedin.com" in l.lower()), "")
        github = next((l for l in links if "github.com" in l.lower()), "")
        leetcode = next((l for l in links if "leetcode.com" in l.lower()), "")

        return {
            "name": name,
            "email": email,
            "phone": phone,
            "links": links,
            "linkedin": linkedin,
            "github": github,
            "leetcode": leetcode
        }

    def _segment_sections(self, blocks: List[TextBlock]) -> Dict[str, List[TextBlock]]:
        """Partitions blocks under identified section headings."""
        sections: Dict[str, List[TextBlock]] = {
            "header": [],
            "summary": [],
            "skills": [],
            "experience": [],
            "projects": [],
            "education": [],
            "certifications": [],
            "achievements": [],
            "unassigned": []
        }

        current_section = "header"

        for b in blocks:
            text_clean = b.text.strip().lower()
            clean_heading = re.sub(r"^[^a-zA-Z0-9]+", "", text_clean).strip()

            # Check if this block is a section heading
            matched_section = None
            if len(b.text.strip()) < 50 and not b.text.strip().endswith("."):
                for sec_name, pattern in self.HEADING_PATTERNS.items():
                    if pattern.match(clean_heading):
                        matched_section = sec_name
                        break

            if matched_section:
                current_section = matched_section
            else:
                sections[current_section].append(b)

        return sections

    def _extract_summary(self, blocks: List[TextBlock]) -> Optional[str]:
        if not blocks:
            return None
        text = " ".join(b.text.strip() for b in blocks if b.text.strip())
        return text if text else None

    def _extract_skills(self, blocks: List[TextBlock]) -> List[str]:
        skills: List[str] = []
        for b in blocks:
            line = b.text.strip()
            # If line is "Category: Skill1, Skill2"
            if ":" in line:
                _, rest = line.split(":", 1)
                line = rest.strip()
            # Split by comma, pipe, bullet, semicolon
            parts = re.split(r"[,|;•\u2022\u25cf/]+", line)
            for p in parts:
                clean_skill = p.strip()
                # Exclude purely numeric or single char non-skills (except C, R)
                if clean_skill and len(clean_skill) <= 40 and not clean_skill.isdigit():
                    if clean_skill not in skills:
                        skills.append(clean_skill)
        return skills

    def _extract_experience(self, blocks: List[TextBlock]) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Extracts experience roles and attached bullets."""
        entries: List[Dict[str, Any]] = []
        unassigned: List[str] = []

        current_entry: Optional[Dict[str, Any]] = None

        for b in blocks:
            text = b.text.strip()
            if not text:
                continue

            is_bullet = bool(self.BULLET_PREFIX_PATTERN.match(text)) or b.kind == "bullet"

            if not is_bullet and self._looks_like_role_or_company(text):
                # Start new experience entry
                company, role, dates = self._parse_org_header(text)
                current_entry = {
                    "company": company,
                    "role": role,
                    "dates": dates,
                    "bullets": [],
                    "bullet_provenance": []
                }
                entries.append(current_entry)
            elif is_bullet:
                bullet_clean = self.BULLET_PREFIX_PATTERN.sub("", text).strip()
                if current_entry is not None:
                    current_entry["bullets"].append(bullet_clean)
                    current_entry["bullet_provenance"].append(b.source_ref)
                else:
                    unassigned.append(bullet_clean)
            else:
                # Could be a continuation of previous bullet or unassigned detail
                if current_entry and current_entry["bullets"]:
                    # If previous bullet doesn't end with period, append as continuation
                    prev = current_entry["bullets"][-1]
                    if not prev.endswith((".", "!", "?")):
                        current_entry["bullets"][-1] = f"{prev} {text}"
                    else:
                        unassigned.append(text)
                elif current_entry:
                    # Update company/role if empty
                    if not current_entry["role"] and len(text) < 60:
                        current_entry["role"] = text
                    else:
                        unassigned.append(text)
                else:
                    unassigned.append(text)

        # Cleanup entries: preserve entries with bullets OR valid dates
        final_entries = [e for e in entries if e["bullets"] or e.get("dates")]
        for e in entries:
            if not e["bullets"] and not e.get("dates"):
                unassigned.append(f"{e.get('company', '')} - {e.get('role', '')}")

        return final_entries, unassigned

    def _extract_projects(self, blocks: List[TextBlock]) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Extracts project names and attached bullets."""
        entries: List[Dict[str, Any]] = []
        unassigned: List[str] = []
        current_proj: Optional[Dict[str, Any]] = None

        for b in blocks:
            text = b.text.strip()
            if not text:
                continue

            is_bullet = bool(self.BULLET_PREFIX_PATTERN.match(text)) or b.kind == "bullet"

            if not is_bullet and (len(text) < 80 and not text.endswith(".")):
                proj_name, dates = self._parse_project_header(text)
                current_proj = {
                    "name": proj_name,
                    "dates": dates,
                    "bullets": [],
                    "bullet_provenance": []
                }
                entries.append(current_proj)
            elif is_bullet:
                bullet_clean = self.BULLET_PREFIX_PATTERN.sub("", text).strip()
                if current_proj is not None:
                    current_proj["bullets"].append(bullet_clean)
                    current_proj["bullet_provenance"].append(b.source_ref)
                else:
                    unassigned.append(bullet_clean)
            else:
                if current_proj and current_proj["bullets"]:
                    prev = current_proj["bullets"][-1]
                    if not prev.endswith((".", "!", "?")):
                        current_proj["bullets"][-1] = f"{prev} {text}"
                    else:
                        unassigned.append(text)
                else:
                    unassigned.append(text)

        final_projects = [p for p in entries if p["bullets"]]
        for p in entries:
            if not p["bullets"]:
                unassigned.append(p.get("name", ""))

        return final_projects, unassigned

    def _extract_education(self, blocks: List[TextBlock]) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Extracts institution and degree entries."""
        entries: List[Dict[str, Any]] = []
        unassigned: List[str] = []
        school_keywords = ["university", "college", "institute", "school", "academy", "polytechnic"]
        degree_keywords = ["bachelor", "master", "phd", "b.tech", "m.tech", "b.s.", "m.s.", "b.e.", "m.e.", "bba", "mba", "associate", "degree", "diploma"]

        current_edu: Dict[str, Any] = {"school": "", "degree": "", "dates": ""}

        for b in blocks:
            text = b.text.strip()
            text_lower = text.lower()

            found_school = any(k in text_lower for k in school_keywords)
            found_degree = any(k in text_lower for k in degree_keywords)
            dates = ""
            date_match = self.DATE_PATTERN.search(text)
            if date_match:
                dates = date_match.group(0).strip()
                text = text.replace(dates, "").strip(" |-,")

            if found_school and found_degree:
                parts = [p.strip() for p in re.split(r"[|–—\-,]", text) if p.strip()]
                school = parts[0] if parts else text
                degree = " ".join(parts[1:]) if len(parts) > 1 else "Degree"
                entries.append({"school": school, "degree": degree, "dates": dates})
            elif found_school:
                if current_edu["school"]:
                    entries.append(dict(current_edu))
                    current_edu = {"school": "", "degree": "", "dates": ""}
                current_edu["school"] = text
                if dates:
                    current_edu["dates"] = dates
            elif found_degree:
                current_edu["degree"] = text
                if dates:
                    current_edu["dates"] = dates
                if current_edu["school"]:
                    entries.append(dict(current_edu))
                    current_edu = {"school": "", "degree": "", "dates": ""}
            else:
                unassigned.append(text)

        if current_edu.get("school") or current_edu.get("degree"):
            entries.append(current_edu)

        return entries, unassigned

    def _extract_flat_list(self, blocks: List[TextBlock]) -> List[str]:
        items: List[str] = []
        for b in blocks:
            text = self.BULLET_PREFIX_PATTERN.sub("", b.text.strip()).strip()
            if text and text not in items:
                items.append(text)
        return items

    def _looks_like_role_or_company(self, text: str) -> bool:
        if len(text) > 120 or text.endswith("."):
            return False
        # If contains dates or separators
        if self.DATE_PATTERN.search(text) or "|" in text or " - " in text or " – " in text or " — " in text:
            return True
        role_words = ["engineer", "developer", "manager", "lead", "analyst", "intern", "consultant", "architect", "scientist", "director"]
        if any(w in text.lower() for w in role_words):
            return True
        return False

    def _parse_org_header(self, text: str) -> Tuple[str, str, str]:
        dates = ""
        date_match = self.DATE_PATTERN.search(text)
        if date_match:
            raw_dates = date_match.group(0).strip()
            dates = raw_dates
            if ";" in dates:
                dates = dates.split(";")[0].strip()
            text = text.replace(f"({raw_dates})", "")
            text = text.replace(raw_dates, "")
            text = re.sub(r"\(\s*\)", "", text).strip(" |–—-,()")

        parts = [p.strip(" |–—-,()") for p in re.split(r"\s*[|–—]\s*|\s+-\s+", text) if p.strip(" |–—-,()")]
        if len(parts) >= 2:
            return parts[0], parts[1], dates
        elif len(parts) == 1:
            # Check if has 'at' e.g. "Software Engineer at Google"
            if " at " in parts[0]:
                sub = parts[0].split(" at ", 1)
                return sub[1].strip(), sub[0].strip(), dates
            return parts[0], "", dates
        return "", "", dates

    def _parse_project_header(self, text: str) -> Tuple[str, str]:
        dates = ""
        date_match = self.DATE_PATTERN.search(text)
        if date_match:
            dates = date_match.group(0).strip()
            text = text.replace(f"({dates})", "")
            text = text.replace(dates, "")
            text = re.sub(r"\(\s*\)", "", text).strip(" |–—-,()")

        parts = [p.strip(" |–—-,()") for p in re.split(r"[|–—\-]", text) if p.strip(" |–—-,()")]
        name = parts[0] if parts else text
        return name, dates

    # --------------------------------------------------------------------------
    # Deterministic Bullet Metadata Extraction
    # --------------------------------------------------------------------------

    def extract_bullet_metadata(self, bullet: str, company: str = "", role: str = "") -> Dict[str, Any]:
        """Rule-based extraction of technologies, keywords, metrics, and domain."""
        bullet_lower = bullet.lower()

        # 1. Technologies
        matched_tech = []
        for tech in self.KNOWN_TECH:
            pattern = r"(?<!\w)" + re.escape(tech) + r"(?!\w)"
            if re.search(pattern, bullet_lower):
                # Standardize capitalization
                matched_tech.append(tech.title() if len(tech) > 3 else tech.upper())

        # 2. Metrics
        metric_pattern = re.compile(
            r"(?<!\w)(?:[$€£]\s*)?[-+]?\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:%|percent\b|ms\b|milliseconds\b|seconds\b|[kKmMbB]\b))?"
        )
        matched_metrics = [m.strip() for m in metric_pattern.findall(bullet) if m.strip()]

        # 3. Action keywords
        action_verbs = [
            "designed", "developed", "built", "implemented", "scaled", "led", "managed",
            "created", "delivered", "optimized", "reduced", "increased", "orchestrated",
            "engineered", "accelerated", "integrated", "streamlined", "automated", "architected"
        ]
        matched_keywords = [v for v in action_verbs if re.search(r"\b" + v + r"\b", bullet_lower)]

        # 4. Domain inference
        domain = "General Software"
        if any(t in matched_tech for t in ["Pytorch", "Tensorflow", "Llm", "Rag", "Langchain", "Openai", "Embeddings"]):
            domain = "AI / Machine Learning"
        elif any(t in matched_tech for t in ["Aws", "Gcp", "Azure", "Docker", "Kubernetes", "Terraform", "Ci/Cd"]):
            domain = "Cloud & DevOps"
        elif any(t in matched_tech for t in ["React", "React.Js", "Next.Js", "Vue", "Angular"]):
            domain = "Frontend"
        elif any(t in matched_tech for t in ["Fastapi", "Flask", "Django", "Postgresql", "Postgres", "Redis", "Kafka"]):
            domain = "Backend"

        return {
            "technologies": sorted(set(matched_tech)),
            "keywords": sorted(set(matched_keywords)),
            "metrics": matched_metrics,
            "domain": domain
        }
