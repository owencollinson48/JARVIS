"""SQLite storage. Sample data is inserted only on first initialization."""
import sqlite3
from pathlib import Path
from datetime import date, timedelta


def connect(path):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    return db


def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, title TEXT NOT NULL,
            due TEXT NOT NULL, priority TEXT NOT NULL, project TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, role TEXT NOT NULL, content TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')
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
            db.execute('INSERT INTO messages(role,content) VALUES(?,?)', ('assistant', 'Welcome to JARVIS. This is a local scripted demo, not an AI model. Your tasks and conversation history stay in this project’s SQLite database.'))
