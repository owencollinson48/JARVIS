"""Owner-controlled permissions. Tool output never grants additional authority."""
import json
import re
from pathlib import Path
from flask import current_app
from .. import storage, computer

DEFAULTS = dict(enabled=False, automatic=True, recovery=True, account_access=False,
                share_files=False, remember_activity=True, max_rounds=12, max_tools=30)
SECRET = re.compile(r'(?i)(-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|\bsk-[a-zA-Z0-9_-]{16,})')
SECRET_ASSIGN = re.compile(r"(?i)\b(?:api[_-]?key|auth[_-]?token|password|client[_-]?secret)[\"']?\s*[=:]\s*[\"']?([^\"'\s,};]{6,})")


def contains_secret(value):
    if SECRET.search(value) or re.search(r'\b(?:ghp_[A-Za-z0-9]{30,}|AKIA[A-Z0-9]{16}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,})',value):return True
    for match in re.finditer(r'(?<![0-9A-Za-z])(?:[3-6][0-9 -]{11,23}[0-9])(?![0-9A-Za-z])',value):
        digits=re.sub(r'[^0-9]','',match[0])
        if 13<=len(digits)<=19 and len(set(digits))>1:
            numbers=[int(x) for x in digits][::-1]
            total=sum(x if i%2==0 else (x*2-9 if x*2>9 else x*2) for i,x in enumerate(numbers))
            if total%10==0:return True
    for match in SECRET_ASSIGN.finditer(value):
        candidate=match[1]
        if not candidate.startswith(('os.','process.','environ.','getenv(','configuration(','None','null','input(')):
            return True
    return False

SENSITIVE_NAMES = {'.env', '.ssh', '.aws', '.azure', '.gnupg', '.git', 'credentials', 'secrets',
                   'passwords', 'login data', 'cookies', 'web data', 'credential manager'}

class ApprovalRequired(Exception):
    def __init__(self, reason, preview=None, level=3):
        super().__init__(reason); self.reason=reason; self.preview=preview; self.level=level

class Cancelled(Exception):
    pass


def config(db):
    row=db.execute("SELECT value FROM settings WHERE key='agent_policy'").fetchone()
    return {**DEFAULTS, **(json.loads(row[0]) if row else {})}


def connect():
    return storage.connect(current_app.config['DATABASE'])


def settings():
    with connect() as db:return config(db)


def check(job_id):
    with connect() as db:
        row=db.execute('SELECT status FROM agent_jobs WHERE id=?',(job_id,)).fetchone()
        if not row or row[0] not in ('running','queued') or not config(db)['enabled']:
            raise Cancelled('The task was stopped.')


def require(ctx, level, reason):
    check(ctx.job_id)
    if ctx.approved_level>=level:return
    cfg=settings()
    if level==3 or level==2 and not cfg['recovery'] or level==1 and not cfg['automatic']:
        raise ApprovalRequired(reason,level=level)


def computer_access(ctx):
    check(ctx.job_id)
    with connect() as db:
        if not computer.enabled(db):raise ValueError('Windows computer controls are off. Enable them in Settings.')


def sensitive_path(path):
    parts=[p.casefold() for p in Path(path).parts]
    return any(p in SENSITIVE_NAMES or p.startswith('.env.') for p in parts) or Path(path).suffix.lower() in ('.pem','.key','.pfx','.kdbx')


def guard_data(value):
    """Suppress common secret formats instead of returning them to the model or audit log."""
    def strings(item):
        if isinstance(item,str):yield item
        elif isinstance(item,dict):
            for key,child in item.items():
                if isinstance(child,str):yield str(key)+'='+child
                yield from strings(child)
        elif isinstance(item,list):
            for child in item:yield from strings(child)
    if any(contains_secret(item) for item in strings(value)):return {'withheld':True,'reason':'Sensitive-looking content was withheld. Inspect it locally; no secret was sent to the model.'}
    return value



def authority(db):
    import hashlib
    snapshot=dict(policy=config(db),roots=[dict(r) for r in db.execute('SELECT * FROM trusted_roots ORDER BY alias')],
                  targets=[dict(r) for r in db.execute('SELECT * FROM computer_targets ORDER BY alias')],enabled=computer.enabled(db))
    return hashlib.sha256(json.dumps(snapshot,sort_keys=True).encode()).hexdigest()



def financial_path(path):
    return any(word in Path(path).name.casefold() for word in ('bank','financial','finance','statement','credit','payment','tax'))



def sanitise_context(value):
    if isinstance(value,str):return '[Sensitive-looking content withheld; inspect it locally.]' if contains_secret(value) else value
    if isinstance(value,list):return [sanitise_context(v) for v in value]
    if isinstance(value,dict):return {k:sanitise_context(v) for k,v in value.items()}
    return value
