# JARVIS — personal command centre

The existing JARVIS application now has an **animated voice-first HUD** around its OpenAI chat, explicit memory and persistent tasks. Built with Python, Flask, vanilla JavaScript and SQLite. The dashboard, tasks, projects, local briefing and profile work without an API key. Real AI chat requires internet access, an OpenAI API key and API billing.

[View a screenshot of the HUD with sample data](docs/hud-preview.png).

## The new voice-first interface

The same Python/Flask/JavaScript/SQLite stack and database are retained. No React, Vite, FastAPI or new runtime dependency is required. There is no frontend build step: Flask serves the CSS, SVG and JavaScript directly.

- **Command centre:** original cyan vector rings over a dark background, a large microphone core, live local date/time/timezone and compact modules. The reference image is inspiration only, never a background or static replacement for the rings.
- **Focused panels:** Tasks, University, Projects, History, Memory, Settings, Briefing and Deadlines open as native dialogs. Close with the × button or Escape to return home. The panel selector switches sections without losing the voice home screen. The University panel shows your existing University tasks; it does not invent timetable events.
- **Text:** type below the core and choose Send. Shortcut prompts fill a draft; they do not send it. History remains available in its own panel. Short local commands work without OpenAI: `/tasks`, `/university`, `/work`, `/projects`, `/briefing`, `/reminders`, `/history`, `/memory`, `/settings`, `/help`, and “what time is it?”. Local commands open panels or show information; they do not modify your tasks.
- **Voice input:** use current Windows Edge or Chrome at `http://127.0.0.1:5000`. Click the core or Microphone, read the browser-service privacy prompt, then enable voice for this page. Allow microphone permissions in your browser if asked. A waveform/RMS input meter reflects actual captured input. Recognition produces a **draft**; review it and click Send to make an AI request or save an explicit memory. If you already have a draft, replacing it requires confirmation.
- **Voice output:** off by default. Click **Speech off**, consent to browser speech use, then click **Read reply**. Settings has an optional **Read new AI replies aloud automatically** checkbox, off by default. **Stop audio**, muting, or Escape stops output. A local installed English voice is preferred where available. Replies read aloud are limited to 4,000 characters; the full text remains in History.
- **Keyboard:** Space toggles voice input when focus is outside a text field, select, link, button or open dialog. Normal button keyboard activation still works. Escape stops audio and closes the top dialog. All controls have visible focus and labels. The skip link goes directly to text input.
- **Microphone lifecycle:** no background listening, wake word or raw-audio recording. The microphone closes after recognition ends, on error, on Stop/Escape, on opening a panel, when the page is hidden and when a 30-second limit is reached. If a browser permission request resolves after you cancel, the stream is immediately released.
- **Privacy:** browser speech recognition/synthesis can send audio or text to browser/OS services. JARVIS asks for consent first and does not upload audio to its backend. No OpenAI audio endpoint or additional paid speech API has been added. Sending reviewed text still uses your existing paid OpenAI chat integration. Consent and voice settings last only for the open page; they are not new personal data stored in SQLite.
- **Truthful signals:** slow idle orbits are decorative. Listening glow and the input bars use real time-domain microphone RMS (smoothed and scaled ×4). Processing is shown only while a real backend operation is pending. Speaking follows speech start/end events, **not measured output volume**. AI status is “configured, not checked” until a successful submitted AI request; then it reports the last successful reply time, not a continuous connection. Task progress comes from saved records; an empty list shows 0%. No CPU, network-speed, weather or storage statistics are invented.
- **Responsive and accessible:** desktop side modules become a compact grid on small screens, with text input ahead of the widgets. Reduced motion follows your OS preference and can also be enabled for this page in Settings. Decorative animation pauses behind panels and when the page is hidden.
- **Not implemented:** shifts, weekly work hours, recurring university events, calendar integration, Windows reminders, notifications and computer automation. Their panels explain the limitation. The existing free daily briefing remains based on saved tasks.

