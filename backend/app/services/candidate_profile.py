"""Merge sourced candidate facts without silently resolving disagreements."""
import hashlib
import json
import re
from difflib import SequenceMatcher
from app.services.discovery import normalized


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]


def candidate_key(resumes):
    emails = sorted({normalized((r.parsed_raw or {}).get("email")) for r in resumes} - {""})
    return digest(emails if emails else sorted(r.id for r in resumes))


def skill_categories(skills):
    vocab = {
        "Programming": {"python", "sql", "java", "javascript", "typescript", "go", "c", "c++", "c#", "rust", "r", "bash"},
        "Frameworks & Libraries": {"fastapi", "django", "flask", "react", "next.js", "node.js", "pytorch", "tensorflow", "pandas", "numpy", "scikit-learn"},
        "Databases": {"postgresql", "postgres", "mysql", "mongodb", "redis", "sqlite", "pgvector", "snowflake"},
        "Cloud & Development Tools": {"aws", "gcp", "azure", "docker", "kubernetes", "git", "github", "ci/cd", "terraform", "linux"},
    }
    result = {}
    for skill in skills:
        category = next((name for name, terms in vocab.items() if normalized(skill) in terms), "Additional Skills")
        result.setdefault(category, []).append(skill)
    return result


def merge_profile(resumes, evidence, decisions=None):
    decisions = decisions or {}
    profile, conflicts, provenance = {}, [], {}

    def choose(path, options):
        unique = {}
        for value, ref in options:
            if value in (None, "", [], {}):
                continue
            key = normalized(value) if isinstance(value, str) else digest(value)
            if key not in unique:
                unique[key] = {"value": value, "sources": []}
            unique[key]["sources"].append(ref)
        choices = list(unique.values())
        provenance[path] = choices
        if not choices:
            return ""
        if len(choices) == 1:
            return choices[0]["value"]
        cid = digest([path, sorted(unique)])
        decision = decisions.get(cid)
        if decision is not None and any(c["value"] == decision for c in choices):
            return decision
        conflicts.append({"id": cid, "field": path, "kind": "profile", "options": choices})
        return ""  # Do not insert a disputed value into a draft.

    for field in ("name", "email", "phone", "linkedin", "github", "leetcode"):
        profile[field] = choose(field, [((r.parsed_raw or {}).get(field), f"resume:{r.id}") for r in resumes])
    for field in ("skills", "certifications", "achievements", "links"):
        values = {}
        for r in resumes:
            raw = (r.parsed_raw or {}).get(field) or []
            if isinstance(raw, dict):
                raw = [s for group in raw.values() for s in (group if isinstance(group, list) else [group])]
            for value in raw:
                if not isinstance(value, str):
                    continue
                values.setdefault(normalized(value), value)
                provenance.setdefault(f"{field}:{value}", []).append(f"resume:{r.id}")
        profile[field] = list(values.values())
    # Confirmed terminology stays traceable to the achievement that established it.
    for item in evidence:
        for skill in item["data"].get("confirmed_terms", []):
            if normalized(skill) not in {normalized(s) for s in profile["skills"]}:
                profile["skills"].append(skill)
            provenance.setdefault(f"skills:{skill}", []).extend(item["source_refs"])
    for section, fields in (("education", ("school", "degree")), ("experience", ("company", "role")), ("projects", ("name",))):
        groups = {}
        for resume in resumes:
            for entry in (resume.parsed_raw or {}).get(section, []) or []:
                key = tuple(normalized(entry.get(f)) for f in fields)
                groups.setdefault(key, []).append((entry, f"resume:{resume.id}"))
        profile[section] = []
        for key, entries in groups.items():
            merged = {f: entries[0][0].get(f, "") for f in fields}
            for field in ("dates", "location", "technologies"):
                options = []
                for entry, ref in entries:
                    value = entry.get(field)
                    if field == "dates":
                        value = value or entry.get("date_range") or entry.get("year") or entry.get("graduation_year")
                    options.append((value, ref))
                merged[field] = choose(f"{section}:{'/'.join(key)}:{field}", options)
            merged["source_refs"] = sorted({ref for _, ref in entries})
            profile[section].append(merged)
    suppressed = set()
    for index, left in enumerate(evidence):
        for right in evidence[index + 1:]:
            a, b = left["data"], right["data"]
            # Only highly similar descriptions warrant a possible-conflict flag.
            clean = lambda t: re.sub(r"\d+(?:\.\d+)?", "#", normalized(t))
            if SequenceMatcher(None, clean(a["content"]), clean(b["content"])).ratio() < .9:
                continue
            same_job = (normalized(a.get("company")), normalized(a.get("role")), a.get("section")) == (normalized(b.get("company")), normalized(b.get("role")), b.get("section"))
            same_numbers = re.findall(r"\d+(?:\.\d+)?", a["content"]) == re.findall(r"\d+(?:\.\d+)?", b["content"])
            polarity = lambda text: bool(re.search(r"\b(not|never|planned|proposed)\b", text, re.I))
            if same_job and same_numbers and polarity(a["content"]) == polarity(b["content"]):
                continue
            cid = digest(["evidence", left["id"], left["revision"], right["id"], right["revision"]])
            if decisions.get(cid) == "both":
                continue
            if decisions.get(cid) in (left["id"], right["id"]):
                suppressed.add(right["id"] if decisions[cid] == left["id"] else left["id"])
            else:
                conflicts.append({"id": cid, "kind": "evidence", "field": "Possible conflicting metric or attribution",
                    "options": [{"value": e["id"], "label": f'{e["data"].get("company", "")}: {e["data"]["content"]}', "sources": e["source_refs"]} for e in (left, right)] + [{"value": "both", "label": "Both are accurate, separate achievements", "sources": left["source_refs"] + right["source_refs"]}]})
    profile["source_map"] = provenance
    profile["source_documents"] = [{"id": r.id, "filename": getattr(r, "name", "Uploaded resume"),
                                    "text": (r.parsed_raw or {}).get("raw_source_text", ""),
                                    "summary": (r.parsed_raw or {}).get("profile_summary", ""),
                                    "unassigned_text": (r.parsed_raw or {}).get("unassigned_text", [])}
                                   for r in resumes]
    profile["candidate_key"] = candidate_key(resumes)
    profile["skill_categories"] = skill_categories(profile["skills"])
    profile["evidence"] = [e for e in evidence if e["id"] not in suppressed]
    return profile, conflicts
