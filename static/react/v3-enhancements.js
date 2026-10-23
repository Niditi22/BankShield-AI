/* BankShield V3 compatibility layer for the included prebuilt React V2 bundle.
 * Running npm run build regenerates the V3 React UI from frontend/src and no
 * longer needs this layer. The backend API is the same in both modes.
 */
(() => {
  'use strict';
  const htmlEscape = s => String(s ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  async function request(path, body) {
    const session=await fetch('/api/session',{credentials:'same-origin',cache:'no-store'}).then(r=>r.json());
    const r=await fetch('/api'+path,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf},body:JSON.stringify(body)});
    const data=await r.json().catch(()=>({error:'Unable to read server response'}));
    if(!r.ok)throw Error(data.error||'Request failed');return data;
  }
  function showForgot() {
    if(document.querySelector('#bs-forgot-modal'))return;
    const overlay=document.createElement('div');overlay.id='bs-forgot-modal';overlay.className='bs-modal-backdrop';
    overlay.innerHTML=`<section class="bs-modal" role="dialog" aria-modal="true" aria-label="Password reset request">
      <button type="button" class="bs-modal-close" aria-label="Close">✕</button>
      <p class="bs-kicker">PASSWORD RECOVERY</p><h2>Request a password reset</h2>
      <p>Choose a new password. It will only become active after an administrator independently verifies your identity and approves the request.</p>
      <form id="bs-reset-form"><label>Customer email<input name="email" type="email" required autocomplete="email"></label>
      <label>New password (12+ characters)<input name="password" type="password" required minlength="12" maxlength="128" autocomplete="new-password"></label>
      <label>Confirm new password<input name="confirm_password" type="password" required minlength="12" maxlength="128" autocomplete="new-password"></label>
      <div id="bs-reset-response" role="status"></div><button type="submit">Send request to administrator</button></form>
      <p class="caption">For privacy, responses don't disclose whether an email exists. Passwords are never emailed.</p></section>`;
    document.body.appendChild(overlay);
    overlay.querySelector('.bs-modal-close').addEventListener('click',()=>overlay.remove());
    overlay.addEventListener('click',e=>{if(e.target===overlay)overlay.remove()});
    overlay.querySelector('form').addEventListener('submit',async e=>{
      e.preventDefault();const f=e.currentTarget,msg=overlay.querySelector('#bs-reset-response');
      const data=Object.fromEntries(new FormData(f));
      if(data.password!==data.confirm_password){msg.textContent='Passwords do not match.';return}
      const btn=f.querySelector('button[type=submit]');btn.disabled=true;msg.textContent='';
      try{const response=await request('/password-reset-requests',data);msg.textContent=response.message;f.reset()}
      catch(err){msg.textContent=err.message}finally{btn.disabled=false}
    });
  }
  const guidance={
    signature:['Signature capture guide','Use dark ink on plain white paper. Photograph the entire signature straight-on without blur, shadows or glare. Use your usual signing style.'],
    video:['Camera recording guide','Use Chrome/Edge on localhost. Sit in even lighting with one unobstructed face. Look forward and stay still for 15 seconds, turn slightly left and right, then stop at 12–25 seconds.'],
    audio:['Voice recording guide','Use a quiet room. Choose your language, read the entire phrase and code clearly at natural speed, record 3–40 seconds, then listen and retake if unclear.'],
    photo:['Reference photo guide','Look straight at the camera for the front shot; for left/right turn gently about 30–45 degrees. Keep both eyes visible if possible. Avoid shadows and blur.']
  };
  function guide(mode) {
    const d=document.createElement('aside');d.className='bs-capture-guide';d.dataset.bsGuide=mode;
    const [heading,body]=guidance[mode];
    d.innerHTML='<b>'+htmlEscape(heading)+'</b><p>'+htmlEscape(body)+'</p><small>Better input helps reduce errors; no result is guaranteed.</small>';
    return d;
  }
  function addGuide(section,mode){
    if(!section || section.querySelector(`[data-bs-guide="${mode}"]`))return;
    const g=guide(mode);
    const attach=section.querySelector('.upload,.video-stage,.spoken-prompt,.three-grid');
    if(attach)attach.parentElement.appendChild(g);else section.appendChild(g);
  }
  function enrich() {
    if(window.__BANKSHIELD_V3_REACT__)return;
    const login=document.querySelector('.login-panel');
    if(login&&login.querySelector('.tabs .selected')?.textContent?.trim()==='Customer'&&!login.querySelector('#bs-forgot-link')){
      const link=document.createElement('button');link.type='button';link.className='text-button bs-forgot-link';link.id='bs-forgot-link';link.textContent='Forgot password?';
      const form=login.querySelector('form');form?.after(link);link.addEventListener('click',showForgot);
    }
    if(login&&login.querySelector('.tabs .selected')?.textContent?.trim()!=='Customer')login.querySelector('#bs-forgot-link')?.remove();
    document.querySelectorAll('.panel').forEach(section=>{
      const h=(section.querySelector('h2')?.textContent||'').toLowerCase();
      if(h.includes('current signature')||h.includes('reference signature'))addGuide(section,'signature');
      else if(h.includes('short camera check'))addGuide(section,'video');
      else if(h.includes('verification phrase')||h.includes('reference voice'))addGuide(section,'audio');
      else if(h.includes('three views'))addGuide(section,'photo');
    });
    document.querySelectorAll('.score').forEach(score=>{
      if(score.querySelector('.bs-score-explain'))return;
      const label=score.querySelector('.score-title')?.textContent?.toLowerCase()||'';
      const p=document.createElement('p');p.className='bs-score-explain';
      p.textContent=label.includes('similarity')?'Matching similarity index (0–100). This is NOT an identity probability.':'Raw model fake-class score (0–100), NOT the probability the sample is fake. See diagnostic notes.';
      score.querySelector('strong')?.after(p);
      if(label.includes('deepfake') && score.textContent.includes('INCONCLUSIVE')){
        p.classList.add('bs-ambiguous');p.textContent+=' Predicted crop and full-frame scores disagree — manual review required.';
      }
    });
    const activity=[...document.querySelectorAll('.panel')].find(p=>p.querySelector('h2')?.textContent?.includes('Application activity'));
    if(activity){
      const table=activity.querySelector('table');
      if(table&&!table.querySelector('.bs-pdf-heading')){
        const th=document.createElement('th');th.className='bs-pdf-heading';th.textContent='Validation PDF';table.querySelector('thead tr')?.appendChild(th);
      }
      table?.querySelectorAll('tbody tr').forEach(row=>{
        if(row.querySelector('.bs-pdf-cell'))return;
        const id=Number(row.cells[0]?.textContent?.match(/BS-(\d+)/)?.[1]);
        const state=row.cells[3]?.textContent?.trim().toLowerCase();
        const td=document.createElement('td');td.className='bs-pdf-cell';
        if(id && (state==='approved'||state==='rejected')){
          const a=document.createElement('a');a.href='/api/applications/'+id+'/validation.pdf';a.download='';a.className='bs-report-link';a.textContent='↓ Download PDF';td.appendChild(a);
        }else td.textContent='After decision';
        row.appendChild(td);
      });
    }
    const adminHeader=[...document.querySelectorAll('h1')].find(h=>h.textContent?.includes('Your identity review desk'));
    if(adminHeader&&!document.querySelector('#bs-reset-queue'))loadAdminResetQueue(adminHeader.closest('.page-heading'));
  }
  let adminLoading=false;
  async function loadAdminResetQueue(heading){
    if(adminLoading)return;adminLoading=true;
    try{
      const resp=await fetch('/api/admin',{credentials:'same-origin',cache:'no-store'});
      if(!resp.ok)return;
      const data=await resp.json();const pending=(data.password_resets||[]).filter(x=>x.state==='pending');
      if(!heading||!heading.isConnected||document.querySelector('#bs-reset-queue'))return;
      const sec=document.createElement('section');sec.id='bs-reset-queue';sec.className='panel';
      sec.innerHTML='<h2>Password recovery requests <span class="count">'+pending.length+'</span></h2><p class="muted">Approve only after independently verifying the customer’s identity. Passwords are hashed and never shown.</p>';
      if(!pending.length)sec.innerHTML+='<p class="muted">No pending password reset requests.</p>';
      for(const x of pending){
        const d=document.createElement('div');d.className='bs-reset-row';
        d.innerHTML='<b>'+htmlEscape(x.email)+'</b><small>Requested '+new Date(x.requested_at*1000).toLocaleString()+'</small><label>Officer note <input placeholder="Describe verification or denial" maxlength="1000"></label><label class="checkline"><input type="checkbox"> Independently verified customer identity</label><div class="bs-reset-actions"><button type="button" data-answer="approved">Approve reset</button><button type="button" data-answer="rejected">Reject reset</button></div><p role="alert"></p>';
        for(const b of d.querySelectorAll('button'))b.addEventListener('click',async()=>{
          const note=d.querySelector('input:not([type=checkbox])').value.trim(),verified=d.querySelector('input[type=checkbox]').checked;
          const decision=b.dataset.answer;
          if(note.length<5 || (decision==='approved'&&!verified)){d.querySelector('[role=alert]').textContent='Write a reason (5+ characters) and verify identity before approval.';return}
          b.disabled=true;
          try{await request('/admin/password-resets/'+x.id,{decision,note,identity_verified:verified});sec.remove();loadAdminResetQueue(heading)}
          catch(err){d.querySelector('[role=alert]').textContent=err.message;b.disabled=false}
        });
        sec.appendChild(d);
      }
      heading.after(sec);
    }catch(err){ /* a normal app error should not prevent the original dashboard */ }
    finally{adminLoading=false}
  }
  // Poll is intentionally low-frequency: React's own 5s updates can replace
  // nodes outside its V2 virtual DOM. Insertions are idempotent.
  enrich();setInterval(enrich,1600);
})();
