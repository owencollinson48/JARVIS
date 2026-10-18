"""Deterministic, allowlisted Windows commands with single-use confirmation previews."""
import json
import re
import secrets
import sqlite3
import time
from pathlib import Path
from flask import Blueprint, current_app, jsonify, request
from . import storage, windows

bp = Blueprint('computer', __name__, url_prefix='/api/computer')
BUILTINS = ('spotify', 'calculator', 'notepad')
FILE_TYPES = {'.txt','.md','.pdf','.docx','.xlsx','.pptx','.csv','.png','.jpg','.jpeg','.gif','.mp3','.wav','.mp4'}


def connect():
    return storage.connect(current_app.config['DATABASE'])


def enabled(db):
    row = db.execute("SELECT value FROM settings WHERE key='computer_enabled'").fetchone()
    return bool(row and row[0] == '1')


def pending(db):
    db.execute("UPDATE computer_actions SET status='expired',result='Confirmation expired.' WHERE status='pending' AND expires<=?", (time.time(),))
    row = db.execute("SELECT id,preview,expires FROM computer_actions WHERE status='pending' ORDER BY created DESC LIMIT 1").fetchone()
    return dict(row) if row else None


def state(db):
    return dict(supported=windows.supported(), enabled=enabled(db), builtins=BUILTINS,
                targets=[dict(row) for row in db.execute('SELECT alias,kind,path FROM computer_targets ORDER BY alias')],
                pending=pending(db), recent=[dict(row) for row in db.execute('SELECT id,preview,status,result FROM computer_actions WHERE preview LIKE ? ORDER BY created DESC LIMIT 100',('%'+request.args.get('q','')[:100]+'%',))])


def normalize(content, literal=False):
    value = content.strip() if literal else content.strip().rstrip('.!?').strip()
    value = re.sub(r'^(?:jarvis[, ]+)?(?:(?:could|can|would) you (?:please )?|please )?', '', value, flags=re.I)
    if not literal:value = re.sub(r' please$', '', value, flags=re.I)
    return value


def parse(content):
    value = normalize(content)
    lower = value.lower()
    if lower in ('volume up','turn the volume up','turn up the volume','turn it up','increase volume'):
        return dict(kind='volume',delta=10)
    if lower in ('volume down','turn the volume down','turn down the volume','turn it down','lower the volume'):
        return dict(kind='volume',delta=-10)
    if lower in ('spotify next','spotify previous','next song on spotify','pause spotify','play spotify'):
        return dict(kind='invalid',error='Spotify-only playback is not verified. With Spotify as your active player, use next song, previous song or toggle playback to send a Windows media command.')
    if lower in ('next song','next track','skip song','skip track','change the song'):
        return dict(kind='media', command='next')
    if lower in ('previous song','previous track'):
        return dict(kind='media', command='previous')
    if lower in ('play pause','play/pause','toggle playback'):
        return dict(kind='media', command='play_pause')
    if lower in ('pause music','play music','resume music'):
        return dict(kind='invalid',error='I cannot read playback state to guarantee play or pause. Say toggle playback to send Windows’s play/pause button.')
    match = re.fullmatch(r'(?:set |change |adjust )?(?:the )?(?:system |master )?volume(?: to)? (\d{1,3})(?:\s*(?:%|percent|per cent))?', lower)
    if match:
        number = int(match[1])
        if not 0 <= number <= 100:
            return dict(kind='invalid', error='Choose a volume between 0 and 100 percent.')
        return dict(kind='volume', percent=number)
    match = re.fullmatch(r'(?:search (?:the )?(?:internet|web|browser)(?: for)?|search for|google) (.+)', value, flags=re.I)
    if match:
        return dict(kind='search', query=match[1].strip()[:300])
    match = re.fullmatch(r'replace text in ([a-z][a-z0-9 ]{0,39}):(.+?) \| (.*?) \| (.*)',normalize(content,literal=True),flags=re.I|re.S)
    if match:return dict(kind='replace_text',root=match[1].lower(),relative=match[2],old=match[3],new=match[4])
    match = re.fullmatch(r'create text file ([a-z][a-z0-9 ]{0,39}):(.+?) \| (.*)',normalize(content,literal=True),flags=re.I|re.S)
    if match:return dict(kind='create_text',root=match[1].lower(),relative=match[2],content=match[3])
    match = re.fullmatch(r'create folder ([a-z][a-z0-9 ]{0,39}):(.+)',value,flags=re.I)
    if match:return dict(kind='create_directory',root=match[1].lower(),relative=match[2])
    match = re.fullmatch(r'(?:open|visit|go to) (https?://.+)',value,flags=re.I)
    if match:
        try:return dict(kind='navigate',url=windows.website(match[1]))
        except ValueError as error:return dict(kind='invalid',error=str(error))
    match = re.fullmatch(r'open windows (themes|background|display|sound|bluetooth|apps)',lower)
    if match:return dict(kind='settings',page=match[1])
    match = re.fullmatch(r'(?:open file|open folder) ([a-z][a-z0-9 ]{0,39}):(.*)',value,flags=re.I)
    if match:return dict(kind='root_open',root=match[1].lower(),relative=match[2].strip())
    match = re.fullmatch(r'(?:open|launch) (.+)', value, flags=re.I)
    if match:
        alias = re.sub(r'^(?:my |the )', '', match[1].lower()).strip()
        return dict(kind='open', alias=alias)
    return None


