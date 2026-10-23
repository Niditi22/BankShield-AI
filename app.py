import os, json, sqlite3, secrets, time, functools, io, re, math
from pathlib import Path
from datetime import timedelta, datetime, timezone
import click
import numpy as np
import cv2
from scipy.io import wavfile
from scipy import signal
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from flask import Flask, request, session, jsonify, g, send_file, send_from_directory, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException
from inference import normalize_image, blank, health
from video_validation import inspect_video

ROOT=Path(__file__).resolve().parent
SEGMENTS=('details','signature','front','left','right','audio')
TEXTS={'English':'I confirm that I am submitting this banking verification myself. My verification code is', 'Hindi':'मैं पुष्टि करता या करती हूँ कि यह बैंक सत्यापन मैं स्वयं कर रहा या रही हूँ। मेरा सत्यापन कोड है', 'Marathi':'मी पुष्टी करतो किंवा करते की हे बँक पडताळणी अर्ज मी स्वतः सादर करत आहे. माझा पडताळणी क्रमांक आहे'}
def create_app(test_config=None):
    app=Flask(__name__)
    app.config.update(DATA_DIR=str(ROOT/'instance'),MAX_CONTENT_LENGTH=45*1024*1024,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',PERMANENT_SESSION_LIFETIME=timedelta(minutes=30))
    if test_config: app.config.update(test_config)
    data=Path(app.config['DATA_DIR']); data.mkdir(parents=True,exist_ok=True); (data/'media').mkdir(exist_ok=True)
    key=data/'secret.key'
    if not key.exists(): key.write_text(secrets.token_hex(32))
    app.secret_key=os.environ.get('SECRET_KEY') or key.read_text()
    app.config['SESSION_COOKIE_SECURE']=os.environ.get('BANKSHIELD_HTTPS')=='1'
    def db():
        if 'db' not in g:
            g.db=sqlite3.connect(data/'bankshield.db',timeout=30); g.db.row_factory=sqlite3.Row
        return g.db
    @app.teardown_appcontext
    def close(_):
        if 'db' in g: g.db.close()
    with app.app_context():
        db().executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL,approved TEXT);
        CREATE TABLE IF NOT EXISTS revisions(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,payload TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'pending',feedback TEXT NOT NULL DEFAULT '{}',created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS applications(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,purpose TEXT NOT NULL,reference TEXT NOT NULL,evidence TEXT NOT NULL,analysis TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'pending',note TEXT NOT NULL DEFAULT '',created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,actor INTEGER,event TEXT,target TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS attempts(key TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS password_resets(
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
          proposed_hash TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
          requested_at REAL NOT NULL, reviewed_at REAL,
          reviewed_by INTEGER, admin_note TEXT NOT NULL DEFAULT '',
          FOREIGN KEY (user_id) REFERENCES users(id)
        );
        ''')
        columns={r[1] for r in db().execute('PRAGMA table_info(applications)')}
        for name,definition in [('analysis_state',"TEXT NOT NULL DEFAULT 'legacy'"),('analysis_progress',"TEXT NOT NULL DEFAULT ''"),('analysis_error',"TEXT NOT NULL DEFAULT ''")]:
            if name not in columns:db().execute(f'ALTER TABLE applications ADD COLUMN {name} {definition}')
        ucols={r[1] for r in db().execute('PRAGMA table_info(users)')}
        if 'password_version' not in ucols:
            db().execute('ALTER TABLE users ADD COLUMN password_version INTEGER NOT NULL DEFAULT 0')
        if 'decided_at' not in columns:
            db().execute('ALTER TABLE applications ADD COLUMN decided_at REAL')
        db().execute('CREATE INDEX IF NOT EXISTS idx_resets_state ON password_resets(state,requested_at)')
        db().execute('PRAGMA journal_mode=WAL');db().commit()
    def log(event,target): db().execute('INSERT INTO audit(actor,event,target,created) VALUES(?,?,?,?)',(session.get('uid'),event,str(target),time.time()))
    def user():
        u=db().execute('SELECT * FROM users WHERE id=?',(session.get('uid'),)).fetchone()
        if u and session.get('password_version')!=u['password_version']:
            session.clear()
            return None
        return u
    def protect(role=None,approved=False):
        def decorate(fn):
            @functools.wraps(fn)
            def wrapped(*a,**kw):
                u=user()
                if not u: abort(401,description='Please sign in.')
                if role and u['role']!=role: abort(403)
                if approved and not u['approved']: abort(403,description='Enrollment must be approved first.')
                return fn(*a,**kw)
            return wrapped
        return decorate
    @app.before_request
    def csrf():
        g.new_media=[]
        if request.path.startswith('/api/') and request.method not in ('GET','HEAD','OPTIONS'):
            if not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),session.get('csrf','!')): abort(403,description='Session expired. Refresh this page.')
    @app.after_request
    def headers(r):
        if r.status_code >= 400:
            for p in getattr(g,'new_media',[]): p.unlink(missing_ok=True)
        r.headers['Cache-Control']='no-store'; r.headers['X-Content-Type-Options']='nosniff'; r.headers['X-Frame-Options']='DENY'
        r.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return r
    @app.errorhandler(HTTPException)
    def http_error(e): return jsonify(error=e.description),e.code
    @app.errorhandler(ValueError)
    def value_error(e): return jsonify(error=str(e)),400
    def unpack(row):
        if row is None:return None
        r=dict(row)
        for k in ('payload','feedback','reference','evidence','analysis','approved'):
            if k in r and r[k]: r[k]=json.loads(r[k])
        r.pop('password',None); return r
    def latest(uid): return db().execute('SELECT * FROM revisions WHERE user_id=? ORDER BY id DESC LIMIT 1',(uid,)).fetchone()
    def media_path(mid):
        if not re.fullmatch(r'[a-f0-9]{32}\.(png|wav|webm|mp4)',mid): raise ValueError('Invalid media ID')
        return data/'media'/mid
    def save_upload(name,kind):
        f=request.files.get(name)
        if not f or not f.filename: raise ValueError(f'Missing {name}')
        raw=f.read(31*1024*1024)
        if not raw or len(raw)>30*1024*1024: raise ValueError('Each recording must be under 30 MB.')
        ext='.png' if kind in ('image','signature') else '.wav' if kind=='audio' else '.webm'
        if kind=='video' and raw[4:8]==b'ftyp': ext='.mp4'
        mid=secrets.token_hex(16)+ext; p=media_path(mid); g.new_media.append(p)
        if kind in ('image','signature'):
            try: normalize_image(io.BytesIO(raw),p,kind=='signature')
            except Exception as e: raise ValueError('Upload a clear PNG/JPEG image. '+str(e))
        elif kind=='audio':
            try: sr,a=wavfile.read(io.BytesIO(raw))
            except Exception: raise ValueError('Use the microphone recorder (PCM WAV).')
            if sr<8000 or sr>96000 or a.ndim>2 or not 3<=len(a)/sr<=45: raise ValueError('Audio must be 3–45 seconds at 8–96 kHz.')
            if a.ndim==2:a=a.mean(axis=1)
            a=a.astype(np.float64); peak=np.max(np.abs(a))
            if peak<1: raise ValueError('Audio appears silent. Please record again.')
            a=a/32768 if peak>1 else a
            if np.sqrt(np.mean(a*a))<.0005: raise ValueError('Audio too quiet. Move closer to the microphone.')
            # Preserve original for forensic analysis. Cleaned copy is for listening only.
            p.write_bytes(raw)
            b=signal.sosfilt(signal.butter(3,[80,min(7000,sr*.45)],fs=sr,btype='bandpass',output='sos'),a)
            active=np.where(np.abs(b)>max(.003,np.max(np.abs(b))*.025))[0]
            if len(active): b=b[max(0,active[0]-int(.15*sr)):min(len(b),active[-1]+int(.15*sr))]
            cleaned=secrets.token_hex(16)+'.wav'; g.new_media.append(media_path(cleaned)); wavfile.write(media_path(cleaned),sr,(np.clip(b,-1,1)*32767).astype(np.int16))
            return {'original':mid,'cleaned':cleaned}
        else:
            p.write_bytes(raw)
            inspect_video(p,request.form.get('video_seconds'))
        return mid
    def details():
        fields={k:request.form.get(k,'').strip() for k in ('name','phone','dob','address')}
        if any(not v for v in fields.values()) or any(len(v)>500 for v in fields.values()): raise ValueError('Complete all personal details (maximum 500 characters each).')
        if not re.fullmatch(r'[+0-9 ()-]{7,20}',fields['phone']): raise ValueError('Enter a valid phone number.')
        from datetime import date
        try:
            if date.fromisoformat(fields['dob'])>=date.today(): raise ValueError()
        except ValueError: raise ValueError('Enter a valid past date of birth.')
        return fields
    def challenge_check():
        c=session.get('challenge')
        if not c or time.time()-c['created']>1200 or request.form.get('challenge_id')!=c['id']: raise ValueError('Recording prompt expired. Generate a new prompt and record again.')
        return c
    @app.get('/')
    def index(): return send_from_directory(ROOT/'static/react','index.html')
    @app.get('/v3-enhancements.js')
    def compat_ui_js():return send_from_directory(ROOT/'static/react','v3-enhancements.js')
    @app.get('/v3-overrides.css')
    def compat_ui_css():return send_from_directory(ROOT/'static/react','v3-overrides.css')
    @app.get('/assets/<path:filename>')
    def assets(filename): return send_from_directory(ROOT/'static/react/assets',filename)
    @app.get('/api/session')
    def current():
        u=user()
        session.setdefault('csrf',secrets.token_hex(24))
        return jsonify(csrf=session['csrf'],user=unpack(u))
    @app.post('/api/login')
    def login():
        j=request.get_json(); email=j.get('email','').strip().lower(); key=(request.remote_addr or '')+'|'+email
        count=db().execute('SELECT COUNT(*) FROM attempts WHERE key=? AND created>?',(key,time.time()-600)).fetchone()[0]
        if count>=8: abort(429,description='Too many attempts. Wait 10 minutes.')
        u=db().execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
        if not u or not check_password_hash(u['password'],j.get('password','')) or u['role']!=j.get('role'):
            db().execute('INSERT INTO attempts VALUES(?,?)',(key,time.time())); db().commit(); abort(401,description='Invalid credentials or wrong portal.')
        session.clear(); session.update(uid=u['id'],csrf=secrets.token_hex(24),password_version=u['password_version']); session.permanent=True
        log('login',u['id']); db().commit(); return jsonify(ok=True)
    @app.post('/api/password-reset-requests')
    def request_password_reset():
        # Passwords never change from an unauthenticated request. The submitted
        # new password is stored ONLY as a salted hash until an officer approves.
        j=request.get_json(silent=True) or {}
        email=str(j.get('email','')).strip().lower()
        new=str(j.get('password','')); confirm=str(j.get('confirm_password',''))
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254:
            raise ValueError('Enter a valid email address.')
        if new!=confirm:raise ValueError('New password and confirmation must match.')
        if len(new)<12 or len(new)>128:raise ValueError('Choose a password of 12–128 characters.')
        key='reset|'+(request.remote_addr or '')+'|'+email
        now=time.time()
        if db().execute('SELECT COUNT(*) FROM attempts WHERE key=? AND created>?',(key,now-3600)).fetchone()[0]>=3:
            abort(429,description='Too many requests. Try again in one hour.')
        db().execute('INSERT INTO attempts VALUES(?,?)',(key,now))
        customer=db().execute("SELECT id FROM users WHERE email=? AND role='customer'",(email,)).fetchone()
        if customer and not db().execute("SELECT 1 FROM password_resets WHERE user_id=? AND state='pending'",(customer['id'],)).fetchone():
            db().execute('INSERT INTO password_resets(user_id,proposed_hash,requested_at) VALUES(?,?,?)',
                         (customer['id'],generate_password_hash(new),now))
            log('password_reset_requested',customer['id'])
        db().commit()
        return jsonify(ok=True,message='If this customer account exists, its password reset request has been sent to the administrator. The new password works only after the administrator approves and verifies your identity independently.')

    @app.post('/api/logout')
    def logout(): session.clear(); return jsonify(ok=True)
    @app.get('/api/challenge')
    def challenge():
        lang=request.args.get('language','English')
        if lang not in TEXTS: raise ValueError('Unsupported language')
        session['challenge']={'id':secrets.token_hex(16),'text':TEXTS[lang]+' '+str(secrets.randbelow(900000)+100000)+'.','language':lang,'created':time.time()}
        return jsonify(session['challenge'])
    @app.post('/api/register')
    def register():
        if user(): raise ValueError('Log out before registering another account.')
        email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254: raise ValueError('Enter a valid email.')
        if len(password)<12: raise ValueError('Use a password of at least 12 characters.')
        if db().execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone(): raise ValueError('Account already exists. Sign in to check your status.')
        if request.form.get('consent')!='yes': raise ValueError('Consent is required.')
        c=challenge_check(); payload={'details':details(),'prompt':c}
        for s in SEGMENTS[1:]:payload[s]=save_upload(s,'audio' if s=='audio' else 'signature' if s=='signature' else 'image')
        cur=db().execute('INSERT INTO users(email,password,role) VALUES(?,?,?)',(email,generate_password_hash(password),'customer'))
        uid=cur.lastrowid; db().execute('INSERT INTO revisions(user_id,payload,created) VALUES(?,?,?)',(uid,json.dumps(payload),time.time()))
        session.pop('challenge',None); log('enrollment_submitted',uid); db().commit(); return jsonify(ok=True)
    @app.get('/api/customer')
    @protect('customer')
    def customer():
        apps=[{k:r[k] for k in ('id','purpose','state','note','created')} for r in db().execute('SELECT * FROM applications WHERE user_id=? ORDER BY id DESC',(session['uid'],))]
        return jsonify(revision=unpack(latest(session['uid'])),applications=apps)
    @app.post('/api/revision')
    @protect('customer')
    def revision():
        prev=latest(session['uid'])
        if prev and prev['state']=='pending': raise ValueError('A revision is already awaiting review.')
        payload=json.loads(prev['payload']) if prev else json.loads(user()['approved'])
        feedback=json.loads(prev['feedback']) if prev else {}
        changed=set()
        if request.form.get('name'):
            payload['details']=details(); changed.add('details')
        for s in SEGMENTS[1:]:
            if s in request.files:
                payload[s]=save_upload(s,'audio' if s=='audio' else 'signature' if s=='signature' else 'image'); changed.add(s)
        if 'audio' in changed:payload['prompt']=challenge_check()
        required={k for k,v in feedback.items() if v.get('status') in ('redo','deny')}
        if not required.issubset(changed): raise ValueError('Replace all flagged sections: '+', '.join(sorted(required-changed)))
        if not changed:raise ValueError('Select at least one section to update.')
        db().execute('INSERT INTO revisions(user_id,payload,created) VALUES(?,?,?)',(session['uid'],json.dumps(payload),time.time()))
        session.pop('challenge',None); log('revision_submitted',session['uid']); db().commit(); return jsonify(ok=True)
    @app.post('/api/applications')
    @protect('customer',approved=True)
    def application():
        purpose=request.form.get('purpose')
        if purpose not in ('Loan','Pension','KYC'):raise ValueError('Invalid purpose')
        c=challenge_check(); ref=json.loads(user()['approved'])
        evidence={'signature':save_upload('signature','signature'),'video':save_upload('video','video'),'audio':save_upload('audio','audio'),'prompt':c}
        result=blank()
        cur=db().execute('INSERT INTO applications(user_id,purpose,reference,evidence,analysis,created,analysis_state,analysis_progress) VALUES(?,?,?,?,?,?,?,?)',(session['uid'],purpose,json.dumps(ref),json.dumps(evidence),json.dumps(result),time.time(),'queued','Queued for local inference'))
        session.pop('challenge',None); log('application_submitted',cur.lastrowid); db().commit(); return jsonify(ok=True,id=cur.lastrowid)
    @app.get('/api/admin')
    @protect('admin')
    def admin():
        users=[unpack(r) for r in db().execute("SELECT * FROM users WHERE role='customer'")]
        resets=[dict(r) for r in db().execute('''SELECT p.id,p.user_id,p.state,p.requested_at,p.reviewed_at,p.admin_note,
            u.email FROM password_resets p JOIN users u ON p.user_id=u.id ORDER BY p.id DESC LIMIT 100''')]
        return jsonify(users=users,revisions=[unpack(r) for r in db().execute('SELECT * FROM revisions ORDER BY id DESC')],applications=[unpack(r) for r in db().execute('SELECT * FROM applications ORDER BY id DESC')],password_resets=resets,audit=[dict(r) for r in db().execute('SELECT * FROM audit ORDER BY id DESC LIMIT 100')])
    @app.post('/api/admin/password-resets/<int:rid>')
    @protect('admin')
    def review_password_reset(rid):
        j=request.get_json(silent=True) or {}
        decision=j.get('decision'); note=str(j.get('note','')).strip()
        if decision not in ('approved','rejected') or not 5<=len(note)<=1000:
            raise ValueError('Select Approve or Reject and write an officer note (5–1000 characters).')
        if decision=='approved' and j.get('identity_verified') is not True:
            raise ValueError('Confirm identity verification using an independent trusted channel before approving.')
        row=db().execute('SELECT * FROM password_resets WHERE id=?',(rid,)).fetchone()
        if not row:abort(404)
        now=time.time()
        cur=db().execute("""UPDATE password_resets SET state=?,reviewed_at=?,reviewed_by=?,admin_note=?,
          proposed_hash='' WHERE id=? AND state='pending'""",(decision,now,session['uid'],note,rid))
        if cur.rowcount!=1:abort(409,description='This reset request has already been reviewed.')
        if decision=='approved':
            db().execute('UPDATE users SET password=?,password_version=password_version+1 WHERE id=?',
                         (row['proposed_hash'],row['user_id']))
            # Any other outstanding reset request must not silently override the new password.
            db().execute("""UPDATE password_resets SET state='rejected',admin_note='Superseded by another approved reset',
              proposed_hash='',reviewed_at=?,reviewed_by=? WHERE user_id=? AND state='pending'""",
                         (now,session['uid'],row['user_id']))
        log('password_reset_'+decision,rid);db().commit()
        return jsonify(ok=True)

    @app.post('/api/admin/revisions/<int:rid>')
    @protect('admin')
    def review_revision(rid):
        row=db().execute('SELECT * FROM revisions WHERE id=?',(rid,)).fetchone()
        if not row:abort(404)
        j=request.get_json(); feedback=j.get('feedback',{})
        if set(feedback)!=set(SEGMENTS) or any(v.get('status') not in ('accept','redo','deny') for v in feedback.values()):raise ValueError('Review all six sections.')
        if any(v['status'] in ('redo','deny') and not str(v.get('note','')).strip() for v in feedback.values()):raise ValueError('Explain each requested correction.')
        state='approved' if all(v['status']=='accept' for v in feedback.values()) else 'rejected' if any(v['status']=='deny' for v in feedback.values()) else 'changes_requested'
        cur=db().execute("UPDATE revisions SET state=?,feedback=? WHERE id=? AND state='pending'",(state,json.dumps(feedback),rid))
        if cur.rowcount!=1:abort(409,description='This revision has already been reviewed.')
        if state=='approved':db().execute('UPDATE users SET approved=? WHERE id=?',(row['payload'],row['user_id']))
        log('enrollment_'+state,rid); db().commit(); return jsonify(ok=True)
    @app.post('/api/admin/applications/<int:aid>')
    @protect('admin')
    def review_application(aid):
        j=request.get_json(); decision=j.get('decision'); note=str(j.get('note','')).strip()
        if decision not in ('approved','rejected') or not note or len(note)>2000:raise ValueError('Choose a decision and enter a reason (up to 2000 characters).')
        if not j.get('manual_review'):raise ValueError('Confirm manual evidence review and model limitations.')
        row=db().execute('SELECT analysis_state,analysis FROM applications WHERE id=?',(aid,)).fetchone()
        if not row:abort(404)
        if decision=='approved' and row['analysis_state']!='complete':raise ValueError('Approval is blocked until all six checks complete. Resolve model/quality failures and reanalyze.')
        cur=db().execute("UPDATE applications SET state=?,note=?,decided_at=? WHERE id=? AND state='pending' AND (? != 'approved' OR analysis_state='complete')",(decision,note,time.time(),aid,decision))
        if cur.rowcount!=1:abort(409,description='Application is missing or already reviewed.')
        log('application_'+decision,aid); db().commit(); return jsonify(ok=True)
    @app.get('/api/applications/<int:aid>/validation.pdf')
    @protect('customer')
    def validation_pdf(aid):
        rec=db().execute("""SELECT a.id,a.purpose,a.state,a.note,a.created,a.decided_at,u.email,
            a.reference FROM applications a JOIN users u ON u.id=a.user_id
            WHERE a.id=? AND a.user_id= ?""",(aid,session['uid'])).fetchone()
        if not rec:abort(404)
        if rec['state'] not in ('approved','rejected'):
            abort(409,description='A decision is required before the validation PDF can be downloaded.')
        # Build per request, using only the owner's record; no raw biometrics or scores.
        b=io.BytesIO();pdf=canvas.Canvas(b,pagesize=(595,842),pageCompression=1)
        pdf.setTitle('BankShield Verification Decision BS-'+str(aid).zfill(4))
        pdf.setAuthor('BankShield Research Prototype')
        def text(x,y,body,font='Helvetica',size=11,color='#243C35'):
            pdf.setFillColor(HexColor(color));pdf.setFont(font,size)
            pdf.drawString(x,y,str(body))
        pdf.setFillColor(HexColor('#143B32'));pdf.rect(0,750,595,92,stroke=0,fill=1)
        text(42,797,'BANKSHIELD',font='Helvetica-Bold',size=23,color='#FFFFFF')
        text(42,773,'Verification decision record  |  Research prototype',size=10,color='#E5F4EC')
        name=json.loads(rec['reference']).get('details',{}).get('name','Customer')
        rows=[('Reference','BS-'+str(aid).zfill(4)),('Customer',name),('Account',rec['email']),
              ('Request type',rec['purpose']),('Submitted (UTC)',datetime.fromtimestamp(rec['created'],timezone.utc).strftime('%d %b %Y, %H:%M UTC')),
              ('Decision','APPROVED' if rec['state']=='approved' else 'DISAPPROVED'),
              ('Decision time (UTC)',datetime.fromtimestamp(rec['decided_at'],timezone.utc).strftime('%d %b %Y, %H:%M UTC') if rec['decided_at'] else 'Not recorded (legacy decision)')]
        y=712
        for label,value in rows:
            text(44,y,label,size=10,color='#5F7770')
            # Explicitly truncate long labels to stay within the page.
            from reportlab.pdfbase.pdfmetrics import stringWidth
            val=str(value)
            while len(val)>1 and stringWidth(val,'Helvetica-Bold',11)>345:val=val[:-1]
            if val!=str(value):val=val[:-1]+'...'
            text(200,y,val,font='Helvetica-Bold',size=11)
            pdf.setStrokeColor(HexColor('#DEE6DF'));pdf.line(44,y-16,550,y-16);y-=46
        text(44,y-8,'Officer decision / reason',font='Helvetica-Bold',size=12)
        from reportlab.lib.utils import simpleSplit
        y-=32
        for line in simpleSplit(rec['note'],'Helvetica',10,490)[:11]:
            text(44,y,line,size=10);y-=17
        text(44,121,'IMPORTANT',font='Helvetica-Bold',size=11,color='#9C5F19')
        text(44,102,'This report records a human verification decision only.',size=10)
        text(44,86,'It is not a loan sanction, pension authorization, or certified proof of identity.',size=10)
        text(44,70,'Scores are experimental and are deliberately excluded from the customer report.',size=10)
        pdf.setStrokeColor(HexColor('#D9E2DC'));pdf.line(44,52,550,52)
        text(44,35,'Generated from the recorded BankShield decision. No electronic signature attached.',size=8,color='#6E7C77')
        pdf.showPage();pdf.save();b.seek(0)
        log('validation_pdf_downloaded',aid);db().commit()
        return send_file(b,mimetype='application/pdf',as_attachment=True,
                         download_name='BankShield_BS-'+str(aid).zfill(4)+'_validation.pdf')

    @app.get('/api/admin/models')
    @protect('admin')
    def model_health():return jsonify(health())
    @app.post('/api/admin/applications/<int:aid>/reanalyze')
    @protect('admin')
    def reanalyze(aid):
        cur=db().execute("UPDATE applications SET analysis_state='queued',analysis_progress='Queued for reanalysis',analysis_error='',analysis=? WHERE id=? AND state='pending' AND analysis_state NOT IN ('queued','running')",(json.dumps(blank()),aid))
        if cur.rowcount!=1:abort(409,description='Application is already processing, decided, or missing.')
        log('analysis_requeued',aid);db().commit();return jsonify(ok=True)
    @app.get('/media/<mid>')
    @protect()
    def media(mid):
        p=media_path(mid); u=user()
        # Only media referenced by this customer's records, or admin, can be served.
        if u['role']!='admin':
            blobs=[r[0] for r in db().execute('SELECT payload FROM revisions WHERE user_id=?',(u['id'],))]
            blobs += [r[0] for r in db().execute('SELECT evidence FROM applications WHERE user_id=?',(u['id'],))]
            if not any('"'+mid+'"' in b for b in blobs):abort(403)
        if not p.exists():abort(404)
        return send_file(p,conditional=True)
    @app.cli.command('create-admin')
    @click.option('--email',prompt=True)
    @click.password_option(confirmation_prompt=True)
    def create_admin(email,password):
        if len(password)<12:raise click.ClickException('Password must contain at least 12 characters.')
        try:db().execute('INSERT INTO users(email,password,role) VALUES(?,?,?)',(email.lower().strip(),generate_password_hash(password),'admin')); db().commit()
        except sqlite3.IntegrityError:raise click.ClickException('Email already exists.')
        click.echo('Administrator created.')
    return app

app=create_app()
if __name__=='__main__':
    from waitress import serve
    from worker import start_worker
    start_worker(app.config['DATA_DIR'])
    print('BankShield React: http://localhost:5000',flush=True)
    serve(app,host='127.0.0.1',port=5000,threads=4)
