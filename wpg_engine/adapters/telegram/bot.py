"""
Main Telegram bot class
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from wpg_engine.adapters.telegram.handlers import register_handlers
from wpg_engine.config.settings import settings
from wpg_engine.models import init_db

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram bot for WPG engine"""

    def __init__(self):
        if not settings.telegram.token:
            raise ValueError("Telegram bot token is not configured")

        self.bot = Bot(
            token=settings.telegram.token,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
        )
        self.dp = Dispatcher()

        # Register handlers
        register_handlers(self.dp)

    async def start(self) -> None:
        """Start the bot"""
        logger.info("Starting Telegram bot...")

        # Initialize database
        await init_db()

        # Store bot instance in dispatcher for handlers
        self.dp["bot_instance"] = self

        try:
            await self.dp.start_polling(self.bot)
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop the bot"""
        logger.info("Stopping Telegram bot...")
        await self.bot.session.close()

    async def run(self) -> None:
        """Run the bot"""
        try:
            await self.start()
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot error: {e}")
            raise


async def main():
    """Main function to run the bot"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    bot = TelegramBot()
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
