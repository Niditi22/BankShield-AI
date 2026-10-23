"""Actual local pretrained inference. No constant, random, or complementary fake scores."""
import json, math, os, threading, time, gc
from pathlib import Path
from functools import lru_cache
import cv2
import numpy as np
from PIL import Image
from scipy.io import wavfile
from scipy.signal import resample_poly
from model_catalog import WEIGHTS,HF_MODELS,FACE_FILES
from legacy_analysis import normalize_image,signature_similarity,video_evidence

KEYS=('signature_fake','signature_match','video_fake','face_match','audio_fake','speaker_match')
LOCK=threading.Lock()
def blank():return {'scores':{k:{'value':None,'status':'queued','note':'Waiting for model inference.'} for k in KEYS},'notes':[]}
def result(value,model,note,raw=None,**extra):
    value=float(value)
    if not math.isfinite(value) or not 0<=value<=100:raise ValueError('Non-finite or invalid model score')
    return {'value':round(value,2),'status':'computed','model_version':model,'note':note,**({'raw_cosine':round(float(raw),6)} if raw is not None else {}),**extra}
def configure_torch():
    import torch
    torch.set_num_threads(max(1,min(4,os.cpu_count() or 2)))
    return torch

def load_signature():
    torch=configure_torch()
    from torchvision.models.resnet import ResNet,BasicBlock
    from torch import nn
    safe=[ResNet,BasicBlock,nn.AdaptiveAvgPool2d,nn.Conv2d,nn.Linear,nn.BatchNorm2d,nn.Sequential,nn.ReLU,nn.MaxPool2d,nn.Dropout]
    path=WEIGHTS/'signature'/'model.pt'
    if not path.exists():raise FileNotFoundError('Signature weights missing. Run setup_models.py.')
    # The publisher serialized a standard torchvision network. Allow only these
    # reviewed framework classes; never use unrestricted pickle/remote code.
    with torch.serialization.safe_globals(safe):
        model=torch.load(path,map_location='cpu',weights_only=True)
    if not isinstance(model,ResNet) or model.fc[-1].out_features!=2:raise ValueError('Unexpected signature architecture')
    return model.eval()

def signature_tensor(path):
    torch=configure_torch()
    from torchvision import transforms
    with Image.open(path) as im:
        im = im.convert('RGB')
        gray = np.array(im.convert('L'))
        pts = cv2.findNonZero((gray < 240).astype(np.uint8))
        if pts is not None and len(pts) >= 30:
            x, y, w, h = cv2.boundingRect(pts)
            pad = 12
            x0, y0 = max(0, x - pad), max(0, y - pad)
            x1, y1 = min(im.width, x + w + pad), min(im.height, y + h + pad)
            im = im.crop((x0, y0, x1, y1))
        transform=transforms.Compose([transforms.Resize((224,224)),transforms.ToTensor(),transforms.Normalize([.485,.456,.406],[.229,.224,.225])])
        return transform(im).unsqueeze(0)

def signatures(reference,current):
    torch=configure_torch();model=load_signature();features=[]
    handle=model.avgpool.register_forward_hook(lambda module,inputs,output:features.append(output.flatten(1)))
    try:
        with torch.inference_mode():
            a=model(signature_tensor(reference));b=model(signature_tensor(current))
            forged=float(torch.softmax(b,dim=-1)[0,0]) # Published label order: Forged, Original.
            cosine=float(torch.nn.functional.cosine_similarity(features[0],features[1]).item())
        version='ResNet34-CEDAR@'+HF_MODELS['signature']['revision'][:8]
        contradiction=forged>=.80 and cosine>=.90
        return {
          'signature_fake':result(forged*100,version,'Experimental CEDAR forged-class softmax score. Not an AI-generation detector or calibrated fraud probability. Unvalidated for camera images, Indic scripts and your customer population. '+('High forgery label conflicts with strong reference feature similarity: INCONCLUSIVE, review manually.' if contradiction else ''),
          metric_type='classifier',review_flag='inconsistent_signature' if contradiction else None),
          'signature_match':result(max(0,min(1,cosine))*100,version,'Cosine similarity of the signature classifier’s pooled features ×100 (negative values clipped to 0). This classifier was not trained for signer identity; similarity is exploratory, not a probability.',cosine,metric_type='similarity',interpretation='Exploratory signature-feature similarity'),
        }
    finally:handle.remove();del model;gc.collect()

