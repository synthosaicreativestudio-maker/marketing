#!/usr/bin/env python3
"""
Скрипт для обновления SHEET_ID в .env файле.
"""

import os

def update_sheet_id():
    """Обновляет SHEET_ID в .env файле."""
    env_file = '.env'
    new_sheet_id = '15XxSIpD_gMZaSOIrqDVCNI2EqBzphEGiG0ZNJ3HR8hI'
    
    if not os.path.exists(env_file):
        print(f"❌ Файл {env_file} не найден")
        return
    
    # Читаем содержимое файла
    with open(env_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Обновляем SHEET_ID
    updated = False
    for i, line in enumerate(lines):
        if line.startswith('SHEET_ID='):
            old_value = line.strip().split('=', 1)[1]
            lines[i] = f'SHEET_ID={new_sheet_id}\n'
            print(f"✅ Обновлен SHEET_ID: {old_value} -> {new_sheet_id}")
            updated = True
            break
    
    if not updated:
        # Добавляем SHEET_ID если его нет
        lines.append(f'SHEET_ID={new_sheet_id}\n')
        print(f"✅ Добавлен SHEET_ID: {new_sheet_id}")
    
    # Записываем обновленный файл
    with open(env_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"✅ Файл {env_file} обновлен")

if __name__ == "__main__":
    update_sheet_id()
