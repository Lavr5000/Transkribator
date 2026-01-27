import sys
from pathlib import Path

# Add work_chats to path (same as task_manager.py)
sys.path.insert(0, str(Path(r"C:\Users\user\Desktop\РАБОТА\telegram\work_chats")))

try:
    from sender import ChatSender
    import asyncio

    async def send():
        s = ChatSender()

        # Read message from file
        with open(r'C:\Users\user\.claude\0 ProEKTi\Transkribator\telegram_message.txt', 'r', encoding='utf-8') as f:
            message = f.read()

        await s.send_message('Приемка квартир', message)
        await s.close()

    asyncio.run(send())
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
