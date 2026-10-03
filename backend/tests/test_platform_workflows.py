from test_security_workflow import client, setup
from app.config import settings
from app.db import SessionLocal
from app.models import Evidence, Encounter
from cryptography.fernet import Fernet
from sqlalchemy import select
from datetime import date
import uuid


def test_sync_is_idempotent_and_isolated(client):
    h,s,_=setup(client,'District A','a@example.org')
    other,_,_=setup(client,'District B','b@example.org')
    child=client.post('/api/clients',headers=h,json={'name':'Fictional Child','reference':'TEST-1','date_of_birth':'2024-01-01','sex':'Female','facility_id':s['facilities'][0]['id']}).json()
    data={'operation_id':str(uuid.uuid4()),'encounter':{'client_id':child['id'],'programme':'growth','visit_date':str(date.today()),'assessment':'Fictional review','measurements':{'weight_kg':12.3}}}
    first=client.post('/api/sync/encounters',headers=h,json=data)
    assert first.status_code==201,first.text
    replay=client.post('/api/sync/encounters',headers=h,json=data)
    assert replay.status_code in (200,201),replay.text
    assert replay.json()['replayed']
    assert len(client.get('/api/encounters',headers=h).json())==1
    data['encounter']['measurements']['weight_kg']=13
    assert client.post('/api/sync/encounters',headers=h,json=data).status_code==409
    data['operation_id']=str(uuid.uuid4())
    assert client.post('/api/sync/encounters',headers=other,json=data).status_code==404
    with SessionLocal() as db:
        entry=db.scalar(select(Encounter))
        assert entry.source_type=='Offline Sync'
        assert entry.form_version==1 and entry.form_snapshot


def test_exports_queue_and_evidence_are_scoped(client,monkeypatch):
    monkeypatch.setattr(settings(),'evidence_encryption_key',Fernet.generate_key().decode())
    h,s,_=setup(client,'District A','a@example.org')
    other,_,_=setup(client,'District B','b@example.org')
    facility=s['facilities'][0]['id']
    indicator=client.post('/api/indicators',headers=h,json={'name':'Test coverage','programme':'growth','definition':'Fictional indicator','numerator_definition':'Served','denominator_definition':'Eligible','target':90,'approval_reference':'TEST ONLY'}).json()
    report=client.post('/api/reports',headers=h,json={'facility_id':facility,'period':'2026-09','values':[{'indicator_id':indicator['id'],'numerator':60,'denominator':100}]}).json()
    for state in ['Submitted','Verified','Approved','Locked']:
        assert client.post('/api/reports/'+report['id']+'/transition',headers=h,json={'state':state}).status_code==200
    intelligence=client.get('/api/intelligence',headers=h,params={'organization_id':h['X-Organization-ID'],'period':'2026-09'})
    assert intelligence.status_code==200,intelligence.text
    assert intelligence.json()['signals']
    path='/api/reports/'+report['id']
    assert client.get(path+'/export/pdf',headers=h).content.startswith(b'%PDF-')
    assert client.get(path+'/export/xlsx',headers=h).content.startswith(b'PK')
    assert client.get(path+'/export/pdf',headers=other).status_code==404
    job=client.post(path+'/jobs',headers=h,json={'format':'pdf'})
    assert job.status_code==202,job.text
    assert client.get('/api/report-jobs/'+job.json()['id'],headers=h).json()['state']=='Completed'
    assert client.get('/api/report-jobs/'+job.json()['id']+'/download',headers=h).content.startswith(b'%PDF-')
    visit=client.post('/api/registers/supervision',headers=h,json={'title':'Fictional visit','facility_id':facility,'details':{'date':'2026-10-03','status':'Scheduled'}})
    assert visit.status_code==201,visit.text
    payload=b'%PDF-1.4 fictional authorized evidence'
    upload=client.post('/api/supervision/'+visit.json()['id']+'/evidence',headers=h,files={'file':('evidence.pdf',payload,'application/pdf')})
    assert upload.status_code==201,upload.text
    id=upload.json()['id']
    assert client.get('/api/evidence/'+id+'/download',headers=h).content==payload
    assert client.get('/api/evidence/'+id+'/download',headers=other).status_code==404
    with SessionLocal() as db:
        assert 'fictional authorized' not in db.get(Evidence,id).encrypted_content


def test_owner_provisioning_and_revoked_regional_scope(client,monkeypatch):
    import os
    from urllib.parse import urlparse, parse_qs
    monkeypatch.setattr(settings(),'main_admin_email','owner@example.org')
    result=client.post('/api/platform/setup',headers={'X-Setup-Token':os.environ['SETUP_TOKEN']},json={'name':'Test Owner','email':'owner@example.org','password':'StrongOwnerPassword123!'})
    assert result.status_code==201,result.text
    oh={'Authorization':'Bearer '+result.json()['access_token']}
    central=next(r for r in client.get('/api/geography/regions').json() if r['name']=='Central')
    r=client.post('/api/platform/organizations',headers=oh,json=dict(name='Fictional New Directorate',organization_type='District Health Directorate',region_id=central['id'],health_district_name='Fictional Health District',subdistricts=[{'name':'Fictional Subdistrict'}],facilities=[],admin_name='Fictional Admin',admin_email='new@example.org',programmes=['growth']))
    assert r.status_code==201,r.text
    org=r.json()['organization']['id']
    token=parse_qs(urlparse(r.json()['invitation']['url']).query)['reset'][0]
    assert client.post('/api/auth/password-reset/complete',json={'token':token,'password':'NewPassword123!'}).status_code==200
    assert client.get('/api/auth/me',headers=oh).json()['platform_admin']
    assert client.get('/api/clients',headers={**oh,'X-Organization-ID':org}).status_code==403
    assert client.get('/api/platform/organizations/'+org,headers=oh).status_code==200
    r=client.post('/api/platform/staff',headers=oh,json={'name':'Regional Test','email':'regional-test@example.org','level':'REGION','role':'Regional Nutrition Officer','region_id':central['id']})
    assert r.status_code==201,r.text
    token=parse_qs(urlparse(r.json()['invitation']['url']).query)['reset'][0]
    client.post('/api/auth/password-reset/complete',json={'token':token,'password':'RegionalPassword123!'})
    login=client.post('/api/auth/login',json={'email':'regional-test@example.org','password':'RegionalPassword123!'}).json()
    rh={'Authorization':'Bearer '+login['access_token']}
    assert client.get('/api/intelligence',headers=rh).status_code==200
    assert client.get('/api/platform/staff',headers=rh).status_code==403
    assert client.get('/api/clients',headers={**rh,'X-Organization-ID':org}).status_code==403
    grants=client.get('/api/platform/staff',headers=oh).json()['grants']
    grant=next(g for g in grants if g['role']=='Regional Nutrition Officer')
    assert client.patch('/api/platform/assignments/grant/'+grant['id'],headers=oh,json={'active':False}).status_code==200
    assert client.get('/api/intelligence',headers=rh).status_code==403
