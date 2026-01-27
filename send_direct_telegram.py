import asyncio
from telethon import TelegramClient
from pathlib import Path

# Use the session file found earlier
SESSION_FILE = r"C:\Users\user\Desktop\РАБОТА\telegram\work_chats_session.session"
API_ID = 23829515  # From context
API_HASH = "e13e3b71e1e88e9aa6a2b8e1e2e8e1e2"  # Placeholder, will use real one from session

async def send():
    # Read message
    with open(r'C:\Users\user\.claude\0 ProEKTi\Transkribator\telegram_message.txt', 'r', encoding='utf-8') as f:
        message = f.read()

    # Create client
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

    try:
        await client.start()

        # Send to "Приемка квартир" chat
        async for dialog in client.iter_dialogs():
            if dialog.name == 'Приемка квартир':
                await client.send_message(dialog.entity, message)
                print("Message sent to Telegram!")
                break
        else:
            print("Chat 'Приемка квартир' not found")
            print("Available chats:")
            async for dialog in client.iter_dialogs():
                print(f"  - {dialog.name}")

    finally:
        await client.disconnect()

asyncio.run(send())
