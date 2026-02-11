#!/usr/bin/env python3
"""
Скрипт для обновления переменных окружения.
"""

import os

def update_env_file():
    """Обновляет .env файл с новыми переменными."""
    
    # Читаем существующий .env файл
    env_file = '.env'
    env_vars = {}
    
    if os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value
    
    # Обновляем переменные
    env_vars['WEB_APP_MENU_URL'] = 'https://synthosaicreativestudio-maker.github.io/marketing/menu.html'
    
    # Записываем обновленный .env файл
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write("# Telegram Bot Configuration\n")
        f.write(f"TELEGRAM_TOKEN=\"{env_vars.get('TELEGRAM_TOKEN', '')}\"\n")
        f.write(f"ADMIN_TELEGRAM_ID={env_vars.get('ADMIN_TELEGRAM_ID', '')}\n\n")
        
        f.write("# OpenAI Configuration\n")
        f.write(f"OPENAI_API_KEY=\"{env_vars.get('OPENAI_API_KEY', '')}\"\n")
        f.write(f"OPENAI_ASSISTANT_ID=\"{env_vars.get('OPENAI_ASSISTANT_ID', '')}\"\n\n")
        
        f.write("# Google Sheets Configuration\n")
        f.write(f"SHEET_URL=\"{env_vars.get('SHEET_URL', '')}\"\n")
        f.write(f"TICKETS_SHEET_URL=\"{env_vars.get('TICKETS_SHEET_URL', '')}\"\n")
        f.write(f"WEB_APP_URL=\"{env_vars.get('WEB_APP_URL', '')}\"\n")
        f.write(f"WEB_APP_MENU_URL=\"{env_vars.get('WEB_APP_MENU_URL', '')}\"\n")
        f.write(f"SHEET_ID={env_vars.get('SHEET_ID', '')}\n\n")
        
        f.write("# Google Cloud Platform Service Account\n")
        f.write(f"GCP_SA_FILE={env_vars.get('GCP_SA_FILE', '')}\n")
        f.write(f"SHEET_NAME={env_vars.get('SHEET_NAME', '')}\n\n")
        
        f.write("# Appeals sheet configuration\n")
        f.write(f"APPEALS_SHEET_ID={env_vars.get('APPEALS_SHEET_ID', '')}\n")
        f.write(f"APPEALS_SHEET_NAME={env_vars.get('APPEALS_SHEET_NAME', '')}\n")
    
    print("✅ .env файл обновлен с новой переменной WEB_APP_MENU_URL")

if __name__ == "__main__":
    update_env_file()