def target_for(db, alias):
    if alias in BUILTINS:
        return None
    row = db.execute('SELECT alias,kind,path FROM computer_targets WHERE alias=?', (alias,)).fetchone()
    if not row:
        raise ValueError('That name is not approved. Add its exact file, folder or app path in Settings → Computer controls first.')
    return dict(row)


def run(action_id):
    # Commit before calling Windows: duplicates/restarts can never automatically replay an action.
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM computer_actions WHERE id=?', (action_id,)).fetchone()
        if not row or row['status'] != 'pending':
            return dict(ok=False, reply='That action is no longer pending. Ask for a new preview.')
        if row['expires'] <= time.time():
            db.execute("UPDATE computer_actions SET status='expired' WHERE id=?", (action_id,))
            return dict(ok=False, reply='That confirmation expired. Ask for the action again.')
        if not enabled(db) or not windows.supported():
            db.execute("UPDATE computer_actions SET status='cancelled' WHERE id=?", (action_id,))
            return dict(ok=False, reply='Windows computer controls are unavailable or disabled. Nothing was executed.')
        action = json.loads(row['payload'])
        try:
            target = target_for(db, action['alias']) if action['kind'] == 'open' else None
        except ValueError as error:
            db.execute("UPDATE computer_actions SET status='cancelled' WHERE id=?", (action_id,))
            return dict(ok=False, reply=str(error))
        db.execute("UPDATE computer_actions SET status='executing' WHERE id=?", (action_id,))
    try:
        if action['kind'] in ('text_edit','text_create','folder_create','text_restore'):
            from . import files
            with connect() as db:result=files.execute(db,action)
        elif action['kind'] in ('root_open','move'):
            from . import workspace
            with connect() as db:
                if action['kind']=='move':result=workspace.move(db,action)
                else:
                    _,path=workspace.root_path(db,action['root'],action['relative'])
                    if not path.is_dir() and path.suffix.lower() not in FILE_TYPES:raise ValueError('Unsupported file type.')
                    result=windows.execute({'kind':'open','alias':path.name},{'kind':'folder' if path.is_dir() else 'file','path':str(path)})
        elif action['kind']=='workflow':
            with connect() as db:workflow=db.execute('SELECT steps FROM workflows WHERE name=?',(action['name'],)).fetchone()
            if not workflow:raise ValueError('Workflow removed.')
            results=[]
            for step in json.loads(workflow[0]):
                with connect() as db:
                    if not enabled(db):raise ValueError('Emergency stop or controls disabled.')
                    selected=target_for(db,step['alias']) if step['kind']=='open' else None
                results.append(windows.execute(step,selected))
            result='Workflow finished: '+' '.join(results)
        else:result = windows.execute(action, target)
        status = 'executed'
    except (OSError, ValueError, KeyError) as error:
        result = 'Windows could not complete the approved action. Check that the app or file exists and is accessible. No automatic retry was made.'
        if action['kind'] in ('text_edit','text_create','folder_create','text_restore') and isinstance(error,ValueError):result=str(error)
        status = 'failed'
    except Exception:
        result = 'Windows returned an unexpected error. The outcome is unknown; check the application before repeating the request. No retry was made.'
        status = 'unknown'
    with connect() as db:
        db.execute('UPDATE computer_actions SET status=?,result=? WHERE id=?', (status, result, action_id))
    return dict(ok=status == 'executed', reply=result)


