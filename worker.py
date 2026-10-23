"""Single local background worker, with durable SQLite job state and restart recovery."""
import json, sqlite3, threading, time, traceback
from pathlib import Path
from inference import analyze, blank, KEYS

def connect(data):
    con=sqlite3.connect(Path(data)/'bankshield.db',timeout=30);con.row_factory=sqlite3.Row;return con

def process_next(data,engine=analyze):
    con=connect(data)
    try:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute("SELECT * FROM applications WHERE analysis_state='queued' ORDER BY id LIMIT 1").fetchone()
        if not row:con.commit();return False
        aid=row['id'];con.execute("UPDATE applications SET analysis_state='running',analysis_progress='Starting analysis',analysis_error='' WHERE id=?",(aid,));con.commit()
        ref=json.loads(row['reference']);evi=json.loads(row['evidence']);base=Path(data)/'media'
        refs={s:str(base/ref[s]) for s in ('signature','front','left','right')};refs['audio']=str(base/ref['audio']['original'])
        current={'signature':str(base/evi['signature']),'video':str(base/evi['video']),'audio':str(base/evi['audio']['original'])}
        def progress(label):
            print(f'[Analysis #{aid}] {label}',flush=True)
            con.execute('UPDATE applications SET analysis_progress=? WHERE id=?',(label,aid));con.commit()
        try:
            output=engine(refs,current,progress)
            complete=all(output['scores'].get(k,{}).get('status')=='computed' and output['scores'][k].get('value') is not None for k in KEYS)
            state='complete' if complete else 'partial'
            errors='; '.join(k+': '+output['scores'][k]['note'] for k in KEYS if output['scores'].get(k,{}).get('status')!='computed')
            con.execute('UPDATE applications SET analysis=?,analysis_state=?,analysis_progress=?,analysis_error=? WHERE id=?',(json.dumps(output),state,'All six checks finished' if complete else 'Some checks need attention',errors[:4000],aid))
        except Exception as e:
            traceback.print_exc();con.execute("UPDATE applications SET analysis_state='failed',analysis_progress='Analysis failed',analysis_error=? WHERE id=?",(type(e).__name__+': '+str(e)[:1000],aid))
        con.execute('INSERT INTO audit(actor,event,target,created) VALUES(NULL,?,?,?)',('analysis_finished',str(aid),time.time()));con.commit();return True
    finally:con.close()

def start_worker(data):
    con=connect(data);con.execute("UPDATE applications SET analysis_state='queued',analysis_progress='Resuming after server restart' WHERE analysis_state='running'");con.commit();con.close()
    def loop():
        while True:
            try:
                if not process_next(data):time.sleep(2)
            except Exception:traceback.print_exc();time.sleep(3)
    t=threading.Thread(target=loop,name='bankshield-inference',daemon=True);t.start();return t
