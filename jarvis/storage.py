"""SQLite storage. Sample data is inserted only on first initialization."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import date, timedelta


@contextmanager
def connect(path):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, title TEXT NOT NULL,
            due TEXT NOT NULL, priority TEXT NOT NULL, project TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, role TEXT NOT NULL, content TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY, category TEXT NOT NULL,
            content TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS computer_targets(alias TEXT PRIMARY KEY,kind TEXT NOT NULL,path TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS computer_actions(id TEXT PRIMARY KEY,payload TEXT NOT NULL,preview TEXT NOT NULL,
            status TEXT NOT NULL,created REAL NOT NULL,expires REAL NOT NULL,result TEXT);
        CREATE TABLE IF NOT EXISTS calendar_events(id INTEGER PRIMARY KEY,title TEXT NOT NULL,kind TEXT NOT NULL,start TEXT NOT NULL,end TEXT NOT NULL,timezone TEXT NOT NULL,recurrence TEXT NOT NULL DEFAULT 'none',until_date TEXT,break_minutes INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS notices(id INTEGER PRIMARY KEY,dedupe TEXT UNIQUE,category TEXT,body TEXT,task_id INTEGER,created TEXT,status TEXT NOT NULL DEFAULT 'unread');
        CREATE TABLE IF NOT EXISTS channel_context(channel TEXT PRIMARY KEY,task_id INTEGER);
        CREATE TABLE IF NOT EXISTS communication_jobs(id TEXT PRIMARY KEY,channel TEXT,body TEXT,task_id INTEGER,due TEXT,status TEXT,provider_sid TEXT,created TEXT,result TEXT,approved INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS communication_usage(day TEXT,channel TEXT,attempts INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(day,channel));
        CREATE TABLE IF NOT EXISTS webhook_receipts(sid TEXT PRIMARY KEY,status TEXT,created TEXT);
        CREATE TABLE IF NOT EXISTS trusted_roots(alias TEXT PRIMARY KEY,path TEXT NOT NULL,allow_read INTEGER NOT NULL DEFAULT 0,allow_move INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS workflows(name TEXT PRIMARY KEY,steps TEXT NOT NULL,preapproved INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS realtime_sessions(id TEXT PRIMARY KEY,provider_call TEXT,started REAL,status TEXT);
        CREATE TABLE IF NOT EXISTS realtime_tool_calls(session TEXT,call_id TEXT,PRIMARY KEY(session,call_id));
        CREATE TABLE IF NOT EXISTS realtime_events(session TEXT,event TEXT,PRIMARY KEY(session,event));
        CREATE TABLE IF NOT EXISTS ai_usage(day TEXT PRIMARY KEY, attempts INTEGER NOT NULL DEFAULT 0);
        ''')
        db.execute("UPDATE computer_actions SET status='unknown',result='Stale execution; outcome unknown. No retry was made.' WHERE status='executing' AND created<strftime('%s','now')-300")
        if 'dispatch_started' not in {r[1] for r in db.execute('PRAGMA table_info(communication_jobs)')}:
            db.execute('ALTER TABLE communication_jobs ADD COLUMN dispatch_started REAL')
        if 'quota_reserved' not in {r[1] for r in db.execute('PRAGMA table_info(communication_jobs)')}:
            db.execute('ALTER TABLE communication_jobs ADD COLUMN quota_reserved INTEGER NOT NULL DEFAULT 0')
        db.execute("UPDATE communication_jobs SET status='unknown',result='Stale provider dispatch; not retried.' WHERE status='sending' AND (dispatch_started IS NULL OR dispatch_started<strftime('%s','now')-120)")
        if 'allow_edit' not in {r[1] for r in db.execute('PRAGMA table_info(trusted_roots)')}:
            db.execute('ALTER TABLE trusted_roots ADD COLUMN allow_edit INTEGER NOT NULL DEFAULT 0')
        db.execute("CREATE TABLE IF NOT EXISTS file_revisions(id TEXT PRIMARY KEY,root TEXT NOT NULL,relative TEXT NOT NULL,path TEXT NOT NULL,original_hash TEXT NOT NULL,saved_hash TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'saved',created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        columns = {row[1] for row in db.execute('PRAGMA table_info(messages)')}
        if 'source' not in columns:
            db.execute("ALTER TABLE messages ADD COLUMN source TEXT NOT NULL DEFAULT 'demo'")
        if 'channel' not in columns:
            db.execute("ALTER TABLE messages ADD COLUMN channel TEXT NOT NULL DEFAULT 'desktop'")
        if not db.execute("SELECT 1 FROM settings WHERE key='seeded'").fetchone():
            today = date.today()
            samples = [('Outline next university assignment', 0, 'High', 'University'),
                       ('Review Collinson Creative project pipeline', 1, 'High', 'Collinson Creative'),
                       ('Plan workouts for the week', 2, 'Medium', 'Personal Life'),
                       ('Prepare client proposal moodboard', 3, 'Medium', 'Collinson Creative'),
                       ('Organise lecture notes', 5, 'Low', 'University')]
            db.executemany('INSERT INTO tasks(title,due,priority,project) VALUES(?,?,?,?)',
                           [(t, (today+timedelta(days=d)).isoformat(), p, project) for t,d,p,project in samples])
            db.executemany('INSERT INTO settings VALUES(?,?)', [('name', 'Commander'), ('seeded', '1')])
            db.execute('INSERT INTO messages(role,content) VALUES(?,?)', ('assistant', 'Welcome to JARVIS. Configure your backend OpenAI API key to enable AI chat. Tasks, chat history and explicitly saved memories persist locally. No facts are automatically saved as memories.'))