@lru_cache(maxsize=1)
def face_models():
    detector=cv2.FaceDetectorYN.create(str(WEIGHTS/'face/yunet.onnx'),'',(320,320),.8,.3,5000)
    recognizer=cv2.FaceRecognizerSF.create(str(WEIGHTS/'face/sface.onnx'),'')
    return detector,recognizer

def face_crop(frame):
    if frame is None:raise ValueError('Image could not be decoded')
    detector,recognizer=face_models()
    h,w=frame.shape[:2];factor=min(1.,640/max(h,w));scaled=cv2.resize(frame,(int(w*factor),int(h*factor)))
    detector.setInputSize((scaled.shape[1],scaled.shape[0]));_,faces=detector.detect(scaled)
    if faces is None or len(faces)!=1:raise ValueError('Exactly one detectable face is required. Retake in even lighting, with both eyes visible.')
    crop=recognizer.alignCrop(scaled,faces[0]);embedding=recognizer.feature(crop).flatten()
    embedding=embedding/(np.linalg.norm(embedding)+1e-12)
    face=faces[0]
    fx,fy,fw,fh=face[0]/factor,face[1]/factor,face[2]/factor,face[3]/factor
    cx,cy=fx+fw*0.5,fy+fh*0.5
    def get_portrait(scale):
        sz=int(max(fw,fh)*scale)
        x0,y0=max(0,int(cx-sz*0.5)),max(0,int(cy-sz*0.5))
        x1,y1=min(w,int(cx+sz*0.5)),min(h,int(cy+sz*0.5))
        return frame[y0:y1,x0:x1]
    return crop,embedding,get_portrait(1.5),get_portrait(1.8)

def video_frames(path,count=8):
    # Sample by decoded-frame index, not unreliable browser WebM FPS metadata.
    cap=cv2.VideoCapture(str(path));frames=[];index=0;stride=12
    try:
        while index<3500:
            ok,f=cap.read()
            if not ok:break
            if index%stride==0:
                h,w=f.shape[:2]
                if max(h,w)>720:
                    factor=720/max(h,w)
                    f=cv2.resize(f,(max(1,int(w*factor)),max(1,int(h*factor))))
                frames.append(f)
                if len(frames)>128:
                    frames=frames[::2];stride*=2
            index+=1
    finally:cap.release()
    if not frames:raise ValueError('No video frames decoded')
    ids=np.linspace(0,len(frames)-1,min(count,len(frames))).astype(int)
    return [frames[i] for i in ids]

def image_classifier():
    configure_torch()
    from transformers import AutoImageProcessor,AutoModelForImageClassification
    p=WEIGHTS/'video'
    return AutoImageProcessor.from_pretrained(p,local_files_only=True,use_fast=False),AutoModelForImageClassification.from_pretrained(p,local_files_only=True,use_safetensors=True).eval()

def fake_index(config):
    matches=[int(i) for i,label in config.id2label.items() if str(label).lower()=='fake']
    if len(matches)!=1:raise ValueError('Model fake/real label mapping could not be verified')
    return matches[0]

