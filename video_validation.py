"""Validate uploaded camera duration using decoded presentation timestamps.

Browser WebM duration/FPS metadata can be absent or misleading. Decode actual
frames and prefer their presentation timestamps; use FPS only as a last resort.
The duration check never claims the media was captured live.
"""
import math
import cv2

class VideoValidationError(ValueError):
    pass


def estimate_duration(frame_times, frame_count, fps):
    valid=[float(t) for t in frame_times if t is not None and math.isfinite(float(t)) and float(t)>=0]
    if len(valid)>=2 and valid[-1]>valid[0] and all(b>=a for a,b in zip(valid,valid[1:])):
        # Last decoded frame timestamp (+ half-to-one frame duration) is a better
        # duration estimate than the container frame-count/FPS for browser WebM.
        deltas=[b-a for a,b in zip(valid,valid[1:]) if b>a]
        if deltas:
            delta=sorted(deltas)[len(deltas)//2]
            if 0.004<=delta<=1.0:
                return valid[-1]-valid[0]+delta,'frame timestamps'
    if fps and math.isfinite(fps) and 5<=fps<=120 and frame_count>0:
        return frame_count/fps,'decoder FPS fallback'
    raise VideoValidationError('Video timing could not be verified. Retake using Chrome or Edge.')


def inspect_video(path, client_duration=None):
    frames=0;times=[];fps=0
    try:
        import av
        with av.open(str(path)) as container:
            video=next((s for s in container.streams if s.type=='video'),None)
            if video is None:raise VideoValidationError('No video track found.')
            if video.average_rate:
                fps=float(video.average_rate)
            for frame in container.decode(video):
                frames+=1
                if frame.width*frame.height>1920*1080:
                    raise VideoValidationError('Video resolution must be 1080p or below.')
                if frames>3500:raise VideoValidationError('Video too long; record 12–25 seconds.')
                times.append(float(frame.time) if frame.time is not None else None)
    except ImportError:
        # Keeps the app usable if PyAV hasn't yet been installed, but browsers
        # should install PyAV to validate unreliable WebM FPS correctly.
        cap=cv2.VideoCapture(str(path))
        fps=float(cap.get(cv2.CAP_PROP_FPS))
        try:
            while frames<=3500:
                ok,frame=cap.read()
                if not ok:break
                frames+=1
                if frame.shape[0]*frame.shape[1]>1920*1080:raise VideoValidationError('Video resolution must be 1080p or below.')
                ms=cap.get(cv2.CAP_PROP_POS_MSEC)
                times.append(ms/1000 if ms>0 else None)
        finally:cap.release()
    except VideoValidationError:raise
    except Exception as exc:raise VideoValidationError('Video could not be decoded. Try recording again in Chrome or Edge.') from exc
    if frames<40 or frames>3500:
        raise VideoValidationError('Not enough readable video frames. Record 12–25 seconds in good light.')
    try:
        duration,method=estimate_duration(times,frames,fps)
    except VideoValidationError:
        # Browser stopwatch is auxiliary only and may be forged. Accept only
        # when the decoded frame count is consistent with plausible capture FPS.
        try:seconds=float(client_duration)
        except (TypeError,ValueError):seconds=0
        if 10<=seconds<=45 and 5<=frames/seconds<=60:
            duration,method=seconds,'browser timer fallback (unverified)'
        else:raise
    # FPS metadata, especially WebM, can be wrong despite valid timestamp duration.
    if not 10<=duration<=45:
        raise VideoValidationError(f'Video is {duration:.1f} seconds by {method}. Record 12–25 seconds (accepted: 10–45 seconds).')
    return {'frames':frames,'duration':round(duration,2),'method':method}
