#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
from telethon import TelegramClient

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

API_ID = 31918065
API_HASH = "a50f17d6633b2142a9e622f24e90dd6a"
SESSION_FILE = r"C:\Users\user\.claude\0 ProEKTi\blogger\telegram_session.session"
CHAT_NAME = "Приемка квартир"

async def send_task():
    task_file = r'C:\Users\user\.claude\0 ProEKTi\Transkribator\task_for_remote_claude.txt'

    with open(task_file, 'r', encoding='utf-8') as f:
        message = f.read()

    print("Sending task to Telegram...")
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

    try:
        await client.start()
        print("Connected!")

        async for dialog in client.iter_dialogs():
            if dialog.name == CHAT_NAME:
                await client.send_message(dialog.entity, message)
                print("[OK] Task sent!")
                break
    finally:
        await client.disconnect()

if __name__ == "__main__":
    import asyncio
    asyncio.run(send_task())
