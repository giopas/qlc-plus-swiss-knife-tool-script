# Security audit of Swiss Knife 3.9.7

Done on 21 October 2026 on the code of 3.9.6 (tag `v3.9.6`: about 42,000 lines of Python in `app.py`, `core` and `routes`, and 18,000 of JavaScript). The fixes are in 3.9.7. This is the second full audit; the first (v0.7.1) is in the CHANGELOG under 0.8.0.

## What Swiss Knife is, for this purpose

A program that runs on the computer of the person using it. It opens shows (`.qxw`), fixture definitions (`.qxf`) and library files that other people may have made, it writes new files next to them, it serves a page to a tablet on stage, it talks to Claude through a local MCP server, and it can update itself. It has no accounts and keeps no secrets.

**Who could attack it, and how**

| Attacker | Way in | What they would want |
|---|---|---|
| A web page the user visits while Swiss Knife runs | The browser can reach `127.0.0.1:5731`. Cross-site requests, or DNS rebinding (a name that points at 127.0.0.1) | Read shows and file paths, write files, quit or change settings |
| A person on the same network (the venue Wi-Fi) | The tablet server listens on all interfaces | Read files from the export folder |
| Someone who sends a show, a library file or a fixture definition | The file's content | Run script in the page, make the program read or write elsewhere, exhaust memory |
| Someone who controls a download | The update, the GitHub fixture fetch | Run their code, write outside the folder |
| A script or program already running as the same user | `127.0.0.1:5731` has no password | Not in scope: such a program already has the user's files |

## How the audit was done

1. Read the entry points: `app.py` (headers, Origin check, quit), every route that writes a path, the updater, the Stage Monitor server and its exported script, the MCP server and its folder list, the Library installer, the GitHub fetch helpers, the native pickers and every `subprocess`, `open`, `extract` and XML call.
2. Static scan with Bandit over `app.py core routes tools launchers packaging`, every finding looked at (table below).
3. Dependency check with `pip-audit` on `requirements.txt` (Flask 3.1.3, Werkzeug 3.1.9, Jinja2 3.1.6, MarkupSafe 3.0.4, itsdangerous 2.2.0, click 8.5.0, blinker 1.9.0): no known vulnerabilities on the audit date.
4. **Poisoned show test.** A copy of a corpus show in which every name, caption, path, model, mode and author (475 fields) is an `<img onerror>` that records its own field. The show is opened the way the page opens it, every one of the 21 screens is visited, the buttons that only read are pressed, the Show Paperwork preview is drawn with every section, and the exported Stage Monitor page is opened in a browser. This is now `tools/xss_probe.py`.
5. Probes of the running server: other Host names, other Origins, `Origin: null`, paths with `..`, symlinks and a directory listing on the tablet server, archives with escaping links, XML with entities.
6. A search of the repository for keys, tokens and passwords (none) and a look at the three CI workflows.

## Findings

Severity is the impact if it were used, with how likely that is in brackets. Every fix has a test in `tests/test_security_397.py`.

