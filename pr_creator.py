"""
PRCreator - Pushes the fix branch and opens a GitHub Pull Request
with a detailed, human-readable description of every change made.
"""

import os
import re
import subprocess
import urllib.request
import urllib.error
import json
from typing import List


class PRCreator:
    def __init__(self, repo_url: str, repo_path: str, token: str = None):
        self.repo_url = repo_url
        self.repo_path = repo_path
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.owner, self.repo_name = self._parse_repo(repo_url)

    def _parse_repo(self, url: str):
        """Extract owner/repo from GitHub URL"""
        match = re.search(r"github\.com[:/]([^/]+)/([^/\.]+)", url)
        if match:
            return match.group(1), match.group(2).replace(".git", "")
        raise ValueError(f"Cannot parse GitHub URL: {url}")

    def create_pr(self, fixed_items, skipped_items) -> str:
        """Push branch and create PR, return PR URL"""
        branch = "devdebt-agent/auto-fixes"

        # Push the branch
        push_url = f"https://{self.token}@github.com/{self.owner}/{self.repo_name}.git"
        result = subprocess.run(
            ["git", "push", push_url, f"HEAD:{branch}", "--force"],
            capture_output=True, text=True, cwd=self.repo_path
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to push branch: {result.stderr}")

        # Build PR body
        body = self._build_pr_body(fixed_items, skipped_items)

        # Create PR via GitHub API
        pr_data = {
            "title": f"[DevDebt Agent] Auto-fix {len(fixed_items)} technical debt items",
            "body": body,
            "head": branch,
            "base": "main",
        }

        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/{self.owner}/{self.repo_name}/pulls",
                data=json.dumps(pr_data).encode(),
                headers={
                    "Authorization": f"token {self.token}",
                    "Content-Type": "application/json",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "DevDebt-Agent/1.0",
                },
                method="POST"
            )
            with urllib.request.urlopen(req) as response:
                pr = json.loads(response.read())
                return pr["html_url"]
        except urllib.error.HTTPError as e:
            # Try with 'master' base if 'main' fails
            if e.code == 422:
                pr_data["base"] = "master"
                req = urllib.request.Request(
                    f"https://api.github.com/repos/{self.owner}/{self.repo_name}/pulls",
                    data=json.dumps(pr_data).encode(),
                    headers={
                        "Authorization": f"token {self.token}",
                        "Content-Type": "application/json",
                        "Accept": "application/vnd.github.v3+json",
                        "User-Agent": "DevDebt-Agent/1.0",
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req) as response:
                    pr = json.loads(response.read())
                    return pr["html_url"]
            raise

    def _build_pr_body(self, fixed_items, skipped_items) -> str:
        """Generate a detailed, human-readable PR description"""
        categories = {}
        for item in fixed_items:
            categories.setdefault(item.category, []).append(item)

        lines = [
            "## 🤖 DevDebt Agent — Automated Technical Debt Fix",
            "",
            "> This PR was created autonomously by [DevDebt Agent](https://github.com/YOUR_USERNAME/devdebt-agent).",
            "> Every change was validated against git history before being applied.",
            "> **Please review carefully before merging.**",
            "",
            "---",
            "",
            f"### Summary",
            f"- ✅ **Fixed:** {len(fixed_items)} issues",
            f"- ⏭️ **Skipped:** {len(skipped_items)} issues (intentional or unsafe)",
            "",
        ]

        if fixed_items:
            lines += ["### Changes Made", ""]
            for cat, items in categories.items():
                lines.append(f"#### `{cat}` ({len(items)} fixes)")
                for item in items:
                    ctx = item.git_context
                    lines += [
                        f"- **`{item.file_path}:{item.line_number}`** — {item.description}",
                        f"  - Fix applied: {getattr(item, 'fix_applied', item.fix_suggestion)}",
                        f"  - Last touched by: `{ctx.get('last_author', 'unknown')}` "
                        f"({ctx.get('days_since_change', '?')} days ago)",
                        f"  - Commit context: *\"{ctx.get('last_commit_msg', 'no message')}\"*",
                        "",
                    ]

        if skipped_items:
            lines += [
                "---",
                "### Items Skipped (Not Auto-Fixed)",
                "",
                "These items were detected but intentionally not modified:",
                "",
            ]
            for item in skipped_items[:10]:
                lines.append(f"- `{item.file_path}:{item.line_number}` — {item.description}")
                lines.append(f"  - Reason skipped: {item.skip_reason}")

        lines += [
            "",
            "---",
            "### How DevDebt Agent Ensures Safety",
            "",
            "1. **Git blame analysis** — checks who last touched each line and when",
            "2. **Commit message parsing** — skips code with WIP/draft/todo in history",
            "3. **Suppression detection** — respects `# noqa` and `# pylint: disable` comments",
            "4. **Issue link detection** — skips code linked to open issues in commit messages",
            "5. **Recency check** — skips lines modified in the last 7 days (may be active WIP)",
            "",
            "*DevDebt Agent — Open Innovation Hackathon 2025*",
        ]

        return "\n".join(lines)
