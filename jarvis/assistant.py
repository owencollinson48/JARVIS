"""Explicit memory management and AI chat routes, using the existing SQLite file."""
from flask import Blueprint, current_app, jsonify, request
from . import ai, storage, computer, planning

bp = Blueprint('assistant', __name__, url_prefix='/api')
CATEGORIES = ('preference', 'project', 'fact')


def connection():
    return storage.connect(current_app.config['DATABASE'])


def payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError('Send a JSON object.')
    return data


def text(value, maximum, label):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
        raise ValueError(f'{label} must contain 1 to {maximum} characters.')
    return value.strip()


def insert_memory(db, category, content):
    if category not in CATEGORIES:
        raise ValueError('Choose preference, project or fact.')
    db.execute('BEGIN IMMEDIATE')
    if db.execute('SELECT count(*) FROM memories').fetchone()[0] >= ai.MAX_MEMORIES:
        raise ValueError(f'You can save up to {ai.MAX_MEMORIES} memories. Delete an old one first.')
    return db.execute('INSERT INTO memories(category,content) VALUES(?,?)', (category, content)).lastrowid


def begin_change():
    lock = current_app.extensions['assistant_lock']
    if not lock.acquire(blocking=False):
        raise ai.AssistantError('Another chat or memory change is in progress. Wait for it to finish, then try again.', 409)
    return lock


@bp.post('/memories')
def save_memory():
    data = payload()
    content = text(data.get('content'), 500, 'Memory')
    category = data.get('category', 'fact')
    lock = begin_change()
    try:
        with connection() as db:
            memory_id = insert_memory(db, category, content)
        return jsonify(id=memory_id), 201
    finally:
        lock.release()


@bp.put('/memories/<int:memory_id>')
def edit_memory(memory_id):
    data=payload();content=text(data.get('content'),500,'Memory');category=data.get('category','fact')
    if category not in CATEGORIES:raise ValueError('Choose preference, project or fact.')
    lock=begin_change()
    try:
        with connection() as db:
            if not db.execute('UPDATE memories SET category=?,content=? WHERE id=?',(category,content,memory_id)).rowcount:return jsonify(error='Memory not found.'),404
            cutoff=db.execute('SELECT coalesce(max(id),0) FROM messages').fetchone()[0]
            db.execute("INSERT INTO settings VALUES('ai_history_after',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(cutoff),))
        return jsonify(ok=True)
    finally:lock.release()


@bp.delete('/memories/<int:memory_id>')
def delete_memory(memory_id):
    lock = begin_change()
    try:
        with connection() as db:
            if not db.execute('DELETE FROM memories WHERE id=?', (memory_id,)).rowcount:
                return jsonify(error='Memory no longer exists.'), 404
            # Prevent old chat from reintroducing deleted facts on future requests.
            cutoff = db.execute('SELECT coalesce(max(id),0) FROM messages').fetchone()[0]
            db.execute("INSERT INTO settings(key,value) VALUES('ai_history_after',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(cutoff),))
        return jsonify(ok=True)
    finally:
        lock.release()


@bp.post('/chat')
def chat():
    data = payload()
    content = text(data.get('content'), 2000, 'Message')
    lock = begin_change()
    try:
        with connection() as db:
            planned = planning.task_command(db, content)
            if planned:
                db.executemany('INSERT INTO messages(role,content,source,channel) VALUES(?,?,?,?)',[('user',content,'local','desktop'),('assistant',planned['reply'],'local','desktop')])
        if planned:return jsonify(ok=True,local=True,**planned)
        command = computer.handle(content, data.get('action_id'))
        if command:
            with connection() as db:
                db.executemany('INSERT INTO messages(role,content,source) VALUES(?,?,?)', [('user',content,'local'),('assistant',command['reply'],'local')])
            return jsonify(command)
        if content.lower() == '/remember' or content.lower().startswith('/remember '):
            fact = text(content[len('/remember'):], 500, 'Memory after /remember')
            with connection() as db:
                insert_memory(db, 'fact', fact)
                db.executemany('INSERT INTO messages(role,content,source) VALUES(?,?,?)',
                               [('user', content, 'local'), ('assistant', 'Saved to local memory: '+fact, 'local')])
            return jsonify(ok=True, memory_saved=True)
        key, model, limit = ai.configuration()
        if not key:
            raise ai.AssistantError('AI is not configured. Add OPENAI_API_KEY to your Windows user environment variables, then restart JARVIS. See README.md for key and spending setup.')
        with connection() as db:
            snapshot, history = ai.context(db)
            ai.reserve_attempt(db, limit)
        reply = ai.answer(content, snapshot, history, key, model)
        with connection() as db:
            db.executemany('INSERT INTO messages(role,content,source) VALUES(?,?,?)',
                           [('user', content, 'openai'), ('assistant', reply, 'openai')])
        return jsonify(ok=True)
    finally:
        lock.release()


@bp.errorhandler(ai.AssistantError)
def assistant_error(error):
    return jsonify(error=str(error)), error.status
