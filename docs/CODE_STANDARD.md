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

## 5. Commits

- Short, clear English: `<type>: <subject>` (`feat`, `fix`, `docs`, `test`, `chore`).
- One logical change per commit; the playbook changes before code lands
  (design change ⇒ update `docs/playbook_platform.md` first).
- Never commit: `data/`, `videos/*.mp4`, `.env`, secrets.

## 6. Process

- Branch: `main` (stable, passes its week's pass-criteria) + `dev/<feature>` branches.
- Small PRs: ≤ 300 diff lines; self-review before pushing.
- Quality gate before merge: ruff + pytest green + the step's pass-criteria executed manually
  and pasted into the PR body.
