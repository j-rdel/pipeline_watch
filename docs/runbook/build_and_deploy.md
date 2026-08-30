# Build and deploy failures

The compile / package / bundle / deploy step failed after tests passed.

## Build failures — policy

- **Autofix only for lockfile issues.** If the failure is `uv sync` or
  `npm ci` complaining about an out-of-date lockfile, the agent MAY
  regenerate the lockfile and open a PR. Nothing else.
- For missing system libraries, wrong Python version, or Docker image
  build errors: **notify only**.

## Deploy failures — policy

- **Never autofix.** Deploy failures can leak credentials, roll back
  half-applied migrations, or brick a production service.
- Notify with:
  - The deploy target (which environment).
  - The step that failed (image push, container start, health check).
  - Whether a rollback is needed.
- Severity is always at least **high**; **critical** if the failure
  affected `production`.

## Signals

- Build: `error: Microsoft Visual C++`, `unable to open lockfile`,
  `Package X not found`, `Container image failed to build`.
- Deploy: `readiness probe failed`, `image push denied`, `permission denied`
  on the deploy target, `health check timeout`.