def camera(reference,current):
    torch=configure_torch();refs=[];notes=[]
    for key in ('front','left','right'):
        try:refs.append(face_crop(cv2.imread(reference[key]))[1])
        except ValueError as e:notes.append(key+' reference: '+str(e))
    # Compare the same time points both as raw camera frames and as aligned
    # faces. Domain shift from forced cropping was causing opaque 99% outputs.
    # This is a diagnostic two-view assessment, NOT a validated ensemble.
    frames=video_frames(current,count=4);samples=[];embeddings=[];blur=[]
    for f in frames:
        try:
            crop,embedding,portrait,context=face_crop(f)
            embeddings.append(embedding)
            blur.append(float(cv2.Laplacian(cv2.cvtColor(portrait,cv2.COLOR_BGR2GRAY),cv2.CV_64F).var()))
            samples.append((Image.fromarray(cv2.cvtColor(portrait,cv2.COLOR_BGR2RGB)),
                            Image.fromarray(cv2.cvtColor(context,cv2.COLOR_BGR2RGB))))
        except ValueError:pass
    if len(samples)<3:raise ValueError('Fewer than three usable single-face frames. Retake with steady light and a frontal face.')
    output={}
    if refs:
        cosines=[max(float(np.dot(emb,r)) for r in refs) for emb in embeddings]
        median=float(np.median(cosines))
        output['face_match']=result(max(0,min(1,median))*100,'OpenCV SFace 2021dec',
            'Median best-reference SFace cosine similarity, scaled ×100; NOT a percent chance that the identities match. '
            +f'{len(refs)} usable reference views and {len(samples)} frames. '+' '.join(notes),median,
            metric_type='similarity', interpretation='Identity similarity, not an identity probability')
    else:
        output['face_match']={'value':None,'status':'failed','note':'No usable reference face. Ask the customer to replace reference photos.'}
    processor,model=image_classifier()
    try:
        idx=fake_index(model.config);face_scores=[];frame_scores=[]
        with torch.inference_mode():
            for face,frame in samples:
                # Both views use the same publisher's weights. A mismatch
                # indicates instability, not independently confirmed reality.
                # One batched forward pass instead of two model calls.
                batch=processor(images=[face,frame],return_tensors='pt')
                probs=model(**batch).logits.softmax(-1)
                face_scores.append(float(probs[0,idx]))
                frame_scores.append(float(probs[1,idx]))
        face_median=float(np.median(face_scores));full_median=float(np.median(frame_scores))
        disagreement=abs(face_median-full_median)
        spread=float(np.std([(x+y)/2 for x,y in zip(face_scores,frame_scores)]))
        low_quality=min(blur)<12  # conservative technical warning, not a fraud threshold
        unstable=disagreement>=.35 or spread>=.30
        note=(f'Raw face-crop median {face_median*100:.1f}%; raw context median {full_median*100:.1f}%; '
              f'frame variability {spread*100:.1f} points across {len(samples)} sampled frames. '
              'These are uncalibrated fake-class model scores, NOT probability of fraud. '
              'Frame classifier is not a replay detector; no temporal authenticity validation. '
              +('Face-crop and context predictions disagree: INCONCLUSIVE; request manual review or retake. ' if unstable else '')
              +('Low sharpness detected: retake under steady lighting. ' if low_quality else ''))
        # Median of paired-view scores is robust to a single extreme frame;
        # retaining the two raw medians avoids obscuring 99% false positives.
        score=float(np.median([(x+y)/2 for x,y in zip(face_scores,frame_scores)]))*100
        output['video_fake']=result(score,'ViT two-view diagnostic@'+HF_MODELS['video']['revision'][:8],note,
            metric_type='classifier',interpretation='Needs manual review' if unstable or low_quality else 'Uncalibrated image-classifier output',
            review_flag='inconsistent_views' if unstable else 'poor_capture_quality' if low_quality else None,
            raw_face_crop_pct=round(face_median*100,2),raw_full_frame_pct=round(full_median*100,2),
            sample_count=len(samples))
        return output
    finally:del model;gc.collect()

