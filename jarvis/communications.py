"""Opt-in Twilio SMS/calls. Fixed recipient, signed callbacks, quotas and no retries."""
import json
import os
import re
import secrets
import time
import threading
from datetime import datetime,timedelta,timezone
from urllib.parse import urlparse
from flask import Blueprint,current_app,jsonify,request,Response
from twilio.rest import Client
from twilio.http.http_client import TwilioHttpClient
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse
from . import storage,planning,ai

bp=Blueprint('communications',__name__,url_prefix='/api/communications')
public=Blueprint('telephony',__name__,url_prefix='/telephony')
DEFAULTS=dict(sms=False,calls=False,recipient_consent=False,sms_limit=5,call_limit=2,call_seconds=120,categories=[])
NAMES=('TWILIO_ACCOUNT_SID','TWILIO_AUTH_TOKEN','TWILIO_FROM_NUMBER','TWILIO_ALLOWED_NUMBER','JARVIS_PUBLIC_URL')


def connect():return storage.connect(current_app.config['DATABASE'])


def config(db):
    row=db.execute("SELECT value FROM settings WHERE key='communication_config'").fetchone()
    return {**DEFAULTS,**(json.loads(row[0]) if row else {})}


def provider():
    values={name:os.environ.get(name,'').strip() for name in NAMES}
    if any(not value for value in values.values()):raise ValueError('Configure Twilio credentials, both phone numbers and JARVIS_PUBLIC_URL in backend environment variables. See docs/COMMUNICATIONS.md.')
    for name in ('TWILIO_FROM_NUMBER','TWILIO_ALLOWED_NUMBER'):
        if not re.fullmatch(r'\+[1-9]\d{6,14}',values[name]):raise ValueError('Phone variables must use E.164 format, such as + followed by country code and number.')
    url=urlparse(values['JARVIS_PUBLIC_URL'])
    if url.scheme!='https' or not url.hostname or url.hostname in ('localhost','127.0.0.1') or url.username or url.password or url.path not in ('','/') or url.query or url.fragment:raise ValueError('JARVIS_PUBLIC_URL must be a public HTTPS origin with no path or credentials.')
    values['JARVIS_PUBLIC_URL']=values['JARVIS_PUBLIC_URL'].rstrip('/')
    return values


def client(values):return Client(values['TWILIO_ACCOUNT_SID'],values['TWILIO_AUTH_TOKEN'],http_client=TwilioHttpClient(timeout=15,max_retries=0))


def status(db):
    try:provider();ready=True;error=None
    except ValueError as exc:ready=False;error=str(exc)
    last=db.execute("SELECT value FROM settings WHERE key='worker_last'").fetchone()
    return dict(config=config(db),configured=ready,error=error,last_worker=last[0] if last else None,
                variables={name:bool(os.environ.get(name)) for name in NAMES},
                jobs=[dict(row) for row in db.execute('SELECT id,channel,body,due,status,provider_sid,result,approved FROM communication_jobs ORDER BY created DESC LIMIT 60')])


def validate_signature():
    try:values=provider()
    except ValueError:return Response('Telephony is not configured.',503)
    url=values['JARVIS_PUBLIC_URL']+request.path
    if request.query_string:url+='?'+request.query_string.decode('ascii')
    if not RequestValidator(values['TWILIO_AUTH_TOKEN']).validate(url,request.form,request.headers.get('X-Twilio-Signature','')):return Response('Invalid provider signature.',403)
    if request.form.get('AccountSid') and request.form['AccountSid']!=values['TWILIO_ACCOUNT_SID']:return Response('Account mismatch.',403)
    return None


def reserve(db,channel,limit):
    day=planning.now_local(db).date().isoformat()
    db.execute('INSERT OR IGNORE INTO communication_usage VALUES(?,?,0)',(day,channel))
    if not db.execute('UPDATE communication_usage SET attempts=attempts+1 WHERE day=? AND channel=? AND attempts<?',(day,channel,limit)).rowcount:raise ValueError('The local daily communication limit is reached. No automatic retry will be made.')


def sms_text(body):
    # At most 60 UTF-16 code units: one Unicode SMS segment, even with astral characters.
    value=body.strip()
    if len(value.encode('utf-16-le'))//2<=60:return value
    value=value[:57]
    while len((value+'...').encode('utf-16-le'))//2>60:value=value[:-1]
    return value+'...'


def create_job(db,channel,body,due,approved=False,task_id=None,identifier=None):
    identifier=identifier or secrets.token_urlsafe(20)
    db.execute('INSERT OR IGNORE INTO communication_jobs(id,channel,body,task_id,due,status,created,approved) VALUES(?,?,?,?,?,?,?,?)',
               (identifier,channel,sms_text(body) if channel=='sms' else body[:500],task_id,due,'pending' if approved else 'draft',datetime.now(timezone.utc).isoformat(),int(approved)))
    return identifier



