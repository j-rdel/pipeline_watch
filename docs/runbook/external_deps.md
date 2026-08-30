# External dependency failures

An API, service, or infrastructure component outside the repo returned an
error, timed out, or was rate-limited.

## Policy

- **Never autofix code.** The failure is not in our code — patching would
  hide the real problem.
- **Notify** and recommend one of:
  - Wait and retry (transient 5xx or timeout).
  - Bump the retry / timeout policy in the client (persistent slowness).
  - Escalate to the owner of the failing service.
- Attach the flakiness score in the notification. High score + external-dep
  usually means the client already needs a resilience fix.

## Signals

- HTTP status codes 500, 502, 503, 504 in the log.
- `TimeoutError`, `ConnectionError`, `socket.gaierror`.
- Provider-specific error strings: `ThrottlingException`, `503 upstream`,
  `read timeout`.

## Escalation heuristics

- 1-2 similar failures in the last 24 h → transient, wait.
- 3+ in the last 24 h → open an issue against the client library, tag
  the on-call SRE.