def audio_array(path):
    sr,a=wavfile.read(str(path));dtype=a.dtype
    if np.issubdtype(dtype,np.integer):
        if dtype==np.uint8:a=(a.astype(np.float32)-128)/128
        else:a=a.astype(np.float32)/max(abs(np.iinfo(dtype).min),np.iinfo(dtype).max)
    else:a=a.astype(np.float32)
    if a.ndim==2:a=a.mean(axis=1)
    if not np.all(np.isfinite(a)):raise ValueError('Audio contains invalid samples')
    divisor=math.gcd(sr,16000);a=resample_poly(a,16000//divisor,sr//divisor).astype(np.float32)
    if len(a)<3*16000 or np.sqrt(np.mean(a*a))<.0005:raise ValueError('Audio is too short or too quiet; record clear speech for at least three seconds.')
    a = a - np.mean(a)
    from scipy import signal
    a = signal.sosfilt(signal.butter(4, [80, 7500], fs=16000, btype='bandpass', output='sos'), a).astype(np.float32)
    return a

def speech_chunks(a,seconds=5,max_chunks=6):
    energy = np.abs(a)
    thresh = max(0.003, float(np.max(energy)) * 0.05)
    active = np.where(energy > thresh)[0]
    if len(active):
        margin = int(0.2 * 16000)
        a_active = a[max(0, active[0]-margin):min(len(a), active[-1]+margin)]
        if len(a_active) >= 16000:
            a = a_active
    width=seconds*16000
    if len(a)<=width:return [a]
    starts=np.linspace(0,len(a)-width,min(max_chunks,int(np.ceil(len(a)/width)))).astype(int)
    chunks=[a[s:s+width] for s in starts]
    usable=[c for c in chunks if np.sqrt(np.mean(c*c))>.002]
    if not usable:raise ValueError('No sufficiently audible audio segments. Retake closer to the microphone.')
    return usable

def audio_classifier():
    configure_torch()
    from transformers import AutoFeatureExtractor,AutoModelForAudioClassification
    p=WEIGHTS/'audio'
    return AutoFeatureExtractor.from_pretrained(p,local_files_only=True),AutoModelForAudioClassification.from_pretrained(p,local_files_only=True,use_safetensors=True).eval()

def synthetic_audio(path,ref_path=None):
    torch=configure_torch();chunks=speech_chunks(audio_array(path));extractor,model=audio_classifier()
    try:
        idx=fake_index(model.config);values=[]
        with torch.inference_mode():
            for c in chunks:
                inputs=extractor(c,sampling_rate=16000,return_tensors='pt');values.append(float(model(**inputs).logits.softmax(-1)[0,idx]))
        score_val=float(np.mean(values))
        note=f'Mean fake-class softmax over {len(values)} original-audio windows at 16 kHz. Not a calibrated probability. Hindi/Marathi and new cloning methods have not been validated here. Speech content is checked manually.'
        flag=None
        interpretation=None
        if ref_path is not None:
            try:
                spk=speakers(ref_path,path)
                if score_val>=0.80 and spk.get('value',0)>=70:
                    flag='inconsistent_audio'
                    interpretation='Needs manual review'
                    note+=' High synthetic score conflicts with strong reference speaker similarity: INCONCLUSIVE, review manually.'
            except Exception:pass
        return result(score_val*100,'Wav2Vec2 audio@'+HF_MODELS['audio']['revision'][:8],note,
            metric_type='classifier',interpretation=interpretation,review_flag=flag)
    finally:del model;gc.collect()

def speaker_model():
    configure_torch()
    from transformers import Wav2Vec2FeatureExtractor,WavLMForXVector
    p=WEIGHTS/'speaker'
    # transformers uses weights_only loading with the pinned supported torch version.
    return Wav2Vec2FeatureExtractor.from_pretrained(p,local_files_only=True),WavLMForXVector.from_pretrained(p,local_files_only=True).eval()

def speakers(ref,cur):
    torch=configure_torch();extractor,model=speaker_model()
    try:
        def embedding(path):
            vectors=[]
            with torch.inference_mode():
                for c in speech_chunks(audio_array(path),seconds=5,max_chunks=3):
                    inputs=extractor(c,sampling_rate=16000,return_tensors='pt');vectors.append(model(**inputs).embeddings[0])
            return torch.nn.functional.normalize(torch.stack(vectors).mean(0),dim=0)
        a,b=embedding(ref),embedding(cur);cosine=float(torch.dot(a,b))
        return result(max(0,min(1,cosine))*100,'WavLM SV@'+HF_MODELS['speaker']['revision'][:8],'Cosine similarity of mean speaker embeddings ×100 (negative values clipped to 0). Not identity probability. Cloned voices can match the source speaker; inspect synthetic-speech evidence separately.',cosine,metric_type='similarity',interpretation='Speaker embedding similarity, not identity probability')
    finally:del model;gc.collect()

def analyze(reference,evidence,progress=lambda label:None):
    out=blank()
    def run(label,keys,fn):
        progress(label)
        try:
            values=fn()
            if len(keys)==1:out['scores'][keys[0]]=values
            else:out['scores'].update(values)
        except Exception as e:
            for k in keys:out['scores'][k]={'value':None,'status':'failed','note':type(e).__name__+': '+str(e)[:400]+'. Check model health / run setup_models.py, or retake poor-quality evidence.'}
        gc.collect()
    with LOCK:
        run('Signature model & reference comparison',('signature_fake','signature_match'),lambda:signatures(reference['signature'],evidence['signature']))
        run('Face recognition & video frame classifier',('video_fake','face_match'),lambda:camera(reference,evidence['video']))
        progress('Extracting experimental rPPG signal')
        try:out['rppg']=video_evidence(evidence['video'])
        except Exception as e:out['rppg']={'pulse_bpm':None,'frames':0,'single_face_frames':0,'quality':'failed','note':str(e)}
        run('Synthetic-speech model',('audio_fake',),lambda:synthetic_audio(evidence['audio'],reference['audio']))
        run('Speaker-reference comparison',('speaker_match',),lambda:speakers(reference['audio'],evidence['audio']))
    out['notes']=['No automatic approval. Scores have not been calibrated against this bank population.','rPPG signal extraction does not prove live capture.','Spoken challenge correctness requires officer review.']
    return out

def health():
    checks={}
    for key,spec in HF_MODELS.items():
        missing=[f for f in spec['files'] if not (WEIGHTS/key/f).exists()]
        checks[key]={'ok':not missing,'message':'Files installed. '+spec['repo'] if not missing else 'Missing: '+', '.join(missing)+'. Run setup_models.py.'}
    missing=[f for f in FACE_FILES if not (WEIGHTS/'face'/f).exists()]
    checks['face']={'ok':not missing,'message':'YuNet and SFace files installed.' if not missing else 'Missing: '+', '.join(missing)}
    diag=WEIGHTS/'diagnostics.json'
    if diag.exists():
        try:
            d=json.loads(diag.read_text())
            for k,v in d['checks'].items():
                if k in checks and checks[k]['ok']:checks[k]=v
        except Exception:checks['diagnostics']={'ok':False,'message':'Diagnostics file could not be read; rerun setup.'}
    else:checks['diagnostics']={'ok':False,'message':'Forward-pass diagnostics have not run. Run setup_models.py.'}
    return {'ready':all(v['ok'] for v in checks.values()),'checks':checks}

def diagnose():
    import tempfile
    from PIL import ImageDraw
    torch=configure_torch();checks={}
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'signature.png';im=Image.new('RGB',(600,240),'white');ImageDraw.Draw(im).line([(30,160),(150,50),(290,150),(500,80)],fill='black',width=4);im.save(path)
        def check(key,fn):
            print('Forward pass:',key,flush=True)
            try:
                value=fn();checks[key]={'ok':True,'message':'Model loaded and finite forward-pass output verified. This is a software smoke test, not an accuracy evaluation.','output':value}
            except Exception as e:checks[key]={'ok':False,'message':type(e).__name__+': '+str(e)}
            gc.collect()
        check('signature',lambda:{k:v['value'] for k,v in signatures(path,path).items()})
        def image_test():
            processor,model=image_classifier()
            with torch.inference_mode():p=model(**processor(images=im,return_tensors='pt')).logits.softmax(-1)
            if not torch.isfinite(p).all():raise ValueError('Nonfinite output')
            return {'fake_label_index':fake_index(model.config),'shape':list(p.shape)}
        check('video',image_test)
        def audio_test():
            proc,model=audio_classifier();a=np.sin(2*np.pi*220*np.arange(64000)/16000).astype(np.float32)*.1
            with torch.inference_mode():p=model(**proc(a,sampling_rate=16000,return_tensors='pt')).logits.softmax(-1)
            if not torch.isfinite(p).all():raise ValueError('Nonfinite output')
            return {'fake_label_index':fake_index(model.config),'shape':list(p.shape)}
        check('audio',audio_test)
        def speaker_test():
            proc,model=speaker_model();a=np.sin(2*np.pi*220*np.arange(64000)/16000).astype(np.float32)*.1
            with torch.inference_mode():e=model(**proc(a,sampling_rate=16000,return_tensors='pt')).embeddings
            if not torch.isfinite(e).all():raise ValueError('Nonfinite output')
            return {'embedding_shape':list(e.shape)}
        check('speaker',speaker_test)
        def face_test():
            det,rec=face_models();det.setInputSize((320,320));det.detect(np.zeros((320,320,3),np.uint8));e=rec.feature(np.full((112,112,3),120,np.uint8))
            if not np.isfinite(e).all():raise ValueError('Nonfinite output')
            return {'embedding_shape':list(e.shape)}
        check('face',face_test)
    return {'ready':all(v['ok'] for v in checks.values()),'checks':checks,'tested_at':time.time()}
