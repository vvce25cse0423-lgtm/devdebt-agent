#!/usr/bin/env python3
"""
DevDebt Agent - Autonomous Technical Debt Resolution using GitAgent
Open Innovation Hackathon Submission
"""

import argparse
import sys
from agent.scanner import DebtScanner
from agent.git_context import GitContextReader
from agent.fixer import DebtFixer
from agent.pr_creator import PRCreator
from agent.reporter import Reporter


def main():
    parser = argparse.ArgumentParser(
        description="DevDebt Agent - Autonomously find and fix technical debt in GitHub repos"
    )
    parser.add_argument("--repo", required=True, help="GitHub repo URL to scan (e.g. https://github.com/owner/repo)")
    parser.add_argument("--token", help="GitHub personal access token (or set GITHUB_TOKEN env var)")
    parser.add_argument("--dry-run", action="store_true", help="Scan and report only, don't create PR")
    parser.add_argument("--max-fixes", type=int, default=10, help="Max number of issues to fix per run (default: 10)")
    parser.add_argument("--categories", nargs="+",
                        choices=["unused-imports", "dead-code", "outdated-deps", "missing-tests", "lint"],
                        default=["unused-imports", "lint"],
                        help="Debt categories to target")
    args = parser.parse_args()

    print("\n╔══════════════════════════════════════════╗")
    print("║        DevDebt Agent  v1.0.0             ║")
    print("║  Autonomous Technical Debt Resolution    ║")
    print("╚══════════════════════════════════════════╝\n")

    reporter = Reporter()

    # Step 1: Clone and scan the repo
    print(f"[1/4] Scanning repository: {args.repo}")
    scanner = DebtScanner(args.repo, args.token)
    repo_path, debt_items = scanner.scan(categories=args.categories)

    if not debt_items:
        print("✅ No technical debt found! Repository is clean.")
        sys.exit(0)

    reporter.print_debt_summary(debt_items)

    # Step 2: Read git history for context
    print(f"\n[2/4] Reading git history for context...")
    ctx_reader = GitContextReader(repo_path)
    debt_items = ctx_reader.enrich_with_context(debt_items)
    print(f"   ✓ Enriched {len(debt_items)} debt items with git blame + commit history")

    # Step 3: Apply safe fixes
    print(f"\n[3/4] Applying safe fixes (max: {args.max_fixes})...")
    fixer = DebtFixer(repo_path)
    fixed_items, skipped_items = fixer.fix(debt_items, max_fixes=args.max_fixes)

    print(f"   ✓ Fixed:   {len(fixed_items)} issues")
    print(f"   ✗ Skipped: {len(skipped_items)} issues (intentional/unsafe)")

    if not fixed_items:
        print("\n⚠️  No safe fixes could be applied automatically.")
        reporter.print_skipped_reasons(skipped_items)
        sys.exit(0)

    if args.dry_run:
        print("\n[DRY RUN] Skipping PR creation. Here's what would have been fixed:")
        reporter.print_fixed_items(fixed_items)
        sys.exit(0)

    # Step 4: Create pull request
    print(f"\n[4/4] Creating pull request...")
    pr_creator = PRCreator(args.repo, repo_path, args.token)
    pr_url = pr_creator.create_pr(fixed_items, skipped_items)

    print(f"\n✅ Done! Pull request created: {pr_url}")
    reporter.print_final_summary(fixed_items, skipped_items, pr_url)


if __name__ == "__main__":
    main()
