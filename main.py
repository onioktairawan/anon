# main.py

import asyncio
from support import start_support_bot
from bot import start_anon_bot

async def main():
    await asyncio.gather(
        start_anon_bot(),    # ← tambahkan tanda kurung untuk menjalankan coroutine
        start_support_bot()
    )

if __name__ == "__main__":
    asyncio.run(main())
