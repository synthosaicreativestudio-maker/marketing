#!/usr/bin/env python3
"""CLI для создания записи в docs/IMPLEMENTATIONS.md

Пример:
  python3 tools/record_impl.py --title "Краткий заголовок" --status работает
"""

import argparse
from datetime import datetime
from pathlib import Path
import os
import subprocess


ROOT = Path(__file__).resolve().parents[1]
IMPL = ROOT / 'docs' / 'IMPLEMENTATIONS.md'


TEMPLATE = (
    "---\n"
    "Дата: {date}\n"
    "Заголовок реализации: {title}\n"
    "Краткое описание: {summary}\n"
    "Техническое решение: {solution}\n"
    "Коммиты/PR: {commits}\n"
    "Шаги для воспроизведения:\n{steps}\n"
    "Статус: {status}\n"
    "Примечания: {notes}\n\n"
)


def open_in_editor(path: Path):
    editor = os.environ.get('EDITOR', 'vi')
    subprocess.call([editor, str(path)])


def append_entry(args):
    now = datetime.now().strftime('%Y-%m-%d')
    entry = TEMPLATE.format(
        date=now,
        title=args.title,
        summary=args.summary or '',
        solution=args.solution or '',
        commits=args.commits or '',
        steps=args.steps or '1. ',
        status=args.status,
        notes=args.notes or '',
    )
    with IMPL.open('a', encoding='utf-8') as f:
        f.write(entry)
    print(f'Запись добавлена в {IMPL}')
    if args.edit:
        open_in_editor(IMPL)


def main():
    parser = argparse.ArgumentParser(description='Record an implementation into docs/IMPLEMENTATIONS.md')
    parser.add_argument('--title', required=True, help='Short title')
    parser.add_argument('--summary', help='Short summary')
    parser.add_argument('--solution', help='Technical solution description')
    parser.add_argument('--commits', help='Commits or PR links/hashes')
    parser.add_argument('--steps', help='Steps to reproduce (use \n for new lines)')
    parser.add_argument('--status', choices=['работает', 'не работает'], default='работает')
    parser.add_argument('--notes', help='Additional notes')
    parser.add_argument('--edit', action='store_true', help='Open IMPLEMENTATIONS.md in $EDITOR after append')
    args = parser.parse_args()
    append_entry(args)


if __name__ == '__main__':
    main()