| # | Severity | Finding | Fix in 3.9.7 |
|---|---|---|---|
| F1 | Medium (low) | **No Host check.** The server answered to any Host name. A web page whose domain is switched to 127.0.0.1 (DNS rebinding) is then the same origin as Swiss Knife and can read every answer to a GET: the open show, its path, settings. Writes were already refused by the Origin check, because the rebinding page's Origin is not ours. | Every request must name `localhost`, `127.0.0.1` or `[::1]`, on port 5731. Anything else gets 403. |
| F2 | High (low) | **A script from a CDN, unpinned and with no integrity check.** `templates/index.html` loaded `gridjs` from `cdn.jsdelivr.net` (latest version, no `integrity`). That script would run in the app's own origin, with the whole API behind it, so whoever controlled that file could read and write the user's shows. It was also unused: no JavaScript calls Grid.js. It broke the rule that the page works offline. | Both tags removed. The Content-Security-Policy no longer names any outside host (`script-src 'self' 'unsafe-inline'`, `connect-src 'self'`, `font-src 'self'`) and adds `frame-ancestors 'none'` and `form-action 'self'`. A test fails if the page ever loads a resource from another host. |
| F3 | Medium (medium) | **The tablet server served the whole export folder to the network.** It is Python's `SimpleHTTPRequestHandler` on `0.0.0.0`: every file under the folder, with a directory listing, and symlinks followed. If the folder was a show folder or Documents, anyone on the venue Wi-Fi could browse and download it. | The server (in the app and in the exported `serve_stage.py`) answers `/` and `/index.html` only. Everything else is 404, no listing. It sends `nosniff`, `X-Frame-Options`, `Referrer-Policy` and a restrictive Content-Security-Policy. Folders exported before 3.9.7 keep the old script until the next export. |
| F4 | Low (low) | **Save routes wrote to any path.** *Save setlist…*, *Save slot file* and the dictionary save wrote a text file to whatever path the request named, replacing an existing file. A request from the page could overwrite, for example, a startup script. Only the page, or a program with no Origin, can call them (see F1), which is why this is low. | `core/safe_paths.py`: the path must be absolute, in an existing folder, not a hidden name, not a symlink or folder, and end in `.txt`, `.csv`, `.tsv`, `.md` or `.text` (or nothing); the dictionary also `.json`. A show, a script or a launcher can no longer be written this way. |
| F5 | Low (low) | **The updater's tar unpack did not look at symlinks.** It refused paths outside the folder and hard links, but not a symlink pointing out, so a later member could be written through it. Archives also had no size limit, and the download could start on any HTTPS host. The download is already checked against `SHA256SUMS` from the same release, and zip archives were already checked. | The tar check now covers symlinks (absolute or outside), device files and fifos, a 2 GB limit on the unpacked size (zip too), and `extractall(filter="tar")`. A download or feed must start on a GitHub host (set `QSK_UPDATE_FEED` for a test or your own mirror). |
| F6 | Low (low) | **`..` was accepted as a GitHub manufacturer name.** The pattern for the manufacturer in the GitHub fixture routes allowed dots, so `..` passed and the request went one folder up in the QLC+ repository. A trailing newline passed as well. | `gh_fetch.valid_component()`: letters, digits, space, `- _ . &`, no `..`, no slash or newline, a `.qxf` ending for files. Used by Quick Start and Cabling. The Brightness download also keeps only the base name. |
| F7 | Low (low) | **XML with entities was parsed.** Shows, definitions and profiles went through Python's XML parser. Current expat refuses the "billion laughs" expansion, but Swiss Knife also runs on older Pythons and expat builds, where a 1 KB file can use gigabytes. | `core/xml_safe.py`: a file that declares an entity is refused before it is parsed (QLC+ files never do), with a size limit (50 MB a show, 8 MB a definition). Used by every place that reads a show, a definition, a fixtures map or an input profile. The Library's page check already refused `<!`. |
| F11 | Medium (low) | **AppleScript text could be closed early.** On macOS the file dialogs are opened with `osascript`, and the text of the dialog (title, default name) was put into an AppleScript string after escaping only the quote. A text ending in a backslash and a quote closed the string, and what followed ran as AppleScript, which can run a shell command (`do shell script`). The texts come from the page, so this is reachable only by what can already call the API (see F1 and F8), and no screen sends such a text. | The backslash is escaped first and line breaks become spaces. A test reads the literal back the way AppleScript does. |
| F8 | Info | **Origin check hardening.** The old check removed `http://` and `https://` and compared the rest. It was correct for the cases tried (`null`, other sites, `localhost:5731.evil.example` all failed), but it was a string comparison. | A parsed check: the Origin must be http or https, a loopback name and port 5731. A request with no Origin is refused when the browser says it is cross-site or same-site (`Sec-Fetch-Site`). `curl` and scripts, which send neither, still work. |
| F9 | Info | Cross-origin isolation headers were missing. | `Cross-Origin-Opener-Policy` and `Cross-Origin-Resource-Policy: same-origin` on every response. |
| F10 | Info | Bandit B324 on a SHA-1 used to name a cache-busting query. | `usedforsecurity=False`. Not a security use. |

## Checked and found sound

