"""Offline integration tests: no real phone, API key, audio or personal-file access."""
import json
import os
import tempfile
import time
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
from twilio.request_validator import RequestValidator
from jarvis import create_app,storage,planning,communications,workspace,relay,ai
from phone_gateway import create_gateway

ENV={'TWILIO_ACCOUNT_SID':'AC'+'a'*32,'TWILIO_AUTH_TOKEN':'offline-test-token','TWILIO_FROM_NUMBER':'+15005550006','TWILIO_ALLOWED_NUMBER':'+15005550009','JARVIS_PUBLIC_URL':'https://jarvis.example.com','OPENAI_API_KEY':'','JARVIS_REALTIME_ENABLED':'0'}

class UpgradeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.path=self.root/'jarvis.db'
  env=patch.dict(os.environ,ENV);env.start();self.addCleanup(env.stop)
  self.app=create_app(self.path);self.client=self.app.test_client();self.client.get('/')
  with self.client.session_transaction() as s:self.headers={'X-CSRF-Token':s['csrf']}
  with storage.connect(self.path) as db:db.execute("INSERT INTO settings VALUES('planner_config',?)",(json.dumps({**planning.DEFAULTS,'quiet_start':0,'quiet_end':0}),))
 def request(self,path,data=None,method='POST'):
  return self.client.open('/api/'+path,method=method,json=data,headers=self.headers)
 def cfg(self,**kwargs):
  with storage.connect(self.path) as db:db.execute("INSERT INTO settings VALUES('communication_config',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps({**communications.DEFAULTS,**kwargs}),))
 def signed(self,path,body,client=None):
  signature=RequestValidator(ENV['TWILIO_AUTH_TOKEN']).compute_signature(ENV['JARVIS_PUBLIC_URL']+path,body)
  return (client or self.client).post(path,data=body,headers={'X-Twilio-Signature':signature})
 def job(self,channel='sms',**kwargs):
  with self.app.app_context(),storage.connect(self.path) as db:return communications.create_job(db,channel,'Test approved reminder',datetime.now(timezone.utc).isoformat(),**kwargs)
 def trust(self,read=True,move=True):
  folder=self.root/'approved';folder.mkdir(exist_ok=True);(folder/'Archive').mkdir(exist_ok=True);(folder/'notes.txt').write_text('Engineering maths revision',encoding='utf-8')
  response=self.request('workspace/roots',dict(alias='study',path=str(folder),allow_read=read,allow_move=move));self.assertEqual(response.status_code,200);return folder
 def test_existing_data_persists_and_worker_start_does_not_replay(self):
  with storage.connect(self.path) as db:
   count=db.execute('SELECT count(*) FROM tasks').fetchone()[0]
   db.execute("INSERT INTO computer_actions VALUES('live','{}','test','executing',?,?,NULL)",(time.time(),time.time()+120))
  create_app(self.path)
  with storage.connect(self.path) as db:
   self.assertEqual(db.execute('SELECT count(*) FROM tasks').fetchone()[0],count);self.assertEqual(db.execute("SELECT status FROM computer_actions WHERE id='live'").fetchone()[0],'executing')
 def test_explicit_task_context_crosses_desktop_sms_and_phone(self):
  reply=self.request('chat',{'content':'Remind me to revise engineering maths tomorrow.'});self.assertEqual(reply.status_code,200);identifier=reply.json['task_id']
  with self.app.app_context():
   text=communications.remote_reply('Move it to Friday.','sms');self.assertIn(str(identifier),text)
   text=''.join(relay.stream_reply('move task '+str(identifier)+' to tomorrow',lambda:False));self.assertIn('moved',text)
  with storage.connect(self.path) as db:
   self.assertEqual({r[0] for r in db.execute("SELECT DISTINCT channel FROM messages WHERE source='local'")},{'desktop','sms','phone'})
 def test_ambiguous_pronoun_clarifies_without_changes(self):
  with storage.connect(self.path) as db:
   before=[tuple(x) for x in db.execute('SELECT * FROM tasks')];reply=planning.task_command(db,'Move it to Friday','sms');self.assertIn('Which task',reply['reply']);self.assertEqual(before,[tuple(x) for x in db.execute('SELECT * FROM tasks')])
 def test_calendar_crud_conflicts_recurrence_and_break_hours(self):
  tomorrow=(datetime.now(timezone.utc)+timedelta(days=1)).date().isoformat();until=(datetime.now(timezone.utc)+timedelta(days=30)).date().isoformat()
  data=dict(title='Saved shift',kind='work',start=tomorrow+'T10:00',end=tomorrow+'T14:00',recurrence='weekly',until_date=until,break_minutes=30)
  result=self.request('planning/events',data);self.assertEqual(result.status_code,201);identifier=result.json['id']
  data.update(title='Lecture',kind='university',start=tomorrow+'T12:00',end=tomorrow+'T13:00',break_minutes=0)
  self.assertEqual(self.request('planning/events',data).status_code,201)
  state=self.client.get('/api/planning/state').json;self.assertTrue(state['briefing']['conflicts']);self.assertGreater(len(state['briefing']['events']),2)
  data.update(title='Shift amended',kind='work');self.assertEqual(self.request('planning/events/'+str(identifier),data,'PUT').status_code,200)
  self.assertEqual(self.request('planning/events/'+str(identifier),method='DELETE').status_code,200)
 def test_dst_rejected_and_weekly_wall_clock_preserved(self):
  with self.assertRaisesRegex(ValueError,'does not exist'):planning.local_datetime('2026-03-29T01:30','Europe/London')
  with self.assertRaisesRegex(ValueError,'ambiguous'):planning.local_datetime('2026-10-25T01:30','Europe/London')
  self.assertIsNotNone(planning.local_datetime('2026-10-25T01:30+01:00','Europe/London'))
 def test_proactive_deduplicates_and_respects_quiet_hours(self):
  with self.app.app_context(),storage.connect(self.path) as db:
   planning.tick(db,True);count=db.execute('SELECT count(*) FROM notices').fetchone()[0];self.assertGreater(count,0)
   planning.tick(db,True);self.assertEqual(count,db.execute('SELECT count(*) FROM notices').fetchone()[0])
   db.execute('DELETE FROM notices')
   with patch('jarvis.planning.quiet',return_value=True):planning.tick(db,True)
   self.assertEqual(db.execute('SELECT count(*) FROM notices').fetchone()[0],0)
 def test_settings_invalid_and_events_never_fabricated(self):
  self.assertEqual(self.request('planning/settings',{**planning.DEFAULTS,'timezone':'Bad/Zone'},'PUT').status_code,400)
  self.assertEqual(self.client.get('/api/planning/state').json['events'],[])
 def test_memory_edit_updates_shared_context_and_excludes_old_chat(self):
  identifier=self.request('memories',dict(content='Old routine',category='preference')).json['id']
  with storage.connect(self.path) as db:db.execute("INSERT INTO messages(role,content,source) VALUES('user','Old routine','openai')")
  self.assertEqual(self.request('memories/'+str(identifier),dict(content='Study mornings',category='preference'),'PUT').status_code,200)
  with self.app.app_context(),storage.connect(self.path) as db:
   context,history=ai.context(db);self.assertEqual(history,[]);self.assertEqual(context['saved_memories'][0]['content'],'Study mornings')
 def test_trusted_search_read_boundary_and_explicit_external_consent(self):
  folder=self.trust();blocked=['../jarvis.db']
  try:
   (folder/'escape.txt').symlink_to(self.path);blocked.append('escape.txt')
  except OSError:
   pass  # Standard Windows accounts may lack symlink permission; traversal is still tested.
  found=self.request('workspace/search',dict(root='study',query='notes')).json;self.assertEqual(found['items'][0]['relative'],'notes.txt')
  for relative in blocked:
   self.assertEqual(self.request('workspace/read',dict(root='study',relative=relative)).status_code,400)
  self.assertIn('Engineering',self.request('workspace/read',dict(root='study',relative='notes.txt')).json['text'])
  with patch('jarvis.ai.answer') as answer:
   self.assertEqual(self.request('workspace/summarise',dict(root='study',relative='notes.txt')).status_code,400);answer.assert_not_called()
  self.assertEqual(self.request('workspace/read',dict(root='study',relative='missing.txt')).status_code,400)
 def test_no_overwrite_move_can_be_reversed(self):
  folder=self.trust()
  with self.app.app_context(),storage.connect(self.path) as db:
   workspace.move(db,dict(root='study',source='notes.txt',destination='Archive/notes.txt'));self.assertFalse((folder/'notes.txt').exists())
   workspace.move(db,dict(root='study',source='Archive/notes.txt',destination='notes.txt'));self.assertTrue((folder/'notes.txt').is_file())
   (folder/'Archive/notes.txt').write_text('keep')
   with self.assertRaises(ValueError):workspace.move(db,dict(root='study',source='notes.txt',destination='Archive/notes.txt'))
   self.assertEqual((folder/'Archive/notes.txt').read_text(),'keep')
 def test_permission_revocation_cancels_pending_and_denies_read(self):
  self.trust(read=False)
  self.assertEqual(self.request('workspace/read',dict(root='study',relative='notes.txt')).status_code,400)
  self.assertEqual(self.request('workspace/preview',dict(kind='open',root='study',relative='notes.txt')).status_code,200)
  self.trust()
  with storage.connect(self.path) as db:self.assertEqual(db.execute('SELECT status FROM computer_actions').fetchone()[0],'cancelled')
 def test_workflow_preapproval_and_version_change_cancel_preview(self):
  payload=dict(name='study mode',steps=['open Spotify','set volume to 25 percent'],preapproved=False)
  self.assertEqual(self.request('workspace/workflows',payload).status_code,200)
  with patch('jarvis.computer.windows.supported',return_value=True),patch('jarvis.computer.windows.execute',return_value='Test driver accepted.') as execute:
   self.request('computer/settings',{'enabled':True},'PUT');reply=self.request('chat',{'content':'run workflow study mode'}).json;self.assertIn('confirm',reply['reply'].lower());execute.assert_not_called()
   self.request('workspace/workflows',{**payload,'steps':['open Notepad']})
   with storage.connect(self.path) as db:self.assertEqual(db.execute("SELECT status FROM computer_actions ORDER BY created DESC LIMIT 1").fetchone()[0],'cancelled')
   self.request('workspace/workflows',{**payload,'preapproved':True});self.request('chat',{'content':'run workflow study mode'});self.assertEqual(execute.call_count,2)
 def test_emergency_stop_disables_and_cancels(self):
  self.cfg(sms=True,calls=True,recipient_consent=True);identifier=self.job(approved=True)
  result=self.request('workspace/emergency-stop',{});self.assertEqual(result.status_code,200)
  with storage.connect(self.path) as db:
   self.assertFalse(communications.config(db)['sms']);self.assertFalse(planning.config(db)['proactive']);self.assertEqual(db.execute('SELECT status FROM communication_jobs WHERE id=?',(identifier,)).fetchone()[0],'cancelled')
 def test_telephony_default_off_no_secrets_in_state_and_csrf_required(self):
  data=self.client.get('/api/communications/state').json;self.assertFalse(data['config']['sms']);self.assertNotIn(ENV['TWILIO_AUTH_TOKEN'],json.dumps(data));self.assertFalse(data['config']['calls'])
  with patch('jarvis.communications.client') as sdk:
   self.assertEqual(self.request('communications/jobs',dict(channel='sms',body='Draft only')).status_code,201);sdk.assert_not_called()
  self.assertEqual(self.client.post('/api/workspace/emergency-stop',json={}).status_code,403)
 def test_telephony_signed_webhooks_gateway_and_fixed_recipient(self):
  gateway=create_gateway(self.path).test_client()
  for path in ('/','/api/state','/api/tasks','/static/app.js'):
   self.assertEqual(gateway.get(path).status_code,404)
  self.assertEqual(gateway.post('/telephony/sms',data={}).status_code,403)
  self.cfg(sms=True,recipient_consent=True)
  body=dict(AccountSid=ENV['TWILIO_ACCOUNT_SID'],From='+15005550001',To=ENV['TWILIO_FROM_NUMBER'],MessageSid='SM'+'b'*32,Body='Remind me to test tomorrow')
  self.assertNotIn('<Message>',self.signed('/telephony/sms',body,gateway).text)
 def test_sms_dedup_shared_task_update_stop_and_single_segment(self):
  self.cfg(sms=True,calls=True,recipient_consent=True)
  body=dict(AccountSid=ENV['TWILIO_ACCOUNT_SID'],From=ENV['TWILIO_ALLOWED_NUMBER'],To=ENV['TWILIO_FROM_NUMBER'],MessageSid='SM'+'c'*32,Body='Remind me to revise maths tomorrow')
  response=self.signed('/telephony/sms',body);self.assertIn('Saved task',response.text)
  self.assertNotIn('<Message>',self.signed('/telephony/sms',body).text)
  body.update(MessageSid='SM'+'d'*32,Body='Move it to Friday');self.assertIn('moved',self.signed('/telephony/sms',body).text)
  body.update(MessageSid='SM'+'e'*32,Body='STOP');self.signed('/telephony/sms',body)
  with storage.connect(self.path) as db:self.assertFalse(communications.config(db)['calls'])
  self.assertLessEqual(len(communications.sms_text('😀'*200).encode('utf-16-le'))//2,60)
 def test_quota_dispatch_failure_unknown_no_retry_and_fixed_number(self):
  self.cfg(sms=True,recipient_consent=True,sms_limit=1);identifier=self.job(approved=True)
  fake=MagicMock();fake.messages.create.side_effect=TimeoutError()
  with self.app.app_context(),patch('jarvis.communications.client',return_value=fake):
   self.assertFalse(communications.dispatch(identifier));self.assertFalse(communications.dispatch(identifier));self.assertEqual(fake.messages.create.call_count,1)
   self.assertEqual(fake.messages.create.call_args.kwargs['to'],ENV['TWILIO_ALLOWED_NUMBER'])
   other=self.job(approved=True)
   with self.assertRaisesRegex(ValueError,'daily'):communications.dispatch(other)
  with storage.connect(self.path) as db:self.assertEqual(db.execute('SELECT status FROM communication_jobs WHERE id=?',(identifier,)).fetchone()[0],'unknown')
 def test_calls_capped_no_recording_signed_voice_and_status(self):
  self.cfg(calls=True,recipient_consent=True,call_seconds=90);identifier=self.job('call',approved=True)
  fake=MagicMock();fake.calls.create.return_value=SimpleNamespace(sid='CA'+'f'*32)
  with self.app.app_context(),patch('jarvis.communications.client',return_value=fake):self.assertTrue(communications.dispatch(identifier))
  self.assertEqual(fake.calls.create.call_args.kwargs['time_limit'],90);self.assertFalse(fake.calls.create.call_args.kwargs['record'])
  body=dict(AccountSid=ENV['TWILIO_ACCOUNT_SID'],CallSid='CA'+'f'*32,From=ENV['TWILIO_FROM_NUMBER'],To=ENV['TWILIO_ALLOWED_NUMBER'])
  response=self.signed('/telephony/voice',body);self.assertIn('ConversationRelay',response.text);self.assertIn('en-GB-Neural2-B',response.text);self.assertIn('wss://jarvis.example.com/telephony/relay',response.text)
  body.update(CallStatus='completed');self.assertEqual(self.signed('/telephony/status',body).status_code,204)
  with storage.connect(self.path) as db:self.assertEqual(db.execute('SELECT status FROM communication_jobs WHERE id=?',(identifier,)).fetchone()[0],'completed')
 def test_disabled_paid_voice_never_calls_provider(self):
  with patch('jarvis.realtime.client') as sdk:
   self.assertFalse(self.client.get('/api/realtime/state').json['enabled']);self.assertEqual(self.request('realtime/sessions',dict(sdp='v=0\r\n',paid_consent=True)).status_code,400);sdk.assert_not_called()
 def test_realtime_handshake_stays_backend_capped_and_transcripts_dedup(self):
  fake=MagicMock();fake.__enter__.return_value=fake;fake.realtime.calls.create.return_value=SimpleNamespace(text='v=0\r\nanswer',response=SimpleNamespace(headers={'location':'/v1/realtime/calls/rtc_test'}))
  with patch.dict(os.environ,{'OPENAI_API_KEY':'offline-key','JARVIS_REALTIME_ENABLED':'1'}),patch('jarvis.realtime.client',return_value=fake),patch('jarvis.realtime.threading.Timer'):
   result=self.request('realtime/sessions',dict(sdp='v=0\r\noffer',paid_consent=True));self.assertEqual(result.status_code,200);identifier=result.json['id']
   payload=dict(role='assistant',content='A thoughtful reply.',event='evt_test')
   for _ in range(2):self.assertEqual(self.request('realtime/sessions/'+identifier+'/transcript',payload).status_code,200)
   with storage.connect(self.path) as db:self.assertEqual(db.execute("SELECT count(*) FROM messages WHERE channel='voice'").fetchone()[0],1)
   self.assertEqual(self.request('realtime/sessions/'+identifier,method='DELETE').status_code,200);fake.realtime.calls.hangup.assert_called_once_with('rtc_test')
   second=self.request('realtime/sessions',dict(sdp='v=0\r\n',paid_consent=True));self.assertEqual(second.status_code,200)
   self.assertEqual(self.request('realtime/sessions',dict(sdp='v=0\r\n',paid_consent=True)).status_code,400)
 def test_research_requires_external_approval(self):
  with patch('jarvis.ai.OpenAI') as sdk:
   self.assertEqual(self.request('workspace/research',{'query':'engineering'}).status_code,400);sdk.assert_not_called()


class RealtimeSDKTests(unittest.TestCase):
 setUp=UpgradeTests.setUp
 request=UpgradeTests.request
 def test_actual_sdk_multipart_response_and_safe_tool_router(self):
  import httpx2 as httpx
  from openai import OpenAI
  requests=[]
  def transport(request):
   requests.append(request)
   return httpx.Response(201,content=b'v=0\r\nanswer',headers={'content-type':'application/sdp','location':'https://api.openai.com/v1/realtime/calls/rtc_offline'})
  def factory():return OpenAI(api_key='test-not-real',base_url='https://api.openai.com/v1',max_retries=0,http_client=httpx.Client(transport=httpx.MockTransport(transport)))
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test-not-real','JARVIS_REALTIME_ENABLED':'1'}),patch('jarvis.realtime.client',side_effect=factory),patch('jarvis.realtime.threading.Timer'):
   result=self.request('realtime/sessions',dict(sdp='v=0\r\n',paid_consent=True));self.assertEqual(result.status_code,200,result.json);identifier=result.json['id']
   self.assertEqual(str(requests[0].url),'https://api.openai.com/v1/realtime/calls');self.assertIn(b'cedar',requests[0].content);self.assertIn(b'interrupt_response',requests[0].content);self.assertIn(b'approved_local_command',requests[0].content)
   reply=self.request('realtime/sessions/'+identifier+'/command',dict(command='Remind me to revise maths tomorrow',call_id='call_test'));self.assertIn('Saved task',reply.json['reply'])
   reply=self.request('realtime/sessions/'+identifier+'/command',dict(command='Remind me to revise maths tomorrow',call_id='call_test'));self.assertIn('not repeated',reply.json['reply'])
   reply=self.request('realtime/sessions/'+identifier+'/command',dict(command='confirm action',call_id='call_confirm'));self.assertIn('on-screen',reply.json['reply'])


class DispatchFreshnessTests(unittest.TestCase):
 setUp=UpgradeTests.setUp
 request=UpgradeTests.request
 cfg=UpgradeTests.cfg
 def test_changed_task_cancels_approved_automatic_sms_before_provider(self):
  self.cfg(sms=True,recipient_consent=True,categories=['deadlines'])
  with self.app.app_context(),storage.connect(self.path) as db:
   planning.tick(db,True);notice=db.execute("SELECT * FROM notices WHERE task_id IS NOT NULL LIMIT 1").fetchone()
   identifier=communications.create_job(db,'sms',notice['body'],datetime.now(timezone.utc).isoformat(),True,notice['task_id'],'notice-'+str(notice['id']))
   db.execute('UPDATE tasks SET completed=1 WHERE id=?',(notice['task_id'],))
  with self.app.app_context(),patch('jarvis.communications.client') as sdk:
   self.assertFalse(communications.dispatch(identifier));sdk.assert_not_called()
  with storage.connect(self.path) as db:self.assertEqual(db.execute('SELECT status FROM communication_jobs WHERE id=?',(identifier,)).fetchone()[0],'cancelled')
 def test_preapproved_browser_search_is_immediate_and_logged(self):
  self.request('workspace/permissions',{'auto_open':True},'PUT')
  with patch('jarvis.computer.windows.supported',return_value=True),patch('jarvis.computer.windows.execute',return_value='Search opened by the test driver.') as execute:
   self.request('computer/settings',{'enabled':True},'PUT');reply=self.request('chat',{'content':'search the web for study methods'});self.assertEqual(reply.status_code,200);execute.assert_called_once();self.assertNotIn('action',reply.json)


class AsyncSmsTests(unittest.TestCase):
 setUp=UpgradeTests.setUp
 cfg=UpgradeTests.cfg
 signed=UpgradeTests.signed
 def test_ai_sms_acknowledges_before_ai_and_reuses_reserved_quota_once(self):
  self.cfg(sms=True,recipient_consent=True,sms_limit=1)
  body=dict(AccountSid=ENV['TWILIO_ACCOUNT_SID'],From=ENV['TWILIO_ALLOWED_NUMBER'],To=ENV['TWILIO_FROM_NUMBER'],MessageSid='SM'+'a1'*16,Body='What should I focus on today?')
  fake=MagicMock();fake.messages.create.return_value=SimpleNamespace(sid='SM'+'b2'*16)
  with patch.dict(os.environ,{'OPENAI_API_KEY':'offline-test'}),patch('jarvis.communications.threading.Thread') as thread,patch('jarvis.ai.answer',return_value='Start with the nearest saved deadline.') as answer,patch('jarvis.communications.client',return_value=fake):
   response=self.signed('/telephony/sms',body);self.assertEqual(response.status_code,200);self.assertNotIn('<Message>',response.text);answer.assert_not_called();thread.return_value.start.assert_called_once()
   args=thread.call_args.kwargs['args'];communications.reply_in_background(*args);fake.messages.create.assert_called_once()
   self.signed('/telephony/sms',body);self.assertEqual(thread.call_count,1)
  with storage.connect(self.path) as db:
   self.assertEqual(db.execute("SELECT attempts FROM communication_usage WHERE channel='sms'").fetchone()[0],1)
   self.assertEqual(db.execute("SELECT status FROM communication_jobs WHERE id=?",('reply-'+body['MessageSid'],)).fetchone()[0],'queued')

if __name__=='__main__':unittest.main()
