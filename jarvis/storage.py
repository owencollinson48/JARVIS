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
        CREATE TABLE IF NOT EXISTS ai_usage(day TEXT PRIMARY KEY, attempts INTEGER NOT NULL DEFAULT 0);
        ''')
        db.execute("UPDATE computer_actions SET status='unknown',result='JARVIS restarted during execution. Outcome is unknown; no retry was made.' WHERE status='executing'")
        columns = {row[1] for row in db.execute('PRAGMA table_info(messages)')}
        if 'source' not in columns:
            db.execute("ALTER TABLE messages ADD COLUMN source TEXT NOT NULL DEFAULT 'demo'")
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
