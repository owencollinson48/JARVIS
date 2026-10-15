'use strict';
window.JarvisUpgrade = (()=>{
 const get=id=>document.getElementById(id),el=(tag,value)=>{const n=document.createElement(tag);n.textContent=value;return n;};
 let hooks,planner,roots,selected=null;
 function button(label,fn){const b=el('button',label);b.type='button';b.onclick=()=>hooks.action(fn);return b;}
 function rows(id,items,render){get(id).replaceChildren(...(items.length?items.map(item=>{const n=el('div','');n.className='upgrade-row';render(n,item);return n;}):[el('p','Nothing saved here yet.')]));}
 function value(id,v){if(!get(id).closest('form')?.contains(document.activeElement))get(id).value=v;}
 function checked(id,v){if(!get(id).closest('form')?.contains(document.activeElement))get(id).checked=v;}
 const run=fn=>hooks.action(async()=>{await fn();await refresh();await window.JarvisComputer.refresh();});
 function form(id,fn){get(id).onsubmit=e=>{e.preventDefault();run(fn);};}
 async function planning(){
  planner=await hooks.api('/api/planning/state');const cfg=planner.config,b=planner.briefing;
  value('plan-zone',cfg.timezone);value('plan-interval',cfg.interval);value('plan-quiet-start',cfg.quiet_start);value('plan-quiet-end',cfg.quiet_end);checked('plan-proactive',cfg.proactive);
  get('planning-summary').textContent=b.summary+' Timezone: '+b.timezone;
  get('next-shift').textContent=b.next_shift?.title||'No saved shifts';get('next-shift-time').textContent=b.next_shift?b.next_shift.start:'Add actual shifts in Planning.';
  rows('planning-conflicts',b.conflicts,(n,x)=>n.append(el('p',`Conflict: ${x.first} / ${x.second} · ${x.start}`)));
  rows('study-slots',b.study_suggestions,(n,x)=>n.append(el('p',`Suggested study: ${x.start} – ${x.end}`),el('small',x.basis)));
  rows('work-events',b.events.filter(x=>x.kind==='work'),(n,x)=>n.append(el('strong',x.title),el('p',`${x.start} – ${x.end} · ${Math.round(((Date.parse(x.end)-Date.parse(x.start))/60000-x.break_minutes)/60*100)/100} paid hours (saved break deducted)`)));
  rows('calendar-events',planner.events,(n,x)=>{
   n.append(el('strong',`${x.title} · ${x.kind}`),el('p',`${x.start} – ${x.end} · ${x.recurrence} · ${x.timezone}`),button('Edit',async()=>{
    get('event-id').value=x.id;get('event-title').value=x.title;get('event-kind').value=x.kind;
    const local=iso=>{const parts=new Intl.DateTimeFormat('sv-SE',{timeZone:cfg.timezone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(iso));return parts.replace(' ','T');};
    get('event-start').value=local(x.start);get('event-end').value=local(x.end);get('event-repeat').value=x.recurrence;get('event-until').value=x.until_date||'';get('event-break').value=x.break_minutes;
   }),button('Delete',async()=>{if(confirm('Delete this saved event and its recurrence?')){await hooks.api('/api/planning/events/'+x.id,'DELETE');await refresh();}}));
  });
  rows('planning-notices',planner.notices,(n,x)=>n.append(el('strong',`${x.category.toUpperCase()} · ${x.status}`),el('p',x.body),...(x.status==='unread'?[button('Mark read',async()=>{await hooks.api('/api/planning/notices/'+x.id,'PUT',{});await planning();})]:[])));
 }
 async function workspace(){
  const data=await hooks.api('/api/workspace/state');roots=data.roots;checked('auto-open',data.auto_open);
  const choice=get('file-root').value;get('file-root').replaceChildren(...roots.map(x=>new Option(x.alias,x.alias)));if(roots.some(x=>x.alias===choice))get('file-root').value=choice;
  rows('root-list',roots,(n,x)=>n.append(el('strong',x.alias),el('p',`${x.path} · read ${x.allow_read?'yes':'no'} · move ${x.allow_move?'yes':'no'}`),button('Remove approval',async()=>{await hooks.api('/api/workspace/roots/'+encodeURIComponent(x.alias),'DELETE');await workspace();})));
  rows('workflow-list',data.workflows,(n,x)=>n.append(el('strong',`${x.name} · ${x.preapproved?'preapproved':'confirmation required'}`),el('pre',JSON.stringify(JSON.parse(x.steps),null,2)),button('Run',async()=>hooks.command('run workflow '+x.name)),button('Delete',async()=>{await hooks.api('/api/workspace/workflows/'+encodeURIComponent(x.name),'DELETE');await workspace();})));
  const log=await hooks.api('/api/computer/state?q='+encodeURIComponent(get('log-query').value));rows('action-log',log.recent,(n,x)=>n.append(el('strong',`${x.status} · ${x.preview}`),el('p',x.result||'Awaiting confirmation.')));
 }
 async function communications(){
  const data=await hooks.api('/api/communications/state'),cfg=data.config;
  const activeJobs=data.jobs.filter(x=>['sending','queued','initiated','ringing','in-progress'].includes(x.status));get('contact-operational-status').textContent=activeJobs.length?activeJobs.map(x=>`${x.channel}: ${x.status}`).join(' · '):'No active SMS or phone dispatch';
  get('background-status').textContent=data.last_worker?'Last completed background check: '+new Date(data.last_worker).toLocaleString():'Background worker has not reported a check. See setup guide to enable checks with the browser closed.';
  get('communication-status').textContent=data.configured?'Backend variables present. Live delivery and voice have not been verified by this status check.':data.error;
  checked('comm-consent',cfg.recipient_consent);checked('comm-sms',cfg.sms);checked('comm-calls',cfg.calls);value('comm-sms-limit',cfg.sms_limit);value('comm-call-limit',cfg.call_limit);value('comm-seconds',cfg.call_seconds);
  if(!get('communication-settings').contains(document.activeElement))document.querySelectorAll('[name="comm-category"]').forEach(x=>x.checked=cfg.categories.includes(x.value));
  rows('contact-jobs',data.jobs,(n,x)=>{
   n.append(el('strong',`${x.channel.toUpperCase()} · ${x.status}`),el('p',x.body),el('small',`${x.due} · ${x.result||'Not sent'}`));
   if(x.status==='draft')n.append(button('Approve this contact',async()=>{if(confirm(`Approve this ${x.channel} to your fixed verified number? Paid provider charges apply.`)){await hooks.api('/api/communications/jobs/'+x.id+'/approve','POST',{});await communications();}}));
   if(['draft','pending'].includes(x.status))n.append(button('Cancel',async()=>{await hooks.api('/api/communications/jobs/'+x.id,'DELETE');await communications();}));
  });
  const voice=await hooks.api('/api/realtime/state');get('paid-voice-toggle').disabled=!(voice.enabled&&voice.configured);
  if(!window.JarvisRealtime.active)get('paid-voice-status').textContent=voice.enabled&&voice.configured?'Paid voice configured; connection not checked.': 'Paid voice disabled or API key missing. Existing browser voice remains available.';
 }
 async function refresh(){const results=await Promise.allSettled([planning(),workspace(),communications()]);const failed=results.find(x=>x.status==='rejected');if(failed)throw failed.reason;}
 return {refresh,init(options){
  hooks=options;window.JarvisRealtime.init(hooks);
  let operations=0;window.addEventListener('jarvis-operation',event=>{const d=event.detail;operations+=d.running?1:-1;operations=Math.max(0,operations);get('operation-status').textContent=operations?d.label:'No foreground operation running';});
  get('browser-zone').onclick=()=>get('plan-zone').value=Intl.DateTimeFormat().resolvedOptions().timeZone;
  form('planning-settings',()=>hooks.api('/api/planning/settings','PUT',{timezone:get('plan-zone').value,interval:+get('plan-interval').value,quiet_start:+get('plan-quiet-start').value,quiet_end:+get('plan-quiet-end').value,proactive:get('plan-proactive').checked}));
  get('event-clear').onclick=()=>{get('event-form').reset();get('event-id').value='';};
  form('event-form',async()=>{const id=get('event-id').value;await hooks.api('/api/planning/events'+(id?'/'+id:''),id?'PUT':'POST',{title:get('event-title').value,kind:get('event-kind').value,start:get('event-start').value,end:get('event-end').value,recurrence:get('event-repeat').value,until_date:get('event-until').value,break_minutes:+get('event-break').value});get('event-form').reset();get('event-id').value='';});
  get('auto-open').onchange=()=>run(()=>hooks.api('/api/workspace/permissions','PUT',{auto_open:get('auto-open').checked}));
  form('root-form',async()=>{await hooks.api('/api/workspace/roots','POST',{alias:get('root-alias').value,path:get('root-path').value,allow_read:get('root-read').checked,allow_move:get('root-move').checked});get('root-form').reset();});
  form('workflow-form',async()=>{await hooks.api('/api/workspace/workflows','POST',{name:get('workflow-name').value,steps:get('workflow-steps').value.split('\n').filter(x=>x.trim()),preapproved:get('workflow-approved').checked});get('workflow-form').reset();});
  form('file-search',async()=>{selected=null;get('document-summary').disabled=true;get('document-text').textContent='';const root=get('file-root').value;const data=await hooks.api('/api/workspace/search','POST',{root,query:get('file-query').value});get('document-status').textContent=data.limited?'Results limited; refine your search.':'';
   rows('file-results',data.items,(n,x)=>n.append(el('strong',x.relative),button('Select & read',async()=>{const doc=await hooks.api('/api/workspace/read','POST',{root,relative:x.relative});selected={root,relative:x.relative};get('document-text').textContent=doc.text;get('document-summary').disabled=false;get('document-status').textContent=doc.truncated?'Text truncated to 20,000 characters.':'Read locally. Nothing sent to OpenAI.';}),button('Preview open',async()=>{await hooks.api('/api/workspace/preview','POST',{root,relative:x.relative,kind:'open'});await window.JarvisComputer.refresh();hooks.notify('Open preview is on the dashboard. Close this panel to confirm.');})));
  });
  get('document-summary').onclick=()=>run(async()=>{if(!selected)return;if(!confirm('Send this document text (up to 20,000 characters) to OpenAI? Paid API charges apply.'))return;const data=await hooks.api('/api/workspace/summarise','POST',{...selected,external_consent:true});get('document-text').textContent=data.reply;});
  form('move-form',async()=>{if(!selected)throw new Error('Select and read a file first.');await hooks.api('/api/workspace/preview','POST',{...selected,kind:'move',destination:get('move-destination').value});hooks.notify('Move preview is on the dashboard. Close this panel to confirm.');});
  form('log-search',workspace);
  form('research-form',async()=>{if(!confirm('Use paid OpenAI web search? The query is sent externally; search tool charges may apply.'))return;const data=await hooks.api('/api/workspace/research','POST',{query:get('research-query').value,external_consent:true});get('research-answer').textContent=data.reply;rows('research-sources',data.sources,(n,x)=>{const a=el('a',x.title||x.url);a.href=x.url;a.target='_blank';a.rel='noopener noreferrer';n.append(a);});});
  form('communication-settings',()=>hooks.api('/api/communications/settings','PUT',{sms:get('comm-sms').checked,calls:get('comm-calls').checked,recipient_consent:get('comm-consent').checked,sms_limit:+get('comm-sms-limit').value,call_limit:+get('comm-call-limit').value,call_seconds:+get('comm-seconds').value,categories:[...document.querySelectorAll('[name="comm-category"]:checked')].map(x=>x.value)}));
  form('contact-form',async()=>{await hooks.api('/api/communications/jobs','POST',{channel:get('contact-channel').value,body:get('contact-body').value,due:get('contact-due').value});get('contact-form').reset();});
  get('emergency-stop').onclick=()=>run(async()=>{window.JarvisHUD.stop();await window.JarvisRealtime.stop();const data=await hooks.api('/api/workspace/emergency-stop','POST',{});hooks.notify(data.reply+(data.call_stop_failures?` ${data.call_stop_failures} provider stop requests failed.`:'')+(data.voice_stop_failures?` ${data.voice_stop_failures} paid voice stop requests could not be confirmed.`:''));});
  setInterval(()=>{if(!document.hidden)hooks.action(async()=>{await planning();await communications();});},60000);
 }};
})();