def handle(content, action_id=None):
    command = normalize(content).lower()
    if command in ('confirm action', 'cancel action'):
        if not isinstance(action_id, str):
            return dict(ok=True, local=True, reply='There is no selected action to confirm. Request a new action preview first.')
        if command == 'confirm action':
            result = run(action_id)
        else:
            with connect() as db:
                changed = db.execute("UPDATE computer_actions SET status='cancelled',result='Cancelled by user.' WHERE id=? AND status='pending'", (action_id,)).rowcount
            result = dict(ok=True, reply='Action cancelled.' if changed else 'That action is no longer pending.')
        return dict(ok=True, local=True, reply=result['reply'])
    workflow_match=re.fullmatch(r'run workflow ([a-z][a-z0-9 ]{0,39})',command)
    action = dict(kind='workflow',name=workflow_match[1]) if workflow_match else parse(content)
    if not action:
        return None
    if action['kind'] == 'invalid':
        return dict(ok=True, local=True, reply=action['error'])
    if action['kind'] in ('replace_text','create_text','create_directory'):
        with connect() as db:
            if not windows.supported() or not enabled(db):return dict(ok=True,local=True,reply='Enable Windows computer controls before changing local files.')
        from . import files
        try:prepared=files.command_preview(action)
        except (ValueError,OSError) as error:return dict(ok=True,local=True,reply=str(error))
        return dict(ok=True,local=True,reply=prepared['action']['preview']+'. Review the preview and confirm action to apply.',action=prepared['action'])
    with connect() as db:
        if not windows.supported():
            return dict(ok=True, local=True, reply='Computer controls require JARVIS running on your Windows PC. This machine cannot execute them.')
        if not enabled(db):
            return dict(ok=True, local=True, reply='Computer controls are off. Enable them in Settings → Computer controls. No action was executed.')
        preapproved=False
        if action['kind']=='workflow':
            workflow=db.execute('SELECT preapproved FROM workflows WHERE name=?',(action['name'],)).fetchone()
            if not workflow:return dict(ok=True,local=True,reply='Approve that workflow in the Autonomy panel first.')
            preapproved=bool(workflow[0]);preview='Run approved workflow: '+action['name']
        elif action['kind'] == 'open':
            try:
                target_for(db, action['alias'])
            except ValueError as error:
                return dict(ok=True, local=True, reply=str(error))
            preapproved=bool(db.execute("SELECT 1 FROM settings WHERE key='auto_open' AND value='1'").fetchone())
            preview = f"Open approved target: {action['alias']}"
        elif action['kind']=='root_open':
            from . import workspace
            try:
                _,path=workspace.root_path(db,action['root'],action['relative'])
                if not path.is_dir() and path.suffix.lower() not in FILE_TYPES:raise ValueError('Unsupported file type; approve executable apps separately in Settings.')
            except (ValueError,OSError) as error:return dict(ok=True,local=True,reply=str(error))
            preview='Open approved folder item: '+action['root']+':'+action['relative']
            preapproved=bool(db.execute("SELECT 1 FROM settings WHERE key='auto_open' AND value='1'").fetchone())
        elif action['kind'] in ('navigate','settings'):
            preview='Visit website: '+action['url'] if action['kind']=='navigate' else 'Open Windows settings: '+action['page']
            preapproved=bool(db.execute("SELECT 1 FROM settings WHERE key='auto_open' AND value='1'").fetchone())
        elif action['kind'] == 'search':
            preapproved=bool(db.execute("SELECT 1 FROM settings WHERE key='auto_open' AND value='1'").fetchone())
            preview = 'Search Google in your default browser for: '+action['query']
        elif action['kind'] == 'volume':
            preview = f"Set Windows master volume to {action['percent']} percent" if 'percent' in action else f"Adjust Windows master volume by {action['delta']} percentage points"
        else:
            preview = {'next':'Next track','previous':'Previous track','play_pause':'Toggle play/pause'}[action['command']]+' in Windows’s active media player (Spotify if active)'
        token = secrets.token_urlsafe(24)
        now = time.time()
        db.execute("UPDATE computer_actions SET status='cancelled',result='Replaced by newer request.' WHERE status='pending'")
        db.execute('INSERT INTO computer_actions(id,payload,preview,status,created,expires) VALUES(?,?,?,\'pending\',?,?)',
                   (token, json.dumps(action), preview, now, now+120))
    if action['kind'] in ('media', 'volume') or preapproved:
        return dict(ok=True, local=True, reply=run(token)['reply'])
    return dict(ok=True, local=True, reply=preview+'. Say “confirm action” to execute, or “cancel action”.', action=dict(id=token,preview=preview,expires=now+120))


