"""
DebtScanner - Clones the repo and identifies technical debt
Uses GitAgent shell tool to run linters and static analysis
"""

import os
import re
import ast
import json
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class DebtItem:
    """Represents a single piece of technical debt"""
    id: str
    category: str          # unused-imports | dead-code | lint | outdated-deps | missing-tests
    file_path: str
    line_number: int
    description: str
    severity: str          # high | medium | low
    effort: str            # minutes | hours | days
    fix_suggestion: str
    raw_code: str = ""
    git_context: dict = field(default_factory=dict)
    safe_to_fix: bool = True
    skip_reason: str = ""


class DebtScanner:
    def __init__(self, repo_url: str, token: str = None):
        self.repo_url = repo_url
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.repo_path = None

    def scan(self, categories: List[str]) -> Tuple[str, List[DebtItem]]:
        """Clone repo and run all requested scanners"""
        self.repo_path = self._clone_repo()
        all_debt = []

        scanners = {
            "unused-imports": self._scan_unused_imports,
            "dead-code":      self._scan_dead_code,
            "lint":           self._scan_lint,
            "outdated-deps":  self._scan_outdated_deps,
            "missing-tests":  self._scan_missing_tests,
        }

        for cat in categories:
            if cat in scanners:
                print(f"   Scanning: {cat}...")
                items = scanners[cat]()
                print(f"   Found {len(items)} {cat} issues")
                all_debt.extend(items)

        # Score and sort by severity
        all_debt = self._score_and_sort(all_debt)
        return self.repo_path, all_debt

    def _clone_repo(self) -> str:
        """Clone the GitHub repository to a temp directory"""
        tmp_dir = tempfile.mkdtemp(prefix="devdebt_")
        clone_url = self.repo_url

        # Inject token for private repos
        if self.token and "github.com" in clone_url:
            clone_url = clone_url.replace("https://", f"https://{self.token}@")

        print(f"   Cloning to {tmp_dir}...")
        result = subprocess.run(
            ["git", "clone", "--depth=50", clone_url, tmp_dir],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to clone repo: {result.stderr}")

        print(f"   ✓ Cloned successfully")
        return tmp_dir

    def _scan_unused_imports(self) -> List[DebtItem]:
        """Find unused imports in Python files using AST analysis"""
        items = []
        py_files = list(Path(self.repo_path).rglob("*.py"))
        # Skip test files, migrations, __init__
        py_files = [f for f in py_files if not any(
            x in str(f) for x in ["test_", "_test", "migration", "venv", ".git", "node_modules"]
        )]

        for py_file in py_files[:50]:  # cap at 50 files
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source)
                unused = self._find_unused_imports_in_tree(tree, source)
                rel_path = str(py_file.relative_to(self.repo_path))

                for imp, lineno in unused:
                    items.append(DebtItem(
                        id=f"unused-import-{rel_path}-{lineno}",
                        category="unused-imports",
                        file_path=rel_path,
                        line_number=lineno,
                        description=f"Unused import: `{imp}`",
                        severity="low",
                        effort="minutes",
                        fix_suggestion=f"Remove unused import `{imp}` at line {lineno}",
                        raw_code=source.splitlines()[lineno - 1].strip() if lineno <= len(source.splitlines()) else ""
                    ))
            except Exception:
                continue

        return items

    def _find_unused_imports_in_tree(self, tree, source: str):
        """AST-based unused import detection"""
        imports = {}
        used_names = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    imports[name] = node.lineno
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    name = alias.asname or alias.name
                    imports[name] = node.lineno
            elif isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)

        return [(name, lineno) for name, lineno in imports.items() if name not in used_names]

    def _scan_dead_code(self) -> List[DebtItem]:
        """Find functions/classes defined but never called"""
        items = []
        py_files = list(Path(self.repo_path).rglob("*.py"))
        py_files = [f for f in py_files if not any(
            x in str(f) for x in ["test_", "venv", ".git", "migration"]
        )]

        all_defined = {}
        all_called = set()

        for py_file in py_files[:30]:
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source)
                rel_path = str(py_file.relative_to(self.repo_path))

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not node.name.startswith("_") and not node.name.startswith("test"):
                            all_defined[node.name] = (rel_path, node.lineno, source.splitlines()[node.lineno-1].strip())
                    elif isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name):
                            all_called.add(node.func.id)
                        elif isinstance(node.func, ast.Attribute):
                            all_called.add(node.func.attr)
            except Exception:
                continue

        for fn_name, (rel_path, lineno, code) in all_defined.items():
            if fn_name not in all_called:
                items.append(DebtItem(
                    id=f"dead-code-{rel_path}-{lineno}",
                    category="dead-code",
                    file_path=rel_path,
                    line_number=lineno,
                    description=f"Potentially dead function: `{fn_name}()` — never called in codebase",
                    severity="medium",
                    effort="minutes",
                    fix_suggestion=f"Remove or document `{fn_name}()` if no longer needed",
                    raw_code=code
                ))

        return items[:20]

    def _scan_lint(self) -> List[DebtItem]:
        """Run pylint/flake8 if available"""
        items = []
        try:
            result = subprocess.run(
                ["python3", "-m", "flake8", "--max-line-length=120",
                 "--select=E401,E711,E712,W291,W293,F401,F811",
                 "--format=%(path)s::%(row)d::%(col)d::%(code)s::%(text)s",
                 self.repo_path],
                capture_output=True, text=True, cwd=self.repo_path
            )
            for line in result.stdout.splitlines()[:30]:
                parts = line.split("::")
                if len(parts) >= 5:
                    file_abs, row, col, code, msg = parts[0], parts[1], parts[2], parts[3], parts[4]
                    try:
                        rel = str(Path(file_abs).relative_to(self.repo_path))
                    except Exception:
                        rel = file_abs
                    items.append(DebtItem(
                        id=f"lint-{rel}-{row}",
                        category="lint",
                        file_path=rel,
                        line_number=int(row),
                        description=f"Lint [{code}]: {msg}",
                        severity="low",
                        effort="minutes",
                        fix_suggestion=f"Fix lint issue {code} at line {row}: {msg}",
                    ))
        except Exception:
            pass
        return items

    def _scan_outdated_deps(self) -> List[DebtItem]:
        """Check for known vulnerable/outdated packages"""
        items = []
        req_file = Path(self.repo_path) / "requirements.txt"
        if not req_file.exists():
            return items

        content = req_file.read_text()
        pinned_old = re.findall(r"(\w[\w\-]*)==([\d\.]+)", content)

        # Known very outdated versions (simple heuristic)
        known_old = {
            "django": ("2.", "Use Django 4.2+"),
            "flask": ("0.", "Use Flask 3.x"),
            "requests": ("1.", "Use requests 2.x"),
            "numpy": ("1.1", "Use NumPy 1.24+"),
            "pillow": ("6.", "Use Pillow 10+"),
            "sqlalchemy": ("1.2", "Use SQLAlchemy 2.x"),
        }

        for pkg, ver in pinned_old:
            pkg_lower = pkg.lower()
            for known_pkg, (old_prefix, suggestion) in known_old.items():
                if known_pkg in pkg_lower and ver.startswith(old_prefix):
                    items.append(DebtItem(
                        id=f"outdated-dep-{pkg}",
                        category="outdated-deps",
                        file_path="requirements.txt",
                        line_number=0,
                        description=f"Outdated dependency: `{pkg}=={ver}`",
                        severity="high",
                        effort="hours",
                        fix_suggestion=suggestion,
                        raw_code=f"{pkg}=={ver}",
                        safe_to_fix=False,
                        skip_reason="Dependency upgrades require human testing"
                    ))

        return items

    def _scan_missing_tests(self) -> List[DebtItem]:
        """Find Python modules with no corresponding test file"""
        items = []
        src_files = list(Path(self.repo_path).rglob("*.py"))
        src_files = [f for f in src_files if not any(
            x in str(f) for x in ["test", "venv", ".git", "migration", "__init__", "setup.py"]
        )]
        test_files = list(Path(self.repo_path).rglob("test_*.py")) + list(Path(self.repo_path).rglob("*_test.py"))
        tested_modules = {f.stem.replace("test_", "").replace("_test", "") for f in test_files}

        for src in src_files[:20]:
            if src.stem not in tested_modules:
                rel = str(src.relative_to(self.repo_path))
                items.append(DebtItem(
                    id=f"missing-test-{rel}",
                    category="missing-tests",
                    file_path=rel,
                    line_number=0,
                    description=f"No test file found for `{src.stem}.py`",
                    severity="medium",
                    effort="hours",
                    fix_suggestion=f"Create `test_{src.stem}.py` with unit tests",
                    safe_to_fix=False,
                    skip_reason="Test creation requires domain knowledge"
                ))

        return items[:10]

    def _score_and_sort(self, items: List[DebtItem]) -> List[DebtItem]:
        """Score items by severity + effort and sort"""
        severity_score = {"high": 3, "medium": 2, "low": 1}
        effort_score = {"minutes": 3, "hours": 2, "days": 1}

        def score(item):
            return severity_score.get(item.severity, 1) + effort_score.get(item.effort, 1)

        return sorted(items, key=score, reverse=True)
