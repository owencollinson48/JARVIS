# JARVIS — personal command centre

**Latest upgrade: [Conversational Windows agent — installation, permissions and limits](docs/MASTER_UPGRADE.md).** This extends the existing app with OpenAI structured tools, background jobs, recoverable document/project editing, Windows UI Automation, reviewed commands, a dedicated browser and screen review. It starts disabled. Existing dashboard and manual controls remain available.


**Computer access update:** [Windows instructions for drive access, file editing/backups/undo and customisation](docs/COMPUTER_ACCESS.md). Uses the existing programs and dependencies. New edit permissions start off; folders or whole drives can be approved explicitly.

JARVIS 2.0 adds saved schedules, proactive notices, editable shared memory, trusted file workflows, optional paid interruptible voice, and a separate signed SMS/phone gateway. **Existing tasks and the animated HUD are preserved.** Start with [the Windows upgrade and communication guide](docs/COMMUNICATIONS.md). Paid features remain off until configured and explicitly enabled.

The existing JARVIS application now has an **animated voice-first HUD** around its OpenAI chat, explicit memory and persistent tasks. Built with Python, Flask, vanilla JavaScript and SQLite. The dashboard, tasks, projects, local briefing and profile work without an API key. Real AI chat requires internet access, an OpenAI API key and API billing.

[View a screenshot of the HUD with sample data](docs/hud-preview.png).

## Hands-free conversation and a British voice

The same Python/Flask/JavaScript/SQLite stack and existing data are retained. Browser speech itself needs no extra paid audio service or frontend build. The new agent adds pinned Windows, document and browser libraries through requirements.txt; the Python/Flask stack is retained.

1. Use current Edge or Chrome at `http://127.0.0.1:5000`. Configure your existing backend OpenAI key and billing first (below).
2. Click the central **JARVIS core**. Read and accept the hands-free cost/privacy prompt, then allow microphone access in the browser. This initial consent is required.
3. Speak naturally. While **CONVERSATION ON · AUTO SEND** is visible, each final recognised phrase is submitted automatically. JARVIS replies aloud, then listens again. No Send press is needed between turns. Wait until LISTENING before speaking again; this is turn-taking, not full-duplex interruption. The microphone closes during speech output so JARVIS does not hear itself.
4. Click the same core again, press Escape or say **“stop listening”** / **“end conversation”** to stop. The core stays usable during a pending AI request. Stopping will not refund/cancel a backend request already sent; its reply may still appear as text, but it will not restart listening.
5. Conversation always starts off on page load. An error, page close or 30-minute session limit ends it. A normal recognition end or no-speech timeout restarts listening while the session is on. Background tabs can continue listening with this consent, but browser/OS restrictions may suspend recognition or speech; JARVIS is not an always-running Windows voice service.

**Costs/privacy:** hands-free speech automatically becomes a chat request using the existing paid OpenAI API, including the same task/memory/history context. The default daily cap remains 20 attempted AI requests. Local panel commands and Windows commands do not call OpenAI. Browser speech may send audio/text to browser/OS providers after consent. No raw audio is stored or sent to the Flask backend. This browser mode uses no OpenAI audio endpoint. Optional paid Realtime voice is separate; see the upgrade guide. No wake word or voice cloning is implemented.

The assistant is instructed to be a warm, composed British-English conversation partner with occasional dry humour and concise spoken answers. This is a style instruction, not a claim to reproduce a film actor's voice. Use Saved memory to explicitly save how you prefer to be addressed or the tone you like. **Settings → Voice & accessibility → Speech voice** lists actual voices exposed by your browser. Automatic selection prefers a British voice. Voice choice is saved in this browser; exact sound depends on the installed/provider voice.

If no British voice is available, on Windows open **Settings → Time & language → Speech → Manage voices / Add voices** and add **English (United Kingdom)** if offered. Restart the browser and choose a British voice in JARVIS. Windows editions and browsers expose different voices; if none is available, JARVIS clearly reports it and uses the system fallback. You can enable Speech/Read reply for typed messages independently; hands-free replies speak automatically unless you mute them.

The animated HUD retains live local clock/timezone, real saved task progress/deadlines, University tasks and focused panels for Tasks, Projects, History, Memory, Briefing and Settings. Planning now provides manually saved shifts, weekly calendar events, deduplicated notices and study suggestions; paid contact and background checks need their documented setup. Idle orbits are decorative; listening uses actual microphone RMS; processing follows the real pending request; speech animation follows speech events, **not measured output amplitude**. OS and manual reduced-motion preferences are respected. Text input always remains available. Space toggles conversation outside controls/text fields/dialogs; Escape stops it and closes the top dialog.

## Limited Windows computer controls

The same local Flask backend acts as the Windows bridge. It is **off by default**. On your Windows copy, open **Settings → Computer controls** and enable it. On Linux/cloud the UI reports that Windows execution is unavailable. No actions are executed during setup or automated tests.

