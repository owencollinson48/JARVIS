# JARVIS 2.0 — Windows setup and first checks

This extends the existing Flask/Python/SQLite/vanilla JavaScript app. Keep your current folder and `data\jarvis.db`. No new desktop program replaces anything you already use. New Python packages install into your existing `.venv`.

## 1. Update safely

1. Stop the app, phone gateway and background worker with **Ctrl+C**. If you previously installed the JARVIS scheduled task, temporarily disable **JARVIS-ApprovedChecks** in Windows Task Scheduler.
2. In File Explorer, copy your entire JARVIS folder to a backup folder you choose. The database is `data\jarvis.db`; do not replace it with someone else's database.
3. Download the current repository ZIP from https://github.com/owencollinson48/JARVIS/archive/refs/heads/main.zip and **Extract All**. Copy its application files into your existing project folder, replacing the old code. Keep your existing `data` and `.venv` folders. Do not run from the ZIP.
4. Open your existing project folder in File Explorer. Click its address bar, type `cmd`, then press Enter. The prompt should end in your actual JARVIS folder, not `C:\>`.
5. Run these commands, one at a time:

```bat
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe app.py
```

Open **http://127.0.0.1:5000** in Edge or Chrome. Later, the start command is simply `.venv\Scripts\python.exe app.py`, from this same folder. Press **Ctrl+C** to stop. Do not turn off Smart App Control; using Python directly avoids depending on the batch launcher.

## 2. Features you can use without new paid services

- **Planning**: click **Use browser timezone**, check it is correct, save preferences, and add actual shifts/classes/study/personal events. Weekly recurrence needs an end date within one year. Work hours deduct your saved unpaid break. Dates that are ambiguous/nonexistent during clock changes are rejected; use a different unambiguous time or supply an explicit offset through the API.
- Proactive checks default on, every 15 minutes, quiet 22:00–07:00 in your saved planning timezone. Equal quiet start/end disables quiet hours. Checks deduplicate saved overdue/deadline/shift/conflict notices and group summaries into morning/evening briefings. The interface refreshes each minute; unchanged snapshots honour the selected interval. No external calendar or employer portal is connected. Study slots are **suggestions based on saved events**, not a claim that your entire diary is known.
- **Memory**: inspect, edit or delete explicit facts/preferences. Nothing learns your routines silently. Editing/deleting starts a new AI history boundary to prevent stale chat from reintroducing the old fact on later requests. Existing active voice sessions have an earlier snapshot: stop and restart them after changing memory.
- Explicit task phrases work without AI: `Remind me to revise engineering maths tomorrow`, `Move it to Friday`, or `Move task 12 to 2026-11-20`. A weekday means its next occurrence (next week if today). This creates/changes a **date-only task**, not a time-specific alarm. Task IDs are included in local confirmations. If the current task reference is ambiguous, JARVIS asks for a task number. Desktop, SMS and telephone use the same owner database. No general free-form task editing is silently inferred.
- **Computer**: approve only folders you want searched. Choose read/move permissions separately. Search returns filenames, sorted newest first, with bounded results; reading is local. Open previews need confirmation. File moves remain within one trusted folder, never overwrite, and need confirmation. To undo, preview a reverse move. Existing source/destination folders must be on a filesystem supporting hard links; unsupported filesystems return an error rather than falling back to a risky overwrite.
- **Settings → Computer controls** still enables the Windows driver. The Computer panel can preapprove opens of already approved applications/files and fixed browser searches. Playback/media and Windows master volume remain immediate. Windows selects the active media player; this does not verify Spotify-specific song changes. Named workflows contain 1–8 approved open/search/media/volume commands. Check **Preapprove** only when you want those exact steps to run without another question. Each step checks current permission; changing roots/workflows cancels old previews. If a workflow stops midway, earlier steps may already have happened: inspect the log before repeating it.
- Documents: UTF-8 TXT/MD/CSV, text PDFs up to 50 pages, DOCX, at most 5 MB and 20,000 extracted characters. Truncation is shown. Scanned PDFs need OCR, which is not implemented. Reading grants no permission to send content externally; summarising requires a separate explicit approval and your existing OpenAI key.
- **Emergency stop** stops browser audio, disables computer commands/proactive checks/SMS/calls, cancels pending previews/contact jobs and requests hangup of known active calls and paid voice sessions. It cannot recall messages or undo an already completed action. Any failed provider stop is reported; use the provider console to end that call. Re-enable only the permissions you want afterwards.

