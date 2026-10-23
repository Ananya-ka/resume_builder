"""Conservative catalog operations: suggestions are not verification or approval."""
import hashlib
import json
import re
from difflib import SequenceMatcher
from fastapi import HTTPException
from app.models.schemas import Resume
from app.catalog.models import EvidenceCatalog, CatalogSource, CatalogClaim, ClaimSource, CatalogConflict, CatalogEvent
from app.catalog.schemas import ClaimData
from app.services.structured_parser import StructuredResumeParser


def norm(text):
    return " ".join(str(text or "").casefold().split()).rstrip(".!")


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def fingerprint(data):
    return digest([norm(data.get(k)) for k in ("kind", "association", "role", "text")])


def owned(db, catalog_id, user_id):
    obj = db.query(EvidenceCatalog).filter_by(id=catalog_id, user_id=user_id).first()
    if not obj:
        raise HTTPException(404, "Catalog not found")
    return obj


def lock_revision(db, catalog, revision):
    # Atomic CAS works on PostgreSQL and SQLite; serializes every catalog mutation.
    count = db.query(EvidenceCatalog).filter_by(id=catalog.id, revision=revision).update(
        {"revision": EvidenceCatalog.revision + 1}, synchronize_session=False)
    if count != 1:
        raise HTTPException(409, "Catalog changed. Refresh before saving.")
    db.refresh(catalog)


def event(db, catalog, actor, action, details, claim=None):
    db.add(CatalogEvent(catalog_id=catalog.id, actor=actor, action=action,
                        claim_id=claim.id if claim else None, details=details))


def make_data(text, association, role, kind, dates=""):
    meta = StructuredResumeParser().extract_bullet_metadata(text)
    # This metadata is lexical extraction, never model-suggested technologies.
    temporal = "planned" if re.search(r"\b(planned|planning|proposed|will|intend)\b", text, re.I) else "unknown"
    return ClaimData(text=text, association=association or "Unassigned", role=role,
                     kind=kind, dates=dates, technologies=meta.get("technologies", []),
                     metrics=meta.get("metrics", []), temporal_status=temporal).model_dump()


def extracted_claims(raw):
    for section, kind, org in (("experience", "experience", "company"), ("projects", "project", "name")):
        for entry in raw.get(section, []) or []:
            association = entry.get(org) or "Unassigned"
            role = entry.get("role", "") if kind == "experience" else ""
            dates = entry.get("dates") or entry.get("date_range") or ""
            passage = entry.get("source_quote", "")
            for text in entry.get("bullets", []) or []:
                if isinstance(text, str) and text.strip():
                    yield make_data(text, association, role, kind, dates), passage
            if dates:
                yield make_data(dates, association, role, "dates", dates), passage
    for entry in raw.get("education", []) or []:
        for field in ("degree", "dates", "year", "graduation_year"):
            if entry.get(field):
                yield make_data(entry[field], entry.get("school") or "Unassigned", "", "education"), entry.get("source_quote", "")
    for section, kind in (("skills", "skill"), ("achievements", "achievement"), ("certifications", "certification")):
        values = raw.get(section) or []
        if isinstance(values, dict):
            values = [v for group in values.values() for v in (group if isinstance(group, list) else [group])]
        for value in values:
            if isinstance(value, str) and value.strip():
                yield make_data(value, "Profile", "", kind), ""


def locate(text, quote):
    """Return actual offsets, tolerating whitespace without inventing quote text."""
    pattern = r"\s+".join(re.escape(w) for w in quote.split())
    match = re.search(pattern, text, re.I) if pattern else None
    return (match.start(), match.end(), match.group()) if match else (None, None, quote)


