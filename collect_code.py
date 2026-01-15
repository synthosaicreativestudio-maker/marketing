#!/usr/bin/env python3
"""
Скрипт для сбора всего кода проекта в один файл для Code Review.
Игнорирует секреты, виртуальные окружения, кэш и другие ненужные файлы.
"""
import os
import re

# Папки, которые мы ИГНОРИРУЕМ
IGNORE_DIRS = {
    '.git', 'venv', 'env', '.venv', '__pycache__', '.idea', '.vscode', 
    'logs', '.ruff_cache', '.mypy_cache', 'node_modules', '.pytest_cache',
    'build', 'dist', '.eggs', '*.egg-info'
}

# Файлы, которые мы ИГНОРИРУЕМ
IGNORE_FILES = {
    '.DS_Store', 'poetry.lock', 'yarn.lock', 'Thumbs.db', '.gitignore',
    'full_project_code.txt'  # Чтобы не включать сам результат
}

# Расширения файлов, которые мы ИГНОРИРУЕМ
IGNORE_EXTENSIONS = {
    '.pyc', '.pyo', '.pyd', '.png', '.jpg', '.jpeg', '.gif', '.svg', 
    '.ico', '.webp', '.sqlite', '.db', '.log', '.tmp', '.temp',
    '.key', '.pem', '.p12', '.pfx', '.crt', '.cer'
}

# Файлы с секретами, которые НЕЛЬЗЯ читать
SECRET_FILES = {
    '.env', '.env.local', '.env.production', '.env.staging', '.env.backup',
    '.env.enc', 'env.server.txt', 'cloudflare_tunnel_token.txt',
    'config.py', 'secrets.py'
}

# Паттерны для поиска секретов в файлах (для предупреждения)
SECRET_PATTERNS = [
    r'API[_\s]*KEY\s*[:=]\s*["\']?[A-Za-z0-9_-]{20,}',
    r'SECRET\s*[:=]\s*["\']?[A-Za-z0-9_-]{20,}',
    r'PASSWORD\s*[:=]\s*["\']?[A-Za-z0-9_-]{10,}',
    r'TOKEN\s*[:=]\s*["\']?[A-Za-z0-9_-]{20,}',
    r'PRIVATE[_\s]*KEY',
    r'CREDENTIALS',
]

# Безопасные .json файлы, которые можно включить
SAFE_JSON_FILES = {
    'package.json', 'tsconfig.json', '.eslintrc.json', '.prettierrc.json'
}

def is_secret_file(file_path: str) -> bool:
    """Проверяет, является ли файл секретным."""
    file_name = os.path.basename(file_path)
    
    # Проверяем имя файла
    if file_name in SECRET_FILES:
        return True
    
    # Проверяем паттерны в имени файла
    if any(pattern in file_name.lower() for pattern in ['secret', 'credential', 'key', 'token']):
        # Исключаем безопасные файлы
        if file_name in SAFE_JSON_FILES:
            return False
        return True
    
    # Проверяем расширение .json (кроме безопасных)
    if file_path.endswith('.json'):
        if file_name in SAFE_JSON_FILES:
            return False
        # Исключаем все .json файлы (могут содержать ключи)
        return True
    
    return False

def check_for_secrets(content: str, file_path: str) -> list:
    """Проверяет содержимое файла на наличие секретов."""
    warnings = []
    for pattern in SECRET_PATTERNS:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            # Показываем только начало совпадения (без самого секрета)
            start = max(0, match.start() - 20)
            end = min(len(content), match.end() + 20)
            snippet = content[start:end].replace('\n', ' ')
            warnings.append(f"  ⚠️  Найден возможный секрет в {file_path}: ...{snippet}...")
    return warnings

