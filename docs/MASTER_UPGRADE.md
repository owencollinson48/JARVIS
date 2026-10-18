# Conversational Windows agent: upgrade and use

This extends the existing JARVIS application inspected at commit `23603c8`. Python, Flask, SQLite, the animated HUD, tasks, planning, explicit memory, browser speech, paid voice and optional communications are retained. There is no replacement frontend or database. New SQLite tables are added without deleting existing records.

The **Agent** panel connects normal conversation to OpenAI's official Responses API and validated function tools. The model receives your objective, chooses inspection/action tools, observes their results and can take further steps. Different phrasing goes to the model unchanged; no exact command vocabulary is required in agent mode. Model decisions can still be wrong. Ambiguous files or objectives may need clarification.

## 1. Update your Windows copy

1. In the JARVIS command window press **Ctrl+C**. Stop any optional JARVIS worker/gateway too. Close the dashboard tab.
2. In File Explorer copy your whole working JARVIS folder and paste it beside the original. Rename the copy `JARVIS-backup-before-agent`. Check it contains your `data` folder. Keep this backup.
3. Get the latest source from [your repository](https://github.com/owencollinson48/JARVIS) using **Code → Download ZIP → Extract All**. Open the extracted folder containing `app.py` and `requirements.txt`. Copy its contents into your **existing working folder**, allowing replacement of application files. Keep your existing `data` and `.venv` folders. Do not delete them. The source ZIP contains neither your database nor your API key.
4. Open Command Prompt in the working folder. For your previously reported location, enter this complete command:

   ```bat
   cd /d "C:\Users\owenc\Downloads\JARVIS-main\JARVIS-main"
   ```

   If you moved the folder, use its actual address instead. Check with `dir app.py` and `dir requirements.txt`. Windows may hide `.txt` and display the file as `requirements`.
5. Update the existing environment and start JARVIS, one command at a time:

   ```bat
   .venv\Scripts\python.exe --version
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   .venv\Scripts\python.exe -m pip check
   .venv\Scripts\python.exe app.py
   ```

   Use your installed **Python 3.13 x64**, rather than the earlier 3.15 ARM64 environment that Windows blocked. If `.venv\Scripts\python.exe` is missing, create it with `py -3.13 -m venv .venv`, then run the install commands above. If an existing environment still reports 3.15, preserve it under an unused backup name before creating the 3.13 environment. Do not rename an environment that does not exist.
6. Keep Command Prompt open. Open the dashboard at `http://127.0.0.1:5000` and press **Ctrl+F5** to load the updated scripts.

The added packages provide Windows UI Automation, mouse/keyboard control, system metrics, Playwright, screenshots and document editing. Windows-specific packages have Windows-only installation markers. Microsoft Edge must already be installed for the dedicated browser. The update does not install system software, change security settings or require administrator access. Leave Smart App Control enabled; a blocked dependency needs diagnosis using its exact filename.

**Every later start**, from the same working folder:

```bat
.venv\Scripts\python.exe app.py
```

## 2. Configure API billing before enabling the agent

If your existing OpenAI chat works, reuse its backend configuration. Otherwise:

1. Create a dedicated API project and key at [OpenAI Platform](https://platform.openai.com/). A ChatGPT subscription does not include API credit.
2. Review [current pricing](https://openai.com/api/pricing/) and the project's billing/usage settings. Set a small project budget and usage alerts, restrict model access and monitor usage. A budget alert is not necessarily a hard spending cutoff.
3. In Windows search **Edit environment variables for your account**. Under **User variables**, add `OPENAI_API_KEY` with your private key. Never paste it into JARVIS chat, source code, screenshots or Git.
4. Close/reopen Command Prompt and restart JARVIS. `OPENAI_MODEL` defaults to `gpt-4.1-mini`, a supported tool/vision-capable model. The SDK uses the official API endpoint. The backend key is never sent to browser code.

The existing `JARVIS_AI_DAILY_LIMIT` defaults to **20 attempted backend AI calls per local day**. Each agent model step consumes an attempt, including failed attempts. A complex objective can consume several attempts. There are also per-task limits: normally 12 model steps, 30 tool calls and a 15-minute wall deadline; the panel allows up to 24 steps and 60 tools. Limits do not guarantee a currency cap. No automatic provider retries are made; a timed-out request might still be billed.

## 3. Enable computer access deliberately

1. Open **Settings → Computer controls** and enable Windows controls.
2. Open **Computer → Trusted folders**. Choose an ordinary test folder first, give it a short name such as `engineering`, and grant read/edit/move permissions as needed. Existing folder permissions are honoured.
3. Open **Agent**. Enable the conversational agent, review the permissions and tick the paid-usage acknowledgement. Click **Save agent permissions**. It starts disabled, so updating alone cannot begin computer actions or paid requests.
4. For the requested wider access, you can explicitly select **Allow accessible Windows drives under my account**. The agent then sees drive aliases such as `account_c`, under your current Windows permissions. Credential locations and private-key files remain excluded. Protected folders, network shares and inaccessible files are not unlocked. Searches are bounded, rather than a complete disk index.
5. Leave ordinary file sharing off initially: extracted text/cells need specific approval before going to OpenAI. Enable **Allow ordinary approved file text/cells to be shared with OpenAI** only if you want ordinary document reading to proceed automatically. Potentially financial files still require review; screenshots always require a local preview and approval.
6. In **Planning**, check your timezone. Relative dates and “yesterday” searches use the configured local clock, not guessed dates.

| Permission | Behaviour |
| --- | --- |
| Level 1: automatic ordinary actions | Inspect/search approved locations, create supported documents, open known applications/documents, control windows, media and master volume, public browsing and supported settings-page navigation. |
| Level 2: automatic with recovery | Edit existing supported files, patch project source, copy/move/rename files and organise explicitly observed files, retaining backups or inverse paths. |
| Level 3: explicit review | Every script/command, software install/uninstall, generic desktop clicks/typing, uncertain browser submissions, screenshot sharing and sensitive sharing. Review the exact arguments/code/image and tick the checkbox before approval. |

Turning off Level 1 or Level 2 adds review to those actions. An approval is single-use, expires after five minutes and is bound to the exact action and permission configuration. The model cannot approve itself. A page or document telling JARVIS to change permissions is untrusted content, not your instruction.

Generic GUI actions always need review because their actual effect cannot reliably be inferred from an accessibility label. Password/payment/verification fields and Windows security prompts require your own input. There are no built-in permanent-delete, drive-format, partition or security-disabling tools. Reviewed scripts run as your user and **are not sandboxed**: inspect their code carefully. No elevation or UAC bypass is implemented.

## 4. Talk normally and inspect actual progress

Type in the usual HUD/chat input, speak through the existing voice controls, or use **Agent → Give JARVIS an objective**. For example:

- “Could you get my engineering project ready and chuck Spotify on?”
- “Find the Python script I edited yesterday, inspect it and suggest a fix.”
- “Change that heading in my report, keeping the formatting.”
- “Put these assignments into a new folder.”
- “Compare these two text files.”
- “My computer is slow. Check what's using the CPU and memory.”

JARVIS can inspect files, make targeted edits and propose/run a test after exact-command review. It must observe results before reporting success. App launch acceptance, a click sent or a page loaded is labelled as such; it is not proof that playback, a submission or an entire workflow completed. Media controls act on Windows's active media player, which may be an app other than Spotify.

Jobs run in a background worker while the Python app stays open. You can continue chatting, see the current tool, inspect each job's activity, approve a pending action or cancel it. One worker serialises desktop/browser operations; a task waiting for approval allows another queued task to run. Up to five jobs may be active. Closing the browser stops browser voice but does not stop backend jobs. Completed jobs do not restart automatically after a process restart; interrupted jobs are marked for inspection.

**Recent workflow context** shows recent file references and the last objective. Clear it there; edit/delete personal facts and preferred applications in **Memory**. Clearing context starts a fresh eligible AI history boundary while leaving visible conversation history intact. Task logs can be deleted separately. Backups remain local until you remove them yourself. Remembering recent activity is optional; inferred personal facts are not silently saved as explicit memories.

Optional browser completion notifications require the panel's button and browser permission. Existing Planning/proactive notices and the optional worker remain configurable; the agent does not install an always-running Windows service or initiate unsolicited computer changes. The separate public phone/SMS gateway still cannot access private desktop/file/agent APIs.

## 5. What the adapters support

| Area | Implemented scope and practical limits |
| --- | --- |
| Files/projects | Approved roots or opted-in accessible drives; bounded filename/content/time search, UTF-8 text reading, version-checked writes and targeted patches, new folders, single-file copy/move/rename and batches up to 25. No overwrites on moves/creation. Known installed/approved VS Code can open a project without running it. |
| Word | DOCX text replacement across supported body/table runs, named paragraph styles and new documents. Preserves supported run formatting; rejects ambiguous replacements and unsupported field/hyperlink layouts. Not full Word layout automation. |
| Excel | XLSX explicit sheet/cell updates and new workbooks; styles retained where supported. Formula-like input needs review. Macros and complex workbook features are not supported. |
| PDF | Extract text, create a simple text PDF, add a text overlay or rotate a page. No OCR, arbitrary existing-text replacement, layout reflow or secure redaction. Overlays do not remove underlying text. |
| Recovery | Original bytes in `data\agent-backups`, SQLite revision hashes, verified saves and restore with a new recovery record. Restoring refuses a newer/changed file. Completed moves record inverse paths; reversing them must pass current checks too. Back up the entire `data` folder, including existing `file-backups`. |
| Desktop | Visible-window discovery, focus/minimise/maximise/restore/close, observed UIA controls, reviewed click/type and reviewed coordinate fallback, keyboard/navigation and primary-screen vision. Some apps expose poor accessibility; secure desktops and JARVIS approval controls are excluded. |
| Browser | Dedicated visible Microsoft Edge profile in `data\agent-browser`, observed tabs/elements, public navigation, reading and reviewed form interaction. Existing signed-in browser tabs are not attached. Private/local addresses, downloads, service workers and WebSockets are blocked. This is a filtered browser controller, not a complete network security sandbox. |
| Commands/software | Exact Python/PowerShell/CMD scripts with interpreter and working-directory review; 30-second execution limit and bounded output. Explicit reviewed `winget` package-ID install/uninstall, user scope where supported. Licences, authentication, unsupported installers and UAC remain manual. A timeout is an uncertain outcome, not permission to retry. |
| Performance/settings | Actual CPU, RAM, disks, running-process metrics and startup-entry names; supported Windows settings pages open without claiming a setting changed. No automatic process killing, startup removal or security changes. |

Document inputs/outputs are capped at 10 MB. Extracted text is bounded and marked when truncated. Large text changes use exact-span patches instead of replacing a whole file from a partial read. Office libraries do not guarantee preservation of every advanced feature: check an important edited document in its native app. Originals are retained for recovery.

The backend screens common credential names/patterns before model sharing and rejects secret memories. This is not a perfect sensitive-data classifier. Treat document sharing and screenshot previews as real disclosure decisions. A screenshot is an image of your primary screen, not continuous surveillance; the approved image is deleted after use, cancellation or detected interrupted-job cleanup. Raw image bytes/base64 are not stored in conversation history. Abrupt crashes can leave local artifacts pending cleanup.

## 6. Voice and stopping

The existing central-core hands-free mode still listens, submits recognised speech, speaks and listens again. Select an available British English voice in Settings. It pauses listening during speech output. It depends on browser/OS support and is not an always-on wake-word service.

For interruptible paid voice, follow [the existing voice/API setup guide](COMMUNICATIONS.md) and set `JARVIS_REALTIME_ENABLED=1`. It retains `gpt-realtime` and Cedar, prompted for refined British delivery, without cloning an actor. With Agent enabled, its structured `agent_request` tool delegates the natural objective to the same backend worker and waits for its result; owner approval still happens on screen. The session has its own snapshot context. Restart voice after changing memories/permissions when you need a fresh snapshot.

Paid audio defaults to **180 seconds and two session attempts per rolling 24 hours**. Optional Windows User variables `JARVIS_REALTIME_SECONDS` (60–1800) and `JARVIS_REALTIME_DAILY_LIMIT` (1–20) change those limits after restarting all JARVIS processes. Longer sessions cost more. There is no automatic reconnect. Audio goes directly to OpenAI while active, so do not speak passwords or other secrets. Raw audio recordings are not saved by JARVIS.

Use **Emergency stop**, **Alt+Shift+S** while the dashboard has focus, or say/type **“stop everything”**, **“stop”**, **“cancel that”** or **“don't do that”**. The recognised stop path does not wait for an AI interpretation. Voice stop still depends on microphone/browser availability; use the visible button or shortcut if speech is unavailable.

Emergency stop disables the agent and computer controls, cancels queued/waiting jobs and stops known command subprocesses where possible. The dedicated browser closes after the current bounded operation returns. An API call already in flight may finish and be billed, but its late tool requests are discarded. A file save/click already completing cannot always be interrupted or reversed. Inspect activity and recovery records before continuing. Re-enable controls explicitly when ready. Turning off the microphone alone does not cancel background work.

## 7. Verification and first checks on your PC

Automated verification used disposable files and mocked model/native Windows adapters, with the actual OpenAI SDK serialization and SQLite job engine. It does not establish live-model accuracy, actual Windows app compatibility or a particular accent. No paid requests, real software installs, messages, calls or personal-file edits were performed during development.

Cloud results: **100 backend tests passed**, installed dependencies passed compatibility checks, Python 3.13 Windows x64 dependency resolution succeeded, and five browser suites passed (existing HUD, planning/communications, file editor, paid voice including agent delegation, and the new agent/approval interface). The normal `app.py` start and eight local JSON readiness endpoints were also exercised. Native Windows actions, actual microphones/voices and live paid-provider results still need the staged PC checks below.

Developer checks:

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

On Linux the command is `.venv/bin/python -m unittest discover -s tests -v`. A developer-only test exercises actual Chromium element handles against locally fulfilled fixture HTML; it skips if `/usr/bin/chromium` is absent. Optional `tests/agent_browser_server.py` plus `tests/agent_browser.cjs` exercise the real job/approval UI with fake providers. Those fixture servers must never replace `app.py` or be exposed publicly.

First use a new folder containing disposable TXT, DOCX, XLSX and PDF copies. Try finding a file, editing one line, inspecting the backup and restoring it. Open Notepad/Spotify, inspect a visible window, review one screenshot, navigate a public documentation page and test emergency stop during a pending approval. Check the native documents after edits. Only widen access once these work on your PC. If something fails, report the displayed error and exact blocked filename; do not send your key or private document contents.