def import_resumes(db, catalog, request, actor):
    if not request.same_candidate_confirmed:
        raise HTTPException(422, "Confirm these resumes belong to the same candidate.")
    resumes = db.query(Resume).filter(Resume.id.in_(request.resume_ids), Resume.user_id == actor).order_by(Resume.id).all()
    if len(resumes) != len(request.resume_ids):
        raise HTTPException(404, "Resume not found")
    for r in resumes:
        raw = r.parsed_raw or {}
        if raw.get("parsing_status") != "ready" or not raw.get("raw_source_text", "").strip():
            raise HTTPException(409, "Wait for all resumes to finish parsing; failed sources must be uploaded again.")
    emails = {norm((r.parsed_raw or {}).get("email")) for r in resumes} - {""}
    existing_email = catalog.identity.get("email")
    if existing_email:
        emails.add(existing_email)
    if len(emails) > 1:
        raise HTTPException(422, "Conflicting candidate emails. Use separate catalogs or correct the source identity first.")
    lock_revision(db, catalog, request.revision)
    if emails:
        catalog.identity = {"email": next(iter(emails))}
    for resume in resumes:
        raw = resume.parsed_raw
        text = raw["raw_source_text"]
        sha = hashlib.sha256(text.encode()).hexdigest()
        source = db.query(CatalogSource).filter_by(catalog_id=catalog.id, resume_id=resume.id, sha256=sha).first()
        if source:  # Repeated import is idempotent, including corrected/rejected claims.
            continue
        source = CatalogSource(catalog_id=catalog.id, resume_id=resume.id, filename=resume.name,
                               kind="resume", sha256=sha, text=text)
        db.add(source)
        db.flush()
        for data, passage in extracted_claims(raw):
            key = fingerprint(data)
            claim = db.query(CatalogClaim).filter_by(catalog_id=catalog.id, fingerprint=key).first()
            start, end, quote = locate(text, data["text"])
            # Literal existence is support for extraction, not proof of the real-world claim.
            context_ok = data["association"] == "Profile" or norm(data["association"]) in norm(text)
            if passage:
                context_ok = context_ok and norm(data["text"]) in norm(passage) and norm(data["association"]) in norm(passage)
            if not claim:
                claim = CatalogClaim(catalog_id=catalog.id, fingerprint=key, data=data, revision=1,
                                     approval="pending", verification="extracted" if start is not None and context_ok else "unresolved", history=[])
                db.add(claim)
                db.flush()
            # Existing claim versions cannot inherit new parse metadata or approval.
            if not db.query(ClaimSource).filter_by(claim_id=claim.id, source_id=source.id, revision=claim.revision).first():
                db.add(ClaimSource(claim_id=claim.id, source_id=source.id, quote=quote,
                                   start=start, end=end, revision=claim.revision))
    db.flush()
    detect_conflicts(db, catalog)
    event(db, catalog, actor, "import", {"resume_ids": request.resume_ids})


def skeleton(data):
    text = norm(data["text"])
    for tech in sorted(data.get("technologies", []), key=len, reverse=True):
        text = re.sub(r"(?<!\w)" + re.escape(tech.casefold()) + r"(?!\w)", "TECH", text)
    text = re.sub(r"\d+(?:\.\d+)?", "NUMBER", text)
    text = re.sub(r"\b(led|assisted|helped|owned|contributed|supported|planned|proposed)\b", "ACTION", text)
    return text