def collect_project_code(output_file='full_project_code.txt'):
    """Собирает весь код проекта в один файл."""
    warnings = []
    total_files = 0
    total_size = 0
    
    with open(output_file, 'w', encoding='utf-8') as outfile:
        # Заголовок
        outfile.write("=" * 80 + "\n")
        outfile.write("PROJECT CODE COLLECTION FOR CODE REVIEW\n")
        outfile.write("=" * 80 + "\n\n")
        
        # Структура папок
        outfile.write("=== PROJECT STRUCTURE ===\n\n")
        for root, dirs, files in os.walk('.'):
            # Фильтрация папок
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
            
            # Пропускаем скрытые папки (кроме корня)
            if root != '.' and os.path.basename(root).startswith('.'):
                continue
            
            level = root.replace('.', '').count(os.sep)
            indent = ' ' * 2 * level
            rel_path = root if root != '.' else '.'
            outfile.write(f"{indent}{os.path.basename(root) or '.'}/\n")
            
            subindent = ' ' * 2 * (level + 1)
            for f in sorted(files):
                if f in IGNORE_FILES or f.startswith('.'):
                    continue
                if any(f.endswith(ext) for ext in IGNORE_EXTENSIONS):
                    continue
                if is_secret_file(os.path.join(root, f)):
                    outfile.write(f"{subindent}{f} [SECRET - EXCLUDED]\n")
                    continue
                outfile.write(f"{subindent}{f}\n")
        
        outfile.write("\n\n" + "=" * 80 + "\n")
        outfile.write("=== FILE CONTENTS ===\n")
        outfile.write("=" * 80 + "\n\n")
        
        # Содержимое файлов
        for root, dirs, files in os.walk('.'):
            # Фильтрация папок
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
            
            # Пропускаем скрытые папки
            if root != '.' and os.path.basename(root).startswith('.'):
                continue
            
            for file in sorted(files):
                if file in IGNORE_FILES or file.startswith('.'):
                    continue
                if any(file.endswith(ext) for ext in IGNORE_EXTENSIONS):
                    continue
                if is_secret_file(os.path.join(root, file)):
                    continue
                
                file_path = os.path.join(root, file)
                
                try:
                    # Проверяем размер файла
                    file_size = os.path.getsize(file_path)
                    total_size += file_size
                    
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as infile:
                        content = infile.read()
                    
                    # Проверяем на секреты
                    file_warnings = check_for_secrets(content, file_path)
                    if file_warnings:
                        warnings.extend(file_warnings)
                    
                    total_files += 1
                    outfile.write(f"\n\n{'='*80}\n")
                    outfile.write(f"FILE: {file_path}\n")
                    outfile.write(f"SIZE: {file_size} bytes\n")
                    outfile.write(f"{'='*80}\n\n")
                    outfile.write(content)
                    
                except UnicodeDecodeError:
                    outfile.write(f"\n\n{'='*80}\n")
                    outfile.write(f"FILE: {file_path} [BINARY FILE - SKIPPED]\n")
                    outfile.write(f"{'='*80}\n\n")
                except Exception as e:
                    outfile.write(f"\n\n{'='*80}\n")
                    outfile.write(f"FILE: {file_path} [ERROR READING: {e}]\n")
                    outfile.write(f"{'='*80}\n\n")
        
        # Статистика и предупреждения
        outfile.write("\n\n" + "=" * 80 + "\n")
        outfile.write("=== STATISTICS ===\n")
        outfile.write("=" * 80 + "\n\n")
        outfile.write(f"Total files processed: {total_files}\n")
        outfile.write(f"Total size: {total_size / 1024 / 1024:.2f} MB\n")
        
        if warnings:
            outfile.write(f"\n\n{'='*80}\n")
            outfile.write("=== SECURITY WARNINGS ===\n")
            outfile.write("=" * 80 + "\n\n")
            outfile.write("⚠️  ВНИМАНИЕ: В следующих файлах обнаружены возможные секреты:\n\n")
            for warning in warnings:
                outfile.write(warning + "\n")
            outfile.write("\nПроверьте эти файлы перед отправкой!\n")
    
    print(f"\n✅ Готово! Весь код собран в файл: {output_file}")
    print(f"📊 Статистика:")
    print(f"   - Обработано файлов: {total_files}")
    print(f"   - Общий размер: {total_size / 1024 / 1024:.2f} MB")
    
    if warnings:
        print(f"\n⚠️  ВНИМАНИЕ: Обнаружено {len(warnings)} предупреждений о возможных секретах!")
        print("   Проверьте файл перед отправкой программисту!")
    else:
        print("\n✅ Секретов не обнаружено. Файл готов к отправке.")

if __name__ == '__main__':
    collect_project_code()
