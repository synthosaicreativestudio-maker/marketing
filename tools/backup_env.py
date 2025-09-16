#!/usr/bin/env python3
"""Инструмент: зашифровать локальный .env и опционно запушить зашифрованную копию в репозиторий.

Принцип: не загружать открытые секреты в репо. Файл шифруется локально симметричным паролем
и сохраняется как `.env.enc`. При необходимости скрипт может закоммитить и запушить этот
файл в указанную ветку удалённого репозитория (рекомендуется отдельный приватный репозиторий).

Требования:
- openssl в PATH (macOS обычно имеет)
- git (если используется --push)

Пример использования:
  python3 tools/backup_env.py --passphrase PROMPT --out .env.enc --push --remote origin --branch env-backups

Опция --passphrase 'PROMPT' означает запрос пароля у пользователя (рекомендуется).
"""

import argparse
import subprocess
from pathlib import Path
import getpass
import sys


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / '.env'


def run(cmd, check=True):
    res = subprocess.run(cmd, shell=True)
    if check and res.returncode != 0:
        raise SystemExit(f'Команда не удалась: {cmd}')


def encrypt_env(passphrase: str, out: Path):
    if not ENV_PATH.exists():
        raise SystemExit('.env не найден в корне проекта')
    # Используем openssl для шифрования симметричным паролем (AES-256-CBC)
    cmd = f"openssl enc -aes-256-cbc -salt -in '{ENV_PATH}' -out '{out}' -pass pass:'{passphrase}'"
    print('Шифруем .env...')
    run(cmd)
    print(f'Зашифрованный файл сохранён: {out}')


def git_commit_and_push(path: Path, remote: str, branch: str, message: str):
    print('Добавляем файл в git и пушим...')
    run(f"git add '{path}'")
    run(f"git commit -m " + "'" + message + "'")
    # Создаём ветку или переключаемся
    run(f"git checkout -B {branch}")
    run(f"git push {remote} {branch}")
    print('Пуш завершён')


def main():
    parser = argparse.ArgumentParser(description='Encrypt .env and optionally push encrypted copy to git remote')
    parser.add_argument('--passphrase', default='PROMPT', help="'PROMPT' to ask interactively or provide passphrase")
    parser.add_argument('--out', default='.env.enc', help='Output encrypted filename')
    parser.add_argument('--push', action='store_true', help='Commit and push encrypted file to git remote')
    parser.add_argument('--remote', default='origin', help='Git remote name')
    parser.add_argument('--branch', default='env-backups', help='Branch to push the encrypted file to')
    parser.add_argument('--message', default='chore: add encrypted env backup', help='Commit message')
    args = parser.parse_args()

    if args.passphrase == 'PROMPT':
        passphrase = getpass.getpass('Введите пароль для шифрования (не отображается): ')
        if not passphrase:
            raise SystemExit('Пароль не задан')
    else:
        passphrase = args.passphrase

    out_path = ROOT / args.out
    encrypt_env(passphrase, out_path)

    if args.push:
        # Пользовательское предупреждение
        confirm = input(f"Вы собираетесь закоммитить и запушить '{out_path}' в удалённый репозиторий. Продолжить? [y/N]: ")
        if confirm.lower() != 'y':
            print('Отменено')
            sys.exit(0)
        git_commit_and_push(out_path, args.remote, args.branch, args.message)


if __name__ == '__main__':
    main()
