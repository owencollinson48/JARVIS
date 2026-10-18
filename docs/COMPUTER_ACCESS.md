# Broader computer access and local file editing

The new controls extend your existing JARVIS. They use your current Windows account, Flask, SQLite and JavaScript; no additional Python packages or desktop applications are needed. They can browse approved folders/drives, open supported files and approved applications, create folders/text files, edit text with previews/backups/undo, open websites, and open Windows customisation pages. They do not bypass Windows permissions, run arbitrary shell commands, or provide unrestricted clicking/typing through every application.

## Update your existing Windows installation

1. Stop JARVIS using **Ctrl+C**. Stop any JARVIS worker/gateway too, and temporarily disable its optional scheduled task if installed.
2. Copy your existing project folder as a backup, including `data`.
3. Download https://github.com/owencollinson48/JARVIS/archive/refs/heads/main.zip and use **Extract All**.
4. Copy the updated application files into your **existing** JARVIS folder, accepting replacement. Keep your existing `data` and `.venv` folders. In particular, copy the entire updated `jarvis` folder, not just `files.py`: routes, database migration, templates, JavaScript and command routing work together.
5. Open Command Prompt inside that existing project folder. Run:

```bat
.venv\Scripts\python.exe app.py
```

6. Refresh the JARVIS browser tab with **Ctrl+F5** to load the new controls. There are no new dependencies in this update. The database migration adds edit permissions and file revisions without replacing tasks, history or settings. The pinned dependencies and backend tests were also checked on Python 3.13.5 in Linux; actual Windows hardware and security behaviour still need your PC check.

## Give access to a folder or a whole drive

1. In JARVIS, open **Settings → Computer controls** and enable Windows controls.
2. Open **Computer → Trusted folders**.
3. Use **Choose a Windows location** to select a common folder or a drive, such as **drive c · C:\**. For OneDrive/redirected folders that are absent from this list, paste the real folder path from File Explorer. You can enter any existing local drive/folder manually.
4. Choose a short name. For example, use `computer` for `C:\`, or `docs` for your Documents folder. Other internal/external drives need their own approval. Network shares are not supported.
5. Select the permissions you want: local document reading, confirmed file moves, and/or **local text reading, editing and creation with confirmation**. Editing permission also permits loading the text into the editor. No new edit permission is granted automatically to old approvals.
6. Click **Save folder approval**. **Change permissions** fills the form for an existing approval; change its checkboxes and save. Removing/replacing a folder approval cancels pending actions.

Approving `C:\` is broad: it permits operations on supported items anywhere under that drive that your Windows account can access. Hidden/system folders may appear, but Windows can still deny access. A drive approval does not approve every executable: launch applications through their existing exact `.exe` approvals in Settings. Keep Windows security enabled and use your normal user account.

## Browse, edit, create and undo

1. In **Computer → Browse, edit & customise files**, choose an approved location.
2. Leave **Relative folder** empty to browse its root, or enter a path relative to it, such as `University\Assignments`. Click **Browse folder**. Up to 300 entries are shown; open a subfolder or use the existing filename search to narrow a large location. Filename search is also bounded rather than claiming to index an entire drive.
3. Use **Browse** to enter a child folder, **Parent folder** to go back, **Preview open** to open a supported file/folder, or **Edit text** to load a text file.
4. Make your text changes, then click **Preview text changes**. Review the diff. Close the panel and use the existing **Confirm action** button on the dashboard. Edits always require confirmation, even if preapproved opening is enabled. The diff also appears on the dashboard for text edits requested through chat.
5. To undo an edit, reopen **Computer → File revisions** (or click **Refresh revisions**), choose **Preview undo**, review and confirm on the dashboard. Undo is refused if the file has newer changes, the folder approval points somewhere else, edit permission was revoked, or the backup was altered.
6. To create something, enter a relative name under **Create a file or folder**. For example, first create folder `Notes`, then text file `Notes\plan.md`. Parent folders must already exist. Preview and confirm each change. Existing paths are never overwritten by creation.

Text editing supports UTF-8 TXT, MD, CSV, JSON, TOML, INI, YAML/YML, CSS, HTML, PY, JS and TS files up to **8,000 bytes**. PDF/Word/Excel files can be opened in their installed applications; their formatted contents are not edited by this plain-text editor. Binary/non-UTF-8/large files are rejected. File associations still determine how approved opens behave. Code-file editing does not automatically execute that code; script extensions are not added to the file-opening allowlist.

A preview makes no file changes. Confirmation rechecks the file's SHA-256 version, current root and permission before saving. If another program changes the file, reload and prepare a new preview. Existing CRLF line endings and a UTF-8 BOM are retained; the final saved size must still fit the limit. The editor preserves the basic file mode and atomically replaces file contents using a temporary sibling. It is intended for ordinary documents/configuration, not preserving every NTFS-specific stream, ACL or application-specific metadata. It is not a filesystem lock against every other running program; keep the same file closed in other editors during a save.

Original bytes are saved under `data\file-backups` with revision metadata in SQLite. Back up that folder together with `data\jarvis.db`. Backups and revisions remain local and are not automatically deleted. Undo restores an edit; creating a new file/folder has no automatic delete/undo action. Use File Explorer to remove a newly created item if needed. If you edit JARVIS's own source/configuration and prevent it from starting, restore the working application files from your project backup or downloaded ZIP while keeping `data`; the revision backup files remain available for manual recovery.

## Commands you can type or say

Here `docs` means the folder name you explicitly approved. Use `/help` and the Computer panel for controls. Existing hands-free browser mode can submit these commands; optional paid voice routes supported commands through the same backend gate and cannot approve its own previews.

| Request | Result |
| --- | --- |
| `open folder docs:University` | Preview opening a folder inside the approved root. |
| `open file docs:University/assignment.pdf` | Preview opening a supported file with its installed application. |
| `create folder docs:Notes` | Preview creating a folder. |
| `create text file docs:Notes/plan.md \| Revise engineering maths tomorrow.` | Preview creating a new text file with that text. |
| `replace text in docs:Notes/plan.md \| tomorrow \| Friday` | Preview one exact replacement. Old text must appear exactly once; otherwise use the editor. |
| `open https://open.spotify.com` | Open that HTTP/HTTPS website in your default browser under your opening rules. |
| `open windows themes` | Open Windows Themes settings. |
| `open windows background` | Open desktop background settings. |
| `open windows display` / `open windows sound` | Open those settings pages. |
| `open windows bluetooth` / `open windows apps` | Open Bluetooth / Installed apps settings. |

