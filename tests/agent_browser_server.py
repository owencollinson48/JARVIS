"""Offline integration fixture: actual jobs/SDK/SQLite, fake model decisions and Windows IO."""
import json
import os
from pathlib import Path
from unittest.mock import patch
import httpx2 as httpx
from flask import jsonify
from openai import OpenAI
from PIL import Image
from jarvis import create_app,storage
from jarvis.agent import policy

ROOT=Path(__file__).resolve().parent.parent/'.ui-check'/os.environ.get('JARVIS_AGENT_FIXTURE_DIR','master-agent')
ROOT.mkdir(parents=True,exist_ok=True)
(ROOT/'engineering_notes.txt').write_text('Draft engineering notes.',encoding='utf-8')


def payload(outputs=None,text='Finished the offline fixture task.'):
    if outputs is None:outputs=[dict(type='message',id='m',status='completed',role='assistant',content=[dict(type='output_text',text=text,annotations=[])])]
    return dict(id='r',object='response',created_at=1,status='completed',model='gpt-4.1-mini',output=outputs)


def call(name,args):return dict(type='function_call',id='fc_'+name,call_id='call_'+name,name=name,arguments=json.dumps(args),status='completed')


def transport(request):
    body=json.loads(request.content);goal=next((m['content'] for m in reversed(body['input']) if m.get('role')=='user' and isinstance(m.get('content'),str)),'')
    calls=[m for m in body['input'] if m.get('type')=='function_call']
    if not calls:
        if 'screen' in goal.lower():result=payload([call('screen_observe',{})])
        elif 'command' in goal.lower():result=payload([call('command_execute',dict(interpreter='python',root='engineering',folder='',script='print("offline command fixture")'))])
        else:result=payload([call('files_read',dict(root='engineering',path='engineering_notes.txt'))])
    elif calls[-1]['name']=='files_read' and 'fix' in goal.lower():
        output=next(m for m in reversed(body['input']) if m.get('type')=='function_call_output')
        read=json.loads(output['output'])
        result=payload([call('files_patch',dict(root='engineering',path='engineering_notes.txt',old='Draft',new='Reviewed',version=read['version']))])
    elif calls[-1]['name']=='files_patch':result=payload(text='The engineering notes were updated and the saved bytes verified. An original backup is available.')
    elif calls[-1]['name']=='screen_observe':result=payload(text='I inspected the approved test snapshot. It is not a live desktop feed.')
    else:result=payload(text='The approved offline fixture step finished.')
    return httpx.Response(200,json=result)


def sdk(**kwargs):return OpenAI(**kwargs,http_client=httpx.Client(transport=httpx.MockTransport(transport)))


if __name__=='__main__':
    with patch.dict(os.environ,{'OPENAI_API_KEY':'offline-browser-test','OPENAI_MODEL':'gpt-4.1-mini','JARVIS_AI_DAILY_LIMIT':'100'}),patch('jarvis.agent.jobs.OpenAI',side_effect=sdk),patch('jarvis.windows.supported',return_value=True),patch('jarvis.agent.desktop.application_catalog',return_value={'spotify':None}),patch('jarvis.agent.desktop.list_windows',return_value=[]),patch('jarvis.windows.execute',return_value='TEST ONLY: Windows driver mocked.'),patch('jarvis.agent.commands.run_process',return_value=dict(exit_code=0,output='TEST ONLY: process mocked.')),patch('PIL.ImageGrab.grab',return_value=Image.new('RGB',(640,360),'navy')):
        app=create_app(ROOT/'jarvis.db')
        app.view_functions['files.locations']=lambda:jsonify(supported=False,locations=[])
        with storage.connect(app.config['DATABASE']) as db:
            db.execute("INSERT INTO settings VALUES('computer_enabled','1') ON CONFLICT(key) DO UPDATE SET value='1'")
            db.execute("INSERT INTO settings VALUES('agent_policy',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps(policy.DEFAULTS),))
            db.execute("INSERT INTO trusted_roots(alias,path,allow_read,allow_move,allow_edit) VALUES('engineering',?,1,1,1) ON CONFLICT(alias) DO UPDATE SET path=excluded.path",(str(ROOT),))
        app.run(host='127.0.0.1',port=int(os.environ.get('JARVIS_TEST_PORT','5041')),debug=False)
