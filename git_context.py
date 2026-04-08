"""
GitContextReader - Reads git history, blame, and commit messages
to understand WHY code exists before the agent changes it.
This is the core GitAgent differentiator.
"""

import subprocess
from pathlib import Path
from typing import List


class GitContextReader:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def enrich_with_context(self, debt_items) -> list:
        """Add git context to each debt item"""
        for item in debt_items:
            if item.line_number > 0 and item.file_path:
                item.git_context = self._get_line_context(item.file_path, item.line_number)
                # Mark as unsafe if recently modified or has suppression comment
                self._check_if_intentional(item)
        return debt_items

    def _get_line_context(self, rel_path: str, line_number: int) -> dict:
        """Get git blame + recent commits for a specific line"""
        context = {
            "last_author": "unknown",
            "last_commit_msg": "",
            "last_commit_hash": "",
            "days_since_change": 9999,
            "has_suppression": False,
            "linked_issue": None,
        }

        try:
            # git blame for the specific line
            blame = subprocess.run(
                ["git", "blame", "-L", f"{line_number},{line_number}",
                 "--porcelain", rel_path],
                capture_output=True, text=True, cwd=self.repo_path
            )
            if blame.returncode == 0:
                lines = blame.stdout.splitlines()
                for l in lines:
                    if l.startswith("author "):
                        context["last_author"] = l.replace("author ", "").strip()
                    elif l.startswith("summary "):
                        context["last_commit_msg"] = l.replace("summary ", "").strip()
                    elif l.startswith("author-time "):
                        import time
                        ts = int(l.replace("author-time ", "").strip())
                        context["days_since_change"] = int((time.time() - ts) / 86400)
                if lines:
                    context["last_commit_hash"] = lines[0].split(" ")[0][:8]

            # Check for issue references in commit message
            import re
            msg = context["last_commit_msg"]
            issue_match = re.search(r"(#\d+|JIRA-\d+|TODO-\d+)", msg, re.IGNORECASE)
            if issue_match:
                context["linked_issue"] = issue_match.group(1)

            # Check for noqa/pylint disable on that line
            full_path = Path(self.repo_path) / rel_path
            if full_path.exists():
                file_lines = full_path.read_text(errors="ignore").splitlines()
                if 0 < line_number <= len(file_lines):
                    line_text = file_lines[line_number - 1]
                    if any(s in line_text for s in ["noqa", "pylint: disable", "# type: ignore", "# noinspection"]):
                        context["has_suppression"] = True

        except Exception:
            pass

        return context

    def _check_if_intentional(self, item):
        """
        Mark item as unsafe to auto-fix if git history suggests it's intentional.
        This is the key safety mechanism of DevDebt Agent.
        """
        ctx = item.git_context

        # Rule 1: Has a linting suppression comment = intentional
        if ctx.get("has_suppression"):
            item.safe_to_fix = False
            item.skip_reason = "Has suppression comment (noqa/pylint:disable) — likely intentional"

        # Rule 2: Linked to an open issue = someone is tracking it
        if ctx.get("linked_issue"):
            item.safe_to_fix = False
            item.skip_reason = f"Linked to issue {ctx['linked_issue']} in commit history"

        # Rule 3: Modified very recently (< 7 days) = might be WIP
        if ctx.get("days_since_change", 9999) < 7:
            item.safe_to_fix = False
            item.skip_reason = f"Modified {ctx['days_since_change']} days ago — may be active WIP"

        # Rule 4: Commit message contains "wip", "draft", "temp", "todo"
        commit_msg = ctx.get("last_commit_msg", "").lower()
        wip_signals = ["wip", "draft", "temp", "temporary", "todo", "fixme", "hack", "workaround"]
        for signal in wip_signals:
            if signal in commit_msg:
                item.safe_to_fix = False
                item.skip_reason = f"Commit message contains '{signal}' — likely intentional temporary code"
                break

    def get_repo_summary(self) -> dict:
        """Get high-level repo statistics"""
        summary = {}
        try:
            # Total commits
            result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                capture_output=True, text=True, cwd=self.repo_path
            )
            summary["total_commits"] = result.stdout.strip()

            # Top contributors
            result = subprocess.run(
                ["git", "shortlog", "-sn", "--no-merges", "HEAD"],
                capture_output=True, text=True, cwd=self.repo_path
            )
            contributors = []
            for line in result.stdout.splitlines()[:5]:
                parts = line.strip().split("\t")
                if len(parts) == 2:
                    contributors.append({"commits": parts[0].strip(), "name": parts[1].strip()})
            summary["top_contributors"] = contributors

            # Last commit date
            result = subprocess.run(
                ["git", "log", "-1", "--format=%cr"],
                capture_output=True, text=True, cwd=self.repo_path
            )
            summary["last_commit"] = result.stdout.strip()

        except Exception:
            pass

        return summary
