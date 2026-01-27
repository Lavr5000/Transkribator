#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Send task to Telegram via Userbot
"""
import sys
import os
from telethon import TelegramClient

# Set UTF-8 encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Configuration (from working blogger setup)
API_ID = 31918065
API_HASH = "a50f17d6633b2142a9e622f24e90dd6a"
SESSION_FILE = r"C:\Users\user\.claude\0 ProEKTi\blogger\telegram_session.session"
CHAT_NAME = "Приемка квартир"

async def send_task():
    """Send task to Telegram chat"""
    task_file = r'C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer\TASK_for_Claude.txt'

    if not os.path.exists(task_file):
        print(f"[ERROR] Task file not found: {task_file}")
        return

    # Read task
    with open(task_file, 'r', encoding='utf-8') as f:
        message = f'📋 ЗАДАЧА ДЛЯ CLAUDE CODE:\n\n{f.read()}'

    print("Connecting to Telegram...")
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

    try:
        await client.start()
        print("Connected!")

        # Find chat
        print(f"Looking for chat: {CHAT_NAME}...")
        chat_found = False
        async for dialog in client.iter_dialogs():
            if dialog.name == CHAT_NAME:
                print(f"Found chat: {dialog.name} (ID: {dialog.id})")

                # Send message
                await client.send_message(dialog.entity, message)

                print("[OK] Task sent successfully to Telegram group!")
                chat_found = True
                break

        if not chat_found:
            print(f"[ERROR] Chat '{CHAT_NAME}' not found!")
            print("\nAvailable chats:")
            async for dialog in client.iter_dialogs():
                print(f"  - {dialog.name}")

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()

if __name__ == "__main__":
    import asyncio
    asyncio.run(send_task())
