"""Disposable SQLite, real extraction, inline Celery delivery; no network/provider."""
import pytest
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
from app.models.schemas import User, Resume
from app.catalog.api import router
from app.api.routes import router as base_router
from app.catalog.models import CatalogClaim, CatalogConflict, EvidenceCatalog
from app.catalog.service import make_data, detect_conflicts, fingerprint
from app.worker import tasks
from migrations.catalog_v1 import upgrade

@pytest.fixture
def env(monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    @event.listens_for(engine,'connect')
    def fk(conn,_):conn.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    monkeypatch.setattr(tasks,'SessionLocal',factory)
    monkeypatch.setattr(tasks,'ResumeParser',lambda:SimpleNamespace(client=None))
    monkeypatch.setattr(tasks.parse_resume_task,'delay',lambda *args:tasks.parse_resume_task.run(*args))
    app=FastAPI();app.include_router(router);app.include_router(base_router)
    def db():
        with factory() as session:yield session
    app.dependency_overrides[get_db]=db
    with TestClient(app,headers={'X-User-Id':'alice'}) as client:yield client,factory
    engine.dispose()

def document(metric=40,year=2022):
    return f'''Jane Doe
jane@example.com
Skills
Python, Redis, PostgreSQL
Experience
Meridian | Software Engineer | Jan 2020 - Jan {year}
- Maintained PostgreSQL databases.
Projects
Ingestion
- Reduced ingestion runtime by {metric}% using Python.
- Built response caching using Redis.
'''

def three(client):
    r=client.post('/api/resumes/upload-batch',files=[('files',(f'version-{i}.txt',document(m,y).encode(),'text/plain')) for i,(m,y) in enumerate([(40,2022),(40,2022),(50,2023)])])
    assert r.status_code==200,r.text
    ids=[x['id'] for x in r.json()]
    assert all(r['parsed_raw']['parsing_status']=='ready' for r in client.get('/api/resumes').json())
    cat=client.post('/api/catalogs',json={'name':'Jane'}).json()
    r=client.post(f'/api/catalogs/{cat["id"]}/imports',json={'resume_ids':ids,'revision':cat['revision'],'same_candidate_confirmed':True})
    assert r.status_code==200,r.text
    return r.json(),ids

def action(client,cat,claim,verb,**extra):
    return client.post(f'/api/catalogs/{cat["id"]}/claims/{claim["id"]}/actions',json={'catalog_revision':cat['revision'],'claim_revision':claim['revision'],'action':verb,'reason':'Checked my records','confirm_accuracy':True,**extra})

def test_three_resume_acceptance_and_persistent_approval(env):
    c,factory=env;cat,ids=three(c)
    claim=next(x for x in cat['claims'] if '40%' in x['data']['text'])
    assert len(claim['sources'])==2
    assert all(x['approval']=='pending' for x in cat['claims'])
    assert {'dates','metrics'}<={x['kind'] for x in cat['conflicts']}
    assert action(c,cat,claim,'approve').status_code==409
    conflict=next(x for x in cat['conflicts'] if x['kind']=='metrics')
    r=c.post(f'/api/catalogs/{cat["id"]}/conflicts/{conflict["id"]}/resolve',json={'catalog_revision':cat['revision'],'choice':'select','selected_claim_id':claim['id'],'reason':'50% was incorrect'})
    assert r.status_code==200,r.text
    cat=r.json();r=action(c,cat,claim,'approve');assert r.status_code==200,r.text
    cat=r.json()
    with factory() as db:assert db.get(CatalogClaim,claim['id']).approval=='approved'
    loaded=c.get(f'/api/catalogs/{cat["id"]}').json()
    assert next(x for x in loaded['claims'] if x['id']==claim['id'])['approval']=='approved'
    assert all(s['start'] is not None for s in claim['sources'])
    r=c.post(f'/api/catalogs/{cat["id"]}/imports',json={'resume_ids':ids,'revision':cat['revision'],'same_candidate_confirmed':True})
    assert r.status_code==200,r.text
    assert len(r.json()['claims'])==len(cat['claims'])
    assert len(next(x for x in r.json()['claims'] if x['id']==claim['id'])['sources'])==2

def test_edit_requires_confirmation_and_resets_approval(env):
    c,_=env;cat,_=three(c);claim=next(x for x in cat['claims'] if x['data']['kind']=='skill')
    assert action(c,cat,claim,'approve',confirm_accuracy=False).status_code==422
    cat=action(c,cat,claim,'approve').json()
    r=action(c,cat,claim,'edit',data={**claim['data'],'contribution':'Implemented the ingestion task'})
    assert r.status_code==200,r.text
    cat=r.json();updated=next(x for x in cat['claims'] if x['id']==claim['id'])
    assert updated['revision']==2 and updated['approval']=='pending'
    assert updated['history'][0]['approval']=='approved' and updated['sources'][0]['revision']==1
    assert action(c,cat,claim,'approve').status_code==409
    assert action(c,cat,updated,'approve',catalog_revision=1).status_code==409
    assert action(c,cat,updated,'approve').status_code==200

def test_scope_validation_and_identity(env):
    c,factory=env;cat,ids=three(c);path=f'/api/catalogs/{cat["id"]}/imports'
    body={'resume_ids':ids,'revision':cat['revision'],'same_candidate_confirmed':True}
    assert c.get(f'/api/catalogs/{cat["id"]}',headers={'X-User-Id':'bob'}).status_code==404
    assert c.post(path,json={**body,'resume_ids':[ids[0],ids[0]]}).status_code==422
    assert c.post(path,json={**body,'resume_ids':[1,2,3,4]}).status_code==422
    assert c.post(path,json={**body,'same_candidate_confirmed':False}).status_code==422
    assert c.post('/api/catalogs',json={'name':'  '}).status_code==422
    with factory() as db:
        r=db.get(Resume,ids[0]);r.parsed_raw={**r.parsed_raw,'email':'different@example.com'};db.commit()
    assert c.post(path,json=body).status_code==422
    assert c.get(f'/api/catalogs/{cat["id"]}').json()['revision']==cat['revision']

@pytest.mark.parametrize('kind,left,right,org',[
 ('technology_usage','Built caching using Redis.','Built caching using Memcached.','Same'),
 ('ownership_or_status','Led development of the API.','Assisted development of the API.','Same'),
 ('attribution','Reduced query latency by 40%.','Reduced query latency by 40%.','Different')])
def test_conflict_kinds(kind,left,right,org,env):
    _,factory=env
    with factory() as db:
        db.add(User(id='test'));db.flush();cat=EvidenceCatalog(user_id='test',name='Test',identity={},revision=1);db.add(cat);db.flush()
        for text,association in [(left,'Same'),(right,org)]:
            data=make_data(text,association,'','project')
            if 'Memcached' in text:data['technologies']=['Memcached']
            db.add(CatalogClaim(catalog_id=cat.id,fingerprint=fingerprint(data),data=data,approval='pending',verification='extracted',revision=1,history=[]))
        db.flush();detect_conflicts(db,cat);db.flush()
        assert kind in [x.kind for x in db.query(CatalogConflict).all()]

def test_artifact_is_attested_support_not_approval(env):
    c,_=env;cat,_=three(c);claim=next(x for x in cat['claims'] if x['data']['kind']=='skill')
    path=f'/api/catalogs/{cat["id"]}/claims/{claim["id"]}/artifacts'
    body={'catalog_revision':cat['revision'],'claim_revision':1,'title':'Test report','text':'Python test passed.','quote':'Invented','attest_support':True}
    assert c.post(path,json=body).status_code==422
    assert c.post(path,json={**body,'quote':'Python test passed.','attest_support':False}).status_code==422
    r=c.post(path,json={**body,'quote':'Python test passed.'});assert r.status_code==200,r.text
    changed=next(x for x in r.json()['claims'] if x['id']==claim['id'])
    assert changed['approval']=='pending' and changed['verification']=='artifact_supported'
    assert 'not independently verified' in changed['confidence_indicator']

def test_unmatched_parse_is_unresolved(env):
    c,factory=env;cat,ids=three(c)
    with factory() as db:
        r=db.get(Resume,ids[0]);r.parsed_raw={**r.parsed_raw,'raw_source_text':'Jane jane@example.com','projects':[{'name':'Invented','bullets':['Invented outcome 900%.']}]};db.commit()
    r=c.post(f'/api/catalogs/{cat["id"]}/imports',json={'resume_ids':[ids[0]],'revision':cat['revision'],'same_candidate_confirmed':True})
    assert r.status_code==200,r.text
    claim=next(x for x in r.json()['claims'] if x['data']['text']=='Invented outcome 900%.')
    assert claim['verification']=='unresolved' and claim['approval']=='pending' and claim['sources'][0]['start'] is None

def test_reject_organize_invalid_resolution(env):
    c,_=env;cat,_=three(c);claim=next(x for x in cat['claims'] if x['data']['kind']=='skill')
    r=action(c,cat,claim,'organize',tags=['Backend']);assert r.status_code==200,r.text
    cat=r.json();changed=next(x for x in cat['claims'] if x['id']==claim['id'])
    assert changed['data']['tags']==['Backend'] and changed['approval']=='pending'
    cat=action(c,cat,claim,'reject').json()
    assert next(x for x in cat['claims'] if x['id']==claim['id'])['approval']=='rejected'
    conflict=cat['conflicts'][0]
    assert c.post(f'/api/catalogs/{cat["id"]}/conflicts/{conflict["id"]}/resolve',json={'catalog_revision':cat['revision'],'choice':'select','selected_claim_id':999,'reason':'test'}).status_code==422

def test_migration_additive_idempotent():
    engine=create_engine('sqlite://')
    with engine.begin() as conn:
        User.__table__.create(conn);conn.execute(User.__table__.insert().values(id='untouched'))
        upgrade(conn);upgrade(conn)
        assert len(inspect(conn).get_table_names())==8
        assert conn.exec_driver_sql('select count(*) from careerproof_schema_versions').scalar()==1
        assert conn.exec_driver_sql('select id from users').scalar()=='untouched'
    engine.dispose()
