import React,{useEffect,useRef,useState} from 'react';
import {Camera,Mic,Square,RotateCcw,Check,Video} from 'lucide-react';
import {api} from './api';
function useBlobUrl(blob){const [url,set]=useState('');useEffect(()=>{if(!blob){set('');return}const u=URL.createObjectURL(blob);set(u);return()=>URL.revokeObjectURL(u)},[blob]);return url}
export function PhotoCapture({angle,value,onChange}){const video=useRef(null),stream=useRef(null),mounted=useRef(true);const [live,setLive]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');const url=useBlobUrl(value);const stop=()=>{stream.current?.getTracks().forEach(t=>t.stop());stream.current=null};useEffect(()=>()=>{mounted.current=false;stop()},[]);
async function start(){try{setError('');setBusy(true);stop();const s=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:{ideal:640},height:{ideal:480}},audio:false});if(!mounted.current){s.getTracks().forEach(t=>t.stop());return}stream.current=s;setLive(true);requestAnimationFrame(()=>{if(video.current)video.current.srcObject=s})}catch(e){setError('Camera could not start. Allow camera permission in Chrome/Edge and close other camera apps. '+e.message)}finally{setBusy(false)}}
async function capture(){const v=video.current;if(!v?.videoWidth){setError('Wait for the camera image to appear.');return}const canvas=document.createElement('canvas');canvas.width=v.videoWidth;canvas.height=v.videoHeight;canvas.getContext('2d').drawImage(v,0,0);const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));if(!blob){setError('Photo capture failed. Please try again.');return}onChange(blob);stop();setLive(false)}
return <div className="capture-card"><div className="capture-title"><b>{angle[0].toUpperCase()+angle.slice(1)} profile</b>{value&&<span className="tiny-ok"><Check size={14}/>Captured</span>}</div><div className="camera-stage">{live?<video ref={video} autoPlay muted playsInline/>:url?<img src={url} alt={`${angle} profile preview`}/>:<div className="capture-empty"><Camera size={36}/><span>{angle==='front'?'Look straight at the camera':`Turn your face gently to the ${angle}`}</span></div>}{live&&<div className="face-guide"/>}</div><p className="caption">{angle==='front'?'Keep your entire face inside the frame.':'Turn about 30–45°, keeping both eyes visible where possible.'}</p><div className="actions">{live?<><button type="button" onClick={capture}><Camera size={16}/>Click photo</button><button type="button" className="quiet" onClick={()=>{stop();setLive(false)}}>Cancel</button></>:<button type="button" className={value?'outline':''} disabled={busy} onClick={start}>{value?<RotateCcw size={15}/>:<Camera size={15}/>} {busy?'Opening camera…':value?'Retake photo':'Open camera'}</button>}</div>{error&&<div className="error">{error}</div>}</div>}
export function SignatureUpload({value,onChange}){const url=useBlobUrl(value);return <div className="upload"><label className="upload-label"><span>Choose signature image</span><input type="file" accept="image/jpeg,image/png" onChange={e=>onChange(e.target.files[0]||null)}/></label><p className="caption">Dark ink, white paper. PNG or JPEG. Resize preserves proportions; it cannot recover blurred detail.</p>{url&&<img className="signature-preview" src={url} alt="Signature preview"/>}</div>}
function wavBlob(chunks,sr){const count=chunks.reduce((n,c)=>n+c.length,0),v=new DataView(new ArrayBuffer(44+count*2));const str=(o,s)=>[...s].forEach((c,i)=>v.setUint8(o+i,c.charCodeAt(0)));str(0,'RIFF');v.setUint32(4,36+count*2,true);str(8,'WAVE');str(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,sr,true);v.setUint32(28,sr*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);str(36,'data');v.setUint32(40,count*2,true);let pos=44;for(const c of chunks)for(const x of c){v.setInt16(pos,Math.max(-1,Math.min(1,x))*32767,true);pos+=2}return new Blob([v],{type:'audio/wav'})}
export function AudioCapture({value,onChange}){const [language,setLanguage]=useState('English'),[challenge,setChallenge]=useState(null),[error,setError]=useState(''),[running,setRunning]=useState(false),[opening,setOpening]=useState(false),[seconds,setSeconds]=useState(0);const state=useRef({}),mounted=useRef(true),callback=useRef(onChange);callback.current=onChange;const url=useBlobUrl(value?.blob);
async function stop(save=true){const s=state.current;state.current={};clearInterval(s.timer);if(!s.stream)return;s.processor?.disconnect();s.source?.disconnect();s.stream.getTracks().forEach(t=>t.stop());const sr=s.ctx.sampleRate;await s.ctx.close();if(!mounted.current)return;setRunning(false);if(save){const duration=s.chunks.reduce((n,c)=>n+c.length,0)/sr;if(duration<3){setError('Record for at least 3 seconds, reading the entire phrase.');return}callback.current({blob:wavBlob(s.chunks,sr),challenge:s.challenge})}}
useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;stop(false)}},[]);
useEffect(()=>{let cancelled=false;setChallenge(null);callback.current(null);api('/challenge?language='+encodeURIComponent(language)).then(c=>{if(!cancelled)setChallenge(c)}).catch(e=>{if(!cancelled)setError(e.message)});return()=>{cancelled=true}},[language]);
async function start(){try{setError('');setOpening(true);const stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false}});if(!mounted.current){stream.getTracks().forEach(t=>t.stop());return}const ctx=new AudioContext();await ctx.resume();const source=ctx.createMediaStreamSource(stream),processor=ctx.createScriptProcessor(4096,1,1),chunks=[];processor.onaudioprocess=e=>chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));source.connect(processor);processor.connect(ctx.destination);const startTime=Date.now();const timer=setInterval(()=>{setSeconds(Math.floor((Date.now()-startTime)/1000));if(Date.now()-startTime>=40000)stop()},300);state.current={stream,ctx,source,processor,chunks,timer,challenge};setRunning(true);setSeconds(0);callback.current(null)}catch(e){setError('Microphone error: '+e.message)}finally{setOpening(false)}}
return <div><label>Spoken language<select value={language} disabled={running||opening} onChange={e=>setLanguage(e.target.value)}><option>English</option><option>Hindi</option><option>Marathi</option></select></label><div className="spoken-prompt">{challenge?.text||'Preparing a fresh verification phrase…'}</div><div className="actions"><button type="button" disabled={!challenge||opening} className={running?'red':''} onClick={()=>running?stop():start()}>{running?<Square size={16}/>:<Mic size={16}/>} {opening?'Opening microphone…':running?`Stop · ${seconds}s`:'Record voice'}</button>{value&&<span className="tiny-ok"><Check size={14}/>Recording saved</span>}</div><p className="caption">Read the full phrase and code. Record 3–40 seconds. Listen before continuing.</p>{url&&<audio controls src={url}/>} {error&&<div className="error">{error}</div>}</div>}
export function VideoCapture({value,onChange}){
 const [running,setRunning]=useState(false),[opening,setOpening]=useState(false),
       [seconds,setSeconds]=useState(0),[error,setError]=useState('');
 const el=useRef(null),state=useRef({}),mounted=useRef(true);
 const callback=useRef(onChange);callback.current=onChange;
 const url=useBlobUrl(value?.blob);
 useEffect(()=>{mounted.current=true;return()=>{
   mounted.current=false;const s=state.current;clearInterval(s.timer);
   if(s.rec&&s.rec.state!=='inactive'){s.rec.onstop=null;s.rec.stop()}
   s.stream?.getTracks().forEach(t=>t.stop());
 }},[]);
 useEffect(()=>{if(running&&el.current&&state.current.stream){
   el.current.srcObject=state.current.stream;
   el.current.play().catch(()=>{});
 }},[running]);
 async function start(){
   let stream;
   try{
     setError('');setOpening(true);
     if(!window.MediaRecorder)throw Error('Your browser does not support camera video recording. Use Chrome or Edge.');
     stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:{ideal:640,max:1280},height:{ideal:480,max:720},frameRate:{ideal:24,max:30}},audio:false});
     if(!mounted.current){stream.getTracks().forEach(t=>t.stop());return}
     const type=['video/webm;codecs=vp8','video/webm;codecs=vp9','video/webm','video/mp4'].find(x=>MediaRecorder.isTypeSupported(x));
     const rec=new MediaRecorder(stream,{...(type?{mimeType:type}:{}),videoBitsPerSecond:950000});
     const chunks=[];const started=performance.now();
     rec.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};
     rec.onerror=e=>setError('Recording failed: '+(e.error?.message||'Unknown recording error'));
     rec.onstop=()=>{
       const s=state.current;clearInterval(s.timer);
       stream.getTracks().forEach(t=>t.stop());
       if(!mounted.current)return;
       setRunning(false);if(el.current)el.current.srcObject=null;
       const duration=(performance.now()-started)/1000;
       if(duration<11.5){setError('Record at least 12 seconds before stopping.');return}
       if(chunks.length===0){setError('Camera returned an empty recording. Retake the video.');return}
       const mime=rec.mimeType||type||'video/webm';
       callback.current({blob:new Blob(chunks,{type:mime}),seconds:Math.round(duration*10)/10});
     };
     // A single state record controls cleanup and prevents timers from being leaked.
     state.current={stream,rec};
     rec.start(250);
     const timer=setInterval(()=>{
       const t=(performance.now()-started)/1000;
       if(mounted.current)setSeconds(Math.floor(t));
       if(t>=25&&rec.state==='recording')rec.stop();
     },200);
     state.current.timer=timer;
     callback.current(null);setSeconds(0);setRunning(true);
   }catch(e){
     stream?.getTracks().forEach(t=>t.stop());
     setError('Camera error: '+e.message+' Check browser permission, close other camera apps, and use localhost.');
   }finally{if(mounted.current)setOpening(false)}
 }
 function stop(){const r=state.current.rec;if(r&&r.state==='recording')r.stop()}
 return <div><div className="video-stage">{running?<video key="live" ref={el} autoPlay muted playsInline/>:url?<video key="saved" controls src={url}/>:<div className="capture-empty"><Video size={48}/><span>Your camera preview appears here</span></div>}</div>
 <div className="notice">Stay front-facing and steady for 15 seconds, then turn slightly left and right. Record 12–25 seconds. The camera shuts down when you stop.</div>
 <div className="actions"><button type="button" disabled={opening} className={running?'red':''} onClick={running?stop:start}>{running?<Square size={16}/>:<Video size={16}/>} {opening?'Opening camera…':running?`Stop · ${seconds}s`:value?'Record again':'Start camera recording'}</button>
 {value&&<span className="tiny-ok"><Check size={14}/>Saved {value.seconds}s recording</span>}</div>
 {error&&<div className="error" role="alert">{error}</div>}
 </div>
}
