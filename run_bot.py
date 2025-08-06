"""
Main script to run the Telegram bot
"""

import asyncio
import logging

from wpg_engine.adapters.telegram.bot import main

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