def notice_current(db,row):
    if row['task_id'] is not None:
        task=db.execute('SELECT due,completed FROM tasks WHERE id=?',(row['task_id'],)).fetchone()
        return bool(task and not task['completed'] and row['dedupe'].split(':')[2]==task['due'])
    if row['category'] in ('work','important'):
        current=planning.brief(db)
        if row['category']=='work':
            return any(f'shift:{e["id"]}:{e["start"]}'==row['dedupe'] for e in current['events'] if e['kind']=='work')
        import hashlib
        return any('conflict:'+hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest()==row['dedupe'] for c in current['conflicts'])
    return True


def dispatch(identifier):
    values=provider()
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        cfg=config(db);row=db.execute('SELECT * FROM communication_jobs WHERE id=?',(identifier,)).fetchone()
        if not row or row['status']!='pending' or not row['approved']:return False
        if not cfg.get(row['channel']=='sms' and 'sms' or 'calls') or not cfg['recipient_consent']:raise ValueError('Communication or recipient consent is disabled.')
        if planning.quiet(db):return False
        due=datetime.fromisoformat(row['due']);now=datetime.now(timezone.utc)
        if due>now:return False
        if now-due>timedelta(hours=2):
            db.execute("UPDATE communication_jobs SET status='missed',result='Scheduled window missed; not sent late.' WHERE id=?",(identifier,));return False
        if identifier.startswith('notice-'):
            notice=db.execute('SELECT * FROM notices WHERE id=?',(identifier.removeprefix('notice-'),)).fetchone()
            if not notice or not notice_current(db,notice):
                db.execute("UPDATE communication_jobs SET status='cancelled',result='Saved task/schedule changed before dispatch.' WHERE id=?",(identifier,));return False
        if not row['quota_reserved']:reserve(db,row['channel'],cfg['sms_limit'] if row['channel']=='sms' else cfg['call_limit'])
        db.execute("UPDATE communication_jobs SET status='sending',dispatch_started=? WHERE id=?",(time.time(),identifier))
        job=dict(row)
    try:
        api=client(values);base=values['JARVIS_PUBLIC_URL']
        if job['channel']=='sms':
            sent=api.messages.create(to=values['TWILIO_ALLOWED_NUMBER'],from_=values['TWILIO_FROM_NUMBER'],body=job['body'],status_callback=base+'/telephony/status')
        else:
            sent=api.calls.create(to=values['TWILIO_ALLOWED_NUMBER'],from_=values['TWILIO_FROM_NUMBER'],url=base+'/telephony/voice',status_callback=base+'/telephony/status',status_callback_event=['initiated','ringing','answered','completed'],time_limit=cfg['call_seconds'],record=False)
        with connect() as db:
            db.execute("UPDATE communication_jobs SET provider_sid=?,status='queued',result='Provider accepted request; delivery/answer is not confirmed.' WHERE id=? AND status='sending'",(sent.sid,identifier))
            recent=[r[0] for r in db.execute("SELECT DISTINCT task_id FROM communication_jobs WHERE provider_sid IS NOT NULL AND created>? AND task_id IS NOT NULL",((datetime.now(timezone.utc)-timedelta(hours=24)).isoformat(),))]
            binding=job['task_id'] if job['task_id'] and len(recent)<=1 else None
            db.execute("INSERT INTO channel_context VALUES('owner',?) ON CONFLICT(channel) DO UPDATE SET task_id=excluded.task_id",(binding,))
        return True
    except Exception:
        # A timeout can follow acceptance. Never retry an uncertain SMS or call automatically.
        with connect() as db:db.execute("UPDATE communication_jobs SET status='unknown',result='Provider dispatch failed or timed out. Outcome uncertain; not retried. Check Twilio logs.' WHERE id=? AND status='sending'",(identifier,))
        return False


