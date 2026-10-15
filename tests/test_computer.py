"""Computer-control tests: simulated Windows adapter only, never launches real apps."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from jarvis import create_app, storage, computer, windows


class ComputerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'test.db'
        self.app=create_app(self.path)
        self.client=self.app.test_client()
        self.client.get('/')
        with self.client.session_transaction() as session:
            self.headers={'X-CSRF-Token':session['csrf']}
        self.support=patch('jarvis.windows.supported',return_value=True)
        self.support.start();self.addCleanup(self.support.stop)
        self.driver=patch('jarvis.windows.execute',return_value='Test Windows adapter accepted the request.')
        self.execute=self.driver.start();self.addCleanup(self.driver.stop)
        self.ai=patch('jarvis.ai.answer',side_effect=AssertionError('Computer commands must not call the model.'))
        self.ai.start();self.addCleanup(self.ai.stop)

    def post(self,path,data):
        return self.client.post('/api/'+path,json=data,headers=self.headers)

    def chat(self,content,action_id=None):
        return self.post('chat',dict(content=content,action_id=action_id))

    def enable(self):
        response=self.client.put('/api/computer/settings',json={'enabled':True},headers=self.headers)
        self.assertEqual(response.status_code,200)

    def state(self):
        return self.client.get('/api/computer/state').json

    def test_disabled_and_non_windows_are_truthful(self):
        self.assertIn('off',self.chat('open spotify').json['reply'])
        with patch('jarvis.windows.supported',return_value=False):
            self.assertIn('Windows PC',self.chat('open spotify').json['reply'])
            self.assertEqual(self.client.put('/api/computer/settings',json={'enabled':True},headers=self.headers).status_code,400)
        self.execute.assert_not_called()

    def test_open_requires_bound_single_use_confirmation(self):
        self.enable()
        result=self.chat('Could you please open Spotify?').json
        token=result['action']['id']
        self.assertIn('spotify',result['action']['preview'])
        self.execute.assert_not_called()
        self.assertIn('no selected action',self.chat('confirm action').json['reply'])
        self.chat('confirm action','wrong-token')
        self.execute.assert_not_called()
        self.assertTrue(self.chat('Jarvis, confirm action',token).json['local'])
        self.execute.assert_called_once_with({'kind':'open','alias':'spotify'},None)
        self.chat('confirm action',token)
        self.assertEqual(self.execute.call_count,1)
        self.assertEqual(self.state()['recent'][0]['status'],'executed')

    def test_media_and_volume_are_immediate_without_confirmation(self):
        self.enable()
        for content,expected in [('next song',{'kind':'media','command':'next'}),('volume 45 percent',{'kind':'volume','percent':45}),('turn the volume down',{'kind':'volume','delta':-10})]:
            result=self.chat(content).json
            self.assertNotIn('action',result)
            self.execute.assert_called_with(expected,None)
        self.assertEqual(self.execute.call_count,3)
        self.assertIsNone(self.state()['pending'])
        self.chat('set volume to 999 percent')
        self.chat('pause spotify')
        self.chat('pause music')
        self.assertEqual(self.execute.call_count,3)

    def test_search_is_encoded_only_at_driver_and_needs_confirmation(self):
        self.enable()
        result=self.chat('search the internet for engineering study tips & notes').json
        self.execute.assert_not_called()
        self.chat('confirm action',result['action']['id'])
        self.execute.assert_called_once_with({'kind':'search','query':'engineering study tips & notes'},None)

    def test_cancel_replace_expire_and_disable_prevent_execution(self):
        self.enable()
        first=self.chat('open calculator').json['action']['id']
        second=self.chat('open notepad').json['action']['id']
        self.chat('confirm action',first)
        self.execute.assert_not_called()
        self.chat('cancel action',second)
        self.chat('confirm action',second)
        self.execute.assert_not_called()
        third=self.chat('open spotify').json['action']['id']
        with patch('jarvis.computer.time.time',return_value=time.time()+121):
            self.assertIsNone(self.state()['pending'])
            self.chat('confirm action',third)
        self.execute.assert_not_called()
        fourth=self.chat('open spotify').json['action']['id']
        self.client.put('/api/computer/settings',json={'enabled':False},headers=self.headers)
        self.chat('confirm action',fourth)
        self.execute.assert_not_called()

    def test_approved_path_only_and_removal_cancels_preview(self):
        self.enable()
        document=Path(self.temp.name)/'assignment.pdf';document.write_text('Test placeholder, never opened.')
        response=self.post('computer/targets',{'alias':'assignment','kind':'file','path':str(document)})
        self.assertEqual(response.status_code,201)
        token=self.chat('open my assignment').json['action']['id']
        self.chat('confirm action',token)
        self.execute.assert_called_once_with({'kind':'open','alias':'assignment'},dict(alias='assignment',kind='file',path=str(document.resolve())))
        token=self.chat('open assignment').json['action']['id']
        self.client.delete('/api/computer/targets/assignment',headers=self.headers)
        self.chat('confirm action',token)
        self.assertEqual(self.execute.call_count,1)
        self.assertIn('not approved',self.chat('open powershell').json['reply'])
        self.assertIn('not approved',self.chat('open spotify && calc').json['reply'])
        self.assertEqual(self.execute.call_count,1)

    def test_unsafe_target_validation_and_csrf(self):
        for suffix in ('.bat','.cmd','.ps1','.js','.lnk','.url'):
            file=Path(self.temp.name)/('unsafe'+suffix);file.write_text('not executed')
            self.assertEqual(self.post('computer/targets',{'alias':'unsafe','kind':'file','path':str(file)}).status_code,400)
        for body in ({'alias':'spotify','kind':'app','path':'anything'}, {'alias':'x','kind':'file','path':'relative.txt'}, {'alias':'x','kind':'folder','path':'\\\\server\\share'}):
            self.assertEqual(self.post('computer/targets',body).status_code,400)
        self.assertEqual(self.client.put('/api/computer/settings',json={'enabled':True}).status_code,403)
        self.assertEqual(self.client.post('/api/computer/targets',json={}).status_code,403)
        self.assertEqual(self.client.delete('/api/computer/targets/example').status_code,403)

    def test_execution_failure_has_no_success_claim_or_retry(self):
        self.enable()
        self.execute.side_effect=OSError('private implementation detail')
        result=self.chat('next song').json
        self.assertIn('could not complete',result['reply'])
        self.assertNotIn('private implementation',result['reply'])
        self.assertEqual(self.state()['recent'][0]['status'],'failed')
        self.assertEqual(self.execute.call_count,1)
        self.execute.side_effect=RuntimeError('private unexpected detail')
        result=self.chat('next song').json
        self.assertIn('outcome is unknown',result['reply'])
        self.assertNotIn('private unexpected detail',result['reply'])
        self.assertEqual(self.state()['recent'][0]['status'],'unknown')

    def test_restart_does_not_replay_uncertain_action_and_preserves_approvals(self):
        self.enable()
        document=Path(self.temp.name)/'saved.txt';document.write_text('Test fixture')
        self.post('computer/targets',{'alias':'saved note','kind':'file','path':str(document)})
        token=self.chat('open spotify').json['action']['id']
        with storage.connect(self.path) as db:
            db.execute("UPDATE computer_actions SET status='executing',created=0 WHERE id=?",(token,))
        fresh=create_app(self.path).test_client().get('/api/computer/state').json
        self.assertTrue(fresh['enabled'])
        self.assertEqual(fresh['targets'][0]['alias'],'saved note')
        self.assertEqual(fresh['recent'][0]['status'],'unknown')
        self.chat('confirm action',token)
        self.execute.assert_not_called()

    def test_personal_paths_and_local_command_history_never_enter_ai_context(self):
        self.enable()
        self.chat('open spotify')
        with storage.connect(self.path) as db:
            db.execute('INSERT INTO computer_targets VALUES(?,?,?)',('private file','file','C:/Private/private.pdf'))
            from jarvis.ai import context
            snapshot,history=context(db)
        self.assertNotIn('private.pdf',str(snapshot)+str(history))
        self.assertNotIn('open spotify',str(history))


class WindowsAdapterTests(unittest.TestCase):
    def test_linux_adapter_never_launches_anything(self):
        with patch('jarvis.windows.supported',return_value=False), patch('jarvis.windows.webbrowser.open') as browser:
            with self.assertRaises(OSError):windows.execute({'kind':'search','query':'test'})
            browser.assert_not_called()

    def test_browser_search_url_is_fixed_https_and_quoted(self):
        with patch('jarvis.windows.supported',return_value=True),patch('jarvis.windows.webbrowser.open',return_value=True) as browser:
            result=windows.execute({'kind':'search','query':'a & b; $(x)'})
        browser.assert_called_once_with('https://www.google.com/search?q=a%20%26%20b%3B%20%24%28x%29',new=2)
        self.assertIn('not read',result)

    def test_approved_executable_launch_is_one_literal_argument_without_shell(self):
        with tempfile.TemporaryDirectory() as folder:
            app=Path(folder)/'A trusted app.exe';app.write_text('Never executed by this test')
            with patch('jarvis.windows.supported',return_value=True),patch('jarvis.windows.subprocess.Popen') as launch:
                windows.execute({'kind':'open','alias':'my app'},{'kind':'app','path':str(app.resolve())})
                launch.assert_called_once_with([str(app.resolve())],shell=False)

    def test_volume_is_read_back_and_media_is_not_claimed_as_verified(self):
        with patch('jarvis.windows.supported',return_value=True),patch('jarvis.windows._volume',return_value=42) as volume,patch('jarvis.windows._media') as media:
            self.assertIn('reads 42',windows.execute({'kind':'volume','percent':42}))
            volume.assert_called_once_with(42,None)
            self.assertIn('not verified',windows.execute({'kind':'media','command':'next'}))
            media.assert_called_once_with('next')


if __name__=='__main__':unittest.main()
