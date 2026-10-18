"""Bounded searches and verified, recoverable mutations within owner-approved roots."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import tempfile
import time
from flask import current_app
from . import policy
from .. import storage, computer, windows

MAX_FILE=10_000_000
TEXT_EXT={'.txt','.md','.csv','.json','.toml','.ini','.yaml','.yml','.css','.html','.py','.js','.ts','.bat','.ps1'}


def digest(raw):return hashlib.sha256(raw).hexdigest()


def roots():
    with policy.connect() as db:
        result=[dict(r) for r in db.execute('SELECT * FROM trusted_roots')];cfg=policy.config(db)
    if cfg['account_access'] and windows.supported():
        import ctypes
        mask=ctypes.windll.kernel32.GetLogicalDrives()
        result += [dict(alias='account_'+chr(97+n),path=f'{chr(65+n)}:\\',allow_read=1,allow_edit=1,allow_move=1)
                   for n in range(26) if mask & (1<<n)]
    return result


def resolve(root, relative='', permission='allow_read', new=False):
    selected=next((r for r in roots() if r['alias']==root),None)
    if not selected or not selected.get(permission):raise ValueError('This root or operation is not approved in Computer settings.')
    if not isinstance(relative,str) or '\x00' in relative:raise ValueError('A valid relative path is required.')
    value=Path(relative)
    if value.is_absolute() or value.drive or '..' in value.parts:raise ValueError('Use a relative path inside the approved root.')
    base=Path(selected['path'])
    if base.resolve(strict=True)!=base:raise ValueError('The approved root changed. Remove and approve it again.')
    path=(base/value).resolve(strict=not new)
    if not path.is_relative_to(base) or (base/value).is_symlink():raise ValueError('Links outside approved locations are not allowed.')
    if policy.sensitive_path(path):raise ValueError('Credential, authentication and private-key files are excluded. Handle authentication yourself in Windows.')
    if new:
        if not path.parent.is_dir() or path.exists() or (base/value).is_symlink():raise ValueError('Destination needs an existing parent and an unused filename.')
        if any(c in value.name for c in '<>:"|?*') or value.name.endswith((' ','.')):raise ValueError('Use an ordinary Windows filename.')
        if value.name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:raise ValueError('Reserved Windows filename.')
    return path


def remember(ctx,root,relative):
    if not policy.settings()['remember_activity']:return
    with policy.connect() as db:
        row=db.execute("SELECT value FROM agent_context WHERE key='recent_files'").fetchone()
        items=json.loads(row[0]) if row else []
        items=[x for x in items if (x['root'],x['relative'])!=(root,relative)]
        items.insert(0,dict(root=root,relative=relative,used=time.time()))
        db.execute("INSERT INTO agent_context VALUES('recent_files',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps(items[:20]),))


def search(ctx,a):
    policy.require(ctx,1,'Search accessible approved folders without modifying files.')
    selected=[r for r in roots() if not a['root'] or r['alias']==a['root']]
    if not selected:raise ValueError('Approve a folder or enable account drive access first.')
    matches=[];scanned=0;directories=0;limited=False;started=time.monotonic()
    for root in selected:
        if not root['allow_read']:continue
        try:base=resolve(root['alias'])
        except (OSError,ValueError):continue
        for directory,folders,files in os.walk(base,followlinks=False,onerror=lambda e:None):
            policy.check(ctx.job_id)
            directories+=1
            if directories>15000 or time.monotonic()-started>12:limited=True;break
            folders[:]=[n for n in folders if n.casefold() not in {'.git','.venv','node_modules','windows','program files','program files (x86)','$recycle.bin','system volume information'} and not policy.sensitive_path(Path(directory)/n) and not (Path(directory)/n).is_symlink()]
            for name in folders:
                folder=Path(directory)/name
                try:
                    info=folder.stat();relative=str(folder.relative_to(base))
                    if not a['extension'] and not a['contains'] and a['query'].casefold() in (root['alias']+' '+relative).casefold() and (not a['modified_after'] or info.st_mtime>=a['modified_after']):matches.append(dict(root=root['alias'],relative=relative,modified=info.st_mtime,size=0,kind='folder'))
                except OSError:pass
            for name in files:
                scanned+=1
                if scanned>15000 or time.monotonic()-started>12:limited=True;break
                path=Path(directory)/name
                if path.is_symlink() or policy.sensitive_path(path):continue
                try:
                    info=path.stat()
                    if a['modified_after'] and info.st_mtime<a['modified_after']:continue
                    if a['extension'] and path.suffix.lower()!=a['extension'].lower():continue
                    if a['query'].casefold() not in (root['alias']+' '+str(path.relative_to(base))).casefold():continue
                    if a['contains']:
                        if path.suffix.lower() not in TEXT_EXT or info.st_size>100000:continue
                        with path.open('rb') as source:content=source.read(100001)
                        if len(content)>100000 or a['contains'].casefold() not in content.decode('utf-8',errors='replace').casefold():continue
                    matches.append(dict(root=root['alias'],relative=str(path.relative_to(base)),modified=info.st_mtime,size=info.st_size,kind='file'))
                except (OSError,ValueError):continue
            if limited:break
        if limited:break
    return dict(files=sorted(matches,key=lambda x:x['modified'],reverse=True)[:60],scanned=scanned,limited=limited,coverage='Accessible approved locations only; bounded search, never a complete disk index.')


def read_local(root,relative):
    path=resolve(root,relative)
    if not path.is_file() or path.stat().st_size>MAX_FILE:raise ValueError('Choose a readable document up to 10 MB.')
    with path.open('rb') as source:raw=source.read(MAX_FILE+1)
    if len(raw)>MAX_FILE:raise ValueError('The file grew beyond the supported read limit.')
    return path,raw


def read(ctx,a):
    policy.require(ctx,1,'Read this ordinary approved file.')
    path,raw=read_local(a['root'],a['path'])
    if policy.financial_path(path):policy.require(ctx,3,'Share this potentially financial document with OpenAI? Authentication/payment credentials remain withheld.')
    if not policy.settings()['share_files'] and not ctx.approved:
        raise policy.ApprovalRequired('Send this specific document text to OpenAI? File contents stay local until you approve, or enable ordinary-document sharing.')
    if path.suffix.lower() not in TEXT_EXT:raise ValueError('Use documents_read for Word, Excel and PDF files.')
    text=raw.decode('utf-8-sig')
    if '\x00' in text:raise ValueError('Binary content is not supported as text.')
    remember(ctx,a['root'],a['path'])
    return policy.guard_data(dict(text=text[:12000],truncated=len(text)>12000,version=digest(raw),root=a['root'],path=a['path']))


def backup_folder():
    path=Path(current_app.config['DATABASE']).resolve().parent/'agent-backups';path.mkdir(mode=0o700,exist_ok=True);return path


def save_bytes(ctx,root,relative,value,expected,kind='edit'):
    policy.computer_access(ctx)
    path=resolve(root,relative,'allow_edit',new=expected=='new')
    if len(value)>MAX_FILE:raise ValueError('Result exceeds the 10 MB edit limit.')
    if expected=='new':
        with path.open('xb') as output:output.write(value)
        if digest(path.read_bytes())!=digest(value):raise OSError('Save verification failed.')
        remember(ctx,root,relative);return dict(saved=True,verified=True,root=root,path=relative,version=digest(value),recovery='New file; existing content was not overwritten.')
    raw=path.read_bytes()
    if digest(raw)!=expected:raise ValueError('The file changed. Read its latest version before editing; nothing was overwritten.')
    revision=secrets.token_hex(24)
    with os.fdopen(os.open(backup_folder()/revision,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as output:output.write(raw)
    fd,temp=tempfile.mkstemp(prefix='.jarvis-agent-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as output:output.write(value);output.flush();os.fsync(output.fileno())
        os.chmod(temp,path.stat().st_mode & 0o777)
        policy.check(ctx.job_id)
        if digest(path.read_bytes())!=expected:raise ValueError('Concurrent file change detected; save cancelled.')
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    if digest(path.read_bytes())!=digest(value):raise OSError('Save verification failed; backup was retained.')
    with policy.connect() as db:db.execute('INSERT INTO agent_revisions(id,root,path,absolute,original_hash,saved_hash,kind) VALUES(?,?,?,?,?,?,?)',(revision,root,relative,str(path),digest(raw),digest(value),kind))
    remember(ctx,root,relative)
    return dict(saved=True,verified=True,revision=revision,version=digest(value),root=root,path=relative)


def write(ctx,a):
    policy.computer_access(ctx)
    policy.require(ctx,1 if a['version']=='new' else 2,'Create this file, or edit it with a retained original backup.')
    if Path(a['path']).suffix.lower() not in TEXT_EXT:raise ValueError('Use the document tools for formatted files.')
    if policy.contains_secret(a['content']):raise ValueError('Do not write passwords or authentication secrets through the assistant.')
    if Path(a['path']).suffix.lower() in {'.py','.js','.ts','.bat','.ps1'}:
        policy.require(ctx,2,'Edit project code with recovery. Code is not executed automatically.')
    value=a['content'].encode('utf-8')
    if a['version']!='new':
        _,raw=read_local(a['root'],a['path'])
        if len(raw.decode('utf-8-sig'))>12000:raise ValueError('Use files_patch for a large existing file; truncated reads cannot justify replacing the whole document.')
        if b'\r\n' in raw and b'\r\n' not in value:value=value.replace(b'\n',b'\r\n')
        if raw.startswith(b'\xef\xbb\xbf') and not value.startswith(b'\xef\xbb\xbf'):value=b'\xef\xbb\xbf'+value
    return save_bytes(ctx,a['root'],a['path'],value,a['version'])


def transfer(ctx,a):
    policy.computer_access(ctx);policy.require(ctx,2,'Move/rename/copy this file without overwriting, with an inverse operation recorded.')
    source=resolve(a['root'],a['path'],'allow_move');destination=resolve(a['destination_root'],a['destination'],'allow_move',new=True)
    if not source.is_file() or source.stat().st_size>MAX_FILE:raise ValueError('Transfer supports single files up to 10 MB; folders must be organised file by file.')
    raw=source.read_bytes()
    if a['version'] and digest(raw)!=a['version']:raise ValueError('Source changed; re-read its version first.')
    with destination.open('xb') as out:out.write(raw)
    if digest(destination.read_bytes())!=digest(raw):raise OSError('Copy verification failed; source retained.')
    if a['operation']=='move':
        policy.check(ctx.job_id)
        if digest(source.read_bytes())!=digest(raw):raise ValueError('Source changed; retained both files. Inspect before proceeding.')
        source.unlink()
    identifier=secrets.token_hex(24)
    with policy.connect() as db:db.execute('INSERT INTO agent_transfers VALUES(?,?,?,?,?,?,?,?,?,?)',(identifier,a['operation'],a['root'],a['path'],a['destination_root'],a['destination'],digest(raw),'complete',str(source),str(destination)))
    remember(ctx,a['destination_root'],a['destination'])
    return dict(verified=True,operation=a['operation'],recovery_id=identifier,inverse='Move the destination back to its original path with files_transfer; no file was overwritten.')


def mkdir(ctx,a):
    policy.computer_access(ctx);policy.require(ctx,1,'Create this new folder.')
    path=resolve(a['root'],a['path'],'allow_edit',new=True);path.mkdir()
    return dict(created=path.is_dir(),root=a['root'],path=a['path'])


def open_item(ctx,a):
    policy.computer_access(ctx);policy.require(ctx,1,'Open this ordinary approved item.')
    path=resolve(a['root'],a['path'])
    if not path.is_dir() and path.suffix.lower() not in computer.FILE_TYPES:raise ValueError('Approve executable apps separately. Scripts are edited as data, not launched here.')
    result=windows.execute(dict(kind='open',alias=path.name),dict(kind='folder' if path.is_dir() else 'file',path=str(path)))
    remember(ctx,a['root'],a['path']);return dict(result=result,verified='Windows accepted the launch request; inspect windows to verify application readiness.')


def restore(ctx,a):
    policy.computer_access(ctx);policy.require(ctx,2,'Restore this revision if its current hash still matches.')
    with policy.connect() as db:row=db.execute("SELECT * FROM agent_revisions WHERE id=? AND status='saved'",(a['revision'],)).fetchone()
    if not row:raise ValueError('No restorable revision found.')
    path=resolve(row['root'],row['path'],'allow_edit')
    if str(path)!=row['absolute']:raise ValueError('The root approval has changed.')
    raw=(backup_folder()/row['id']).read_bytes()
    if digest(raw)!=row['original_hash']:raise ValueError('Backup integrity check failed.')
    result=save_bytes(ctx,row['root'],row['path'],raw,row['saved_hash'],'restore')
    with policy.connect() as db:db.execute("UPDATE agent_revisions SET status='restored' WHERE id=?",(row['id'],))
    return result



def patch_text(ctx,a):
    policy.computer_access(ctx);policy.require(ctx,2,'Apply one exact project/document text replacement with a retained original backup.')
    path,raw=read_local(a['root'],a['path'])
    if path.suffix.lower() not in TEXT_EXT:raise ValueError('Use document-format tools for this file.')
    text=raw.decode('utf-8-sig');old=a['old'];new=a['new']
    if '\r\n' in text:
        if '\r\n' not in old:old=old.replace('\n','\r\n')
        if '\r\n' not in new:new=new.replace('\n','\r\n')
    if not old or text.count(old)!=1:raise ValueError('The old span must occur exactly once. Read more context or ask which match to change.')
    value=text.replace(old,new,1).encode('utf-8')
    if raw.startswith(b'\xef\xbb\xbf'):value=b'\xef\xbb\xbf'+value
    return save_bytes(ctx,a['root'],a['path'],value,a['version'],'text_patch')