The `|` characters separate literal command fields; these are not shell pipelines. Include spaces around each `|`. For text containing separators, complex/multiline changes, or ambiguous filenames, use the editor. General free-form requests are not a promise that every application can be controlled. The model must not claim changes before the local action result. Text editing and opening commands themselves need no paid API; optional voice/AI services retain their existing billing rules.

**Preapproved opening** can remove repeated confirmation for already approved app/file/folder opens, websites, browser searches and supported settings pages. It never removes edit/create/move/undo confirmation. Opening Windows settings lets **you choose the change**; JARVIS does not pretend a colour, resolution or account setting changed just because it opened the page. These controls do not read browser tabs, sign in, purchase, post externally, change passwords, or disable security settings.

**Emergency stop** remains at the top of the dashboard. It disables computer controls and cancels pending file changes as well as the other existing pending actions. It cannot reverse an edit that already finished; use File revisions for that.

## Developer verification

Run `.venv\Scripts\python.exe -m unittest discover -s tests -v` from the project folder on Windows (Linux: `.venv/bin/python -m unittest discover -s tests -v`). Tests create temporary files and mock OS launches/provider calls. A pre-existing migration test now explicitly closes its fixture SQLite connection, avoiding Python 3.13 warnings and Windows file-lock cleanup problems.

The optional browser regression uses installed developer Playwright/Chromium, not a new application runtime requirement. From the repository on Linux, start `PYTHONPATH=. .venv/bin/python tests/file_browser_server.py`, then run `JARVIS_TEST_URL=http://127.0.0.1:5035 node tests/files_browser.cjs`. This developer-only listener uses `.ui-check` data and mocks Windows launches. Never use it as your real desktop server or expose it publicly. Normal startup remains `app.py` on localhost only. The existing public phone gateway continues to reject every private file route.
