# Communication

*Last Updated: 2026-09-14*

## Internal API

All frontend ↔ backend communication is via `fetch()` to `localhost:5731/api/*` endpoints returning JSON. File downloads (PDF, CSV, QXW) return binary with appropriate content types. File uploads use `multipart/form-data`.

**Security middleware** (defined in `app.py`):
- **CSRF origin check:** `@app.before_request` rejects POST/PATCH/PUT/DELETE with an explicit non-localhost `Origin` header.
- **CSP headers:** `Content-Security-Policy` allows `self` + jsdelivr CDN (Grid.js) + `api.github.com` for connect-src.
- **Additional:** `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`.

## External Integrations

### GitHub QXF Repository
- **Purpose:** Fetch official QLC+ fixture definitions for brightness lookup and Quick Start wizard.
- **API base:** `https://api.github.com/repos/mcallegari/qlcplus/contents/resources/fixtures`
- **Raw base:** `https://raw.githubusercontent.com/mcallegari/qlcplus/master/resources/fixtures`
- **Client:** `core/gh_fetch.py` using `urllib.request` with `User-Agent: qlc-swiss-knife/1.0`
- **Used by:** `core/brightness.py` (manufacturer search), `core/quick_start/` (fixture fetching)
- **Disclosure:** All network calls are disclosed to the user before execution.

No other external services are contacted. The app is fully offline-capable except for GitHub fixture lookups.