@bp.get('/state')
def computer_state():
    with connect() as db:
        return jsonify(state(db))


@bp.put('/settings')
def computer_settings():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get('enabled'), bool):
        raise ValueError('Choose whether to enable computer controls.')
    if data['enabled'] and not windows.supported():
        raise ValueError('Enable controls on the Windows copy of JARVIS; this machine is not Windows.')
    with connect() as db:
        db.execute("INSERT INTO settings(key,value) VALUES('computer_enabled',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", ('1' if data['enabled'] else '0',))
        if not data['enabled']:
            db.execute("UPDATE computer_actions SET status='cancelled',result='Controls disabled.' WHERE status='pending'")
    return jsonify(ok=True)


@bp.post('/targets')
def add_target():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or data.get('kind') not in ('file','folder','app'):
        raise ValueError('Choose file, folder or app.')
    alias = data.get('alias')
    raw = data.get('path')
    if not isinstance(alias,str) or not re.fullmatch(r'[a-z][a-z0-9 ]{0,39}',alias.strip().lower()):
        raise ValueError('Use a name of 1–40 letters, digits and spaces, starting with a letter.')
    alias = alias.strip().lower()
    if alias in BUILTINS:
        raise ValueError('That built-in app name cannot be replaced.')
    if not windows.supported():
        raise ValueError('Approve paths in the Windows copy of JARVIS.')
    if not isinstance(raw,str) or not 1 <= len(raw) <= 1024 or '\x00' in raw:
        raise ValueError('Paste an exact local Windows path.')
    raw = raw.strip().strip('"')
    # No network shares or device paths: approval is for a local item only.
    if raw.startswith(('\\\\','//')):
        raise ValueError('Network and device paths are not supported.')
    try:
        path = Path(raw)
        if not path.is_absolute():
            raise ValueError('Use a full absolute path, not a relative path.')
        path = path.resolve(strict=True)
        if data['kind'] == 'folder':
            valid = path.is_dir()
        else:
            valid = path.is_file() and path.suffix.lower() in ({'.exe'} if data['kind']=='app' else FILE_TYPES)
        if str(path).startswith(('\\\\','//')):
            raise ValueError('Network and device paths are not supported.')
        if not valid:
            raise ValueError('Choose an existing folder, a trusted .exe app, or a supported document/media file.')
    except OSError:
        raise ValueError('That local path could not be found or accessed.') from None
    with connect() as db:
        if db.execute('SELECT count(*) FROM computer_targets').fetchone()[0] >= 50:
            raise ValueError('Remove an approved target before adding more (limit 50).')
        try:
            db.execute('INSERT INTO computer_targets(alias,kind,path) VALUES(?,?,?)', (alias,data['kind'],str(path)))
        except sqlite3.IntegrityError:
            raise ValueError('That name is already approved. Remove it first to change its path.') from None
    return jsonify(ok=True),201


@bp.delete('/targets/<alias>')
def remove_target(alias):
    with connect() as db:
        if not db.execute('DELETE FROM computer_targets WHERE alias=?',(alias,)).rowcount:
            return jsonify(error='That target no longer exists.'),404
        db.execute("UPDATE computer_actions SET status='cancelled',result='Approved targets changed.' WHERE status='pending'")
    return jsonify(ok=True)
