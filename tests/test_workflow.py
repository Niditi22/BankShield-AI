import io, json, sqlite3, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from PIL import Image,ImageDraw
from scipy.io import wavfile
import pytest
from app import create_app, SEGMENTS
from worker import process_next
from inference import KEYS

def picture():
    b=io.BytesIO(); im=Image.new('RGB',(600,240),'white'); ImageDraw.Draw(im).line([(60,150),(170,60),(260,160),(450,90)],fill='black',width=5);im.save(b,'PNG');b.seek(0);return b

def voice():
    b=io.BytesIO();sr=16000;t=np.arange(sr*4)/sr;wavfile.write(b,sr,(np.sin(2*np.pi*220*t)*5000).astype(np.int16));b.seek(0);return b

def post(c,url,p=None,form=False):
    token=c.get('/api/session').json['csrf']
    return c.post('/api'+url,data=p if form else None,json=None if form else p,headers={'X-CSRF-Token':token})

def login(c,email='customer@example.test',role='customer'):
    r=post(c,'/login',{'email':email,'password':'TestingPassword123!','role':role});assert r.status_code==200,r.json

def register(c,email='customer@example.test'):
    ch=c.get('/api/challenge').json
    p={'email':email,'password':'TestingPassword123!','name':'Test Customer','phone':'9999999999','dob':'1990-01-01','address':'Test address','consent':'yes','challenge_id':ch['id'],'audio':(voice(),'voice.wav')}
    for k in ('signature','front','left','right'):p[k]=(picture(),k+'.png')
    r=post(c,'/register',p,True);assert r.status_code==200,r.json

@pytest.fixture
def env(tmp_path):
    app=create_app({'TESTING':True,'DATA_DIR':str(tmp_path)})
    result=app.test_cli_runner().invoke(args=['create-admin','--email','admin@example.test','--password','TestingPassword123!'])
    assert result.exit_code==0,result.output
    c=app.test_client();a=app.test_client();login(a,'admin@example.test','admin');register(c);login(c)
    return app,c,a,tmp_path

def approve(a,rid=1):
    return post(a,f'/admin/revisions/{rid}',{'feedback':{k:{'status':'accept','note':''} for k in SEGMENTS}})

def test_access_and_csrf(env):
    app,c,a,p=env
    assert c.get('/api/admin').status_code==403
    assert c.post('/api/logout',json={}).status_code==403
    assert post(c,'/applications',{},True).status_code==403
    media=c.get('/api/customer').json['revision']['payload']['signature']
    assert app.test_client().get('/media/'+media).status_code==401
    stranger=app.test_client();register(stranger,'other@example.test');login(stranger,'other@example.test')
    assert stranger.get('/media/'+media).status_code==403
    assert a.get('/media/'+media).status_code==200

def test_partial_correction_and_approval(env):
    app,c,a,p=env
    fb={k:{'status':'accept','note':''} for k in SEGMENTS};fb['signature']={'status':'redo','note':'Retake on white paper.'}
    assert post(a,'/admin/revisions/1',{'feedback':fb}).status_code==200
    assert post(c,'/revision',{'name':'Test','phone':'9999999999','dob':'1990-01-01','address':'a'},True).status_code==400
    assert post(c,'/revision',{'signature':(picture(),'sig.png')},True).status_code==200
    assert approve(a,2).status_code==200
    assert c.get('/api/session').json['user']['approved']
    assert approve(a,2).status_code==409

def test_complete_application_snapshot_and_decision(env):
    app,c,a,p=env;assert approve(a).status_code==200
    vp=p/'test.avi';w=cv2.VideoWriter(str(vp),cv2.VideoWriter_fourcc(*'MJPG'),15,(160,120))
    for i in range(180):w.write(np.full((120,160,3),100+i%30,np.uint8))
    w.release()
    ch=c.get('/api/challenge?language=Marathi').json
    payload={'purpose':'Loan','signature':(picture(),'sig.png'),'audio':(voice(),'voice.wav'),'video':(io.BytesIO(vp.read_bytes()),'cam.webm'),'challenge_id':ch['id']}
    r=post(c,'/applications',payload,True);assert r.status_code==200,r.json
    exposed=c.get('/api/customer').json['applications'][0]
    assert 'analysis' not in exposed and 'reference' not in exposed
    pending=post(a,'/admin/applications/1',{'decision':'approved','note':'Too early','manual_review':True})
    assert pending.status_code==400
    def engine(refs,evidence,progress):
        progress('Test inference')
        return {'scores':{k:{'value':100 if k.endswith('match') else 1,'status':'computed','note':'TEST DOUBLE — not a model result'} for k in KEYS}}
    assert process_next(p,engine)
    item=a.get('/api/admin').json['applications'][0]
    assert item['analysis']['scores']['signature_match']['value']==100
    assert item['analysis_state']=='complete'
    assert item['analysis']['scores']['video_fake']['value']==1
    original=item['reference']['details']['name']
    assert post(c,'/revision',{'name':'Updated Customer','phone':'9999999999','dob':'1990-01-01','address':'New address'},True).status_code==200
    assert c.get('/api/session').json['user']['approved']['details']['name']==original
    assert approve(a,2).status_code==200
    assert a.get('/api/admin').json['applications'][0]['reference']['details']['name']==original
    assert post(a,'/admin/applications/1',{'decision':'approved','note':'Manual academic test review','manual_review':True}).status_code==200
    assert c.get('/api/customer').json['applications'][0]['state']=='approved'
    assert post(a,'/admin/applications/1',{'decision':'rejected','note':'Second decision','manual_review':True}).status_code==409

def test_bad_image_and_missing_media(env):
    app,c,a,p=env;approve(a)
    ch=c.get('/api/challenge').json
    r=post(c,'/applications',{'purpose':'Loan','challenge_id':ch['id'],'signature':(io.BytesIO(b'not image'),'x.png')},True)
    assert r.status_code==400
    assert a.get('/api/admin').json['applications']==[]

def test_challenge_required(env):
    app,c,a,p=env;approve(a)
    r=post(c,'/applications',{'purpose':'Loan','challenge_id':'forged'},True)
    assert r.status_code==400


def test_deny_section_and_resubmit(env):
    app,c,a,p=env
    fb={k:{'status':'accept','note':''} for k in SEGMENTS}
    fb['front']={'status':'deny','note':'Face obscured.'}
    assert post(a,'/admin/revisions/1',{'feedback':fb}).status_code==200
    assert c.get('/api/customer').json['revision']['state']=='rejected'
    assert post(c,'/revision',{'signature':(picture(),'sig.png')},True).status_code==400
    assert post(c,'/revision',{'front':(picture(),'front.png')},True).status_code==200
    assert approve(a,2).status_code==200

def test_react_assets_and_admin_model_privacy(env):
    app,c,a,p=env
    html=c.get('/')
    assert html.status_code==200 and b'/assets/' in html.data
    assert c.get('/api/admin/models').status_code==403
    assert a.get('/api/admin/models').status_code==200
    assert post(c,'/admin/applications/1/reanalyze',{}).status_code==403
