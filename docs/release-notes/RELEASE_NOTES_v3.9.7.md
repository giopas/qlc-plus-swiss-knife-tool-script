A second full security audit (`docs/SECURITY_AUDIT_3.9.7.md`) with its fixes, and a Show Paperwork screen that reads in four steps. What a button writes does not change.

### Security

- **Host check (F1).** The server answers only to loopback names on its own port, so a web page cannot reach it through DNS rebinding.
- **No script from the internet (F2).** Grid.js, loaded from a CDN without a pinned version, was not used and is removed. The Content-Security-Policy now allows only the app itself, plus `frame-ancestors 'none'`, `object-src 'none'` and `form-action 'self'`.
- **Tablet server (F3).** It serves only the stage page, not the folder it lives in.
- **Saves (F4).** Setlist and dictionary saves go to an existing folder, with a text extension, and never to a hidden file or a link (`core/safe_paths.py`).
- **Updater (F5).** Downloads only from GitHub hosts; tar archives with links outside the folder, devices or fifos are refused; unpacked size is capped at 2 GB.
- **GitHub names (F6).** `..` and path pieces are refused in fixture names.
- **XML (F7).** Shows and fixture files with entity definitions are refused, and size caps apply (`core/xml_safe.py`).
- **Origin (F8), isolation headers (F9), SHA-1 flag (F10).** Origin `null` is refused; `Sec-Fetch-Site` is checked when there is no Origin; COOP and CORP are sent; the cache-name hash is marked as not for security.
- **AppleScript text (F11).** A backslash in a dialog title could end the text early on macOS; it is now escaped.
- `tests/test_security_397.py` (50 tests) and `tools/xss_probe.py` (advisory): a show whose names are script payloads is loaded into all 21 screens and the paperwork preview. Nothing ran.

### Show Paperwork

- The screen has four numbered steps: **Who is it for?**, **What goes in**, **On every page**, **Check it**.
- Who-it-is-for are toggle chips (Rider, Checklist, Patch, Operator) that can be combined. The **Custom** chip and the shift-click are gone; ticking by hand shows a "Changed by hand" tag and a count of what is in.
- Preview has Expand all and Collapse all. The footer keeps one accent button, Export PDF.
- Section names say what they are: "Patch sheet: DIP switch settings", "Patch list: universe and address".
- 26 new texts in the seven languages. The wiki page `Show-Paperwork` is updated.

---

Downloads for macOS, Windows and Linux, the Claude Desktop file (.mcpb) and the checksums are below. The whole history is in the [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
