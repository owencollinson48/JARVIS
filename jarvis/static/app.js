'use strict';
const $ = id => document.getElementById(id);
let state = {tasks: [], projects: [], messages: [], settings: {}}, editing = null;
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
function navigate(page){document.querySelectorAll('.page').forEach(el=>el.hidden=el.id!==page);document.querySelectorAll('nav button').forEach(el=>el.classList.toggle('active',el.dataset.page===page));$('page-label').textContent={dashboard:'Overview',tasks:'Task manager',projects:'Projects',chat:'Conversation',settings:'Settings'}[page];if(page==='chat')$('messages').scrollTop=$('messages').scrollHeight;}
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
 $('messages').replaceChildren(...state.messages.map(m=>{const bubble=node('div',`message ${m.role}`);bubble.append(node('small','',m.role==='user'?'YOU':'JARVIS · SCRIPTED DEMO'),document.createTextNode(m.content));return bubble;}));
 $('messages').scrollTop=$('messages').scrollHeight;
 if(document.activeElement!==$('display-name'))$('display-name').value=state.settings.name;
}
function openTask(task=null){editing=task; $('dialog-title').textContent=task?'Edit task':'New task';$('task-title').value=task?.title||'';$('task-due').value=task?.due||today();$('task-priority').value=task?.priority||'Medium';$('task-project').value=task?.project||state.projects[0];$('form-error').textContent='';$('task-dialog').showModal();}
document.querySelectorAll('.new-task').forEach(b=>b.onclick=()=>openTask());$('close-dialog').onclick=()=>$('task-dialog').close();
$('task-form').onsubmit=async event=>{event.preventDefault();$('save-task').disabled=true;try{await api(editing?`/api/tasks/${editing.id}`:'/api/tasks',editing?'PUT':'POST',{title:$('task-title').value,due:$('task-due').value,priority:$('task-priority').value,project:$('task-project').value,completed:Boolean(editing?.completed)});$('task-dialog').close();await refresh();}catch(error){$('form-error').textContent=error.message;}finally{$('save-task').disabled=false;}};
$('task-filter').onchange=renderTasks;$('project-filter').onchange=renderProjectTasks;
$('chat-form').onsubmit=event=>{event.preventDefault();action(async()=>{const button=event.target.querySelector('button');button.disabled=true;try{await api('/api/chat','POST',{content:$('chat-input').value});$('chat-input').value='';await refresh();}finally{button.disabled=false;}});};
$('settings-form').onsubmit=event=>{event.preventDefault();action(async()=>{await api('/api/settings','PUT',{name:$('display-name').value});await refresh();notify('Settings saved on this computer.');});};
action(refresh);
