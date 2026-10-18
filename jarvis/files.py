"""Local file browser and revisioned text editor using existing computer approvals."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import tempfile
from flask import Blueprint, current_app, jsonify, request
from . import storage, workspace, computer, windows

bp = Blueprint('files', __name__, url_prefix='/api/files')
TEXT_TYPES = {'.txt', '.md', '.csv', '.json', '.toml', '.ini', '.yaml', '.yml',
              '.css', '.html', '.py', '.js', '.ts'}
MAX_BYTES = 8000


def body():
    value=request.get_json(silent=True)
    if not isinstance(value,dict):raise ValueError('Send a JSON object.')
    return value


def connect():
    return storage.connect(current_app.config['DATABASE'])


def digest(value):
    return hashlib.sha256(value).hexdigest()


def content_bytes(text):
    if not isinstance(text, str) or '\x00' in text:
        raise ValueError('Enter plain text without null characters.')
    value = text.encode('utf-8')
    if len(value) > MAX_BYTES:
        raise ValueError('Text editing supports files up to 8,000 UTF-8 bytes.')
    return value


def destination(db, root, relative):
    if not isinstance(relative, str) or not relative or '\x00' in relative:
        raise ValueError('Enter a relative filename within the approved folder.')
    value = Path(relative)
    if value.is_absolute() or value.drive or '..' in value.parts or value.name in ('.', '..'):
        raise ValueError('Use a relative filename inside the approved folder.')
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {f'COM{n}' for n in range(1,10)} | {f'LPT{n}' for n in range(1,10)}
    for part in value.parts:
        if any(c in part for c in '<>:"|?*') or any(ord(c)<32 for c in part) or part.endswith((' ', '.')) or part.split('.')[0].upper() in reserved:
            raise ValueError('Choose a normal Windows filename without reserved names or alternate streams.')
    _, parent = workspace.root_path(db, root, str(value.parent), 'allow_edit')
    path = parent / value.name
    if path.is_symlink() or path.exists():
        raise ValueError('That destination already exists. Open it in the editor instead.')
    return path


def original(db, root, relative):
    _, path = workspace.root_path(db, root, relative, 'allow_edit')
    if path.suffix.lower() not in TEXT_TYPES or not path.is_file():
        raise ValueError('Choose a supported plain-text file, rather than a PDF, Office document or executable.')
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('This editor supports files up to 8,000 bytes.')
    raw = path.read_bytes()
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ValueError('This editor requires UTF-8 text. Other encodings are not converted automatically.') from None
    if '\x00' in text:
        raise ValueError('Binary files cannot be edited as text.')
    return path, raw, text


@bp.get('/locations')
def locations():
    # Construct suggestions only on the actual Windows installation; no cloud home scan.
    values = []
    if windows.supported():
        home = Path.home()
        values = [dict(name=name.lower(), path=str(home / name))
                  for name in ('Desktop', 'Documents', 'Downloads', 'Pictures', 'Music', 'Videos')
                  if (home / name).is_dir()]
        import ctypes
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        values += [dict(name=f'drive {chr(97 + n)}', path=f'{chr(65 + n)}:\\')
                   for n in range(26) if mask & (1 << n)]
    return jsonify(supported=windows.supported(), locations=values)


@bp.post('/browse')
def browse():
    data = body()
    with connect() as db:
        root, path = workspace.root_path(db, data.get('root'), data.get('relative', ''))
        if not path.is_dir():
            raise ValueError('Choose a folder to browse.')
        items = []; limited = False
        for item in path.iterdir():
            if len(items) >= 300:
                limited = True; break
            if item.is_symlink() or not item.resolve().is_relative_to(root):
                continue
            try:
                items.append(dict(name=item.name, relative=str(item.relative_to(root)),
                                  directory=item.is_dir(), size=item.stat().st_size))
            except OSError:
                continue
        items.sort(key=lambda x: (not x['directory'], x['name'].casefold()))
    return jsonify(items=items, limited=limited,
                   parent=str(path.parent.relative_to(root)) if path != root else None)


@bp.post('/load')
def load():
    data = body()
    with connect() as db:
        _, raw, text = original(db, data.get('root'), data.get('relative'))
    return jsonify(content=text, version=digest(raw), max_bytes=MAX_BYTES)


class FileConflict(ValueError):
    pass


@bp.errorhandler(FileConflict)
def conflict(error):
    return jsonify(error=str(error)),409


def prepare_change(data):
    kind = data.get('kind', 'edit')
    root, relative = data.get('root'), data.get('relative')
    with connect() as db:
        if not computer.enabled(db):
            raise ValueError('Enable computer controls in Settings before preparing changes.')
        if kind == 'edit':
            _, raw, before = original(db, root, relative)
            if data.get('version') != digest(raw):
                raise FileConflict('This file changed since you loaded it. Reload before editing.')
            value = content_bytes(data.get('content'))
            payload = dict(kind='text_edit', root=root, relative=relative,
                           version=digest(raw), content=value.decode('utf-8'))
            after = value.decode('utf-8')
            label = f'Edit {relative} in {root}; keep a local backup'
        elif kind in ('create', 'mkdir'):
            path = destination(db, root, relative)
            if kind == 'create' and path.suffix.lower() not in TEXT_TYPES:
                raise ValueError('Choose a supported plain-text extension.')
            after = content_bytes(data.get('content', '')).decode('utf-8') if kind == 'create' else ''
            before = ''; payload = dict(kind='text_create' if kind == 'create' else 'folder_create',
                                        root=root, relative=relative, content=after)
            label = f'Create {"file" if kind == "create" else "folder"} {relative} in {root}'
        else:
            raise ValueError('Choose edit, create or mkdir.')
    diff = '\n'.join(difflib.unified_diff(before.splitlines(), after.splitlines(),
                                          fromfile='Current file', tofile='Proposed file', lineterm=''))
    if kind == 'edit' and before == after:
        raise ValueError('No text changes to save.')
    return dict(action=workspace.preview(payload, label), diff=diff)


@bp.post('/preview')
def preview_edit():
    return jsonify(prepare_change(body()))


def command_preview(action):
    data=dict(root=action['root'],relative=action['relative'])
    if action['kind']=='replace_text':
        with connect() as db:_,raw,before=original(db,action['root'],action['relative'])
        if not action['old'] or before.count(action['old'])!=1:
            raise ValueError('The old text must appear exactly once. Use the editor to review ambiguous or missing matches.')
        data.update(kind='edit',version=digest(raw),content=before.replace(action['old'],action['new'],1))
    else:data.update(kind='mkdir' if action['kind']=='create_directory' else 'create',content=action.get('content',''))
    return prepare_change(data)


def backup_directory():
    folder = Path(current_app.config['DATABASE']).resolve().parent / 'file-backups'
    folder.mkdir(mode=0o700,exist_ok=True)
    return folder


def replace_text(path, value, expected):
    # Verify again just before replacing; never silently overwrite a known concurrent edit.
    if digest(path.read_bytes()) != expected:
        raise ValueError('The file changed after your preview. Reload it and preview again.')
    mode = stat.S_IMODE(path.stat().st_mode)
    descriptor, temporary = tempfile.mkstemp(prefix='.jarvis-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as output:
            output.write(value); output.flush(); os.fsync(output.fileno())
        os.chmod(temporary, mode)
        if digest(path.read_bytes()) != expected:
            raise ValueError('The file changed while saving. Nothing was overwritten.')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def execute(db, action):
    """Invoked only after the existing single-use Windows confirmation gate."""
    db.execute('BEGIN IMMEDIATE')
    if not computer.enabled(db):
        raise ValueError('Computer controls were stopped. Nothing was changed.')
    kind = action['kind']; root = action['root']; relative = action['relative']
    if kind == 'folder_create':
        destination(db, root, relative).mkdir()
        return 'Folder created inside the approved location.'
    if kind == 'text_create':
        path = destination(db, root, relative)
        if path.suffix.lower() not in TEXT_TYPES:
            raise ValueError('Unsupported text extension.')
        value = content_bytes(action['content'])
        with path.open('xb') as output:
            output.write(value)
        return 'Text file created. No existing file was overwritten.'
    path, raw, _ = original(db, root, relative)
    if digest(raw) != action['version']:
        raise ValueError('This file changed after the preview. Reload and preview again.')
    if kind == 'text_restore':
        revision = db.execute('SELECT * FROM file_revisions WHERE id=? AND status=\'saved\'',
                              (action['revision'],)).fetchone()
        if not revision or revision['root'] != root or revision['relative'] != relative or revision['path'] != str(path) or revision['saved_hash'] != digest(raw):
            raise ValueError('That revision can no longer be undone safely.')
        value = (backup_directory() / revision['id']).read_bytes()
        if digest(value) != revision['original_hash']:
            raise ValueError('The backup changed; restore was cancelled.')
        replace_text(path, value, digest(raw))
        db.execute("UPDATE file_revisions SET status='undone' WHERE id=?", (revision['id'],))
        return 'Previous file contents restored from the local backup.'
    value = content_bytes(action['content'])
    if b'\r\n' in raw and b'\r\n' not in value:
        value = value.replace(b'\n', b'\r\n')
    if raw.startswith(b'\xef\xbb\xbf'):
        value = b'\xef\xbb\xbf' + value
    if len(value)>MAX_BYTES:
        raise ValueError('The saved file would exceed 8,000 bytes including its line endings.')
    identifier = secrets.token_hex(24)
    descriptor=os.open(backup_directory()/identifier,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'wb') as output:
        output.write(raw)
    db.execute('INSERT INTO file_revisions(id,root,relative,path,original_hash,saved_hash) VALUES(?,?,?,?,?,?)',
               (identifier, root, relative, str(path), digest(raw), digest(value)))
    replace_text(path, value, digest(raw))
    return 'Text changes saved and backed up locally. Undo is available in File revisions.'


@bp.get('/revisions')
def revisions():
    with connect() as db:
        rows = [dict(row) for row in db.execute(
            'SELECT id,root,relative,status,created FROM file_revisions ORDER BY rowid DESC LIMIT 100')]
    return jsonify(items=rows)


@bp.post('/revisions/<identifier>/preview')
def preview_restore(identifier):
    with connect() as db:
        row = db.execute("SELECT * FROM file_revisions WHERE id=? AND status='saved'", (identifier,)).fetchone()
        if not row:
            return jsonify(error='Revision not found or already undone.'), 404
        path, raw, _ = original(db, row['root'], row['relative'])
        if str(path)!=row['path']:raise ValueError('This folder approval now points somewhere else. Restore cancelled.')
        if digest(raw) != row['saved_hash']:
            return jsonify(error='The file has newer changes. Reload it; this revision cannot overwrite them.'), 409
        payload = dict(kind='text_restore', root=row['root'], relative=row['relative'],
                       version=digest(raw), revision=identifier)
    return jsonify(action=workspace.preview(payload, f'Restore previous contents of {row["relative"]} in {row["root"]}'))


@bp.get('/previews/<identifier>')
def preview_diff(identifier):
    """Local-only preview display; never included in a model tool result."""
    with connect() as db:
        row=db.execute("SELECT payload FROM computer_actions WHERE id=? AND status='pending'",(identifier,)).fetchone()
        if not row:return jsonify(diff='')
        action=json.loads(row['payload']);kind=action['kind']
        if kind not in ('text_edit','text_create','text_restore'):return jsonify(diff='')
        if kind=='text_create':before='';after=action['content']
        else:
            path,raw,before=original(db,action['root'],action['relative'])
            if digest(raw)!=action['version']:raise FileConflict('The file changed. Reload it before confirming.')
            if kind=='text_restore':
                revision=db.execute('SELECT * FROM file_revisions WHERE id=?',(action['revision'],)).fetchone()
                if not revision or revision['path']!=str(path):raise ValueError('The revision no longer matches this file.')
                saved=(backup_directory()/revision['id']).read_bytes()
                if digest(saved)!=revision['original_hash']:raise ValueError('The backup changed. Restore cancelled.')
                after=saved.decode('utf-8-sig')
            else:after=action['content']
    return jsonify(diff='\n'.join(difflib.unified_diff(before.splitlines(),after.splitlines(),fromfile='Current file',tofile='Proposed file',lineterm='')))
