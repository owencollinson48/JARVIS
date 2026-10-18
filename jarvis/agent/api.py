"""Local owner controls for agent policy, approvals, current jobs and inspectable context."""
import json
import secrets
import time
from flask import Blueprint,current_app,jsonify,request,send_file
from . import policy,jobs,screen
from .. import ai,windows

bp=Blueprint('agent',__name__,url_prefix='/api/agent')


def body():
    data=request.get_json(silent=True)
    if not isinstance(data,dict):raise ValueError('Send a JSON object.')
    return data


def job_view(row):
    item={k:row[k] for k in ('id','goal','channel','status','summary','current_tool','rounds','tool_count','created','updated')}
    item['pending']=json.loads(row['pending']) if row['pending'] and row['status']=='waiting_approval' else None
    return item


@bp.get('/state')
def state():
    with policy.connect() as db:
        cfg=policy.config(db)
        return jsonify(policy=cfg,windows=windows.supported(),ai=ai.status(db),
                       jobs=[job_view(r) for r in db.execute('SELECT * FROM agent_jobs ORDER BY created DESC LIMIT 40')],
                       context={r['key']:json.loads(r['value']) for r in db.execute('SELECT * FROM agent_context')},
                       revisions=[dict(r) for r in db.execute('SELECT id,root,path,kind,status,created FROM agent_revisions ORDER BY rowid DESC LIMIT 40')],
                       transfers=[dict(r) for r in db.execute('SELECT id,operation,source_root,source,destination_root,destination,status FROM agent_transfers ORDER BY rowid DESC LIMIT 40')])


@bp.put('/settings')
def settings():
    data=body()
    for key,value in policy.DEFAULTS.items():
        if isinstance(value,bool) and type(data.get(key)) is not bool:raise ValueError('Choose every agent permission explicitly.')
    for key,low,high in [('max_rounds',1,24),('max_tools',1,60)]:
        if type(data.get(key)) is not int or not low<=data[key]<=high:raise ValueError(f'{key} must be {low}–{high}.')
    if data['enabled'] and data.get('cost_consent') is not True:raise ValueError('Accept paid tool-calling and sharing of the listed context before enabling the agent.')
    if data['enabled'] and not ai.configuration()[0]:raise ValueError('Configure OPENAI_API_KEY on the backend first.')
    if data['account_access'] and not windows.supported():raise ValueError('Full account drive access is a Windows-only option.')
    # Changing any authority cancels old work before it can consume new permissions.
    jobs.cancel()
    with policy.connect() as db:db.execute("INSERT INTO settings VALUES('agent_policy',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps({k:data[k] for k in policy.DEFAULTS}),))
    return jsonify(ok=True)


@bp.post('/jobs')
def create_job():
    identifier=jobs.submit(body().get('goal'))
    return jsonify(id=identifier,status='queued'),202


@bp.get('/jobs/<identifier>')
def get_job(identifier):
    with policy.connect() as db:
        row=db.execute('SELECT * FROM agent_jobs WHERE id=?',(identifier,)).fetchone()
        if not row:return jsonify(error='Task not found.'),404
        result=job_view(row)
        result['events']=[dict(r) for r in db.execute('SELECT tool,status,args,result,created FROM agent_events WHERE job=? ORDER BY id',(identifier,))]
    return jsonify(result)


@bp.post('/jobs/<identifier>/approve')
def approve(identifier):
    data=body()
    with policy.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute("SELECT * FROM agent_jobs WHERE id=? AND status='waiting_approval'",(identifier,)).fetchone()
        if not row:return jsonify(error='Approval is no longer pending.'),409
        pending=json.loads(row['pending'])
        if pending.get('authority')!=policy.authority(db):return jsonify(error='Permissions or approved paths changed. Cancel and request the task again.'),409
        if not isinstance(data.get('nonce'),str) or not secrets.compare_digest(data['nonce'],pending['nonce']):return jsonify(error='Approval does not match this concrete request.'),409
        if time.time()-pending['created']>300:return jsonify(error='Approval expired. Cancel this task and request it again.'),409
        if data.get('reviewed') is not True:raise ValueError('Review the exact action, code/data and destination before approving.')
        state=json.loads(row['state']);state['approval_level']=max(state.get('approval_level',0),pending['level'])
        if pending.get('preview'):state['prepared']=pending['preview']
        db.execute("UPDATE agent_jobs SET state=?,pending=NULL,status='queued',updated=? WHERE id=?",(json.dumps(state),time.time(),identifier))
    jobs.enqueue(current_app._get_current_object(),identifier)
    return jsonify(ok=True),202


@bp.post('/jobs/<identifier>/cancel')
def cancel(identifier):return jsonify(cancelled=jobs.cancel(identifier))


@bp.delete('/jobs/<identifier>')
def delete(identifier):
    with policy.connect() as db:
        row=db.execute('SELECT status FROM agent_jobs WHERE id=?',(identifier,)).fetchone()
        if not row:return jsonify(error='Task not found.'),404
        if row[0] not in jobs.TERMINAL:return jsonify(error='Cancel the active task before deleting its history.'),409
    jobs.cleanup_images(identifier)
    with policy.connect() as db:db.execute('DELETE FROM agent_events WHERE job=?',(identifier,));db.execute('DELETE FROM agent_jobs WHERE id=?',(identifier,))
    return jsonify(ok=True)


@bp.delete('/context')
def clear_context():
    jobs.cancel()
    with policy.connect() as db:
        db.execute('DELETE FROM agent_context')
        cutoff=db.execute('SELECT coalesce(max(id),0) FROM messages').fetchone()[0]
        db.execute("INSERT INTO settings VALUES('ai_history_after',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(cutoff),))
    return jsonify(ok=True)


@bp.get('/jobs/<identifier>/screen')
def screenshot(identifier):
    with policy.connect() as db:row=db.execute("SELECT pending FROM agent_jobs WHERE id=? AND status='waiting_approval'",(identifier,)).fetchone()
    pending=json.loads(row[0]) if row and row[0] else {}
    preview=pending.get('preview')
    if not preview or not jobs.re_token(preview.get('token')):return jsonify(error='No pending screen preview.'),404
    path=screen.folder()/preview['token']
    if not path.is_file():return jsonify(error='Screen preview expired.'),404
    response=send_file(path,mimetype='image/png');response.headers['Cache-Control']='no-store';return response
