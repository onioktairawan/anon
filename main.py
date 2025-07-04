import asyncio
from bot import start_anon_bot
from support import start_support_bot

if __name__ == "__main__":
    asyncio.run(asyncio.gather(
        start_anon_bot(),
        start_support_bot()
    ))