If browser recognition is missing or its remote service fails, text entry and the rest of JARVIS remain available. Windows microphone permissions and actual recognition quality must be checked on your own PC; headless browser tests use a simulated input device and mocked speech services.

## Update your existing Windows installation

**Keep your current project folder and data. You do not need to start over.**

1. Stop JARVIS by pressing **Ctrl+C** in its command window.
2. Copy `data\jarvis.db` to a backup location of your choice while the app is stopped. It contains your existing tasks and history.
3. Download the latest ZIP from GitHub: https://github.com/owencollinson48/JARVIS/archive/refs/heads/main.zip
4. Right-click the downloaded ZIP → **Extract All…** → **Extract**. Do not run from inside the ZIP.
5. Open the extracted folder that contains `app.py` and `requirements.txt`. Copy its contents into your **existing JARVIS project folder**, accepting replacement of application files. The download contains no `data` or `.venv` folder, so your database and environment remain in place. Do not delete your existing project folder.
6. Open a command window **inside your existing project folder**, where `app.py`, `requirements.txt`, `data` and `.venv` are located. Run:

```bat
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

7. Configure your API key as described below before using real chat. Run:

```bat
.venv\Scripts\python.exe app.py
```

8. Open http://127.0.0.1:5000 and press **Ctrl+F5** to load the updated interface. The additive database migration preserves your tasks, settings and old messages. Older demo messages are labelled as legacy/local and are never sent as AI history.

## Enable AI safely — before sending a message

1. Sign in to https://platform.openai.com/ and create a dedicated **JARVIS project**.
2. Configure API billing at https://platform.openai.com/settings/organization/billing . **A ChatGPT subscription does not include API usage.** Review current model pricing at https://openai.com/api/pricing/ .
3. In your project's **Limits** settings, choose a small monthly budget and notification thresholds. **Project budgets are alerts, not a guaranteed hard spending cap.** If using prepaid credits, choose a small initial amount and disable automatic recharge if available; billing enforcement can be delayed. Monitor the Usage page.
4. Create a secret project API key at https://platform.openai.com/api-keys . Keep it private. Do not paste it into chat, browser code, the database or GitHub. If leaked, revoke it and create another.
5. On Windows, search Start for **Edit environment variables for your account**. Under **User variables**, click **New…**. Set **Variable name** to `OPENAI_API_KEY`. Paste your key into **Variable value**, then click **OK** to save and close the dialogs. This keeps it out of source files and shell command history; your Windows account can still access it.
6. Close existing command/terminal windows and reopen one from File Explorer. Restart JARVIS. The AI service module should say **Configured · not checked**. This checks presence only; the first message tests actual API access.
7. Optionally add these non-secret user environment variables through the same dialog:
   - `JARVIS_AI_DAILY_LIMIT`: default `20` AI request attempts per local calendar day. Set `0` to disable paid AI calls. Valid range: 0–1000. Counts persist across restarts and include failed/uncertain requests. This caps JARVIS requests, not your whole OpenAI account or exact money spent.
   - `OPENAI_MODEL`: default `gpt-4.1-mini`, a model supported by the Responses API. Change only to a compatible text model your project can access. Different models have different prices and capabilities.
8. Restart JARVIS after changing environment variables. Use the text field below the core to send **“Summarise my tasks and help me plan today.”** API charges apply only to submitted AI messages, not opening pages, startup, task editing or memory management.

The backend uses the **official OpenAI Python SDK and Responses API** at `https://api.openai.com/v1/responses`. The key is read only on the backend. It is never included in page HTML, JavaScript, API state or the database. Responses use `store=False`; this does not override OpenAI's other applicable data retention/abuse monitoring policies. See https://platform.openai.com/docs/guides/your-data .

## Using chat and memory

