# Security Policy

## Supported Versions

Sandy Wallpaper Studio is currently in pre-release development. Only the latest source on `main` is actively maintained.

| Version | Supported |
|---|---|
| V1.0.0 (main) | Yes |
| Earlier versions | No |

## Scope

This policy covers the project source code at <https://github.com/Sandy32513/Sandy-Wallpaper-Studio>.

**In scope:**
- Code vulnerabilities in `app/`, `scripts/`, and `tests/`
- Dependency vulnerabilities in declared packages (`pyproject.toml`, `requirements.txt`)
- Download or network-boundary bypasses in `app/services/download_service.py`
- Path-traversal or injection vulnerabilities in file-handling or import paths

**Out of scope:**
- Vulnerabilities in third-party wallpaper images downloaded from Wikimedia Commons or other sources (report those to their respective projects)
- Attacks that require physical access to the user's machine
- Self-XSS or social-engineering attacks
- Issues in the Windows operating system itself

## Reporting a Vulnerability

**Do not open a public GitHub issue for a security vulnerability.**

Report security issues privately by:

1. Opening a [GitHub Security Advisory](https://github.com/Sandy32513/Sandy-Wallpaper-Studio/security/advisories/new) (preferred — keeps the report confidential).
2. Or emailing the maintainer directly via the contact listed on the [GitHub profile](https://github.com/Sandy32513).

Please include:

- A description of the vulnerability and its potential impact.
- Steps to reproduce or a proof-of-concept (no live exploitation needed).
- The affected version or commit.
- Any suggested remediation, if you have one.

## Response Timeline

- **Acknowledgement:** within 7 days of receipt.
- **Assessment and triage:** within 14 days.
- **Fix or mitigation:** depends on severity; critical issues will be prioritised.

You will be credited in the fix commit and CHANGELOG unless you prefer to remain anonymous.

## Dependency Advisories

The project uses `pip-audit` to check for known advisories in installed packages. To run it locally:

```powershell
.\.venv\Scripts\python.exe -m pip install pip-audit
.\.venv\Scripts\python.exe -m pip run pip-audit --local
```

Dependabot is configured to open automated pull requests for dependency updates (see `.github/dependabot.yml`).

## Known Limitations

- The unsigned Windows validation bundle is internal development output and is not signed or distributed publicly.
- The Windows Recycle Bin cleanup workflow (Duplicate Manager) is guarded by multiple revalidation steps, but relies on the Windows `IFileOperation` API for the actual file operation; the project does not provide an independent permanent-deletion path.
