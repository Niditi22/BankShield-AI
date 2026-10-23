"""One-time local model download and real forward-pass diagnostics. No API key."""
import argparse, hashlib, json, time, urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from model_catalog import HF_MODELS,FACE_FILES,WEIGHTS,FILE_HASHES

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def download(url,path,expected=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.stat().st_size>0 and (not expected or sha(path)==expected):return
    tmp=path.with_suffix(path.suffix+'.part')
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'BankShield-research/2.0'})
            with urllib.request.urlopen(req,timeout=60) as r,tmp.open('wb') as f:
                while True:
                    chunk=r.read(1024*1024)
                    if not chunk:break
                    f.write(chunk)
            if expected and sha(tmp)!=expected:raise ValueError('SHA256 checksum mismatch for '+path.name)
            tmp.replace(path);print('Downloaded',path.parent.name+'/'+path.name,flush=True);return
        except Exception:
            tmp.unlink(missing_ok=True)
            if attempt==2:raise
            time.sleep(1)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--download-only',action='store_true');args=parser.parse_args()
    WEIGHTS.mkdir(exist_ok=True);jobs=[]
    for key,spec in HF_MODELS.items():
        print('Preparing',key,flush=True)
        for name in spec['files']:
            expected=FILE_HASHES[key+'/'+name]
            jobs.append((f"https://huggingface.co/{spec['repo']}/resolve/{spec['revision']}/{name}",WEIGHTS/key/name,expected))
    for name,url in FACE_FILES.items():jobs.append((url,WEIGHTS/'face'/name,FILE_HASHES['face/'+name]))
    failures=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(download,*j):j[1] for j in jobs}
        for future in as_completed(futures):
            try:future.result()
            except Exception as e:failures.append(str(futures[future])+': '+str(e))
    if failures:
        print('\nDOWNLOAD FAILED. Rerun this command; valid completed files are reused.\n'+'\n'.join(failures));raise SystemExit(1)
    receipt={'models':HF_MODELS,'files':{str(p.relative_to(WEIGHTS)):sha(p) for _,p,_ in jobs}}
    (WEIGHTS/'downloads.json').write_text(json.dumps(receipt,indent=2))
    if not args.download_only:
        from inference import diagnose
        report=diagnose();(WEIGHTS/'diagnostics.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))
        if not report['ready']:raise SystemExit('A model forward pass failed. See diagnostics above. The website can start, but failed checks cannot produce scores.')
    print('Model setup complete.',flush=True)
if __name__=='__main__':main()