def detect_conflicts(db, catalog):
    claims = db.query(CatalogClaim).filter_by(catalog_id=catalog.id).order_by(CatalogClaim.id).all()
    active = {c.id: c for c in claims if c.approval != "rejected"}
    for old in db.query(CatalogConflict).filter_by(catalog_id=catalog.id, state="open").all():
        if any(i not in active or active[i].revision != old.revisions.get(str(i)) for i in old.claim_ids):
            old.state = "superseded"
    for i, a in enumerate(active.values()):
        for b in list(active.values())[i + 1:]:
            x, y = a.data, b.data
            same = (norm(x["association"]), norm(x["role"]), x["kind"]) == (norm(y["association"]), norm(y["role"]), y["kind"])
            similar = SequenceMatcher(None, skeleton(x), skeleton(y)).ratio() >= .82
            kind = None
            if same and x["kind"] == "dates" and norm(x["text"]) != norm(y["text"]):
                kind = "dates"
            elif similar and x["kind"] in {"experience", "project"} and y["kind"] in {"experience", "project"}:
                if not same:
                    kind = "attribution"
                elif x["metrics"] != y["metrics"]:
                    kind = "metrics"
                elif set(map(norm, x["technologies"])) != set(map(norm, y["technologies"])):
                    kind = "technology_usage"
                elif norm(x["text"]) != norm(y["text"]) and re.search(r"\b(led|assisted|helped|owned|contributed|planned|proposed)\b", x["text"] + " " + y["text"], re.I):
                    kind = "ownership_or_status"
            if not kind:
                continue
            key = digest([a.id, a.revision, b.id, b.revision, kind])
            if db.query(CatalogConflict).filter_by(catalog_id=catalog.id, fingerprint=key).first():
                continue
            db.add(CatalogConflict(catalog_id=catalog.id, fingerprint=key, kind=kind,
                claim_ids=[a.id, b.id], revisions={str(a.id): a.revision, str(b.id): b.revision},
                question=f'For {x["association"]}, these sources differ on {kind.replace("_", " ")}. Which statement is accurate, or do they describe separate work?',
                benefit="Your answer keeps dates, tools, ownership and outcomes attached to the right experience. Neither alternative will be approved automatically.", state="open"))


def claim_for(db, catalog, claim_id):
    claim = db.query(CatalogClaim).filter_by(id=claim_id, catalog_id=catalog.id).first()
    if not claim:
        raise HTTPException(404, "Claim not found")
    return claim


def open_conflicts(db, catalog, claim):
    return [c for c in db.query(CatalogConflict).filter_by(catalog_id=catalog.id, state="open").all() if claim.id in c.claim_ids]


def mutate_claim(db, catalog, claim, req, actor):
    if claim.revision != req.claim_revision:
        raise HTTPException(409, "Claim changed. Refresh before saving.")
    if req.action in {"approve", "edit"} and not req.confirm_accuracy:
        raise HTTPException(422, "Explicitly confirm the accuracy of these details.")
    if req.action == "approve" and open_conflicts(db, catalog, claim):
        raise HTTPException(409, "Resolve this claim's conflicts before approval.")
    if req.action == "edit" and req.data is None:
        raise HTTPException(422, "Edited claim data is required.")
    lock_revision(db, catalog, req.catalog_revision)
    before = {"revision": claim.revision, "data": claim.data, "approval": claim.approval, "verification": claim.verification}
    if req.action == "edit":
        data = req.data.model_dump()
        duplicate = db.query(CatalogClaim).filter_by(catalog_id=catalog.id, fingerprint=fingerprint(data)).first()
        if duplicate and duplicate.id != claim.id:
            raise HTTPException(409, "This matches another catalog claim. Review that record instead.")
        claim.history = [*claim.history, {**before, "reason": req.reason}]
        claim.revision += 1
        claim.data = data
        claim.fingerprint = fingerprint(data)
        claim.approval = "pending"
        claim.verification = "user_confirmed"
    elif req.action == "organize":
        claim.data = {**claim.data, "tags": req.tags}
    elif req.action == "approve":
        claim.approval = "approved"
        if claim.verification != "artifact_supported":
            claim.verification = "user_confirmed"
    else:
        claim.approval = "rejected"
    event(db, catalog, actor, req.action, {"before": before, "revision": claim.revision,
          "reason": req.reason, "confirmed": req.confirm_accuracy, "statement": claim.data}, claim)
    db.flush()
    detect_conflicts(db, catalog)


