/* Real background job state; approvals are exclusively owner button actions. */
'use strict';
window.JarvisAgent = (()=>{
 const get=id=>document.getElementById(id),text=(tag,value)=>{const el=document.createElement(tag);el.textContent=value;return el;};
 let hooks,timer,loading=false,initial=true,previous=new Map(),enabled=false,lastSignature='',reviewed=new Map();
 const terminal=new Set(['completed','failed','cancelled','interrupted']);
 function button(label,fn){const b=text('button',label);b.type='button';b.onclick=()=>hooks.action(fn);return b;}
 function setting(id,value){if(!get('agent-settings').contains(document.activeElement))get(id).checked=value;}
 async function details(id){const item=await hooks.api('/api/agent/jobs/'+id);get('agent-audit').replaceChildren(...item.events.map(event=>{const row=text('div','');row.className='upgrade-row';row.append(text('strong',event.tool+' · '+event.status),text('pre',JSON.stringify(JSON.parse(event.args),null,2)),text('pre',JSON.stringify(JSON.parse(event.result),null,2)));return row;}));}
 async function refresh(){
  if(loading)return;loading=true;
  try{
   const data=await hooks.api('/api/agent/state');enabled=data.policy.enabled;
   setting('agent-enabled',enabled);setting('agent-automatic',data.policy.automatic);setting('agent-recovery',data.policy.recovery);setting('agent-account',data.policy.account_access);setting('agent-share-files',data.policy.share_files);setting('agent-remember',data.policy.remember_activity);
   if(!get('agent-settings').contains(document.activeElement)){get('agent-rounds').value=data.policy.max_rounds;get('agent-tools').value=data.policy.max_tools;}
   get('agent-platform').textContent=data.windows?'Windows detected. Native tool readiness is checked when used.':'This machine is not Windows. Native desktop, Edge and Windows commands require your PC; ordinary conversation and local planning can still work.';
   get('agent-service').textContent=enabled?(data.ai.configured?'Conversational agent enabled · paid requests occur only when you submit.':'Agent enabled, but the backend API key is missing.'):'Conversational agent off · enable it below to interpret natural requests with structured tools.';
   const active=data.jobs.filter(x=>!terminal.has(x.status));get('agent-live').textContent=active.length?active.map(x=>`${x.status.toUpperCase()} · ${x.current_tool||x.goal}`).join(' / '):enabled?'Agent ready · no active task':'Conversational agent off';
   const signature=JSON.stringify(data.jobs.map(x=>[x.id,x.status,x.summary,x.current_tool,x.rounds,x.tool_count,x.pending?.nonce]));
   if(signature!==lastSignature){lastSignature=signature;get('agent-job-list').replaceChildren(...data.jobs.map(item=>{
    const row=text('article','');row.className='panel agent-job';row.append(text('strong',item.goal),text('p',`${item.status.toUpperCase()} · ${item.tool_count} tool responses · ${item.rounds} model steps`));
    if(item.current_tool)row.append(text('p','Current operation: '+item.current_tool));
    if(item.summary)row.append(text('p',item.summary));
    const pending=item.pending;
    if(pending){
     const box=text('div','');box.className='agent-approval';box.append(text('h3',`Level ${pending.level} approval required`),text('p',pending.reason),text('pre',JSON.stringify({tool:pending.tool,arguments:pending.args},null,2)));
     if(pending.preview){const img=document.createElement('img');img.src='/api/agent/jobs/'+item.id+'/screen';img.alt='Exact locally captured screenshot awaiting your approval to share with OpenAI';img.className='agent-screen-preview';box.append(img);}
     const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=Boolean(reviewed.get(pending.nonce));check.onchange=()=>reviewed.set(pending.nonce,check.checked);label.append(check,document.createTextNode(' I have reviewed this exact action, data, code and destination.'));box.append(label);
     const approve=button('Approve this action',async()=>{if(!check.checked){hooks.notify('Review the exact request and tick its checkbox first.');return;}await hooks.api('/api/agent/jobs/'+item.id+'/approve','POST',{nonce:pending.nonce,reviewed:true});await refresh();});approve.className='primary';box.append(approve);row.append(box);
    }
    if(!terminal.has(item.status))row.append(button('Cancel task',async()=>{await hooks.api('/api/agent/jobs/'+item.id+'/cancel','POST',{});await refresh();}));
    row.append(button('Inspect activity',()=>details(item.id)));
    if(terminal.has(item.status))row.append(button('Delete task log',async()=>{if(confirm('Delete this task and its tool-event log? File backups and visible conversation history remain.')){await hooks.api('/api/agent/jobs/'+item.id,'DELETE');await refresh();}}));
    const prior=previous.get(item.id);
    if(!initial&&prior&&!terminal.has(prior)&&terminal.has(item.status)){
     try{if(localStorage.getItem('jarvis.agentNotifications')==='on'&&window.Notification?.permission==='granted')new Notification('JARVIS task '+item.status,{body:(item.summary||item.goal).slice(0,180)});}catch{}
     window.dispatchEvent(new Event('jarvis-data-change'));
     window.dispatchEvent(new CustomEvent('jarvis-agent-result',{detail:item}));
    }
    previous.set(item.id,item.status);return row;
   }));}
   get('agent-context').textContent=JSON.stringify(data.context,null,2);
   get('agent-recoveries').replaceChildren(...data.revisions.map(r=>text('p',`${r.id} · ${r.root}:${r.path} · ${r.kind} · ${r.status}`)),...data.transfers.map(r=>text('p',`${r.operation} · ${r.source_root}:${r.source} → ${r.destination_root}:${r.destination} · ${r.status}`)));
   initial=false;
  }finally{loading=false;}
 }
 return {get enabled(){return enabled;},watch(id){previous.set(id,'queued');initial=false;},refresh,async stop(){window.JarvisHUD.stop();const stopping=window.JarvisRealtime.stop();const result=await hooks.api('/api/workspace/emergency-stop','POST',{});await stopping;hooks.notify(result.reply);await refresh();},init(options){hooks=options;
  get('agent-notifications').onclick=()=>hooks.action(async()=>{if(!window.Notification){hooks.notify('Browser notifications are unavailable here. Task results remain in the HUD.');return;}const permission=await Notification.requestPermission();try{localStorage.setItem('jarvis.agentNotifications',permission==='granted'?'on':'off');}catch{}hooks.notify(permission==='granted'?'Completion notifications enabled while this page is running.':'Browser notifications were not enabled.');});
  get('agent-settings').onsubmit=event=>{event.preventDefault();hooks.action(async()=>{await hooks.api('/api/agent/settings','PUT',{enabled:get('agent-enabled').checked,automatic:get('agent-automatic').checked,recovery:get('agent-recovery').checked,account_access:get('agent-account').checked,share_files:get('agent-share-files').checked,remember_activity:get('agent-remember').checked,max_rounds:+get('agent-rounds').value,max_tools:+get('agent-tools').value,cost_consent:get('agent-consent').checked});hooks.notify('Agent permissions saved. Previous active tasks were cancelled so new authority cannot change an old approval.');await refresh();});};
  get('agent-goal-form').onsubmit=e=>{e.preventDefault();hooks.action(async()=>{const result=await hooks.api('/api/agent/jobs','POST',{goal:get('agent-goal').value});this.watch(result.id);get('agent-goal').value='';await refresh();});};
  get('clear-agent-context').onclick=()=>hooks.action(async()=>{if(confirm('Clear recent workflow context and exclude earlier chat from future AI context? Current agent tasks will be cancelled.')){await hooks.api('/api/agent/context','DELETE');await refresh();}});
  window.addEventListener('jarvis-emergency',()=>hooks.action(()=>this.stop()));
  document.addEventListener('keydown',event=>{if(event.altKey&&event.shiftKey&&event.code==='KeyS'){event.preventDefault();hooks.action(()=>this.stop());}});
  timer=setInterval(()=>hooks.action(refresh),1500);window.addEventListener('pagehide',()=>clearInterval(timer));
 }};
})();
