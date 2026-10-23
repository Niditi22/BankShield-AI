"""V3 regression tests. Run after installing requirements and downloading no weights.
Heavy-model accuracy tests require real labeled data and are deliberately separate.
"""
import io, sqlite3
import pytest
from test_workflow import env, login, register, post, approve, picture, voice
from video_validation import estimate_duration, VideoValidationError


def test_browser_frame_timestamps_override_misreported_fps():
    times=[i/24 for i in range(24*15)]
    duration,why=estimate_duration(times,len(times),999.0)
    assert abs(duration-15)<.05
    assert why=='frame timestamps'
    assert estimate_duration([None]*240,240,24)[0]==10
    with pytest.raises(VideoValidationError):
        estimate_duration([None]*80,80,0)


def test_password_reset_admin_workflow_and_invalidates_sessions(env):
    app,c,admin,path=env
    before=c.get('/api/session').json['user']
    assert before['email']=='customer@example.test'
    payload={'email':'customer@example.test','password':'New-Strong-Password-234!',
             'confirm_password':'New-Strong-Password-234!'}
    assert post(c,'/password-reset-requests',{**payload,'confirm_password':'incorrect'}).status_code==400
    assert post(c,'/password-reset-requests',payload).status_code==200
    admin_data=admin.get('/api/admin').json
    resets=admin_data['password_resets'];assert len(resets)==1
    assert resets[0]['state']=='pending'
    assert 'proposed_hash' not in resets[0]
    assert post(c,'/admin/password-resets/1',{'decision':'approved','note':'Verified by officer','identity_verified':True}).status_code==403
    assert post(admin,'/admin/password-resets/1',{'decision':'approved','note':'Verified by officer','identity_verified':False}).status_code==400
    assert post(admin,'/admin/password-resets/1',{'decision':'approved','note':'Independently verified identity','identity_verified':True}).status_code==200
    assert c.get('/api/customer').status_code==401
    assert post(admin,'/admin/password-resets/1',{'decision':'approved','note':'Second approval','identity_verified':True}).status_code==409
    old=post(c,'/login',{'email':'customer@example.test','password':'TestingPassword123!','role':'customer'})
    assert old.status_code==401
    new=post(c,'/login',{'email':'customer@example.test','password':payload['password'],'role':'customer'})
    assert new.status_code==200
    with sqlite3.connect(path/'bankshield.db') as con:
        proposed=con.execute('SELECT proposed_hash FROM password_resets WHERE id=1').fetchone()[0]
    assert proposed==''


def test_password_reset_unknown_address_not_enumerated(env):
    app,c,admin,path=env
    p={'email':'not-registered@example.test','password':'Long-New-Password-123!',
       'confirm_password':'Long-New-Password-123!'}
    resp=post(c,'/password-reset-requests',p)
    assert resp.status_code==200
    assert admin.get('/api/admin').json['password_resets']==[]


def test_customer_pdf_private_and_available_only_after_decision(env):
    app,c,admin,path=env
    assert approve(admin).status_code==200
    # Simulate a genuine completed verification using a database fixture, not
    # fake ML output in production code.
    from inference import blank
    import json, time
    with sqlite3.connect(path/'bankshield.db') as con:
        ref=con.execute('SELECT approved FROM users WHERE email=?',('customer@example.test',)).fetchone()[0]
        con.execute('''INSERT INTO applications(user_id,purpose,reference,evidence,analysis,
            created,analysis_state,analysis_progress) VALUES (?,?,?,?,?,?,?,?)''',
            (con.execute('SELECT id FROM users WHERE email=?',('customer@example.test',)).fetchone()[0],
             'KYC',ref,'{}',json.dumps(blank()),time.time(),'complete','Fixture'))
    aid=1
    assert c.get(f'/api/applications/{aid}/validation.pdf').status_code==409
    assert app.test_client().get(f'/api/applications/{aid}/validation.pdf').status_code==401
    assert post(admin,f'/admin/applications/{aid}',{'decision':'approved','note':'Verified after manual comparison','manual_review':True}).status_code==200
    pdf=c.get(f'/api/applications/{aid}/validation.pdf')
    assert pdf.status_code==200
    assert pdf.data.startswith(b'%PDF-')
    assert pdf.mimetype=='application/pdf'
    assert 'attachment' in pdf.headers['Content-Disposition']
    outsider=app.test_client();register(outsider,'else@example.test');login(outsider,'else@example.test')
    assert outsider.get(f'/api/applications/{aid}/validation.pdf').status_code==404
    assert admin.get(f'/api/applications/{aid}/validation.pdf').status_code==403