def resolve(db, catalog, conflict_id, req, actor):
    conflict = db.query(CatalogConflict).filter_by(id=conflict_id, catalog_id=catalog.id, state="open").first()
    if not conflict:
        raise HTTPException(409, "Conflict is no longer open. Refresh the catalog.")
    if req.choice == "select" and req.selected_claim_id not in conflict.claim_ids:
        raise HTTPException(422, "Select an alternative from this conflict.")
    lock_revision(db, catalog, req.catalog_revision)
    conflict.state = "resolved"
    conflict.resolution = {"choice": req.choice, "selected_claim_id": req.selected_claim_id, "reason": req.reason, "actor": actor}
    if req.choice == "select":
        for cid in conflict.claim_ids:
            if cid != req.selected_claim_id:
                losing = claim_for(db, catalog, cid)
                losing.approval = "rejected"
    event(db, catalog, actor, "resolve_conflict", {"conflict_id": conflict.id, **conflict.resolution})
    db.flush()
    detect_conflicts(db, catalog)


def attach_artifact(db, catalog, claim, req, actor):
    if claim.revision != req.claim_revision:
        raise HTTPException(409, "Claim changed. Refresh first.")
    if not req.attest_support:
        raise HTTPException(422, "Confirm this excerpt supports this exact claim.")
    start, end, quote = locate(req.text, req.quote)
    if start is None:
        raise HTTPException(422, "The supporting quote must occur in the artifact text.")
    lock_revision(db, catalog, req.catalog_revision)
    source = CatalogSource(catalog_id=catalog.id, filename=req.title, kind="artifact_excerpt",
                           text=req.text, sha256=hashlib.sha256(req.text.encode()).hexdigest())
    db.add(source)
    db.flush()
    db.add(ClaimSource(claim_id=claim.id, source_id=source.id, quote=quote, start=start, end=end, revision=claim.revision))
    claim.verification = "artifact_supported"
    # The candidate attests relevance; no claim of independent authenticity verification.
    event(db, catalog, actor, "attach_artifact", {"revision": claim.revision, "source_id": source.id,
          "support_attested_by_candidate": True, "independent_verification": False}, claim)


def view(db, catalog):
    conflicts = db.query(CatalogConflict).filter_by(catalog_id=catalog.id).order_by(CatalogConflict.id).all()
    sources = {s.id: s for s in db.query(CatalogSource).filter_by(catalog_id=catalog.id).all()}
    claims = db.query(CatalogClaim).filter_by(catalog_id=catalog.id).order_by(CatalogClaim.id).all()
    links = db.query(ClaimSource).filter(ClaimSource.claim_id.in_([c.id for c in claims])).all() if claims else []
    output = []
    for c in claims:
        unresolved = [f.id for f in conflicts if f.state == "open" and c.id in f.claim_ids]
        refs = []
        for link in links:
            if link.claim_id == c.id:
                s = sources[link.source_id]
                refs.append({"id": s.id, "filename": s.filename, "kind": s.kind, "resume_id": s.resume_id,
                             "sha256": s.sha256, "quote": link.quote, "start": link.start, "end": link.end, "revision": link.revision})
        indicator = ("Conflicting sources — review required" if unresolved else
                     "Candidate-attested artifact excerpt; not independently verified" if c.verification == "artifact_supported" else
                     "Explicit candidate confirmation" if c.verification == "user_confirmed" else
                     "Literal source extraction; not candidate-approved" if c.verification == "extracted" else
                     "Source attribution needs confirmation")
        output.append({"id": c.id, "revision": c.revision, "data": c.data, "approval": c.approval,
                       "verification": "unresolved" if unresolved else c.verification,
                       "confidence_indicator": indicator, "conflict_ids": unresolved, "sources": refs, "history": c.history})
    events = db.query(CatalogEvent).filter_by(catalog_id=catalog.id).order_by(CatalogEvent.id.desc()).all()
    return {"id": catalog.id, "name": catalog.name, "revision": catalog.revision, "claims": output,
            "conflicts": [{k: getattr(c, k) for k in ("id", "kind", "claim_ids", "question", "benefit", "state", "resolution")} for c in conflicts],
            "events": [{"id": e.id, "claim_id": e.claim_id, "action": e.action, "details": e.details,
                        "actor": e.actor, "created_at": e.created_at.isoformat() if e.created_at else None} for e in events]}
