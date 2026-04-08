"""
DebtFixer - Applies safe, automated fixes to identified debt items.
Only touches items marked safe_to_fix=True after git context analysis.
"""

import re
import subprocess
from pathlib import Path
from typing import List, Tuple


class DebtFixer:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.branch_name = "devdebt-agent/auto-fixes"
        self._create_branch()

    def _create_branch(self):
        """Create a new git branch for fixes"""
        subprocess.run(
            ["git", "checkout", "-b", self.branch_name],
            capture_output=True, cwd=self.repo_path
        )

    def fix(self, debt_items, max_fixes: int = 10) -> Tuple[list, list]:
        """Apply fixes, return (fixed, skipped)"""
        safe_items = [i for i in debt_items if i.safe_to_fix][:max_fixes]
        unsafe_items = [i for i in debt_items if not i.safe_to_fix]

        fixed = []
        skipped = []

        fixers = {
            "unused-imports": self._fix_unused_import,
            "lint":           self._fix_lint_issue,
            "dead-code":      self._skip_needs_human,
            "outdated-deps":  self._skip_needs_human,
            "missing-tests":  self._skip_needs_human,
        }

        for item in safe_items:
            fixer = fixers.get(item.category)
            if fixer:
                success, message = fixer(item)
                if success:
                    item.fix_applied = message
                    fixed.append(item)
                else:
                    item.skip_reason = message
                    skipped.append(item)

        skipped.extend(unsafe_items)

        # Commit all changes
        if fixed:
            self._commit_fixes(fixed)

        return fixed, skipped

    def _fix_unused_import(self, item) -> Tuple[bool, str]:
        """Remove an unused import line"""
        try:
            file_path = Path(self.repo_path) / item.file_path
            lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)

            if item.line_number < 1 or item.line_number > len(lines):
                return False, "Line number out of range"

            target_line = lines[item.line_number - 1]

            # Safety: only remove if it looks like an import line
            if not re.match(r"\s*(import |from .+ import )", target_line):
                return False, "Line doesn't look like an import — skipping"

            # Safety: don't remove if the import name appears elsewhere in file
            content = "".join(lines)
            import_name = self._extract_import_name(target_line)
            if import_name and content.count(import_name) > 1:
                return False, f"`{import_name}` appears elsewhere in file — might be used"

            # Apply the fix
            lines.pop(item.line_number - 1)
            file_path.write_text("".join(lines), encoding="utf-8")
            return True, f"Removed unused import at line {item.line_number}: {target_line.strip()}"

        except Exception as e:
            return False, f"Error applying fix: {e}"

    def _fix_lint_issue(self, item) -> Tuple[bool, str]:
        """Fix simple lint issues (trailing whitespace, etc.)"""
        try:
            file_path = Path(self.repo_path) / item.file_path
            content = file_path.read_text(encoding="utf-8")

            # W291/W293: trailing whitespace
            if "W291" in item.description or "W293" in item.description:
                fixed = re.sub(r"[ \t]+$", "", content, flags=re.MULTILINE)
                if fixed != content:
                    file_path.write_text(fixed, encoding="utf-8")
                    return True, "Removed trailing whitespace"

            # W292: no newline at end of file
            if "W292" in item.description:
                if not content.endswith("\n"):
                    file_path.write_text(content + "\n", encoding="utf-8")
                    return True, "Added newline at end of file"

            return False, "Lint fix not automated for this code — needs human"

        except Exception as e:
            return False, f"Error: {e}"

    def _skip_needs_human(self, item) -> Tuple[bool, str]:
        return False, "Requires human review and domain knowledge"

    def _extract_import_name(self, line: str) -> str:
        """Extract the imported name from an import line"""
        # from x import y as z -> z
        m = re.search(r"import\s+\w+\s+as\s+(\w+)", line)
        if m:
            return m.group(1)
        # from x import y -> y
        m = re.search(r"from\s+\S+\s+import\s+(\w+)", line)
        if m:
            return m.group(1)
        # import x -> x
        m = re.search(r"^import\s+(\w+)", line.strip())
        if m:
            return m.group(1)
        return ""

    def _commit_fixes(self, fixed_items):
        """Commit all applied fixes"""
        subprocess.run(["git", "add", "-A"], cwd=self.repo_path, capture_output=True)

        categories = list(set(i.category for i in fixed_items))
        commit_msg = (
            f"fix(devdebt): auto-fix {len(fixed_items)} technical debt items\n\n"
            f"Categories: {', '.join(categories)}\n\n"
            f"Fixed by DevDebt Agent — git-context-aware autonomous debt resolution.\n"
            f"Each fix was validated against git history before application.\n\n"
            + "\n".join(f"- {i.description} ({i.file_path}:{i.line_number})" for i in fixed_items)
        )

        subprocess.run(
            ["git", "commit", "-m", commit_msg, "--author", "DevDebt Agent <devdebt@agent.ai>"],
            cwd=self.repo_path, capture_output=True
        )
