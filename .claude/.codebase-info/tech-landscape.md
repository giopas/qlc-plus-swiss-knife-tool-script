# Technology Landscape

*Last Updated: 2026-09-14*

## Source-of-Truth Files

| Information | File |
|-------------|------|
| Dependencies | `requirements.txt` |
| Version | `core/workspace.py` (`VERSION = "1.3.0"`) and `app.py` context processor |
| App config | `app.py` (`PORT = 5731`, CSP headers, CSRF) |
| Git ignores | `.gitignore` |
| Launcher scripts | `run.sh` (Unix), `launchers/QLC_Swiss_Knife.bat` (Windows), `launchers/create-macos-app.sh`, `launchers/qlc-swiss-knife.desktop` (Linux) |
| Session files | `.qsk` JSON files (user-created, not in repo) |
| Settings | `settings.json` (gitignored, stores user_name) |

## Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| Language | Python 3.x | Tested with 3.14 (venv) |
| Backend framework | Flask ≥ 3.0 | Only required dependency |
| Native window | pywebview ≥ 5.0 | Optional — falls back to browser |
| Frontend | Vanilla JavaScript (ES6+) | No build step, no bundler |
| UI tables | Grid.js | Loaded from jsdelivr CDN |
| Templates | Jinja2 (via Flask) | Single template: `templates/index.html` |
| CSS | Custom (`static/css/style.css` + `tokens.css`) | Dark/grey/light theme via `data-theme` |
| XML parsing | `xml.etree.ElementTree` (stdlib) | QXW + QXF files |
| PDF generation | `zlib` + `datetime` (stdlib) | Hand-built PDF stream in `core/pdf.py` |
| HTTP client | `urllib.request` (stdlib) | GitHub API calls only |

## Infrastructure

- **Hosting:** Runs locally only (`127.0.0.1:5731`). No deployment, no cloud.
- **CI/CD:** None. Manual releases via git tags + GitHub.
- **Issue tracking:** GitHub Issues with templates (`bug_report.md`, `feature_request.md`).
- **Wiki:** Separate git-tracked `wiki/` directory (GitHub wiki pages, gitignored from main repo).
