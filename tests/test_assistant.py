"""Offline integration tests. Mock HTTP transport exercises the actual OpenAI SDK."""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx2 as httpx
from openai import OpenAI
from jarvis import create_app, storage
from jarvis import ai


def response_payload(text='Start with the university assignment due today.'):
    return {'id':'resp_test', 'object':'response', 'created_at':1, 'status':'completed',
            'model':'gpt-4.1-mini', 'output':[{'type':'message', 'id':'msg_test',
            'status':'completed', 'role':'assistant', 'content':[{'type':'output_text',
            'text':text, 'annotations':[]}]}]}


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'jarvis.db'
        self.env = patch.dict(os.environ, {'OPENAI_API_KEY':'test-key-not-real',
                              'OPENAI_MODEL':'gpt-4.1-mini', 'JARVIS_AI_DAILY_LIMIT':'20'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.app = create_app(self.path)
        self.client = self.app.test_client()
        self.client.get('/')
        with self.client.session_transaction() as session:
            self.headers = {'X-CSRF-Token':session['csrf']}
        self.requests = []

    def post(self, path, data):
        return self.client.post('/api/'+path, json=data, headers=self.headers)

    def delete(self, path):
        return self.client.delete('/api/'+path, headers=self.headers)

    def state(self):
        return self.client.get('/api/state').json

    def mock_sdk(self, handler=None):
        def transport(request):
            self.requests.append(request)
            return handler(request) if handler else httpx.Response(200, json=response_payload())
        def factory(**kwargs):
            self.assertEqual(kwargs['max_retries'], 0)
            self.assertEqual(kwargs['timeout'], 40.0)
            self.assertEqual(kwargs['base_url'], 'https://api.openai.com/v1')
            return OpenAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(transport)))
        return patch('jarvis.ai.OpenAI', side_effect=factory)

    def test_real_sdk_payload_context_history_and_persistence(self):
        memory=self.post('memories', {'category':'preference','content':'I prefer morning study.'})
        self.assertEqual(memory.status_code, 201)
        with self.mock_sdk():
            self.assertEqual(self.post('chat', {'content':'Help plan my day.'}).status_code, 200)
            self.assertEqual(self.post('chat', {'content':'What should I do next?'}).status_code, 200)
        request=self.requests[0]
        self.assertEqual(str(request.url), 'https://api.openai.com/v1/responses')
        self.assertEqual(request.headers['authorization'], 'Bearer test-key-not-real')
        body=json.loads(request.content)
        self.assertFalse(body['store'])
        self.assertEqual(body['max_output_tokens'], 800)
        self.assertEqual(body['model'], 'gpt-4.1-mini')
        self.assertNotIn('tools', body)
        self.assertIn('Never invent', body['instructions'])
        snapshot=json.loads(body['input'][0]['content'].split('\n',1)[1])
        self.assertEqual(snapshot['saved_memories'][0]['content'], 'I prefer morning study.')
        self.assertEqual(len(snapshot['tasks']), 5)
        self.assertEqual(len(body['input']), 2)  # legacy welcome is never sent
        second=json.loads(self.requests[1].content)
        self.assertEqual(second['input'][1]['content'], 'Help plan my day.')
        fresh=create_app(self.path).test_client().get('/api/state').json
        self.assertEqual(fresh['messages'][-1]['source'], 'openai')
        self.assertEqual(fresh['ai']['attempts_today'], 2)
        self.assertNotIn('test-key-not-real', json.dumps(fresh))
        self.assertEqual(len(fresh['memories']),1)
        self.assertEqual(fresh['tasks'], self.state()['tasks'])

    def test_missing_key_no_request_no_fake_reply(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY':''}), self.mock_sdk():
            before=self.state()['messages']
            result=self.post('chat', {'content':'Hello'})
            self.assertEqual(result.status_code,503)
            self.assertIn('OPENAI_API_KEY',result.json['error'])
            self.assertEqual(self.state()['messages'],before)
            self.assertFalse(self.state()['ai']['configured'])
        self.assertEqual(self.requests,[])

    def test_memory_command_works_offline_and_is_not_automatic(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY':''}):
            result=self.post('chat', {'content':'/remember My project is Collinson Creative.'})
        self.assertEqual(result.status_code,200)
        self.assertTrue(result.json['memory_saved'])
        self.assertEqual(self.state()['memories'][0]['category'],'fact')
        self.assertEqual(self.state()['messages'][-1]['source'],'local')
        with self.mock_sdk():
            self.assertEqual(self.post('chat',{'content':'I like tea. Remember that please.'}).status_code,200)
        self.assertEqual(len(self.state()['memories']),1)

    def test_memory_delete_excludes_old_chat_from_new_context(self):
        memory=self.post('memories',{'category':'fact','content':'My old fact.'}).json['id']
        with self.mock_sdk():
            self.post('chat',{'content':'My old fact.'})
        old_messages=self.state()['messages']
        self.assertEqual(self.delete(f'memories/{memory}').status_code,200)
        self.assertEqual(self.state()['messages'],old_messages)
        with self.mock_sdk():
            self.post('chat',{'content':'What do you remember?'})
        body=json.loads(self.requests[-1].content)
        self.assertEqual(len(body['input']),2)
        self.assertNotIn('My old fact.',json.dumps(body))
        self.assertEqual(create_app(self.path).test_client().get('/api/state').json['memories'],[])
        self.assertEqual(self.delete(f'memories/{memory}').status_code,404)

    def test_memory_validation_and_capacity(self):
        for body in ({'content':''},{'content':'x'*501},{'content':5},{'content':'x','category':'bogus'},[]):
            self.assertEqual(self.post('memories',body).status_code,400)
        for i in range(50):
            self.assertEqual(self.post('memories',{'content':f'Fact {i}'}).status_code,201)
        self.assertEqual(self.post('memories',{'content':'One too many'}).status_code,400)
        self.assertEqual(self.post('chat',{'content':'/remember Another fact'}).status_code,400)
        self.assertEqual(len(self.state()['memories']),50)

    def test_daily_limit_persists_and_zero_disables_api(self):
        with patch.dict(os.environ,{'JARVIS_AI_DAILY_LIMIT':'1'}),self.mock_sdk():
            self.assertEqual(self.post('chat',{'content':'Hi'}).status_code,200)
            self.assertEqual(self.post('chat',{'content':'Again'}).status_code,429)
        self.assertEqual(len(self.requests),1)
        self.assertEqual(create_app(self.path).test_client().get('/api/state').json['ai']['attempts_today'],1)
        with patch.dict(os.environ,{'JARVIS_AI_DAILY_LIMIT':'0'}),self.mock_sdk():
            self.assertEqual(self.post('chat',{'content':'No spending'}).status_code,429)
        self.assertEqual(len(self.requests),1)

    def test_provider_errors_are_safe_and_not_retried(self):
        cases=[(401,401,'API key'),(403,403,'permissions'),(429,429,'usage limit'),(500,502,'could not process'),(404,503,'not found')]
        for provider_code,expected,phrase in cases:
            with self.subTest(code=provider_code), self.mock_sdk(lambda req: httpx.Response(provider_code,json={'error':{'message':'private-provider-detail-test-key-not-real','type':'test'}})):
                before=self.state()['messages']
                result=self.post('chat',{'content':'Plan today'})
                self.assertEqual(result.status_code,expected)
                self.assertIn(phrase,result.json['error'])
                self.assertNotIn('private-provider',result.json['error'])
                self.assertEqual(self.state()['messages'],before)
        self.assertEqual(len(self.requests),len(cases))
        self.assertEqual(self.state()['ai']['attempts_today'],len(cases))

    def test_connection_and_timeout_errors(self):
        for exception in (httpx.ConnectError,httpx.ReadTimeout):
            def fail(request):
                raise exception('private diagnostic',request=request)
            with self.subTest(exception=exception), self.mock_sdk(fail):
                response=self.post('chat',{'content':'Hi'})
                self.assertEqual(response.status_code,503)
                self.assertIn('Cannot reach OpenAI',response.json['error'])
        self.assertEqual(len(self.requests),2)

    def test_empty_or_incomplete_response_is_not_saved(self):
        for data in (response_payload(''), {**response_payload(), 'status':'incomplete'}, {'status':'completed'}):
            with self.mock_sdk(lambda req: httpx.Response(200,json=data)):
                before=self.state()['messages']
                self.assertEqual(self.post('chat',{'content':'Hi'}).status_code,502)
                self.assertEqual(self.state()['messages'],before)

    def test_configuration_validation_and_chat_validation(self):
        for limit in ('bad','-1','1001'):
            with patch.dict(os.environ,{'JARVIS_AI_DAILY_LIMIT':limit}), self.mock_sdk():
                self.assertIn('error',self.state()['ai'])
                self.assertEqual(self.post('chat',{'content':'Hello'}).status_code,503)
        for body in ({'content':''},{'content':'x'*2001},[],{'content':None},{'content':'/remember'}):
            self.assertEqual(self.post('chat',body).status_code,400)
        self.assertEqual(self.requests,[])

    def test_concurrent_change_rejected_without_api_call(self):
        with self.app.extensions['assistant_lock'], self.mock_sdk():
            self.assertEqual(self.post('chat',{'content':'Hi'}).status_code,409)
            self.assertEqual(self.post('memories',{'content':'Fact'}).status_code,409)
        self.assertEqual(self.requests,[])

    def test_memory_routes_require_csrf(self):
        self.assertEqual(self.client.post('/api/memories',json={'content':'x'}).status_code,403)
        memory=self.post('memories',{'content':'x'}).json['id']
        self.assertEqual(self.client.delete(f'/api/memories/{memory}').status_code,403)

    def test_context_is_bounded_and_excludes_old_demo_replies(self):
        with storage.connect(self.path) as db:
            db.executemany('INSERT INTO tasks(title,due,priority,project) VALUES(?,?,?,?)',
                           [('Bounded task','2026-12-01','High','University')]*110)
            db.executemany('INSERT INTO messages(role,content,source) VALUES(?,?,?)',
                           [('user','old conversation','openai')]*20)
            snapshot,history=ai.context(db)
        self.assertEqual(len(snapshot['tasks']),100)
        self.assertEqual(snapshot['tasks_omitted'],15)
        self.assertEqual(len(history),12)


class MigrationTests(unittest.TestCase):
    def test_existing_milestone_one_database_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'existing.db'
            with sqlite3.connect(path) as db:
                db.executescript('''
                CREATE TABLE tasks(id INTEGER PRIMARY KEY,title TEXT NOT NULL,due TEXT NOT NULL,priority TEXT NOT NULL,project TEXT NOT NULL,completed INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE messages(id INTEGER PRIMARY KEY,role TEXT NOT NULL,content TEXT NOT NULL);
                CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                INSERT INTO tasks VALUES(1,'Keep my assignment','2026-12-01','High','University',0);
                INSERT INTO messages VALUES(1,'user','Keep my chat');
                INSERT INTO settings VALUES('seeded','1');
                INSERT INTO settings VALUES('name','Owen');
                ''')
            for _ in range(2):
                state=create_app(path).test_client().get('/api/state').json
                self.assertEqual(len(state['tasks']),1)
                self.assertEqual(state['tasks'][0]['title'],'Keep my assignment')
                self.assertEqual(state['messages'][0]['content'],'Keep my chat')
                self.assertEqual(state['messages'][0]['source'],'demo')
                self.assertEqual(state['settings']['name'],'Owen')
                self.assertEqual(state['memories'],[])


if __name__=='__main__':
    unittest.main()