As requested, **playback and volume commands are immediate** once enabled. **App/file/folder launches and browser searches need confirmation by default** (the Computer panel now supports explicit preapproval of approved targets/searches). A structured preview appears and is spoken in hands-free mode. Say **“confirm action”** or **“cancel action”**, or use the preview buttons. “Yes” alone never authorises an action. Previews expire after two minutes; a new action replaces an older pending preview. Confirmations are single-use and cannot be replayed. Actions interrupted by a backend restart are marked outcome unknown and never retried automatically.

| Say or type | Behaviour |
| --- | --- |
| `Open Spotify` | Confirm, then ask Windows to launch the registered Spotify app. Spotify must already be installed. |
| `Open Calculator` / `Open Notepad` | Confirm, then launch the known Windows system app. |
| `Next song` / `Previous song` / `Toggle playback` | Immediately send a Windows media key to the active media player. |
| `Set volume to 40 percent` | Immediately set Windows master volume and read back its value. Range 0–100. |
| `Turn the volume up` / `Turn the volume down` | Immediately change Windows master volume by 10 percentage points, bounded to 0–100. |
| `Search the internet for engineering study tips` | Confirm, then open a Google search in your default browser. |
| `Open my assignment` | Confirm, then open the exact item registered locally as `assignment`. |

**Media limits:** Windows chooses the active media player. These are not verified Spotify-specific controls, and JARVIS cannot report a song title or playback state. Put Spotify into use first. Explicit Spotify-only playback commands and plain play/pause requests return guidance rather than pretending to verify a state; use **toggle playback** if you intend a toggle. System master volume is not Spotify's per-app volume. Browser search opens results; JARVIS does not read results, click pages, navigate arbitrary applications, type into other programs or control windows. Those are future, separately scoped features.

To approve a file/folder/app:

1. In File Explorer, right-click the specific local item → **Copy as path**.
2. In JARVIS Settings → Computer controls, choose a short spoken name such as `assignment`, select its type, paste the path and click **Approve this target**.
3. Say **“open my assignment”**, then **“confirm action”** after the preview.
4. Inspect or remove approvals in the same panel. Removing approval cancels pending launches.

Approvals permit only that exact resolved item, not searching through or reading folders. Supported file types: `.txt`, `.md`, `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.csv`, `.png`, `.jpg`, `.jpeg`, `.gif`, `.mp3`, `.wav`, `.mp4`. Custom apps must be explicitly approved trusted `.exe` files. These manual opening controls do not execute scripts, shortcuts or arbitrary arguments. The optional Agent panel separately supports exact reviewed scripts and desktop interaction under its own permissions; see the upgrade guide. Approval never verifies an executable's trustworthiness; choose only apps you already trust. Built-in app aliases cannot be replaced.

Paths, approvals and recent execution records remain in SQLite; they are not added to model context. Local command history is displayed but excluded from AI history. There is no screenshot capture or credential/profile scanning. Trusted document reading and explicitly approved document summaries are available in the Computer panel. Launch success means Windows accepted the request, not that the application finished loading. Media success means the key was sent, not that a particular track changed. Failures and unknown results are explicit.

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
- **Saved memory:** add a preference, project note or useful fact using the explicit form. You can inspect, edit or delete each saved memory.
- **Explicit chat command:** `/remember I prefer studying in the morning` saves that fact locally, even without a key. This exact command does not call OpenAI. Ordinary chat, including “please remember this”, does **not** automatically save personal facts. Use the form or `/remember`.
- **Delete a memory:** click Delete in Saved memory and confirm. That saved row is removed. All earlier conversation is then excluded from future AI context to prevent old messages from reintroducing it. Earlier chat remains visible locally. Deletion cannot retract messages already sent to OpenAI, and does not erase text from the visible local chat log. If you later type the fact again, it can be sent again.
- Up to 50 memories of 500 characters each. Do not store passwords, keys or other secrets.
- Saved project memories are notes; they do not create new task categories. The existing University, Personal Life and Collinson Creative sections are unchanged.

**Model-generated suggestions do not execute actions.** A separate deterministic local router handles only the computer commands listed above, with their confirmation rules. The legacy chat model has no action tools. Enabling Agent switches natural chat to validated structured tools with the permissions and reviewed execution described in docs/MASTER_UPGRADE.md. Explicit local date-only task commands can create/reschedule a task. Calendar editing stays in Planning; document summaries/research and contact have separate approval controls. Paid voice has a bounded local command tool under the same permissions. It is instructed to distinguish saved facts from suggestions and ask when information is missing. AI can still make mistakes; verify advice. Task management remains in the existing UI.

The daily briefing remains a fast, free summary using fixed local rules. Voice uses browser features where supported, after consent. Saved shift scheduling and notices are implemented. External calendar integrations remain unavailable. The optional Agent panel adds bounded, reviewed GUI automation; see its guide for supported applications and limitations.

## Data sent to OpenAI

When you submit an AI message, including automatic voice submission during an enabled hands-free session, JARVIS sends:

- Your message and local computer date.
- Up to 100 task records, ordered with open tasks first, plus the total count and an explicit omitted count.
- Your saved memories and manually saved upcoming calendar occurrences.
- Up to the last 12 eligible AI messages as described above.

No OpenAI requests are sent just to check configuration. Explicitly approved paid voice streams microphone audio and context to OpenAI; approved summaries send extracted document text, and research sends your search question. See docs/COMMUNICATIONS.md for channel-specific limits and privacy. Browser voice services may make their own requests only after you enable voice; they are separate from the backend chat integration. Legacy demo messages, local memory confirmations and local computer command exchanges are not sent as conversation history. In legacy mode, approved target paths and action records are not added to AI context. Agent mode additionally shares its permitted tool observations and inspectable recent workflow metadata; file text and screenshots have separate sharing controls. Tasks and memories are user data, not instructions. No API key is sent to the browser. The SDK has a 40-second timeout, automatic retries disabled, and an 800-output-token ceiling for legacy chat (1,400 for each agent model step). Extremely long answers may fail the completeness check; no partial reply is saved.

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

`data/jarvis.db` contains tasks, messages, settings, memories, local request counts, explicit computer approvals and recent action records. Back it up while JARVIS is stopped. Database files, virtual environments and `.env*` files are excluded from Git. `.env` files are **not loaded**; use Windows environment variables. This single-user local app has no login or encryption and must not be publicly hosted. It binds only to `127.0.0.1`, validates local Host headers and protects writes with a session CSRF token.

Run offline tests from the project folder:

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Linux/macOS equivalent: `.venv/bin/python -m unittest discover -s tests -v`.

Tests use temporary databases and mock HTTP transport through the actual OpenAI SDK. They do not use your key, call OpenAI or charge money. They cover existing dashboard/task behavior, upgrades from Milestone 1, persistence, explicit memory/deletion, outbound context, spending guards, missing keys, rate limits, invalid models, network timeouts and safe error handling. Live model access still needs your configured key and billing on your PC. The 33 Python tests cover the backend, including Windows action previews, validation, expiry, cancellation, duplicate prevention and execution failures through a mocked adapter.

The optional developer browser suite is `tests/hud_browser.cjs`. It uses Playwright/Chromium, which are **not application dependencies** and do not need installing on your Windows PC just to run JARVIS. Run it against a disposable database, never your personal one. In a Linux developer environment with Node, Playwright and Chromium already available:

```sh
.venv/bin/python -c "from jarvis import create_app; create_app('.ui-check/hud-test.db').run(host='127.0.0.1',port=5010,debug=False)"
# In a second terminal:
JARVIS_TEST_URL=http://127.0.0.1:5010 JARVIS_TEST_CHROMIUM=/usr/bin/chromium node tests/hud_browser.cjs
```

The browser suite exercises task and memory controls, settings, local commands, responsive layout, reduced motion, real pending/error UI, permission consent/denial and audio cleanup. Recognition and speech services and paid API responses are explicitly mocked; the browser microphone analyser uses a simulated audio device. No paid API, real speech service or actual Windows action is called.

On Windows, manually verify: click the core → consent → allow the microphone → speak → hear the response → speak a second turn without pressing Send. Turn the core off during a reply and verify listening stays off. Check a British voice, permission denial and Escape. Enable computer controls, ask to open Notepad, cancel once, then request it again and confirm. Try an approved test document, a browser search, next song with Spotify active and a modest volume setting. Actual Windows/Spotify/device behaviour cannot be verified on the Linux cloud machine; those tests mock the adapter. Existing tasks, history and memories should match your saved data.

## Architecture

- `app.py`: local entry point; Flask debug disabled.
- `jarvis/__init__.py`: existing dashboard/task/settings routes and app factory.
- `jarvis/storage.py`: SQLite schema, additive migration and first-run sample data.
- `jarvis/assistant.py`: chat and explicit memory endpoints; serializes assistant/memory changes.
- `jarvis/ai.py`: backend configuration, bounded context, daily cap and official API integration.
- `jarvis/templates/index.html` and `jarvis/static/style.css`: original vector HUD, responsive layouts and focused workspace dialogs.
- `jarvis/static/app.js`: existing task/chat/memory/settings UI with local panel commands.
- `jarvis/static/hud.js`: state-driven rings, clock, live task metrics, consent and keyboard controls.
- `jarvis/computer.py`: deterministic commands, local approvals and single-use confirmation state.
- `jarvis/windows.py`: limited Windows launch/media/Core Audio adapter using Python standard-library APIs.
- `jarvis/static/conversation.js`: opt-in hands-free session and turn loop.
- `jarvis/static/computer-ui.js`: approval, preview and action history controls.
- `jarvis/static/voice.js`: browser recognition, microphone analyser, speech output and cleanup. All application output is rendered as text, not unsafe HTML.
- `tests/`: offline regression and SDK integration tests.
