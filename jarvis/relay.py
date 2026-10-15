"""Twilio ConversationRelay: authenticated WSS, streaming replies and interruption handling."""
import json
import threading
import time
from flask import current_app,request
from flask_sock import Sock
from openai import OpenAI
from . import communications as comm,planning,ai


def stream_reply(content,cancelled):
    if cancelled():return
    with comm.connect() as db:
        planned=planning.task_command(db,content,'phone')
        if planned:
            db.executemany('INSERT INTO messages(role,content,source,channel) VALUES(?,?,?,?)',[('user',content,'local','phone'),('assistant',planned['reply'],'local','phone')])
    if planned:
        yield planned['reply'];return
    key,model,limit=ai.configuration()
    if not key:yield 'AI is not configured. Please check the desktop.';return
    with comm.connect() as db:snapshot,history=ai.context(db);ai.reserve_attempt(db,limit)
    answer=[]
    with OpenAI(api_key=key,base_url='https://api.openai.com/v1',timeout=40,max_retries=0) as client:
        with client.responses.stream(model=model,instructions=ai.INSTRUCTIONS+' This is a phone call. Use short spoken answers.',input=[{'role':'developer','content':json.dumps(snapshot)},*history,{'role':'user','content':content}],max_output_tokens=500,store=False) as stream:
            for event in stream:
                if cancelled():return
                if event.type=='response.output_text.delta':answer.append(event.delta);yield event.delta
    if not cancelled():
        with comm.connect() as db:db.executemany('INSERT INTO messages(role,content,source,channel) VALUES(?,?,?,?)',[('user',content,'openai','phone'),('assistant',''.join(answer),'openai','phone')])


def serve(ws,app):
    state={'generation':0,'sid':None,'turns':0};lock=threading.Lock();started=time.monotonic()
    def send(data):
        with lock:ws.send(json.dumps(data))
    def respond(text,generation):
        with app.app_context():
            try:
                with comm.connect() as db:allowed=comm.config(db)['calls']
                if generation!=state['generation'] or not allowed:return
                for chunk in stream_reply(text,lambda:generation!=state['generation']):
                    with comm.connect() as db:allowed=comm.config(db)['calls']
                    if generation!=state['generation'] or not allowed:return
                    send(dict(type='text',token=chunk,last=False,interruptible=True,preemptible=True))
                if generation==state['generation']:send(dict(type='text',token='',last=True,interruptible=True))
            except Exception:
                if generation==state['generation']:
                    try:send(dict(type='text',token='The service is unavailable or its limit was reached. Please check the desktop.',last=True))
                    except Exception:pass
    try:
        while time.monotonic()-started<300:
            raw=ws.receive(timeout=20)
            if raw is None:break
            if len(raw)>16000:break
            event=json.loads(raw);kind=event.get('type')
            if kind=='setup':
                values=comm.provider()
                with app.app_context(),comm.connect() as db:
                    cfg=comm.config(db);known=db.execute("SELECT 1 FROM communication_jobs WHERE provider_sid=? AND channel='call' AND approved=1",(event.get('callSid'),)).fetchone()
                if not known or not cfg['calls'] or event.get('to')!=values['TWILIO_ALLOWED_NUMBER']:break
                state['sid']=event['callSid']
            elif not state['sid']:break
            elif kind=='interrupt':state['generation']+=1
            elif kind=='prompt' and event.get('last') is True:
                with app.app_context(),comm.connect() as db:allowed=comm.config(db)['calls']
                if not allowed:send({'type':'end'});break
                text=event.get('voicePrompt','').strip()
                if not 1<=len(text)<=2000:continue
                if text.lower().rstrip('.!?') in ('goodbye','end the call','hang up','stop calling'):
                    send({'type':'end'});break
                state['turns']+=1
                if state['turns']>10:send({'type':'end'});break
                state['generation']+=1
                threading.Thread(target=respond,args=(text,state['generation']),daemon=True).start()
            elif kind=='error':break
    except Exception:pass
    finally:
        state['generation']+=1
        ws.close()


def register(app):
    sock=Sock(app)
    @sock.route('/telephony/relay')
    def relay_socket(ws):serve(ws,current_app._get_current_object())