- **No script injection from show content.** In the poisoned show test no payload ran and no injected element reached the page on any of the 21 screens, the Show Paperwork preview (all 16 sections, with the stage plot and the cabling drawing) or the exported Stage Monitor page. The payload text is visible as text on 14 screens, which shows the show data did reach them and was escaped. The 260 `innerHTML` assignments in the JavaScript are therefore escaping what comes from a file. Names in the cabling and stage plot SVG are escaped on the server.
- **The MCP folder list.** `Allowlist.check()` resolves symlinks (`realpath`) before it compares, new files are only written inside a listed folder as `_vN`, and the tools never overwrite. Folders can only be changed from the page (Origin and Host checked), not by Claude.
- **The Library installer.** File names come from a slug of letters, digits, `_` and `-`; the page check refuses a `<!` (DOCTYPE or entity); built-in ids cannot be taken.
- **The update.** HTTPS only, certificate checked (certifi or the system bundle), the archive is checked against `SHA256SUMS` before it is unpacked, the swap script quotes its paths, the previous version is kept until the new one starts.
- **Subprocesses.** The 13 calls in the program use an argument list, never a shell, with fixed commands (`osascript`, `open`, `xdg-open`, `ifconfig`, `ip`, the update swap script). The one place that builds text for another interpreter, AppleScript, is finding F11.
- **Responses.** Paths are stripped from error messages; a header value with a line break is refused by Werkzeug; no `eval`, `exec`, `pickle`, `yaml.load` or `shell=True` in `core`, `routes` or `app.py`; Flask debug is off and the server binds `127.0.0.1`.
- **Secrets.** None in the repository, the tests or the workflows.

## Bandit, before and after

| | Before (3.9.6) | After (3.9.7) |
|---|---|---|
| High | 2 | 1 |
| Medium | 26 | 22 |
| Low | 91 | 92 |

All of the rest were read. B110 and B112 (22 and 2 places where an error is passed over) are a choice not to break a screen for an optional extra and are not security findings. B404, B603, B606 and B607 are the subprocess calls above. B310 (`urlopen`) is HTTPS to GitHub, the local server, or a local file for a test feed. B314 and B405 (XML) are now behind `xml_safe` for outside files; what remains reads the app's own generated XML. B103 is the executable bit on scripts the app writes on purpose. B108 is a string comparison with `/tmp`, not a temporary file. B311 is a random choice of colours. The remaining High is B202 on the tar unpack, which is checked member by member above it (marked `nosec` with the reason).

## Risks that remain, on purpose

| Risk | Why it stays | What would change it |
|---|---|---|
| `script-src 'unsafe-inline'` | The screens use inline `onclick`. A file that could inject HTML would run script. The poisoned show test shows none does, but the policy would not stop one. | Moving the handlers to `addEventListener` and using a nonce. A large change, not a quick fix. |
| No password on `127.0.0.1:5731` | Another user on the same computer can use it. A shared computer is not the use case. | A random token per start, sent by the page. Worth it only if Swiss Knife is run on shared machines. |
| The tablet page has no password | It is for a tablet on a private hotspot at a gig, and it is read-only (it shows the cue and the cards). Anyone on that network can open it. | A PIN in the address, if users play on venue Wi-Fi. |
| QLC+'s own web port (9999) | Not Swiss Knife's: the page on the tablet talks to it directly. | QLC+ settings. |
| The updater trusts GitHub and its TLS | The checksum comes from the same release as the file, so it guards against a bad download, not against a changed release. The apps are not signed. | Signing and notarising the apps, or a pinned signature key. |
| Windows swap script | Paths with `%` or `&` in the install folder are not escaped for `cmd`. | A folder name like that is unusual; escape or use PowerShell if it is reported. |

## Repeating the audit

```
python3 -m pip install bandit pip-audit
bandit -r app.py core routes tools launchers packaging -q
pip-audit -r requirements.txt
python3 tools/xss_probe.py          # needs Playwright and a Chromium, like tools/shots.py
python3 -m pytest -q tests/test_security_397.py
```

The probe, the Bandit and pip-audit runs are advisory; the tests are part of CI.
