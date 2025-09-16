#!/usr/bin/env python3
"""
Simple docs generator: collects key docs and writes a summary into README.md
Usage:
  python3 tools/generate_docs.py --dry-run
  python3 tools/generate_docs.py --commit

Behavior:
- Reads CHANGELOG.md, IMPLEMENTATIONS.md, RULES.md and produces a `Docs summary` section
- If --commit is passed, stages and commits README.md changes
"""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
README = ROOT / 'README.md'

def read_file(p: Path) -> str:
    if not p.exists():
        return ''
    return p.read_text(encoding='utf-8')

def build_summary(changelog, impls, rules):
    parts = [
        '# Docs summary (auto-generated)\n',
        '## Rules (short)\n',
        rules.strip()[:1000] + ('...' if len(rules) > 1000 else ''),
        '\n\n## Recent changelog (top)\n',
        changelog.strip().split('\n')[0:20] and '\n'.join(changelog.strip().split('\n')[0:20]) or '',
        '\n\n## Recent implementations (top)\n',
        impls.strip().split('\n')[0:40] and '\n'.join(impls.strip().split('\n')[0:40]) or '',
    ]
    return '\n'.join(parts)

def update_readme(summary: str, dry_run=True):
    readme_text = read_file(README)
    marker_start = '<!-- DOCS_SUMMARY_START -->'
    marker_end = '<!-- DOCS_SUMMARY_END -->'
    if marker_start in readme_text and marker_end in readme_text:
        before = readme_text.split(marker_start)[0]
        after = readme_text.split(marker_end)[1]
        new_readme = before + marker_start + '\n' + summary + '\n' + marker_end + after
    else:
        new_readme = readme_text + '\n\n' + marker_start + '\n' + summary + '\n' + marker_end + '\n'

    if dry_run:
        print('--- DRY RUN: Generated summary ---')
        print(summary[:1000])
        return False

    README.write_text(new_readme, encoding='utf-8')
    return True

def git_commit(path: Path, message: str):
    subprocess.check_call(['git', 'add', str(path)])
    subprocess.check_call(['git', 'commit', '-m', message])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--commit', action='store_true')
    args = parser.parse_args()

    changelog = read_file(DOCS / 'CHANGELOG.md')
    impls = read_file(DOCS / 'IMPLEMENTATIONS.md')
    rules = read_file(DOCS / 'RULES.md')

    summary = build_summary(changelog, impls, rules)
    ok = update_readme(summary, dry_run=args.dry_run or not args.commit)

    if ok and args.commit:
        git_commit(README, 'chore(docs): update docs summary (auto)')
        print('Committed README.md')
    else:
        print('Dry run complete. Use --commit to write and commit changes.')

if __name__ == '__main__':
    main()
