'use strict';
const $ = id => document.getElementById(id);
let state = {tasks: [], projects: [], messages: [], memories: [], settings: {}, ai: {}}, editing = null;
const today = () => {const d=new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;};
const dateLabel = value => new Date(`${value}T12:00:00`).toLocaleDateString('en-AU',{month:'short',day:'numeric'});
function node(tag, cls, text) {const el=document.createElement(tag); if(cls)el.className=cls; if(text!==undefined)el.textContent=text; return el;}
function notify(message) {$('notice-text').textContent=message; $('notice').hidden=false;if($('workspace-dialog').open){$('panel-notice').textContent=message;$('panel-notice').hidden=false;}}
$('dismiss-notice').onclick=()=>{$('notice').hidden=true;};
async function api(path, method='GET', data) {
 let label=path.includes('/workspace/search')?'Searching trusted files…':path.includes('/workspace/read')?'Reading approved document locally…':path.includes('/workspace/research')?'Researching the internet through OpenAI…':path.includes('/approve')?'Dispatching approved SMS/call or scheduling it…':path.includes('/workflows')&&method==='POST'?'Saving approved workflow…':path.includes('/chat')?'Processing your request…':null;
 if(label)window.dispatchEvent(new CustomEvent('jarvis-operation',{detail:{running:true,label}}));
 let response;try{response=await fetch(path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name="csrf-token"]').content},body:data===undefined?undefined:JSON.stringify(data)});}finally{if(label)window.dispatchEvent(new CustomEvent('jarvis-operation',{detail:{running:false,label}}));}
 let result; try {result=await response.json();} catch {throw new Error('Unexpected server response. Restart JARVIS and refresh.');}
 if(!response.ok){const error=new Error(result.error||'The request failed. Please try again.');error.status=response.status;throw error;} return result;
}
async function refresh(){try{state=await api('/api/state');render();}catch(error){window.JarvisHUD.backend(false);throw error;}const panels=await Promise.allSettled([window.JarvisComputer.refresh(),window.JarvisUpgrade.refresh()]);const failure=panels.find(x=>x.status==='rejected');if(failure)notify('Your local data loaded, but an additional panel failed: '+failure.reason.message);}
async function action(fn){try{await fn();}catch(error){notify(error.message||'Unable to connect to JARVIS. Check that the server is running.');}}
const panelNames={tasks:'Task manager',university:'University',work:'Work schedule',projects:'Projects',briefing:'Daily briefing',reminders:'Deadlines',chat:'Conversation history',memory:'Saved memory',settings:'Settings',planning:'Planning',autonomy:'Computer & files',communications:'Voice, phone & SMS'};
function homeNavigation(){
 document.body.classList.remove('panel-open');
 document.querySelectorAll('.main-nav button').forEach(el=>{const active=el.dataset.page==='dashboard';el.classList.toggle('active',active);if(active)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});
}
function navigate(page){
 if(page==='dashboard'){$('workspace-dialog').close();homeNavigation();return;}
 if(!panelNames[page])return;
 $('panel-notice').hidden=true;
 window.JarvisHUD.pause();
 document.querySelectorAll('.workspace-content>.page').forEach(el=>el.hidden=el.id!==page);
 $('workspace-title').textContent=panelNames[page];$('panel-switch').value=page;
 document.querySelectorAll('.main-nav button').forEach(el=>{const active=el.dataset.page===page;el.classList.toggle('active',active);if(active)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});
 document.body.classList.add('panel-open');
 if(!$('workspace-dialog').open)$('workspace-dialog').showModal();
 const heading=$(page).querySelector('h1');heading.tabIndex=-1;heading.focus();
 if(page==='chat')$('messages').scrollTop=$('messages').scrollHeight;
}
document.querySelectorAll('[data-page]').forEach(el=>el.addEventListener('click',()=>navigate(el.dataset.page)));
$('panel-switch').onchange=event=>navigate(event.target.value);
$('close-workspace').onclick=()=>$('workspace-dialog').close();
$('workspace-dialog').addEventListener('close',homeNavigation);
function taskRow(task){
 const row=node('div',`task-row ${task.completed?'completed':''}`), check=node('input','task-check'); check.type='checkbox'; check.checked=Boolean(task.completed);check.setAttribute('aria-label',`Complete ${task.title}`);
 check.addEventListener('change',()=>action(async()=>{check.disabled=true;try{await api(`/api/tasks/${task.id}`,'PUT',{...task,completed:check.checked});await refresh();}catch(error){check.checked=!check.checked;throw error;}finally{check.disabled=false;}}));
 const content=node('div','task-content');content.append(node('span','task-name',task.title),node('div','task-meta',`${task.project} · ${dateLabel(task.due)}${!task.completed&&task.due<today()?' · Overdue':''}`));
 const actions=node('div','task-actions'),edit=node('button','', 'Edit'),del=node('button','','Delete'); edit.setAttribute('aria-label',`Edit ${task.title}`); del.setAttribute('aria-label',`Delete ${task.title}`);
 edit.onclick=()=>openTask(task); del.onclick=()=>{if(confirm(`Delete “${task.title}”?`))action(async()=>{await api(`/api/tasks/${task.id}`,'DELETE');await refresh();});};actions.append(edit,del);row.append(check,content,node('span',`priority ${task.priority}`,task.priority),actions);return row;
}
function tasksInto(id,tasks){$(id).replaceChildren(...(tasks.length?tasks.map(taskRow):[node('p','empty','All clear. No tasks here.')]));}
function projectCards(id){$(id).replaceChildren(...state.projects.map((project,index)=>{const tasks=state.tasks.filter(t=>t.project===project),done=tasks.filter(t=>t.completed).length,card=node('article','project-card');card.append(node('div','project-icon',['◇','◈','⌘'][index]),node('h3','',project),node('p','',`${tasks.length-done} open · ${done} completed`));const bar=node('div','progress'),fill=node('span');fill.style.width=`${tasks.length?done/tasks.length*100:0}%`;bar.append(fill);const link=node('button','text-button','View tasks ↗');link.onclick=()=>{$('project-filter').value=project;renderProjectTasks();navigate('projects');};card.append(bar,link);return card;}));}
function renderProjectTasks(){tasksInto('project-tasks',state.tasks.filter(t=>t.project===$('project-filter').value));}
function renderTasks(){const filter=$('task-filter').value;tasksInto('task-list',state.tasks.filter(t=>filter==='all'||(filter==='open'?!t.completed:t.completed)));}
function render(){
 const open=state.tasks.filter(t=>!t.completed), high=open.filter(t=>t.priority==='High'), due=open.filter(t=>t.due===today()), overdue=open.filter(t=>t.due<today());
 $('greeting').textContent=`Welcome back, ${state.settings.name}. Let’s make progress.`;
 $('open-count').textContent=open.length; $('priority-count').textContent=high.length;$('due-count').textContent=due.length;$('done-count').textContent=state.tasks.length-open.length;
 $('briefing-text').textContent=`You have ${open.length} open tasks, with ${due.length} due today and ${overdue.length} overdue. ${high.length} are high priority. ${open.length?'Start with your closest deadline, then make room for your next priority.':'Your queue is clear. Add a task to plan your next step.'}`;
 tasksInto('focus-list',[...open].sort((a,b)=>Number(b.priority==='High')-Number(a.priority==='High')||a.due.localeCompare(b.due)).slice(0,3));
 $('deadlines').replaceChildren(...(open.length?open.slice(0,3).map(t=>{const row=node('div','deadline'),box=node('div','date-box',String(new Date(t.due+'T12:00:00').getDate()));box.append(node('small','',new Date(t.due+'T12:00:00').toLocaleDateString('en-AU',{month:'short'})));const content=node('div');content.append(node('p','',t.title),node('small','',`${t.project}${t.due<today()?' · Overdue':''}`));row.append(box,content);return row;}):[node('p','empty','No upcoming deadlines.')]));
 for(const id of ['task-project','project-filter']){const selection=$(id).value;$(id).replaceChildren(...state.projects.map(p=>{const o=node('option','',p);o.value=p;return o;}));if(state.projects.includes(selection))$(id).value=selection;}
 projectCards('project-list');renderTasks();renderProjectTasks();tasksInto('university-tasks',state.tasks.filter(t=>t.project==='University'));
 $('messages').replaceChildren(...state.messages.map(m=>{const bubble=node('div',`message ${m.role}`);bubble.append(node('small','',m.role==='user'?`YOU · ${(m.channel||'desktop').toUpperCase()}`:m.source==='openai'?'JARVIS · OPENAI':m.source==='local'?'JARVIS · LOCAL CONFIRMATION':'JARVIS · LEGACY / LOCAL MESSAGE'),document.createTextNode(`[${m.channel||'desktop'}] ${m.content}`));return bubble;}));
 $('messages').scrollTop=$('messages').scrollHeight;
 renderMemory(); renderAIStatus();window.JarvisHUD.render(state);
 if(document.activeElement!==$('display-name'))$('display-name').value=state.settings.name;
}
function openTask(task=null){window.JarvisHUD.pause();editing=task; $('dialog-title').textContent=task?'Edit task':'New task';$('task-title').value=task?.title||'';$('task-due').value=task?.due||today();$('task-priority').value=task?.priority||'Medium';$('task-project').value=task?.project||state.projects[0];$('form-error').textContent='';$('task-dialog').showModal();}
document.querySelectorAll('.new-task').forEach(b=>b.onclick=()=>openTask());$('close-dialog').onclick=()=>$('task-dialog').close();
$('new-uni-task').onclick=()=>{openTask();$('task-project').value='University';};
$('task-form').onsubmit=async event=>{event.preventDefault();$('save-task').disabled=true;try{await api(editing?`/api/tasks/${editing.id}`:'/api/tasks',editing?'PUT':'POST',{title:$('task-title').value,due:$('task-due').value,priority:$('task-priority').value,project:$('task-project').value,completed:Boolean(editing?.completed)});$('task-dialog').close();await refresh();}catch(error){$('form-error').textContent=error.message;}finally{$('save-task').disabled=false;}};
$('task-filter').onchange=renderTasks;$('project-filter').onchange=renderProjectTasks;
let sendingChat = false;
function renderAIStatus(){
 const ai=state.ai;
 const text=ai.error||`${ai.configured?'API key configured (connection not checked on startup)':'API key missing — see README.md to enable AI'} · ${ai.model} · ${ai.attempts_today}/${ai.daily_limit} local request attempts today`;
 $('ai-status').textContent=text; $('settings-ai-status').textContent=text;
}
function renderMemory(){
 $('memory-count').textContent=`${state.memories.length} SAVED`;
 $('memory-list').replaceChildren(...(state.memories.length?state.memories.map(memory=>{
  const row=node('div','memory-row'),detail=node('div');
  detail.append(node('span','tag',memory.category.toUpperCase()),node('p','memory-text',memory.content),node('small','task-meta',`Saved ${memory.created_at} UTC`));
  const remove=node('button','','Delete');remove.setAttribute('aria-label',`Delete memory: ${memory.content}`);
  remove.onclick=()=>{if(confirm('Delete this saved memory? Earlier chat will no longer be sent as AI context, but remains visible in history.'))action(async()=>{await api(`/api/memories/${memory.id}`,'DELETE');await refresh();notify('Memory deleted. Earlier conversation is now excluded from AI context.');});};
  const edit=node('button','','Edit');edit.onclick=()=>{const content=prompt('Edit saved memory:',memory.content);if(content!==null)action(async()=>{await api(`/api/memories/${memory.id}`,'PUT',{content,category:memory.category});await refresh();});};row.append(detail,edit,remove);return row;
 }):[node('p','empty','No saved memories. Add a fact above or use /remember in chat.')]));
}
document.querySelectorAll('[data-prompt]').forEach(button=>button.onclick=()=>{$('command-input').value=button.dataset.prompt;$('command-input').focus();});
$('memory-form').onsubmit=event=>{event.preventDefault();action(async()=>{
 $('save-memory').disabled=true;
 try{await api('/api/memories','POST',{category:$('memory-category').value,content:$('memory-content').value});$('memory-content').value='';await refresh();notify('Memory saved locally. It will be included in future AI messages.');}finally{$('save-memory').disabled=false;}
});};
function localCommand(content){
 const command=content.trim().replace(/^jarvis[, ]+/i,'').trim().toLowerCase();
 const aliases={'/tasks':'tasks','show tasks':'tasks','open tasks':'tasks','/briefing':'briefing','daily briefing':'briefing','show briefing':'briefing','/memory':'memory','open memory':'memory','/projects':'projects','/university':'university','/work':'work','/reminders':'reminders','/settings':'settings','/history':'chat','/planning':'planning','/computer':'autonomy','/phone':'communications'};
 if(aliases[command]){navigate(aliases[command]);return `${panelNames[aliases[command]]} opened. This command ran locally.`;}
 if(command==='/help')return 'Local commands: /tasks, /university, /work, /projects, /briefing, /reminders, /history, /memory, /settings. /remember saves an explicit fact. Computer controls: open Spotify; next song; set volume to 40 percent; search the web for a topic; open an approved name. Apps/files/searches need confirm action. Playback/volume are immediate when enabled. Hands-free mode sends recognised phrases automatically using your paid chat API.';
 if(command==='what time is it' || command==='what time is it?')return window.JarvisHUD.clockText();
 if(command.startsWith('/') && !command.startsWith('/remember ') && command!=='/remember')return 'Unknown local command. Type /help to see the available commands.';
 return null;
}
async function sendMessage(input){
 if(sendingChat)return;
 const content=input.value.trim();if(!content)return;
 window.JarvisHUD.pause();
 const localReply=localCommand(content);
 if(localReply){window.JarvisHUD.exchange(content,localReply);input.value='';$('home-status').textContent='Local command · no API request.';window.JarvisHUD.localReply();return;}
 sendingChat=true;
 for(const id of ['send-chat','send-command'])$(id).disabled=true;
 for(const id of ['chat-input','command-input'])$(id).readOnly=true;
 window.JarvisHUD.busy(true);
 const localMemory=content.toLowerCase()==='/remember'||content.toLowerCase().startsWith('/remember ');
 const pending=localMemory?'Saving explicit memory locally…':'Processing your request… AI calls have a 40-second timeout; no automatic retries';
 $('chat-status').textContent=pending;$('home-status').textContent=pending;
 window.JarvisHUD.exchange(content,pending);
 let success=null, failure=null, replyReady=false;
 try{
  const result=await api('/api/chat','POST',{content,action_id:window.JarvisComputer.pendingId});
  success=result;
  input.value='';
  // A saved exchange remains successful even if the following state refresh fails.
  try{
   await refresh();
   const reply=state.messages.filter(message=>message.role==='assistant').at(-1);
   if(reply){window.JarvisHUD.exchange(content,reply.content);replyReady=true;}
  }catch{window.JarvisHUD.exchange(content,'Your message was saved. Refresh the page to read the reply in History.');notify('Your message was saved, but the display could not refresh. Refresh the page to see it.');}
  $('chat-status').textContent=result.memory_saved?'Memory saved locally.':result.local?'Local action response saved.':'Reply saved in local history.';
  $('home-status').textContent=$('chat-status').textContent;
 }catch(error){
  failure=error;
  $('chat-status').textContent=error.message;$('home-status').textContent=error.message;
  try{const result=await api('/api/state');state.ai=result.ai;window.JarvisHUD.backend(true);renderAIStatus();}catch{window.JarvisHUD.backend(false);}
 }finally{
  sendingChat=false;window.JarvisHUD.busy(false);
  for(const id of ['send-chat','send-command'])$(id).disabled=false;
  for(const id of ['chat-input','command-input'])$(id).readOnly=false;
 }
 if(failure)window.JarvisHUD.error(failure.message,!localMemory);
 else if(success)window.JarvisHUD.success(!success.memory_saved&&!success.local,replyReady);
 window.JarvisHUD.renderAI(state.ai);
}
$('chat-form').onsubmit=event=>{event.preventDefault();action(()=>sendMessage($('chat-input')));};
$('command-form').onsubmit=event=>{event.preventDefault();action(()=>sendMessage($('command-input')));};
$('settings-form').onsubmit=event=>{event.preventDefault();action(async()=>{await api('/api/settings','PUT',{name:$('display-name').value});await refresh();notify('Settings saved on this computer.');});};
window.JarvisUpgrade.init({api,action,notify,command:content=>{if(sendingChat)return;$('command-input').value=content;action(()=>sendMessage($('command-input')));}});
window.JarvisComputer.init({api,action,notify,command:content=>{if(sendingChat)return;$('command-input').value=content;action(()=>sendMessage($('command-input')));}});
window.addEventListener('jarvis-voice-submit',event=>{if(sendingChat)return;$('command-input').value=event.detail;action(()=>sendMessage($('command-input')));});
window.addEventListener('jarvis-day-change',()=>action(refresh));
window.addEventListener('jarvis-data-change',()=>action(refresh));
document.addEventListener('visibilitychange',()=>{if(!document.hidden)action(refresh);});
action(refresh);
