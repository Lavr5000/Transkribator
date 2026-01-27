#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Send instructions to Telegram via Userbot
"""
import sys
import os
from telethon import TelegramClient

# Set UTF-8 encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Configuration
API_ID = 31918065
API_HASH = "a50f17d6633b2142a9e622f24e90dd6a"
SESSION_FILE = r"C:\Users\user\.claude\0 ProEKTi\blogger\telegram_session.session"
CHAT_NAME = "Приемка квартир"

async def send_instructions():
    """Send instructions to Telegram chat"""

    # Read message
    msg_file = r'C:\Users\user\.claude\0 ProEKTi\Transkribator\telegram_message.txt'
    with open(msg_file, 'r', encoding='utf-8') as f:
        message = f.read()

    # Read bat file content
    bat_file = r'C:\Users\user\.claude\0 ProEKTi\Transkribator\transcriber_server_start.bat'
    with open(bat_file, 'r', encoding='utf-8') as f:
        bat_content = f.read()

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

                # Send bat file as document
                from io import BytesIO
                bat_bytes = BytesIO(bat_content.encode('utf-8'))
                bat_bytes.name = 'transcriber_server_start.bat'
                await client.send_file(dialog.entity, bat_bytes, caption="📎 Файл для запуска сервера")

                print("[OK] Instructions sent successfully!")
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
    asyncio.run(send_instructions())
