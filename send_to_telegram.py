import sys
sys.path.insert(0, r'C:\Users\user\.claude\0 ProEKTi\telegram\work_chats')
from sender import ChatSender
import asyncio

async def send():
    s = ChatSender()

    # Read message from file
    with open('telegram_message.txt', 'r', encoding='utf-8') as f:
        message = f.read()

    await s.send_message('Приемка квартир', message)
    await s.close()

asyncio.run(send())
