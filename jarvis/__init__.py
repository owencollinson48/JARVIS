"""Local JARVIS application factory and HTTP routes."""
import secrets
import sqlite3
from threading import Lock
from datetime import date
from pathlib import Path
from flask import Flask, jsonify, render_template, request, session
from . import storage, ai
from .assistant import bp as assistant_blueprint
from .computer import bp as computer_blueprint
from .planning import bp as planning_blueprint
from .communications import bp as communications_blueprint, public as telephony_blueprint
from . import relay, communications, realtime, files
from .workspace import bp as workspace_blueprint
from .agent import api as agent_api, jobs as agent_jobs

PROJECTS = ['University', 'Personal Life', 'Collinson Creative']


def create_app(database=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=secrets.token_hex(32), MAX_CONTENT_LENGTH=16384,
                      SESSION_COOKIE_SAMESITE='Strict')
    app.config['DATABASE'] = str(database or Path(__file__).resolve().parent.parent / 'data' / 'jarvis.db')
    storage.initialize(app.config['DATABASE'])
    app.extensions['assistant_lock'] = Lock()
    app.extensions['agent_worker_lock'] = Lock()
    agent_jobs.recover(app)
    app.register_blueprint(assistant_blueprint)
    app.register_blueprint(computer_blueprint)
    app.register_blueprint(planning_blueprint)
    app.register_blueprint(communications_blueprint)
    app.register_blueprint(workspace_blueprint)
    app.register_blueprint(files.bp)
    app.register_blueprint(agent_api.bp)
    app.register_blueprint(realtime.bp)
    app.register_blueprint(telephony_blueprint)
    relay.register(app)

    @app.before_request
    def protect_local_app():
        if request.blueprint=='telephony' or request.endpoint=='relay_socket':
            return communications.validate_signature()
        if request.host.split(':')[0] not in ('localhost', '127.0.0.1'):
            return jsonify(error='Only local access is supported.'), 403
        if request.method in ('POST', 'PUT', 'DELETE'):
            if not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), session.get('csrf', 'missing')):
                return jsonify(error='Refresh the page before making changes.'), 403

    @app.get('/')
    def index():
        session.setdefault('csrf', secrets.token_hex(32))
        return render_template('index.html', csrf=session['csrf'])

    @app.get('/api/state')
    def state():
        with storage.connect(app.config['DATABASE']) as db:
            return jsonify(tasks=[dict(r) for r in db.execute('SELECT * FROM tasks ORDER BY completed, due, id')],
                           messages=[dict(r) for r in db.execute('SELECT * FROM messages ORDER BY id')],
                           settings=dict(db.execute('SELECT key,value FROM settings').fetchall()), projects=PROJECTS,
                           memories=[dict(r) for r in db.execute('SELECT * FROM memories ORDER BY id DESC')],
                           ai=ai.status(db))

    def task_values():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError('A task must be a JSON object.')
        title = data.get('title', '')
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 160:
            raise ValueError('Enter a task title between 1 and 160 characters.')
        due = data.get('due', '')
        try:
            date.fromisoformat(due)
        except (ValueError, TypeError):
            raise ValueError('Choose a valid deadline.')
        if data.get('priority') not in ('High', 'Medium', 'Low') or data.get('project') not in PROJECTS:
            raise ValueError('Choose a valid priority and project.')
        completed = data.get('completed', False)
        if not isinstance(completed, (bool, int)) or completed not in (0, 1):
            raise ValueError('Invalid completion status.')
        return title.strip(), due, data['priority'], data['project'], int(completed)

    @app.post('/api/tasks')
    def add_task():
        values = task_values()
        with storage.connect(app.config['DATABASE']) as db:
            cursor = db.execute('INSERT INTO tasks(title,due,priority,project,completed) VALUES(?,?,?,?,?)', values)
            return jsonify(id=cursor.lastrowid), 201

    @app.put('/api/tasks/<int:task_id>')
    def edit_task(task_id):
        values = task_values()
        with storage.connect(app.config['DATABASE']) as db:
            if not db.execute('UPDATE tasks SET title=?,due=?,priority=?,project=?,completed=? WHERE id=?', (*values, task_id)).rowcount:
                return jsonify(error='Task no longer exists.'), 404
        return jsonify(ok=True)

    @app.delete('/api/tasks/<int:task_id>')
    def delete_task(task_id):
        with storage.connect(app.config['DATABASE']) as db:
            if not db.execute('DELETE FROM tasks WHERE id=?', (task_id,)).rowcount:
                return jsonify(error='Task no longer exists.'), 404
        return jsonify(ok=True)

    @app.put('/api/settings')
    def settings():
        data = request.get_json(silent=True) or {}
        name = data.get('name') if isinstance(data, dict) else None
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60:
            raise ValueError('Enter a display name between 1 and 60 characters.')
        with storage.connect(app.config['DATABASE']) as db:
            db.execute('UPDATE settings SET value=? WHERE key=?', (name.strip(), 'name'))
        return jsonify(ok=True)

    @app.errorhandler(ValueError)
    def invalid(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(sqlite3.Error)
    def database_error(error):
        app.logger.exception('Database operation failed')
        return jsonify(error='The local database is unavailable. Check disk space and restart JARVIS.'), 503

    @app.errorhandler(OSError)
    def file_error(error):
        return jsonify(error='The local file is unavailable or Windows denied access. Check the approved path and permissions.'),400

    @app.errorhandler(ai.AssistantError)
    def assistant_error(error):
        return jsonify(error=str(error)),error.status

    @app.errorhandler(413)
    def too_large(error):
        return jsonify(error='That request is too large.'), 413

    return app
