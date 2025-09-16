#!/usr/bin/env python3
"""Launch bot in isolated subprocess to avoid event loop conflicts."""

import subprocess
import sys
import os
from pathlib import Path

def main():
    # Read token from .env
    env_file = Path('.env')
    if not env_file.exists():
        print("❌ .env file not found!")
        return 1
    
    token = None
    with open(env_file) as f:
        for line in f:
            if line.startswith('TELEGRAM_TOKEN='):
                token = line.split('=', 1)[1].strip().strip('"')
                break
    
    if not token:
        print("❌ TELEGRAM_TOKEN not found in .env!")
        return 1
    
    print(f"🚀 Starting MarketingBot...")
    print(f"📱 Token: {token[:15]}...")
    
    # Set up environment
    env = os.environ.copy()
    env['TELEGRAM_BOT_TOKEN'] = token
    
    # Start bot in subprocess
    try:
        proc = subprocess.Popen(
            [sys.executable, 'bot.py'],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        print(f"✅ Bot started with PID: {proc.pid}")
        print("📋 Bot output:")
        print("-" * 50)
        
        # Stream output
        for line in proc.stdout:
            print(line.rstrip())
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping bot...")
        proc.terminate()
        proc.wait()
        print("✅ Bot stopped")
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