def worker():
    from . import realtime
    with connect() as db:expired=[r[0] for r in db.execute("SELECT id FROM realtime_sessions WHERE status IN ('active','stop-failed') AND started<?",(time.time()-180,))]
    for identifier in expired:realtime.end_session(current_app.config['DATABASE'],identifier)
    with connect() as db:
        planning.tick(db);cfg=config(db)
        if cfg['sms'] and cfg['recipient_consent']:
            for row in db.execute('SELECT * FROM notices WHERE created>?',( (datetime.now(timezone.utc)-timedelta(hours=2)).isoformat(),)).fetchall():
                if row['category'] in cfg['categories'] and notice_current(db,row):create_job(db,'sms',row['body'],datetime.now(timezone.utc).isoformat(),True,row['task_id'],f'notice-{row["id"]}')
        ids=[row[0] for row in db.execute("SELECT id FROM communication_jobs WHERE status='pending' AND approved=1 ORDER BY due LIMIT 20")]
    for identifier in ids:
        try:dispatch(identifier)
        except ValueError:continue
    with connect() as db:db.execute("INSERT INTO settings VALUES('worker_last',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(datetime.now(timezone.utc).isoformat(),))


@bp.get('/state')
def get_state():
    with connect() as db:return jsonify(status(db))


@bp.put('/settings')
def settings():
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or any(type(data.get(k)) is not bool for k in ('sms','calls','recipient_consent')):raise ValueError('Choose channels and explicit recipient consent.')
    for key,low,high in [('sms_limit',0,20),('call_limit',0,5),('call_seconds',30,300)]:
        if type(data.get(key)) is not int or not low<=data[key]<=high:raise ValueError(f'{key} must be {low}–{high}.')
    if not isinstance(data.get('categories'),list) or any(c not in ('deadlines','work','morning','evening','important') for c in data['categories']):raise ValueError('Choose supported notification categories.')
    if data['sms'] or data['calls']:
        provider()
        if not data['recipient_consent']:raise ValueError('Confirm your recipient number is verified in Twilio and that you consent to automated contact.')
    with connect() as db:
        db.execute("INSERT INTO settings VALUES('communication_config',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps({k:data[k] for k in DEFAULTS}),))
        if not data['sms']:db.execute("UPDATE communication_jobs SET status='cancelled' WHERE channel='sms' AND status IN ('draft','pending')")
        if not data['calls']:db.execute("UPDATE communication_jobs SET status='cancelled' WHERE channel='call' AND status IN ('draft','pending')")
    return jsonify(ok=True)


@bp.post('/jobs')
def draft_job():
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or data.get('channel') not in ('sms','call') or not isinstance(data.get('body'),str) or not 1<=len(data['body'].strip())<=500:raise ValueError('Choose SMS/call and enter 1–500 characters.')
    with connect() as db:
        due=planning.local_datetime(data['due'],planning.config(db)['timezone']) if data.get('due') else datetime.now(timezone.utc)
        if due<datetime.now(timezone.utc)-timedelta(minutes=1):raise ValueError('Choose a future schedule time.')
        identifier=create_job(db,data['channel'],data['body'],due.isoformat())
    return jsonify(id=identifier),201


@bp.post('/jobs/<identifier>/approve')
def approve(identifier):
    provider()
    with connect() as db:
        cfg=config(db);row=db.execute('SELECT channel FROM communication_jobs WHERE id=? AND status=\'draft\'',(identifier,)).fetchone()
        if not row:return jsonify(error='Draft not found or already approved.'),409
        if not cfg['recipient_consent'] or not cfg['sms' if row[0]=='sms' else 'calls']:raise ValueError('Enable the channel and confirm recipient consent first.')
        db.execute("UPDATE communication_jobs SET approved=1,status='pending' WHERE id=? AND status='draft'",(identifier,))
    dispatch(identifier)
    return jsonify(ok=True)


@bp.delete('/jobs/<identifier>')
def cancel(identifier):
    with connect() as db:
        if not db.execute("UPDATE communication_jobs SET status='cancelled' WHERE id=? AND status IN ('draft','pending')",(identifier,)).rowcount:return jsonify(error='Job is no longer cancellable here; use Emergency stop for an active call.'),409
    return jsonify(ok=True)


def remote_reply(content,channel):
    """Same owner database; no remote computer execution or inferred task mutation."""
    with connect() as db:
        planned=planning.task_command(db,content,channel)
        if planned:
            db.executemany('INSERT INTO messages(role,content,source,channel) VALUES(?,?,?,?)',[('user',content,'local',channel),('assistant',planned['reply'],'local',channel)])
            return planned['reply']
    key,model,limit=ai.configuration()
    source='openai'
    try:
        if not key:raise ai.AssistantError('AI is not configured.')
        with connect() as db:snapshot,history=ai.context(db);ai.reserve_attempt(db,limit)
        reply=ai.answer(content,snapshot,history,key,model)
    except ai.AssistantError:
        source='local';reply='The AI service is unavailable or its limit was reached. Please check the desktop status.'
    with connect() as db:db.executemany('INSERT INTO messages(role,content,source,channel) VALUES(?,?,?,?)',[('user',content,source,channel),('assistant',reply,source,channel)])
    return reply


def reply_in_background(app,sid,body):
    # Acknowledge the webhook immediately: provider HTTP deadlines are shorter than AI timeouts.
    # The receipt/quota claim is durable before starting; uncertain outcomes are never replayed.
    with app.app_context():
        try:
            response=remote_reply(body,'sms')
            with connect() as db:
                identifier=create_job(db,'sms',response,datetime.now(timezone.utc).isoformat(),True,identifier='reply-'+sid)
                db.execute('UPDATE communication_jobs SET quota_reserved=1 WHERE id=?',(identifier,))
            dispatch(identifier)
            with connect() as db:db.execute("UPDATE webhook_receipts SET status='processed' WHERE sid=?",(sid,))
        except Exception:
            with connect() as db:db.execute("UPDATE webhook_receipts SET status='failed-no-retry' WHERE sid=?",(sid,))


@public.post('/sms')
def inbound_sms():
    values=provider();reply=MessagingResponse()
    if request.form.get('From')!=values['TWILIO_ALLOWED_NUMBER'] or request.form.get('To')!=values['TWILIO_FROM_NUMBER']:return Response(str(reply),mimetype='application/xml')
    sid=request.form.get('MessageSid','');body=request.form.get('Body','').strip()
    if not re.fullmatch(r'SM[a-zA-Z0-9]{10,64}',sid) or not 1<=len(body)<=2000:return Response(str(reply),mimetype='application/xml')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM webhook_receipts WHERE sid=?',(sid,)).fetchone():return Response(str(reply),mimetype='application/xml')
        db.execute('INSERT INTO webhook_receipts VALUES(?,?,?)',(sid,'claimed',datetime.now(timezone.utc).isoformat()))
        cfg=config(db)
        if body.lower()=='stop':
            cfg.update(sms=False,calls=False)
            db.execute("UPDATE settings SET value=? WHERE key='communication_config'",(json.dumps(cfg),))
            db.execute("UPDATE communication_jobs SET status='cancelled' WHERE status IN ('draft','pending')")
            return Response(str(reply),mimetype='application/xml')
        if not cfg['sms'] or not cfg['recipient_consent'] or planning.quiet(db):return Response(str(reply),mimetype='application/xml')
        try:reserve(db,'sms',cfg['sms_limit'])
        except ValueError:return Response(str(reply),mimetype='application/xml')
    # Explicit task commands and missing-key guidance are fast local responses.
    with connect() as db:
        planned=planning.task_command(db,body,'sms')
        if planned:db.executemany("INSERT INTO messages(role,content,source,channel) VALUES(?,?,'local','sms')",[('user',body),('assistant',planned['reply'])])
    if not planned and ai.configuration()[0]:
        threading.Thread(target=reply_in_background,args=(current_app._get_current_object(),sid,body),daemon=True).start()
        return Response(str(reply),mimetype='application/xml')
    response=sms_text(planned['reply'] if planned else remote_reply(body,'sms'))
    reply.message(response)
    with connect() as db:db.execute("UPDATE webhook_receipts SET status='responded' WHERE sid=?",(sid,))
    return Response(str(reply),mimetype='application/xml')


@public.post('/voice')
def voice_hook():
    values=provider();twiml=VoiceResponse()
    with connect() as db:
        cfg=config(db);job=db.execute("SELECT * FROM communication_jobs WHERE provider_sid=? AND channel='call'",(request.form.get('CallSid'),)).fetchone()
    if not cfg['calls'] or not job or request.form.get('To')!=values['TWILIO_ALLOWED_NUMBER'] or request.form.get('From')!=values['TWILIO_FROM_NUMBER']:
        twiml.hangup();return Response(str(twiml),mimetype='application/xml')
    twiml.connect().conversation_relay(url=values['JARVIS_PUBLIC_URL'].replace('https://','wss://',1)+'/telephony/relay',language='en-GB',tts_provider='Google',voice=os.environ.get('JARVIS_PHONE_VOICE','en-GB-Neural2-B'),welcome_greeting='This is your automated JARVIS assistant. '+job['body'],interruptible='true',welcome_greeting_interruptible='true',preemptible='true')
    twiml.hangup()
    return Response(str(twiml),mimetype='application/xml')


@public.post('/status')
def status_hook():
    values=provider();sid=request.form.get('MessageSid') or request.form.get('CallSid');status=request.form.get('MessageStatus') or request.form.get('CallStatus')
    allowed=('queued','sending','sent','delivered','undelivered','failed','initiated','ringing','in-progress','completed','busy','no-answer','canceled')
    with connect() as db:
        if status in allowed:
            db.execute("UPDATE communication_jobs SET status=?,result=? WHERE provider_sid=? AND status NOT IN ('completed','delivered','failed','undelivered')",(status,'Provider status: '+status,sid))
    return Response('',204)
