# Code Standard — fakecam platform

Applies to every PR in this repo. English only for code comments and commit messages;
user-facing docs can be Vietnamese.

## 1. Structure (single source of truth)

- `config/config.yaml` — ALL numbers & paths (cameras, pre, post, seg_s, keep_s, cooldown_s, rtsp_path).
  **No hardcoded URLs, ports or timeouts in code.**
- Every module reads config at load time via `core/config.py`; config validation runs on import:
  camera_id must match `^cam[0-9]{2}$`, wrong values exit immediately.

## 2. File scale limits

| Metric | Hard limit | Target |
|---|---|---|
| Lines per file | ≤ 250 | ~150 |
| Functions/classes per file | ≤ 1 class or ≤ 4 functions | — |
| Function length | ≤ 30 lines | — |
| Nesting depth | ≤ 3 | ≤ 2 |

Exceeding a limit = split the module (exception needs a note in the PR body).

## 3. Comments

- **English only**, explain *why*, not *what*; reference the playbook section when the rule
  comes from `docs/playbook_platform.md` (e.g. `# per §1.4 rule 2: no hardcoded URLs`).
- Each module starts with a 1–3 line docstring stating its responsibility and what it must NOT do
  (e.g. CameraReader must not keep frames in lists).
- No TODO without an owner + ticket/issue reference.

## 4. Python quality

- Type hints on public functions (`config` / `return` types required).
- `frozen` dataclasses for contracts (`core/contract.py`).
- Errors: fail fast at startup; at runtime log + retry only per playbook risk table.
- Threads/lock: shared state guarded by `threading.Condition` (CameraReader pattern —
  latest frame only, no unbounded queues).
- Lint/format: `ruff check` + `ruff format` before every commit (zero-tolerance, config
  lives in `pyproject.toml`).
- Tests: pytest for pure logic (config parsing, cut_clip segment selection); no test for
  subprocess plumbing (covered by soak instead).

## 5. Branches & commits

- **`main` is protected: never commit/push directly.** All work happens on
  `dev/<feature>` branches and lands via PR review.
- Author: **Quiniu**. Commit/PR messages: short, clear, professional English —
  `<type>: <subject>` (`feat`, `fix`, `docs`, `test`, `chore`).
- **No AI/tool attribution in commits, PRs or code comments.** History reads as if
  written by the team, nothing else.
- One logical change per commit; design change ⇒ update `docs/playbook_platform.md` first.
- Never commit: `data/`, `videos/*.mp4`, `.env`, secrets, credentials of any kind.
- PR checklist (body must state): purpose, what changed, pass-criteria executed + output,
  quality checks run (ruff/pytest), security impact if touching network/processes/files.

## 6. Quality gate — every code change, no exceptions

Run before every commit (not before merge):
```
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/pytest -q
```
Failing any step = no commit. Pass-criteria of the current week/test executed manually.

## 7. Security non-negotiables

- **No secrets in code, config or logs.** Tokens/credentials via environment variables only;
  `.env` is gitignored (never force-added).
- RTSP/HTTP endpoints bind to `127.0.0.1` by default; anything exposed on the LAN requires
  an explicit note in the PR + a reason.
- Child processes (`ffmpeg`) are launched from fixed argv arrays — no shell interpolation,
  no f-string command assembly from user/UI input.
- Camera/video filenames from UI/API are validated against a strict pattern before use
  (no path traversal: reject `/`, `..`, absolute paths).
- Upload/uploaded-video size and extension validated; files land only under `videos/`.
- Every PR that touches network, subprocesses or files must state security impact
  (per §5 PR checklist).