- **Home text field / History panel:** ask questions, plan your day, summarise deadlines or request suggested priorities. The latest exchange appears below the core; History retains the complete conversation log. Shortcut buttons fill the input; they do not submit or spend money until you click Send.
- **Previous conversations:** all successful exchanges remain in the local conversation log across restarts. The last 12 AI messages, truncated to 4,000 characters each, are used as context; all saved memories are supplied separately. The conversation log is one continuous thread, not separate named conversations.
- **Saved memory:** add a preference, project note or useful fact using the explicit form. You can inspect every saved memory and delete it individually.
- **Explicit chat command:** `/remember I prefer studying in the morning` saves that fact locally, even without a key. This exact command does not call OpenAI. Ordinary chat, including “please remember this”, does **not** automatically save personal facts. Use the form or `/remember`.
- **Delete a memory:** click Delete in Saved memory and confirm. That saved row is removed. All earlier conversation is then excluded from future AI context to prevent old messages from reintroducing it. Earlier chat remains visible locally. Deletion cannot retract messages already sent to OpenAI, and does not erase text from the visible local chat log. If you later type the fact again, it can be sent again.
- Up to 50 memories of 500 characters each. Do not store passwords, keys or other secrets.
- Saved project memories are notes; they do not create new task categories. The existing University, Personal Life and Collinson Creative sections are unchanged.

**AI suggestions do not execute actions.** Chat cannot edit or complete tasks, create calendar events, save facts without the explicit local command, send reminders, read your files or control your PC. It has no tools or calendar connection. It is instructed to distinguish saved facts from suggestions and ask when information is missing. AI can still make mistakes; verify advice. Task management remains in the existing UI.

The daily briefing remains a fast, free summary using fixed local rules. Voice uses browser features where supported, after consent. Notifications, shift scheduling, calendar integrations and computer automation are **not implemented**, and are labelled accordingly.

## Data sent to OpenAI

Only when you submit an AI message, JARVIS sends:

- Your message and local computer date.
- Up to 100 task records, ordered with open tasks first, plus the total count and an explicit omitted count.
- Your saved memories.
- Up to the last 12 eligible AI messages as described above.

No OpenAI requests are sent just to check configuration. Browser voice services may make their own requests only after you enable voice; they are separate from the backend chat integration. Legacy demo messages and local memory confirmations are not sent as conversation history. Tasks and memories are user data, not instructions. No API key is sent to the browser. The SDK has a 40-second timeout, automatic retries disabled, and an 800-output-token ceiling per request. Extremely long answers may fail the completeness check; no partial reply is saved.

## First installation on Windows

1. Install **Python 3.12 or newer** from https://www.python.org/downloads/windows/ and select **Add python.exe to PATH**.
2. Download the repository ZIP, **Extract All**, and open the folder containing `app.py` and `requirements.txt`. Windows may display the latter as `requirements` when extensions are hidden.
3. To open a command window in that folder, copy its address from File Explorer. In Command Prompt, type `cd /d "COPIED FOLDER ADDRESS"`, replacing the placeholder with your actual path. Keep the quotes. Then run these commands one at a time:

