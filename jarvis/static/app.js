'use strict';
const $ = id => document.getElementById(id);
let state = {tasks: [], projects: [], messages: [], memories: [], settings: {}, ai: {}}, editing = null;
const today = () => {const d=new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;};
const dateLabel = value => new Date(`${value}T12:00:00`).toLocaleDateString(undefined,{month:'short',day:'numeric'});
function node(tag, cls, text) {const el=document.createElement(tag); if(cls)el.className=cls; if(text!==undefined)el.textContent=text; return el;}
function notify(message) {$('notice').textContent=message; $('notice').hidden=false;}
async function api(path, method='GET', data) {
 const response=await fetch(path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name="csrf-token"]').content},body:data===undefined?undefined:JSON.stringify(data)});
 let result; try {result=await response.json();} catch {throw new Error('Unexpected server response. Restart JARVIS and refresh.');}
 if(!response.ok)throw new Error(result.error||'The request failed. Please try again.'); return result;
}
async function refresh(){state=await api('/api/state'); $('connection-status').textContent='● Local data loaded'; render();}
async function action(fn){try{await fn();}catch(error){notify(error.message||'Unable to connect to JARVIS. Check that the server is running.');}}
function navigate(page){document.querySelectorAll('.page').forEach(el=>el.hidden=el.id!==page);document.querySelectorAll('nav button').forEach(el=>el.classList.toggle('active',el.dataset.page===page));$('page-label').textContent={dashboard:'Overview',tasks:'Task manager',projects:'Projects',chat:'Conversation',memory:'Saved memory',settings:'Settings'}[page];if(page==='chat')$('messages').scrollTop=$('messages').scrollHeight;}
document.querySelectorAll('[data-page]').forEach(el=>el.addEventListener('click',()=>navigate(el.dataset.page)));
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
 $('today').textContent=new Date().toLocaleDateString(undefined,{weekday:'long',day:'numeric',month:'long',year:'numeric'}).toUpperCase();
 $('greeting').textContent=`Welcome back, ${state.settings.name}. Let’s make progress.`;
 $('open-count').textContent=open.length; $('priority-count').textContent=high.length;$('due-count').textContent=due.length;$('done-count').textContent=state.tasks.length-open.length;
 $('briefing').textContent=`You have ${open.length} open tasks, with ${due.length} due today and ${overdue.length} overdue. ${high.length} are high priority. ${open.length?'Start with your closest deadline, then make room for your next priority.':'Your queue is clear. Add a task to plan your next step.'}`;
 tasksInto('focus-list',[...open].sort((a,b)=>Number(b.priority==='High')-Number(a.priority==='High')||a.due.localeCompare(b.due)).slice(0,3));
 $('deadlines').replaceChildren(...(open.length?open.slice(0,3).map(t=>{const row=node('div','deadline'),box=node('div','date-box',String(new Date(t.due+'T12:00:00').getDate()));box.append(node('small','',new Date(t.due+'T12:00:00').toLocaleDateString(undefined,{month:'short'})));const content=node('div');content.append(node('p','',t.title),node('small','',`${t.project}${t.due<today()?' · Overdue':''}`));row.append(box,content);return row;}):[node('p','empty','No upcoming deadlines.')]));
 for(const id of ['task-project','project-filter']){const selection=$(id).value;$(id).replaceChildren(...state.projects.map(p=>{const o=node('option','',p);o.value=p;return o;}));if(state.projects.includes(selection))$(id).value=selection;}
 projectCards('project-preview');projectCards('project-list');renderTasks();renderProjectTasks();
 $('messages').replaceChildren(...state.messages.map(m=>{const bubble=node('div',`message ${m.role}`);bubble.append(node('small','',m.role==='user'?'YOU':m.source==='openai'?'JARVIS · OPENAI':m.source==='local'?'JARVIS · LOCAL CONFIRMATION':'JARVIS · LEGACY / LOCAL MESSAGE'),document.createTextNode(m.content));return bubble;}));
 $('messages').scrollTop=$('messages').scrollHeight;
 renderMemory(); renderAIStatus();
 if(document.activeElement!==$('display-name'))$('display-name').value=state.settings.name;
}
function openTask(task=null){editing=task; $('dialog-title').textContent=task?'Edit task':'New task';$('task-title').value=task?.title||'';$('task-due').value=task?.due||today();$('task-priority').value=task?.priority||'Medium';$('task-project').value=task?.project||state.projects[0];$('form-error').textContent='';$('task-dialog').showModal();}
document.querySelectorAll('.new-task').forEach(b=>b.onclick=()=>openTask());$('close-dialog').onclick=()=>$('task-dialog').close();
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
  row.append(detail,remove);return row;
 }):[node('p','empty','No saved memories. Add a fact above or use /remember in chat.')]));
}
document.querySelectorAll('[data-prompt]').forEach(button=>button.onclick=()=>{$('chat-input').value=button.dataset.prompt;$('chat-input').focus();});
$('memory-form').onsubmit=event=>{event.preventDefault();action(async()=>{
 $('save-memory').disabled=true;
 try{await api('/api/memories','POST',{category:$('memory-category').value,content:$('memory-content').value});$('memory-content').value='';await refresh();notify('Memory saved locally. It will be included in future AI messages.');}finally{$('save-memory').disabled=false;}
});};
$('chat-form').onsubmit=event=>{event.preventDefault();if(sendingChat)return;
 action(async()=>{sendingChat=true;$('send-chat').disabled=true;$('chat-input').readOnly=true;
 const content=$('chat-input').value;
 $('chat-status').textContent=content.toLowerCase().startsWith('/remember ')?'Saving locally…':'Waiting for OpenAI… (up to 40 seconds; no automatic retries)';
 try{await api('/api/chat','POST',{content});$('chat-input').value='';await refresh();$('chat-status').textContent='Saved to local conversation history.';}
 catch(error){$('chat-status').textContent=error.message;try{const result=await api('/api/state');state.ai=result.ai;renderAIStatus();}catch{} }
 finally{sendingChat=false;$('send-chat').disabled=false;$('chat-input').readOnly=false;}
 });};
$('settings-form').onsubmit=event=>{event.preventDefault();action(async()=>{await api('/api/settings','PUT',{name:$('display-name').value});await refresh();notify('Settings saved on this computer.');});};
action(refresh);
