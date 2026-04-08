# 🤖 DevDebt Agent

> **GitAgent Hackathon 2025 — Open Innovation Track**
> Autonomously hunt and fix technical debt in real GitHub repositories using git-context-aware AI.

---

## 🎯 Problem Statement

Engineering teams globally lose **~42% of development time** to unresolved technical debt — unused imports, dead code, outdated dependencies, missing tests, and lint violations. Nobody fixes it because no one has the time *or the context*.

**DevDebt Agent** solves this by combining static analysis with **git history intelligence** — reading `git blame`, commit messages, and PR history to understand *why* code exists before changing it.

---

## ✨ How It Works

```
┌─────────────────────────────────────────────────────────┐
│                    DevDebt Agent Flow                    │
├──────────┬──────────────┬────────────┬──────────────────┤
│  1. SCAN │  2. CONTEXT  │  3. FIX    │  4. PR           │
│          │              │            │                  │
│ Clone    │ Read git     │ Apply safe │ Push branch +    │
│ repo     │ blame +      │ fixes on   │ open PR with     │
│ Run lint │ commit msgs  │ new branch │ full explanation │
│ Find     │ Mark unsafe  │ Run tests  │ of every change  │
│ debt     │ items        │            │                  │
└──────────┴──────────────┴────────────┴──────────────────┘
```

### Key Differentiator: Git-Context Safety

Before touching **any** line of code, the agent checks:

| Check | What it looks for | Action if found |
|-------|-------------------|-----------------|
| Suppression comment | `# noqa`, `# pylint: disable` | Skip — intentional |
| Issue link in commit | `#123`, `JIRA-456` in git log | Skip — tracked |
| Recent modification | Changed < 7 days ago | Skip — may be WIP |
| WIP commit message | "wip", "draft", "temp" in commit | Skip — in progress |

---

## 🚀 Quick Start

### 1. Clone this repo
```bash
git clone https://github.com/vvce25cse0423-lgtm/devdebt-agent
cd devdebt-agent
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set your GitHub token
```bash
export GITHUB_TOKEN=ghp_your_token_here
```
> Get a token at: GitHub → Settings → Developer Settings → Personal Access Tokens → Fine-grained tokens
> Required scopes: `repo` (full)

### 4. Run on any public repo
```bash
python agent.py --repo https://github.com/any-owner/any-repo
```

### 5. See the PR appear in the target repo! 🎉

---

## 📖 Full Usage

```bash
python agent.py \
  --repo https://github.com/owner/repo \
  --token ghp_xxxx \
  --categories unused-imports lint \
  --max-fixes 15 \
  --dry-run
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--repo` | required | GitHub repository URL |
| `--token` | `$GITHUB_TOKEN` | GitHub personal access token |
| `--categories` | `unused-imports lint` | Debt types to target |
| `--max-fixes` | `10` | Max issues to fix per run |
| `--dry-run` | `false` | Scan only, no PR created |

### Available Categories

| Category | What it finds | Auto-fixable? |
|----------|--------------|---------------|
| `unused-imports` | Python imports never referenced | ✅ Yes |
| `lint` | Trailing whitespace, missing newlines | ✅ Yes |
| `dead-code` | Functions defined but never called | 🔍 Detected, not auto-fixed |
| `outdated-deps` | Old versions in requirements.txt | 🔍 Detected, not auto-fixed |
| `missing-tests` | Modules with no test file | 🔍 Detected, not auto-fixed |

---

## 🏗️ Project Structure

```
devdebt-agent/
├── agent.py                  # Main entry point
├── requirements.txt
├── README.md
└── agent/
    ├── __init__.py
    ├── scanner.py            # Static analysis + debt detection
    ├── git_context.py        # Git blame + commit history reader
    ├── fixer.py              # Safe fix application + git branch
    ├── pr_creator.py         # GitHub API PR creation
    └── reporter.py           # Console output formatting
```

---

## 🧠 GitAgent Features Used

- **`git clone --depth=50`** — Efficient repo cloning with history
- **`git blame --porcelain`** — Line-level authorship and timestamps
- **`git log` / `git shortlog`** — Commit message mining for WIP signals
- **`git checkout -b`** — Isolated fix branches
- **`git commit`** — Atomic, well-described commits per fix batch
- **`git push`** — Branch publication for PR creation
- **GitHub REST API** — Programmatic PR creation with rich descriptions

---

## 📊 Example Output

```
╔══════════════════════════════════════════╗
║        DevDebt Agent  v1.0.0             ║
║  Autonomous Technical Debt Resolution    ║
╚══════════════════════════════════════════╝

[1/4] Scanning repository: https://github.com/example/myapp
   Scanning: unused-imports...
   Found 12 unused-imports issues
   Scanning: lint...
   Found 8 lint issues

   ┌─ Debt Summary ──────────────────────────┐
   │  🔴 High severity:     2 items           │
   │  🟡 Medium severity:   7 items           │
   │  🟢 Low severity:     11 items           │
   │  📊 Total:            20 items           │
   └─────────────────────────────────────────┘

[2/4] Reading git history for context...
   ✓ Enriched 20 debt items with git blame + commit history

[3/4] Applying safe fixes (max: 10)...
   ✓ Fixed:    9 issues
   ✗ Skipped: 11 issues (intentional/unsafe)

[4/4] Creating pull request...

✅ Done! Pull request created:
   https://github.com/example/myapp/pull/42
```

---

## 🛡️ Safety Guarantees

DevDebt Agent is designed to **never break your codebase**:

1. Works on a **dedicated branch** — never touches main/master directly
2. Skips **recently modified code** (< 7 days) to avoid WIP conflicts
3. Respects **suppression comments** (`# noqa`, `# pylint: disable`)
4. Skips anything **linked to open issues** in commit history
5. Only auto-fixes **high-confidence, low-risk** issues (unused imports, whitespace)
6. Everything else is **reported but not touched** — human decides

---

## 🌍 Real-World Impact

| Metric | Value |
|--------|-------|
| Dev time lost to debt | ~42% (McKinsey, 2023) |
| Avg cost per tech debt hour | $85 (CAST Research) |
| Issues DevDebt can auto-fix | Unused imports, trailing whitespace, missing newlines |
| Issues DevDebt surfaces | Dead code, outdated deps, missing tests |

---

## 🔮 Future Roadmap

- [ ] Support JavaScript/TypeScript (ESLint integration)
- [ ] LLM-powered PR descriptions with severity reasoning
- [ ] GitHub Actions workflow for scheduled debt scans
- [ ] Slack/Teams notification when debt threshold exceeded
- [ ] Dashboard for debt trends over time

---

## 📝 License

MIT — Built for the GitAgent Hackathon 2025
