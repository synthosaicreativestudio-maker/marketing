#!/usr/bin/env python3
"""Configuration validation utility for MarketingBot."""

import os
import sys
from pathlib import Path
from typing import List, Tuple


def validate_env_vars() -> List[Tuple[str, str]]:
    """Validate required environment variables."""
    issues = []
    
    # Required variables
    required_vars = [
        'TELEGRAM_BOT_TOKEN',
        'WEBAPP_URL',
        'AUTH_CODE'
    ]
    
    # Optional but recommended
    recommended_vars = [
        'SHEET_ID',
        'GCP_SA_JSON',
        'REDIS_URL'
    ]
    
    for var in required_vars:
        if not os.environ.get(var):
            issues.append(('error', f'Required environment variable {var} is not set'))
    
    for var in recommended_vars:
        if not os.environ.get(var):
            issues.append(('warning', f'Recommended environment variable {var} is not set'))
    
    # Validate token format
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    if token and not token.count(':') == 1:
        issues.append(('error', 'TELEGRAM_BOT_TOKEN format appears invalid (should contain exactly one colon)'))
    
    # Validate URL format
    webapp_url = os.environ.get('WEBAPP_URL', '')
    if webapp_url and not webapp_url.startswith(('http://', 'https://')):
        issues.append(('error', 'WEBAPP_URL should start with http:// or https://'))
    
    return issues


def validate_file_structure() -> List[Tuple[str, str]]:
    """Validate project file structure."""
    issues = []
    
    required_files = [
        'bot.py',
        'app/main.py',
        'app/__init__.py',
        'plugins/__init__.py',
        'plugins/loader.py',
        'config/plugins.json',
        'requirements.txt',
        'pyproject.toml'
    ]
    
    for file_path in required_files:
        if not Path(file_path).exists():
            issues.append(('error', f'Required file {file_path} is missing'))
    
    # Check for .env file
    if not Path('.env').exists() and not Path('.env.example').exists():
        issues.append(('warning', 'No .env or .env.example file found'))
    
    return issues


def validate_dependencies() -> List[Tuple[str, str]]:
    """Validate Python dependencies."""
    issues = []
    
    try:
        import telegram
        if not hasattr(telegram, '__version__'):
            issues.append(('warning', 'Cannot determine python-telegram-bot version'))
        else:
            version = telegram.__version__
            if not version.startswith('21.'):
                issues.append(('warning', f'python-telegram-bot version {version} may not be compatible (expected 21.x)'))
    except ImportError:
        issues.append(('error', 'python-telegram-bot is not installed'))
    
    try:
        import fastapi
    except ImportError:
        issues.append(('error', 'FastAPI is not installed'))
    
    try:
        import gspread
    except ImportError:
        issues.append(('warning', 'gspread is not installed (Google Sheets integration will not work)'))
    
    return issues


def main():
    """Run all validation checks."""
    print("🔍 MarketingBot Configuration Validation")
    print("=" * 50)
    
    all_issues = []
    
    # Run all validations
    all_issues.extend(validate_env_vars())
    all_issues.extend(validate_file_structure())
    all_issues.extend(validate_dependencies())
    
    # Categorize issues
    errors = [issue for issue in all_issues if issue[0] == 'error']
    warnings = [issue for issue in all_issues if issue[0] == 'warning']
    
    # Print results
    if errors:
        print("\n❌ ERRORS:")
        for _, message in errors:
            print(f"  • {message}")
    
    if warnings:
        print("\n⚠️  WARNINGS:")
        for _, message in warnings:
            print(f"  • {message}")
    
    if not errors and not warnings:
        print("\n✅ All checks passed! Configuration looks good.")
    
    print(f"\nSummary: {len(errors)} errors, {len(warnings)} warnings")
    
    # Exit with appropriate code
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
