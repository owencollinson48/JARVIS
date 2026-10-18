"""File controls in temporary folders; no real Windows launches or paid services."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from jarvis import create_app, storage, windows


class FileControlsTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.base=Path(temporary.name);self.folder=self.base/'approved';self.folder.mkdir()
        self.file=self.folder/'notes.txt';self.file.write_bytes(b'Original study plan\r\n')
        self.database=self.base/'jarvis.db';self.app=create_app(self.database);self.client=self.app.test_client();self.client.get('/')
        with self.client.session_transaction() as session:self.headers={'X-CSRF-Token':session['csrf']}
        platform=patch('jarvis.windows.supported',return_value=True);platform.start();self.addCleanup(platform.stop)
        self.call('computer/settings',{'enabled':True},'PUT');self.approve()

    def call(self,path,data=None,method='POST'):
        return self.client.open('/api/'+path,method=method,json=data,headers=self.headers)

    def approve(self,edit=True,path=None):
        return self.call('workspace/roots',dict(alias='docs',path=str(path or self.folder),allow_read=True,allow_move=True,allow_edit=edit))

    def load(self):
        result=self.call('files/load',{'root':'docs','relative':'notes.txt'});self.assertEqual(result.status_code,200,result.json);return result.json

    def prepare(self,content='Revised study plan\n'):
        loaded=self.load()
        return self.call('files/preview',dict(root='docs',relative='notes.txt',version=loaded['version'],content=content,kind='edit'))

    def confirm(self,response):
        self.assertEqual(response.status_code,200,response.json)
        return self.call('chat',{'content':'confirm action','action_id':response.json['action']['id']})

    def test_edit_preview_backup_preserves_crlf_undo_and_single_use(self):
        before=self.file.read_bytes();preview=self.prepare();self.assertIn('-Original study plan',preview.json['diff']);self.assertEqual(self.file.read_bytes(),before)
        diff=self.call('files/previews/'+preview.json['action']['id'],method='GET').json['diff'];self.assertIn('+Revised study plan',diff)
        self.assertIn('backed up',self.confirm(preview).json['reply']);self.assertEqual(self.file.read_bytes(),b'Revised study plan\r\n')
        revisions=self.call('files/revisions',method='GET').json['items'];self.assertEqual(len(revisions),1)
        self.assertEqual((self.base/'file-backups'/revisions[0]['id']).read_bytes(),before)
        self.assertIn('no longer pending',self.confirm(preview).json['reply'])
        restore=self.call('files/revisions/'+revisions[0]['id']+'/preview',{});self.assertIn('restored',self.confirm(restore).json['reply']);self.assertEqual(self.file.read_bytes(),before)
        self.assertEqual(self.call('files/revisions/'+revisions[0]['id']+'/preview',{}).status_code,404)

    def test_stale_load_and_stale_confirmation_never_overwrite(self):
        loaded=self.load();self.file.write_text('External change',encoding='utf-8')
        response=self.call('files/preview',dict(root='docs',relative='notes.txt',version=loaded['version'],content='Overwrite'))
        self.assertEqual(response.status_code,409)
        preview=self.prepare();self.file.write_text('Newer external edit',encoding='utf-8')
        self.assertIn('changed',self.confirm(preview).json['reply']);self.assertEqual(self.file.read_text(),'Newer external edit')

    def test_permissions_off_by_default_and_revocation_cancels_preview(self):
        preview=self.prepare();self.approve(edit=False)
        self.assertEqual(self.call('files/load',{'root':'docs','relative':'notes.txt'}).status_code,400)
        self.assertIn('no longer pending',self.confirm(preview).json['reply']);self.assertIn(b'Original',self.file.read_bytes())
        self.assertEqual(self.call('workspace/roots',dict(alias='legacy',path=str(self.folder),allow_read=True,allow_move=False)).status_code,200)
        with storage.connect(self.database) as db:self.assertEqual(db.execute("SELECT allow_edit FROM trusted_roots WHERE alias='legacy'").fetchone()[0],0)

    def test_file_and_folder_create_no_overwrite_and_traversal(self):
        folder=self.call('files/preview',dict(root='docs',relative='Archive',kind='mkdir'));self.confirm(folder);self.assertTrue((self.folder/'Archive').is_dir())
        file=self.call('files/preview',dict(root='docs',relative='Archive/new.md',kind='create',content='New notes'));self.confirm(file);self.assertEqual((self.folder/'Archive/new.md').read_text(),'New notes')
        for relative in ('../outside.txt',str(self.base/'outside.txt'),'Archive/new.md'):
            self.assertEqual(self.call('files/preview',dict(root='docs',relative=relative,kind='create',content='bad')).status_code,400)
        preview=self.call('files/preview',dict(root='docs',relative='race.txt',kind='create',content='proposed'))
        (self.folder/'race.txt').write_text('External file');self.confirm(preview);self.assertEqual((self.folder/'race.txt').read_text(),'External file')

    def test_unsupported_binary_large_and_bad_payloads(self):
        for name,raw in [('bad.exe',b'executable'),('binary.txt',b'a\x00b'),('large.txt',b'a'*8001),('encoding.txt',b'\xff')]:
            (self.folder/name).write_bytes(raw)
            self.assertEqual(self.call('files/load',dict(root='docs',relative=name)).status_code,400)
        self.assertEqual(self.call('files/load',dict(root='docs',relative={})).status_code,400)
        self.assertEqual(self.prepare('x'*8001).status_code,400)
        self.assertEqual(self.call('files/browse',['bad']).status_code,400)
        for name in ('CON.txt','notes:stream.txt','trailing.','COM1.md'):
            self.assertEqual(self.call('files/preview',dict(root='docs',relative=name,kind='create',content='blocked')).status_code,400)
        self.assertEqual(self.client.post('/api/files/preview',json={}).status_code,403)

    def test_backup_tampering_and_newer_changes_block_undo(self):
        self.confirm(self.prepare());revision=self.call('files/revisions',method='GET').json['items'][0]
        restore=self.call('files/revisions/'+revision['id']+'/preview',{})
        (self.base/'file-backups'/revision['id']).write_text('Tampered')
        self.assertIn('backup changed',self.confirm(restore).json['reply']);self.assertIn(b'Revised',self.file.read_bytes())
        self.file.write_text('Newer revision')
        self.assertEqual(self.call('files/revisions/'+revision['id']+'/preview',{}).status_code,409)

    def test_root_repointing_cannot_restore_into_a_different_location(self):
        self.confirm(self.prepare());revision=self.call('files/revisions',method='GET').json['items'][0]
        other=self.base/'other';other.mkdir();(other/'notes.txt').write_bytes(self.file.read_bytes());self.approve(path=other)
        self.assertEqual(self.call('files/revisions/'+revision['id']+'/preview',{}).status_code,400)

    def test_symlink_escape_denied(self):
        outside=self.base/'outside.txt';outside.write_text('Private outside file')
        try:(self.folder/'link.txt').symlink_to(outside)
        except OSError:self.skipTest('Symlink creation unavailable for this Windows account.')
        self.assertEqual(self.call('files/load',dict(root='docs',relative='link.txt')).status_code,400)
        names=[x['name'] for x in self.call('files/browse',dict(root='docs')).json['items']];self.assertNotIn('link.txt',names)

    def test_emergency_stop_cancels_edits(self):
        preview=self.prepare();self.call('workspace/emergency-stop',{})
        self.confirm(preview);self.assertIn(b'Original',self.file.read_bytes())

    def test_chat_text_replacement_previews_and_checks_ambiguity(self):
        preview=self.call('chat',{'content':'replace text in docs:notes.txt | Original | New'})
        self.assertIn('confirm',preview.json['reply']);self.confirm(preview);self.assertIn(b'New',self.file.read_bytes())
        self.file.write_text('duplicate duplicate')
        reply=self.call('chat',{'content':'replace text in docs:notes.txt | duplicate | changed'})
        self.assertIn('exactly once',reply.json['reply']);self.assertEqual(self.file.read_text(),'duplicate duplicate')
        self.confirm(self.call('chat',{'content':'create text file docs:hello.txt | Hello there!'}));self.assertEqual((self.folder/'hello.txt').read_text(),'Hello there!')

    def test_browse_nested_folder_and_open_only_after_confirmation(self):
        (self.folder/'child').mkdir()
        state=self.call('files/browse',dict(root='docs')).json;self.assertIsNone(state['parent']);self.assertEqual(state['items'][0]['name'],'child')
        self.assertEqual(self.call('files/browse',dict(root='docs',relative='child')).json['parent'],'.')
        with patch('jarvis.windows.execute',return_value='Test launch accepted.') as driver:
            preview=self.call('chat',{'content':'open folder docs:child'});driver.assert_not_called();self.confirm(preview);self.assertEqual(driver.call_args.args[1]['kind'],'folder')

    def test_url_navigation_settings_and_no_automatic_setting_changes(self):
        with patch('jarvis.windows.execute',return_value='Test adapter accepted.') as driver:
            preview=self.call('chat',{'content':'open https://example.org/notes?q=test'});driver.assert_not_called();self.confirm(preview);self.assertEqual(driver.call_args.args[0]['kind'],'navigate')
        for value in ('file:///private','javascript:alert(1)','https://user:pass@example.org','https://example.org\\@other.org','https://example.org\nHeader'):
            with self.assertRaises(ValueError):windows.website(value)
        with patch('jarvis.windows.os.startfile',create=True) as start:
            reply=windows.execute({'kind':'settings','page':'themes'});start.assert_called_once_with('ms-settings:themes');self.assertIn('No settings were changed',reply)
        with patch('jarvis.windows.webbrowser.open',return_value=True) as browser:
            windows.execute({'kind':'navigate','url':'https://example.org/'});browser.assert_called_once_with('https://example.org/',new=2)


if __name__=='__main__':unittest.main()
