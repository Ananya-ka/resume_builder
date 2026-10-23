from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.routes import get_current_user_id
from app.models.schemas import User
from app.catalog.models import EvidenceCatalog
from app.catalog.schemas import CreateCatalog, ImportResumes, ClaimAction, ResolveConflict, ArtifactInput, CatalogOut, CatalogSummary
from app.catalog import service

router = APIRouter(prefix="/api/catalogs", tags=["Evidence Catalog"])


@router.get("", response_model=list[CatalogSummary])
def list_catalogs(db: Session = Depends(get_db), user: str = Depends(get_current_user_id)):
    return [dict(id=c.id, name=c.name, revision=c.revision) for c in db.query(EvidenceCatalog).filter_by(user_id=user).order_by(EvidenceCatalog.id).all()]


@router.post("", response_model=CatalogOut, status_code=201)
def create_catalog(req: CreateCatalog, db: Session = Depends(get_db), user: str = Depends(get_current_user_id)):
    if not db.query(User).filter_by(id=user).first():
        db.add(User(id=user))
        db.flush()
    catalog = EvidenceCatalog(user_id=user, name=req.name, identity={}, revision=1)
    db.add(catalog)
    db.flush()
    service.event(db, catalog, user, "create_catalog", {})
    db.commit()
    return service.view(db, catalog)


@router.get("/{catalog_id}", response_model=CatalogOut)
def get_catalog(catalog_id: int, db: Session = Depends(get_db), user: str = Depends(get_current_user_id)):
    return service.view(db, service.owned(db, catalog_id, user))


@router.post("/{catalog_id}/imports", response_model=CatalogOut)
def import_sources(catalog_id: int, req: ImportResumes, db: Session = Depends(get_db), user: str = Depends(get_current_user_id)):
    catalog = service.owned(db, catalog_id, user)
    service.import_resumes(db, catalog, req, user)
    db.commit()
    return service.view(db, catalog)


@router.post("/{catalog_id}/claims/{claim_id}/actions", response_model=CatalogOut)
def claim_action(catalog_id: int, claim_id: int, req: ClaimAction, db: Session = Depends(get_db), user: str = Depends(get_current_user_id)):
    catalog = service.owned(db, catalog_id, user)
    service.mutate_claim(db, catalog, service.claim_for(db, catalog, claim_id), req, user)
    db.commit()
    return service.view(db, catalog)


@router.post("/{catalog_id}/conflicts/{conflict_id}/resolve", response_model=CatalogOut)
def resolve_conflict(catalog_id: int, conflict_id: int, req: ResolveConflict, db: Session = Depends(get_db), user: str = Depends(get_current_user_id)):
    catalog = service.owned(db, catalog_id, user)
    service.resolve(db, catalog, conflict_id, req, user)
    db.commit()
    return service.view(db, catalog)


@router.post("/{catalog_id}/claims/{claim_id}/artifacts", response_model=CatalogOut)
def add_artifact(catalog_id: int, claim_id: int, req: ArtifactInput, db: Session = Depends(get_db), user: str = Depends(get_current_user_id)):
    catalog = service.owned(db, catalog_id, user)
    service.attach_artifact(db, catalog, service.claim_for(db, catalog, claim_id), req, user)
    db.commit()
    return service.view(db, catalog)
