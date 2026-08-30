"""GitHub PR publisher — always dry-run for this evaluation build.

Opening a real PR is intentionally out of scope:

  1. It's an irreversible side effect visible to collaborators (§4.5 of the
     challenge explicitly permits simulating destructive actions).
  2. Correctly applying an LLM-produced diff to files fetched via the
     REST API requires a diff-parser + apply loop that's larger than the
     safety value it adds for a demo.

The publisher therefore always builds the PR payload (title, body, patch)
and logs it, then returns None. Downstream open_pr writes pr_url=None,
and the IncidentReport shows the intended patch without any GitHub write.

To actually open PRs later:
  - Extend GitHubClient with a POST /repos/{owner}/{repo}/pulls path
  - Parse ProposedPatch.diff and PUT the resulting file contents
  - Flip this publisher's `dry_run` to False when a --post flag is passed
"""

from __future__ import annotations

from pipeline_watch.config import settings
from pipeline_watch.observability import get_logger
from pipeline_watch.schema import IncidentReport


class GitHubPRPublisher:
    def __init__(self, dry_run: bool | None = None) -> None:
        # `dry_run` is not really configurable yet — kept as an arg so tests
        # can flip it once real posting is implemented.
        self.dry_run = settings.pw_dry_run if dry_run is None else dry_run
        self._log = get_logger("pipeline_watch.publishers.github_pr")

    def _build_payload(self, report: IncidentReport) -> dict:
        assert report.proposed_patch is not None, "open_pr must not be called without a patch"
        patch = report.proposed_patch
        body_lines = [
            "## Automated fix by pipeline_watch",
            "",
            f"- **Classification:** {report.classification.label} "
            f"(confidence {report.classification.confidence:.2f})",
            f"- **Severity:** {report.severity.value}",
            f"- **Correlation id:** `{report.correlation_id}`",
            f"- **Source run:** `{report.run_id}` on `{report.workflow}`",
            "",
            "### Diagnosis",
            report.root_cause_hypothesis,
            "",
            "### Suggested action",
            report.suggested_action,
            "",
            "### Rationale",
            patch.rationale,
            "",
            "```diff",
            patch.diff.rstrip(),
            "```",
        ]
        return {
            "title": f"[pipeline_watch] {report.classification.label} autofix on {patch.file_path}",
            "head": f"pipeline_watch/{report.correlation_id}",
            "base": report.classification.label,  # placeholder — real impl uses default branch
            "body": "\n".join(body_lines),
            "file_path": patch.file_path,
            "diff": patch.diff,
        }

    def open_pr(self, report: IncidentReport) -> str | None:
        if report.proposed_patch is None:
            self._log.warning("github_pr.open_pr.no_patch", correlation_id=report.correlation_id)
            return None

        payload = self._build_payload(report)
        # We always dry-run in this build (see module docstring).
        self._log.info(
            "github_pr.open_pr.dry_run",
            correlation_id=report.correlation_id,
            title=payload["title"],
            file_path=payload["file_path"],
            reason=(
                "dry-run enforced for this evaluation build; "
                "real PR creation requires a diff-apply loop not implemented here"
            ),
        )
        return None
