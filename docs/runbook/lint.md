# Lint failures

Style violations reported by `ruff`, `flake8`, or `eslint`. These do not
change program behavior and are usually mechanical to fix.

## Policy

- **Autofix allowed.** The agent MAY generate a PR that applies `ruff format`
  or the equivalent one-shot fixer. The PR is never merged automatically —
  a human still reviews and merges.
- **Never touch business logic.** Only whitespace, imports (when the rule
  is "unused import"), and formatting. Renames, refactors, or logic changes
  are out of scope.
- **Allowlist of files:** `.github/workflows/`, `requirements.txt`,
  `pyproject.toml`, `uv.lock`, plus any Python file whose only failing rules
  are pure style. Anything outside triggers `notify_only`.

## Signals

- Log lines matching `E\d\d\d` (ruff codes), `F\d\d\d`, or
  `<path>:<line>:<col>: <rule> <message>`.
- Exit code 1 with `Found N errors.` in the tail.

## Common false positives

- A "lint failure" that is actually a `NameError` at import time is NOT
  a lint issue — that is a runtime bug. Look at the traceback shape, not
  just the failing job name.
