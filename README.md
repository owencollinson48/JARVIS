# JARVIS — local personal command centre

A Windows-friendly dashboard built with Python 3.11+, Flask, vanilla JavaScript and SQLite. No Node build tools, paid services or API keys. All assets are local.

## First run on Windows

1. Install **Python 3.12 or newer** from https://www.python.org/downloads/windows/ and select **Add python.exe to PATH** in the installer.
2. Download or clone this repository into a folder on your PC.
3. Open that folder in File Explorer, type `cmd` into its address bar, then press Enter. Run these commands one at a time:

```bat
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

4. Keep the command window open. Open **http://127.0.0.1:5000** in your browser. Only open this address after starting the app.
5. Press **Ctrl+C** in the command window to stop the app.

## Start again later

Double-click **start.bat**, or open a command window inside the project folder and run:

```bat
.venv\Scripts\python.exe app.py
```

Then open http://127.0.0.1:5000 in your browser. If port 5000 is already in use, stop your previous JARVIS window with Ctrl+C. Do not run two copies.

## What works

- Overview with the browser's current date, task counts, priorities, deadlines and overdue labels.
- Add, edit, complete, reopen and delete tasks; filter by completion and project.
- University, Personal Life and Collinson Creative project summaries.
- A daily briefing calculated with fixed rules from saved tasks.
- Local conversation history with explicitly scripted demo replies, plus a saved display name.
- Sample tasks on the first run only; deleting all tasks does not reseed them.
- Responsive keyboard-accessible controls, request validation and local error messages.

**Not implemented:** language model AI, microphone input, speech output, reminder notifications, external integrations and computer automation. Disabled voice controls are labelled. Task deadlines are displayed only; there is no background scheduler.

## Data and privacy

The first start creates `data/jarvis.db` inside this folder. Tasks, chat history and settings survive restarts. For a backup, stop JARVIS and copy this file somewhere safe. Database files and the Python environment are excluded from Git. Keep this folder private: chat history is plain text in SQLite. No account/login or encryption is included. The app binds only to 127.0.0.1 and is intended for a single user on their own PC, not public hosting. No external service calls are made.

## Tests

From the project folder on Windows:

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

On Linux/macOS use `.venv/bin/python` instead of `.venv\Scripts\python.exe`. Tests use temporary databases and never modify your personal task data.

Manual browser check: add a task, edit it, tick its checkbox, switch to Completed, reopen it, then delete it. Send a chat message, change the display name in Settings, and restart the app to verify persistence. Resize the browser to check the mobile layout.

## Architecture

- `app.py`: local startup entry point (Flask development server; debug disabled).
- `jarvis/__init__.py`: application factory, local HTTP API, validation and request protection.
- `jarvis/storage.py`: SQLite schema and first-run sample data.
- `jarvis/templates/index.html`: dashboard and navigation sections.
- `jarvis/static/`: offline CSS and JavaScript UI, with safe text rendering.
- `tests/test_app.py`: task lifecycle, persistence, seeding, validation, assets and local request protections.

The API and storage are separate from the UI so later milestones can add real AI and voice deliberately. SQLite uses Python's standard library; Flask is the only direct third-party dependency. The pinned requirements include its runtime dependencies.
