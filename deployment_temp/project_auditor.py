import os

# --- КОНФИГУРАЦИЯ ---
OUTPUT_FILE = "FULL_PROJECT_DUMP.txt"

# Какие файлы читать (расширения)
ALLOWED_EXTENSIONS = {
    '.py', '.txt', '.md', '.json', '.yml', '.yaml', 
    '.js', '.html', '.css', '.sh'
}

# Какие файлы ИСКЛЮЧАТЬ (чтобы не слить пароли и мусор)
IGNORE_FILES = {
    'project_auditor.py', # Не читать самого себя
    'FULL_PROJECT_DUMP.txt',
    '.env',               # ВАЖНО: Игнорируем файл с ключами
    'credentials.json',   # ВАЖНО: Игнорируем ключи Google
    '.DS_Store',
    'db.sqlite3'
}

# Какие папки ИГНОРИРОВАТЬ
IGNORE_DIRS = {
    'venv', 'env', '.git', '__pycache__', '.idea', '.vscode', 
    'node_modules', 'media', 'static'
}

def generate_tree(startpath):
    """Генерирует визуальное дерево файлов"""
    tree_str = "### PROJECT STRUCTURE ###\n"
    for root, dirs, files in os.walk(startpath):
        # Фильтрация папок
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * (level)
        tree_str += f"{indent}{os.path.basename(root)}/\n"
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            if f not in IGNORE_FILES:
                tree_str += f"{subindent}{f}\n"
    return tree_str + "\n" + "="*50 + "\n\n"

def collect_files(startpath):
    """Читает содержимое файлов"""
    content_str = "### FILE CONTENTS ###\n"
    
    for root, dirs, files in os.walk(startpath):
        # Фильтрация папок
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            if file in IGNORE_FILES:
                continue
                
            _, ext = os.path.splitext(file)
            if ext not in ALLOWED_EXTENSIONS:
                continue
                
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, startpath)
            
            content_str += f"\n{'='*20} START FILE: {rel_path} {'='*20}\n"
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content_str += f.read()
            except Exception as e:
                content_str += f"[ERROR READING FILE: {e}]"
                
            content_str += f"\n{'='*20} END FILE: {rel_path} {'='*20}\n"
            
    return content_str

def main():
    root_dir = os.getcwd()
    print(f"Starting audit in: {root_dir}")
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        # 1. Записываем дерево
        f.write(generate_tree(root_dir))
        # 2. Записываем содержимое
        f.write(collect_files(root_dir))
        
    print(f"Audit completed! File saved as: {OUTPUT_FILE}")
    print("Please send this file to the manager.")

if __name__ == "__main__":
    main()
