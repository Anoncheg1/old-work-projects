#!/usr/bin/env python3
import os
import sys
from typing import List, Optional
from pathlib import Path
import requests


LOG_FOLDER = Path('/home/mpoil/log')
TELEGRAM_LOG = LOG_FOLDER / 'telegram-output.log'


LOG_FOLDER: str = os.environ.get('LOG_FOLDER', None)
if LOG_FOLDER:
    LOG_FOLDER = Path('/home/mpoil/log')
    TELEGRAM_LOG: str = LOG_FOLDER / 'telegram-output.log'
    MAIN_LOG:str  = LOG_FOLDER / 'log.log'

TOKEN = 'xxx'
CHAT_ID = '-4k'

def send_telegram_notification(message: str, telegram_log: Optional[str] = None, main_log: Optional[str] = None):
    if telegram_log:
        telegram_log_path = Path(telegram_log)
        telegram_log_path.parent.mkdir(parents=True, exist_ok=True)

        last_message = telegram_log_path.read_text().strip().split('\n')[-1] if telegram_log_path.exists() else ''

        if message != last_message:
            with telegram_log_path.open('a') as f:
                f.write(f"{message}\n")
    else:
        # Always send if there's no telegram log to check against
        last_message = ''

    if message != last_message:
        if main_log:
            main_log_path = Path(main_log)
            main_log_path.parent.mkdir(parents=True, exist_ok=True)
            with main_log_path.open('a') as f:
                f.write(f"{message}\n")

        print(f"{message}\n")

    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": message},
        headers={"User-Agent": "mozilla"}
    ).raise_for_status()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("No input")
        sys.exit(1)

    send_telegram_notification(' '.join(sys.argv[1:]))
