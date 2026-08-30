# Test failures

`pytest`, `unittest`, `jest`, or similar reporting a real regression.

## Policy

- **Never autofix.** Test failures indicate either a code bug or an
  outdated expectation — both need a human decision.
- **Always notify** the PR author with:
  - The exact failing test name.
  - The exception type and message.
  - The last 5-10 lines of the traceback, verbatim.
- If the flakiness estimator marks the failure as flaky (score > 0.4 with
  ≥ 2 similar failures in 7 days), still notify but downgrade severity to
  medium — a flaky test is a *test* problem, not a *production* problem.

## Signals

- `FAILED` / `AssertionError` / `Traceback (most recent call last):` in
  the log.
- Test runner exit code 1 with a summary line like `N failed, M passed`.

## Anti-patterns

- Do not suggest deleting the failing test.
- Do not suggest adding `@pytest.mark.skip`.
- Do not suggest raising the assertion threshold to "just make it pass".