No unrestricted mouse/keyboard control, credentials handling, banking, purchasing, deleting files, security changes or arbitrary shell execution is implemented. Browser search opens results in your current default browser; it cannot read your authenticated browser tabs. Optional approved research uses OpenAI web search and returns cited links instead.

## 3. OpenAI key, voice and costs — read before enabling

Your existing text-chat key still works. A ChatGPT subscription does **not** include API credit.

1. Visit https://platform.openai.com/ and create a dedicated API project and key. Keep the key private. Never paste it into chat, browser code, a screenshot, Git or this document.
2. Check https://openai.com/api/pricing/ for current text, **Realtime audio**, transcription and web-search tool pricing. Audio tokens and search tools are additional billable usage; costs vary with conversation length. No price is hard-coded here.
3. In OpenAI project billing/limits, set a small monthly budget and email thresholds; start with small prepaid credit and keep automatic recharge off if that suits your budget. Provider budget notifications may be alerts rather than hard stops; check the current account controls. The app's request/session guards are not a guaranteed currency spending cap.
4. In Windows Start, search **Edit environment variables for your account** → **Environment Variables** → **User variables → New**. Set `OPENAI_API_KEY` to your private key. Do not put it in application files. Existing `OPENAI_MODEL` defaults to `gpt-4.1-mini`; `JARVIS_AI_DAILY_LIMIT` defaults to 20 attempted backend AI requests per day, including failed attempts. Set 0 to stop new backend AI starts/research requests. Existing live audio must be stopped separately.
5. Close/reopen Command Prompt after changing variables, then restart JARVIS. Never print or share variable values. Environment variables are private configuration, not an encrypted secret vault; other programs under your Windows account may be able to access them.

The original central-core browser voice remains available. Its quality depends on the installed/online Windows/browser voice; choose an English UK voice in Settings. It listens, submits a phrase, speaks, then listens again. It does not listen during its own speech. Browser recognition may use the browser provider's network service after your consent.

For **natural interruptible paid voice**, add User variable `JARVIS_REALTIME_ENABLED` with value `1`, restart JARVIS and open **Phone & SMS → Natural desktop voice → Start paid voice**. It uses official OpenAI Realtime (`gpt-realtime`) with **Cedar**, prompted for refined male British delivery. This is an original synthetic voice, not a cloned actor. Tone/accent and latency need listening checks on your PC; neither is guaranteed by a prompt.

The start dialog explains audio/context sharing and fees. One button starts/stops this mode. It streams microphone audio directly to OpenAI over WebRTC while active; interruptions use server voice detection. A three-minute client timer and backend hangup timer limit normal sessions; two session attempts per rolling 24 hours, 600 output tokens per response, and 12 local tool calls per session. No automatic reconnect/retry. If the backend process is killed, its timer cannot run; client shutdown normally disconnects media. The optional worker also closes expired known sessions after restarts. Monitor your provider usage; these controls do not replace billing controls.

Paid voice can request the same bounded local commands and explicit date-only task commands through a backend tool. It cannot approve its own action preview: use the on-screen confirmation. Transcripts and tool confirmations are stored in the same SQLite history. Transcripts are machine-generated and can contain recognition errors. Model context is a snapshot at session start plus that conversation; restart to pick up changes from another channel. No raw audio recording is written by JARVIS. Text summaries and web research require their separate approval buttons. Set `JARVIS_REALTIME_ENABLED=0` and restart to disable new paid voice sessions.

## 4. Twilio fees, verified number and spending controls

SMS/calls remain **off** even when environment variables exist. No actual SMS/call was sent during development tests.

Before signing up or enabling:

- Check https://www.twilio.com/en-us/sms/pricing and https://www.twilio.com/en-us/voice/pricing for **your destination country**. Number rental, outbound/inbound SMS segments, carrier fees, calls by duration, taxes and applicable registration fees can apply. Inbound SMS can cost money even when JARVIS declines to reply.
- Calls additionally use **Twilio ConversationRelay** speech recognition/TTS and OpenAI text responses: see https://www.twilio.com/en-us/voice/conversationrelay and its current pricing. Enable a supported **Google English UK** voice for your account/region. Caller ID uses your Twilio number; displaying the name JARVIS is carrier/registration dependent, not guaranteed.
- A public HTTPS/WSS endpoint or tunnel may have separate hosting/subscription costs. No tunnel subscription is included. Trial accounts restrict destinations and may play a trial announcement; registration/verified-number requirements vary by country.
- In Twilio Console, restrict messaging/voice geographic permissions to the destinations you need, verify your own recipient, set small billing/usage notifications and review auto-recharge. See https://www.twilio.com/docs/usage/api/usage-trigger for usage-trigger options. A Twilio alert alone is **not a hard spending limit**. Set app SMS/call caps conservatively, monitor the Console and disable the channels if needed. No program can promise a provider currency cap based solely on a message count.

Create these **Windows User environment variables**, using real values only on your PC:

| Name | Value |
| --- | --- |
| `TWILIO_ACCOUNT_SID` | Your account SID from Twilio Console |
| `TWILIO_AUTH_TOKEN` | Your private Twilio auth token; used for API and webhook signature validation |
| `TWILIO_FROM_NUMBER` | Your purchased SMS/voice-capable Twilio number, `+` country code and number |
| `TWILIO_ALLOWED_NUMBER` | **Your own verified mobile number**, same international E.164 format |
| `JARVIS_PUBLIC_URL` | Your stable public HTTPS origin, for example `https://your-jarvis.example.com`; no path |
| `JARVIS_PHONE_VOICE` (optional) | Default `en-GB-Neural2-B`; choose a Google UK male ConversationRelay voice supported by your Twilio account |

The fixed allowed recipient is backend configuration; the browser and AI cannot supply arbitrary phone numbers. Changing it requires updating environment variables/restarting and reviewing consent again. Do not paste credentials into this repository. The app does not automatically load `.env` files.

## 5. Separate secure phone gateway

Keep the desktop UI bound to **127.0.0.1:5000**. **Never tunnel or reverse-proxy that desktop port.** Only `phone_gateway.py`, bound to **127.0.0.1:5002**, should receive public phone traffic. Its app rejects every desktop/API/static route, even if a proxy rewrites the Host header to localhost. Public callbacks require a valid Twilio signature and the expected account/phone numbers. Do not disable signature validation to make a tunnel work.

In a second Command Prompt in your project folder:

```bat
.venv\Scripts\python.exe phone_gateway.py
```

This supplies the local gateway for an initial personal test. Configure your chosen HTTPS/WSS tunnel or reverse proxy to forward **only `/telephony/` paths to 127.0.0.1:5002**, preserving the complete path and query. The external origin must exactly match `JARVIS_PUBLIC_URL`, including its hostname and any nonstandard port. WebSocket upgrade support is required for `/telephony/relay`. If the tunnel hostname changes, update that variable, restart all processes and update Twilio webhooks. Network access to `api.twilio.com` and `api.openai.com` is needed; browser WebRTC must also reach OpenAI's media endpoints. Do not expose your LAN, trusted folders or the desktop UI. Running the gateway doesn't itself install a tunnel or configure DNS/TLS/firewall rules. The included Flask listener is a development server: before permanent public operation, deploy this **gateway-only app** behind a hardened, WebSocket-capable service/reverse proxy. Never forward desktop routes as a workaround.

In Twilio Console → your phone number → Messaging, set **A message comes in** to:

```text
https://YOUR-EXACT-HOST/telephony/sms
```

Choose **HTTP POST**. Outbound SMS status and outbound voice/status URLs are set by the app. Calls are outbound to your verified number only; inbound phone calls are not implemented. Outbound voice connects to `/telephony/voice` and then `/telephony/relay`. Do not configure your incoming-call webhook as an outbound call route.

In the local JARVIS UI, open **Phone & SMS**:

1. Confirm the recipient is your verified number and tick explicit consent.
2. Start with **1 SMS/day**, calls off, and **no automatic categories**. Save.
3. Draft a short SMS, inspect it, then **Approve this contact**. This is the first deliberate paid delivery test. `queued` means Twilio accepted it; only signed `delivered` confirms SMS delivery. Check the Console and your phone.
4. Reply with a simple task instruction. The shared DB should update; inspect History and Tasks. Replies may be truncated to one Unicode SMS segment (60 UTF-16 units; full history stays local). Provider STOP/unsubscribe rules can add their own handling/charges. Incoming `STOP` also disables JARVIS SMS/calls and cancels pending contact jobs when Twilio forwards it. A disabled channel/quiet hours/quota yields no AI reply, although the provider may still charge for inbound delivery.
5. Only after checking costs, enable calls with **1/day, 60 seconds**, draft a call, then explicitly approve it. Answer, try a question and `Move task 12 to Friday`, interrupt, and say `Goodbye` to end. A call is never recorded by this code. Ten user turns per call and provider duration limits apply. Provider speech processing still occurs under its own privacy policy.
6. Approve automatic SMS categories individually if desired. Saving those categories is advance permission for matching saved notices. Calls are never automatically triggered by categories: each call reminder needs its own approval. Quiet hours defer due contact; reminders over two hours late become **missed**, so they are not unexpectedly delivered the next day. Request failures/timeouts become **unknown**, never retried automatically because the provider might already have accepted them.

Free-form AI SMS replies acknowledge the incoming webhook immediately and prepare the reply in a background thread, then dispatch a fixed-recipient outbound SMS using the already reserved quota. This avoids waiting for AI inside the provider’s shorter HTTP deadline. Local task commands can reply directly. Keep the gateway process running; if it is terminated while preparing a reply, the claimed request is not replayed automatically.

Duplicate incoming SMS IDs are claimed before processing, so provider retries cannot repeat a task mutation or AI charge. A timeout after that claim may lose the reply instead of repeating it. Multiple recent reminder subjects clear the ambiguous `it` reference; say the task number to resolve it. Live call text streams through ConversationRelay; microphone interruptions suppress stale output. Remote phone/SMS requests have no Windows computer-control tools. Shared memory is sent as context, but edit/delete it in the desktop Memory panel. Changing saved memory cannot retract data already sent to a provider.

## 6. Checks with the browser closed

The PC must remain on. In another Command Prompt:

```bat
.venv\Scripts\python.exe task_worker.py
```

Keep this process running for notices and due approved contacts. To perform one check only:

```bat
.venv\Scripts\python.exe task_worker.py --once
```

To install a limited-permission Windows task that runs one check every five minutes:

```bat
.venv\Scripts\python.exe install_scheduler.py
```

This is an explicit installation you run; tests do not install tasks. It does not overwrite an existing task and does not enable paid channels. The script uses this project's Python executable and absolute worker path, so keep the project at its current location. Windows Task Scheduler → **JARVIS-ApprovedChecks → Properties** shows the actual sign-in/availability conditions; the default non-admin setup runs in your current user context. It won't wake or turn on the PC automatically. New environment variables require reopening terminal sessions; a sign-out/sign-in may be needed for an existing scheduler service context.

To pause background work, right-click that task → **Disable**. To remove it, use Task Scheduler → **Delete** for **JARVIS-ApprovedChecks** only. Re-enable the task after updating/backing up. Do not run duplicate continuous workers; database claims prevent repeat sends but multiple processes waste checks. Gateway availability is additionally required for SMS replies and live phone calls. Closing all Python processes prevents live service. This is not an always-on hosted assistant.

## Verification and remaining manual checks

Automated Python tests use temporary databases and fake providers; browser tests use Chromium, a disposable DB, mocked speech/Windows drivers and no paid API requests. They cover data migrations, existing tasks, signed webhooks, fixed recipient, quotas, uncertain outcomes without retries, SMS deduplication, cross-channel task changes, file boundaries/no overwrite/reversal, permission revocation, workflow approvals, paid voice SDP serialization through the actual OpenAI SDK, transcript deduplication and emergency cancellation.

You still need to verify on your Windows PC: the chosen voice's actual sound/accent, interruption quality, recognition, Spotify/media keys, audio output and actual OS file/application launches. Live OpenAI/Twilio access, number verification, regional rules, billing, secure public TLS/WSS routing and real delivery/calls remain unconfigured until you complete their setup. API credentials and public hosting are deliberately absent from Git and cloud tests. Status panels distinguish configured from connected, approved from sent, queued from delivered, and suggestions from saved actions.
