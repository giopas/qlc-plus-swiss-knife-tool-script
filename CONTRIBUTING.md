# Contributing to QLC+ Swiss Knife

Thank you for taking the time to contribute! This is an independent community project and all feedback — whether bug reports, suggestions, or code — is genuinely appreciated.

---

## Table of Contents

- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features or Improvements](#suggesting-features-or-improvements)
- [Submitting Code](#submitting-code)
- [Code Style Guidelines](#code-style-guidelines)
- [Important Notes](#important-notes)

---

## Reporting Bugs

If you found something that doesn't work as expected, please [open a Bug Report issue](../../issues/new?template=bug_report.md).

To help diagnose the problem quickly, please include:

- **Your operating system** (Windows 10/11, macOS version, Linux distro)
- **Python version** (`python3 --version`)
- **Which tab / feature** was active when the issue occurred (Setlist Manager, Dictionary, Setup Checklist, Triggers)
- **Steps to reproduce** — the more specific the better
- **What you expected** to happen vs. **what actually happened**
- **Error messages or tracebacks** — if the app printed anything to the terminal, please paste it
- **Your `.qxw` file** — if the bug is workspace-specific, sharing a minimal example (or a anonymised version) helps enormously. You can attach files directly to GitHub issues.

---

## Suggesting Features or Improvements

Have an idea that would make the tool more useful for live productions? Please [open a Feature Request issue](../../issues/new?template=feature_request.md).

Good feature requests explain:

- **The problem you're trying to solve** — "I want to…" or "It's frustrating that…"
- **Your proposed solution** — even a rough description is fine
- **Alternatives you considered**, if any
- **Which tab or workflow** it would affect

There is no promise that every suggestion will be implemented, but all ideas are read and considered for the [Roadmap](ROADMAP.md).

---

## Submitting Code

Pull requests are welcome! Here is the recommended workflow:

1. **Fork** the repository and create a new branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes.** Keep commits focused — one logical change per commit.

3. **Test on at least one platform** (Windows, macOS, or Linux) with a real `.qxw` file if possible.

4. **Open a Pull Request** against the `main` branch. In the PR description:
   - Explain what the change does and why
   - Reference any related issues (e.g. `Closes #12`)
   - Note which platform(s) you tested on

5. Be patient — this is a solo project maintained in spare time. Reviews may take a few days.

---

## Code Style Guidelines

- **Pure Python 3 stdlib only.** No external dependencies — this is intentional and must be preserved.
- **tkinter UI only.** No third-party GUI frameworks.
- Follow the existing file structure: one self-contained `.py` file.
- Use descriptive variable and function names.
- Add docstrings to new classes and non-trivial functions.
- Keep the version string updated in the module docstring at the top of the file.

---

## Important Notes

- This project is **not affiliated with the official QLC+ project**. Please do not open issues here for problems with QLC+ itself — use the [official QLC+ repository](https://github.com/mcallegari/qlcplus) for that.
- Be respectful and constructive in all interactions. Rude or dismissive comments will be closed without response.
- By submitting a pull request, you agree that your contribution will be licensed under the same [MIT License](LICENSE) as the rest of the project.
