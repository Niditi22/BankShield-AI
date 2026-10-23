"""Local evidence analysis. No untrained network is represented as a detector."""
import cv2
import numpy as np
from PIL import Image, ImageOps
from scipy import signal

KEYS = ('signature_fake','signature_match','video_fake','face_match','audio_fake','speaker_match')
def unavailable():
    return {k: {'value': None, 'status': 'unavailable', 'note': 'Validated model and weights not configured.'} for k in KEYS}

def normalize_image(src, dst, signature=False):
    with Image.open(src) as im:
        if im.width * im.height > 20_000_000: raise ValueError('Image too large; maximum 20 megapixels.')
        im = ImageOps.exif_transpose(im).convert('RGBA')
        bg = Image.new('RGBA', im.size, 'white'); bg.alpha_composite(im)
        im = bg.convert('RGB')
        if min(im.size) < 60: raise ValueError('Image is too small. Retake a clear image.')
        if signature:
            gray = np.array(ImageOps.grayscale(im))
            _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
            pts = cv2.findNonZero(mask)
            if pts is None or np.count_nonzero(mask) < 30: raise ValueError('Signature image appears blank.')
            x,y,w,h = cv2.boundingRect(pts); im = im.crop((x,y,x+w,y+h))
        im = ImageOps.pad(im, (600,240) if signature else (480,480), color='white')
        im.save(dst, 'PNG')

def signature_similarity(a,b):
    def ink(p):
        g=cv2.imread(str(p),0)
        return cv2.threshold(g,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]>0
    a,b=ink(a),ink(b)
    return round(100*2*np.logical_and(a,b).sum()/max(1,a.sum()+b.sum()),1)

def video_evidence(path):
    cap=cv2.VideoCapture(str(path)); fps=cap.get(cv2.CAP_PROP_FPS)
    face=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
    series=[]; total=0; detected=0
    while total<1800:
        ok,frame=cap.read()
        if not ok: break
        total+=1
        gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
        boxes=face.detectMultiScale(gray,1.15,5,minSize=(60,60))
        if len(boxes)==1:
            detected+=1; x,y,w,h=boxes[0]
            roi=frame[y+int(.15*h):y+int(.35*h),x+int(.25*w):x+int(.75*w)]
            series.append((total,float(roi[:,:,1].mean())))
    cap.release()
    result={'frames':total,'single_face_frames':detected,'pulse_bpm':None,'note':'Experimental green-channel rPPG. A pulse signal does not prove liveness or exclude a deepfake.'}
    if len(series)<100 or detected/max(total,1)<.5:
        result['quality']='insufficient face visibility'; return result
    try:
        from video_validation import inspect_video
        duration=inspect_video(path)['duration']
    except Exception:
        result['quality']='unverifiable video timing';return result
    sampling_fps=total/duration
    if duration<10 or sampling_fps<8 or sampling_fps>120:
        result['quality']='insufficient timing quality';return result
    indices,g=np.array(series).T
    t=(indices-1)/sampling_fps
    uniform=np.arange(t[0],t[-1],1/sampling_fps)
    values=signal.detrend(np.interp(uniform,t,g))
    f,p=signal.periodogram(values,fs=sampling_fps);band=(f>=.7)&(f<=3)
    if band.any() and p[band].sum()>1e-6:
        result['pulse_bpm']=round(float(f[band][np.argmax(p[band])]*60),1)
        result['quality']='experimental estimate; motion and lighting can dominate'
    else: result['quality']='no usable signal'
    return result
