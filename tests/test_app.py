import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from jarvis import create_app


class JarvisTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict('os.environ', {'OPENAI_API_KEY': '', 'OPENAI_MODEL': 'gpt-4.1-mini', 'JARVIS_AI_DAILY_LIMIT': '20'})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'test.db'
        self.app = create_app(self.path)
        self.client = self.app.test_client()
        self.client.get('/')
        with self.client.session_transaction() as session:
            self.headers = {'X-CSRF-Token': session['csrf']}
        self.task = dict(title='Integration test', due='2026-12-10', project='University', priority='High', completed=False)

    def tearDown(self):
        self.temp.cleanup()

    def state(self):
        return self.client.get('/api/state').get_json()

    def test_task_lifecycle_and_restart(self):
        response = self.client.post('/api/tasks', json=self.task, headers=self.headers)
        self.assertEqual(response.status_code, 201)
        task_id = response.json['id']
        changed = {**self.task, 'title': 'Edited task', 'completed': True}
        self.assertEqual(self.client.put(f'/api/tasks/{task_id}', json=changed, headers=self.headers).status_code, 200)
        fresh = create_app(self.path).test_client().get('/api/state').json
        saved = next(t for t in fresh['tasks'] if t['id'] == task_id)
        self.assertEqual(saved['title'], 'Edited task')
        self.assertEqual(saved['completed'], 1)
        self.assertEqual(self.client.delete(f'/api/tasks/{task_id}', headers=self.headers).status_code, 200)
        self.assertFalse(any(t['id'] == task_id for t in self.state()['tasks']))

    def test_validation_and_missing_tasks(self):
        for change in ({'title': ''}, {'due': 'bad'}, {'priority': 'Urgent'}, {'project': 'Unknown'}, {'completed': 'yes'}):
            self.assertEqual(self.client.post('/api/tasks', json={**self.task, **change}, headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post('/api/tasks', json=[], headers=self.headers).status_code, 400)
        self.assertEqual(self.client.put('/api/tasks/9999', json=self.task, headers=self.headers).status_code, 404)
        self.assertEqual(self.client.delete('/api/tasks/9999', headers=self.headers).status_code, 404)

    def test_chat_and_settings_persist(self):
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key-not-real'}), patch('jarvis.ai.answer', return_value='A tested AI reply'):
            self.assertEqual(self.client.post('/api/chat', json={'content':'Hello'}, headers=self.headers).status_code, 200)
        self.assertEqual(self.client.put('/api/settings', json={'name':'Owen'}, headers=self.headers).status_code, 200)
        fresh = create_app(self.path).test_client().get('/api/state').json
        self.assertEqual(fresh['settings']['name'], 'Owen')
        self.assertEqual(fresh['messages'][-2]['content'], 'Hello')
        self.assertEqual(fresh['messages'][-1]['content'], 'A tested AI reply')
        self.assertEqual(self.client.post('/api/chat', json={'content':''}, headers=self.headers).status_code, 400)
        self.assertEqual(self.client.put('/api/settings', json={'name':''}, headers=self.headers).status_code, 400)

    def test_seed_is_once_even_after_deleting_tasks(self):
        for task in self.state()['tasks']:
            self.client.delete(f"/api/tasks/{task['id']}", headers=self.headers)
        self.assertEqual(create_app(self.path).test_client().get('/api/state').json['tasks'], [])

    def test_page_assets_and_local_protection(self):
        page = self.client.get('/')
        self.assertIn(b'JARVIS', page.data)
        for asset in ('app.js','style.css'):
            with self.client.get('/static/'+asset) as response:
                self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post('/api/tasks', json=self.task).status_code, 403)
        self.assertEqual(self.client.get('/api/state', base_url='http://evil.example').status_code, 403)


if __name__ == '__main__':
    unittest.main()
