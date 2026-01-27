#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Send Sherpa installation instruction to Telegram"""

import sys
import asyncio
from pathlib import Path
from telethon import TelegramClient

# UTF-8 for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Configuration from Obsidian
SESSION_PATH = r"C:\Users\user\.claude\REDACTED-PATH\Transkribator\work_chats_session"
API_ID = 31918065
API_HASH = "a50f17d6633b2142a9e622f24e90dd6a"

async def send():
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)

    try:
        await client.connect()

        if not await client.is_user_authorized():
            print("❌ Сессия не авторизована!")
            return

        me = await client.get_me()
        print(f"✅ Подключено: {me.first_name}")

        # Read message from file
        message_file = r"C:\Users\user\.claude\REDACTED-PATH\Transkribator\telegram_message.txt"
        with open(message_file, 'r', encoding='utf-8') as f:
            message = f.read()

        # Find chat "Приемка квартир"
        dialogs = await client.get_dialogs()
        target_dialog = None

        for dialog in dialogs:
            if dialog.name and 'Приемка квартир' in dialog.name:
                target_dialog = dialog
                break

        if not target_dialog:
            print("❌ Чат 'Приемка квартир' не найден")
            print("\nДоступные чаты:")
            async for d in client.iter_dialogs():
                if d.name:
                    print(f"  - {d.name}")
            return

        print(f"🎯 Чат найден: {target_dialog.name}")

        # Send message
        await client.send_message(target_dialog.entity, message)
        print("✅ Сообщение отправлено!")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.disconnect()
        print("\n👋 Сессия закрыта")

if __name__ == "__main__":
    asyncio.run(send())