```bat
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

4. Keep the command window open and visit http://127.0.0.1:5000 . Configure the key and billing above for AI; the dashboard and explicit memory work offline.
5. Stop with **Ctrl+C**. To start again, double-click **start.bat** or run `.venv\Scripts\python.exe app.py` from the same folder. If Windows Smart App Control blocks the batch file, leave protection enabled and try the direct Python command instead. If Python itself is blocked, inspect the exact blocked filename and use a trusted Python installer; do not bypass Windows security settings. Do not run two copies at once.

## Troubleshooting

- **requirements.txt not found:** run `dir requirements.txt`. If it is missing, you are in the wrong folder or still inside the ZIP. Extract it and use the folder containing the application files.
- **AI is not configured:** add the Windows user variable, close/reopen the command window, then restart the app. Never send your key to someone helping troubleshoot.
- **Rejected API key:** check the key belongs to your OpenAI project and is active; replace/revoke it if necessary.
- **Voice unavailable or denied:** use current Edge or Chrome on localhost, check browser site permissions and Windows microphone privacy settings. If recognition remains unavailable, type in the home text field. Never disable Windows security protections to use voice.
- **Rate or usage limit:** check API credits, project permissions and billing, then wait before trying again. No automatic retries are made.
- **Daily request limit:** local cap reached; wait until the next local calendar day or deliberately change `JARVIS_AI_DAILY_LIMIT` and restart. Failed requests also consume an attempt because billing may be uncertain.
- **Cannot reach OpenAI / timeout:** check internet access to `api.openai.com` over HTTPS. Your draft remains in the input and no false assistant reply is saved. A timeout may still be billed; do not repeatedly click Send.
- **Model not found / denied:** check `OPENAI_MODEL` and project model access.
- **Another change in progress:** wait for the current chat to finish before changing memories or sending another message.
- **Port 5000 already in use:** stop your previous JARVIS command window with Ctrl+C before starting another.

## Local storage and tests

`data/jarvis.db` contains tasks, messages, settings, memories and local request counts. Back it up while JARVIS is stopped. Database files, virtual environments and `.env*` files are excluded from Git. `.env` files are **not loaded**; use Windows environment variables. This single-user local app has no login or encryption and must not be publicly hosted. It binds only to `127.0.0.1`, validates local Host headers and protects writes with a session CSRF token.

Run offline tests from the project folder:

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Linux/macOS equivalent: `.venv/bin/python -m unittest discover -s tests -v`.

Tests use temporary databases and mock HTTP transport through the actual OpenAI SDK. They do not use your key, call OpenAI or charge money. They cover existing dashboard/task behavior, upgrades from Milestone 1, persistence, explicit memory/deletion, outbound context, spending guards, missing keys, rate limits, invalid models, network timeouts and safe error handling. Live model access still needs your configured key and billing on your PC. The 19 Python tests continue to cover the backend.

The optional developer browser suite is `tests/hud_browser.cjs`. It uses Playwright/Chromium, which are **not application dependencies** and do not need installing on your Windows PC just to run JARVIS. Run it against a disposable database, never your personal one. In a Linux developer environment with Node, Playwright and Chromium already available:

```sh
.venv/bin/python -c "from jarvis import create_app; create_app('.ui-check/hud-test.db').run(host='127.0.0.1',port=5010,debug=False)"
# In a second terminal:
JARVIS_TEST_URL=http://127.0.0.1:5010 JARVIS_TEST_CHROMIUM=/usr/bin/chromium node tests/hud_browser.cjs
```

The browser suite exercises task and memory controls, settings, local commands, responsive layout, reduced motion, real pending/error UI, permission consent/denial and audio cleanup. Recognition and speech services and paid API responses are explicitly mocked; the browser microphone analyser uses a simulated audio device. No paid API or real speech service is called.

On Windows, manually verify: click the core → consent → allow your microphone → say a short request → check the draft → Send. Try Escape while listening, deny permission once, try Read reply, and check that muting and switching tabs stop audio. Confirm actual recognition support on your installed browser. Task progress, deadlines, history and saved memories should match your existing data.

## Architecture

- `app.py`: local entry point; Flask debug disabled.
- `jarvis/__init__.py`: existing dashboard/task/settings routes and app factory.
- `jarvis/storage.py`: SQLite schema, additive migration and first-run sample data.
- `jarvis/assistant.py`: chat and explicit memory endpoints; serializes assistant/memory changes.
- `jarvis/ai.py`: backend configuration, bounded context, daily cap and official API integration.
- `jarvis/templates/index.html` and `jarvis/static/style.css`: original vector HUD, responsive layouts and focused workspace dialogs.
- `jarvis/static/app.js`: existing task/chat/memory/settings UI with local panel commands.
- `jarvis/static/hud.js`: state-driven rings, clock, live task metrics, consent and keyboard controls.
- `jarvis/static/voice.js`: browser recognition, microphone analyser, speech output and cleanup. All application output is rendered as text, not unsafe HTML.
- `tests/`: offline regression and SDK integration tests.
