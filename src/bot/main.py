import asyncio
import logging
import sys
from typing import Optional
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from src.config import settings
from src.bot.handlers import router
from src.bot.utils import sanitize_secrets

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("uzex_bot")


def validate_bot_token(token: Optional[str] = None) -> str:
    """Validates that BOT_TOKEN exists and is not a placeholder."""
    actual_token = token if token is not None else settings.BOT_TOKEN
    if not actual_token or actual_token.strip() == "" or "your_telegram_bot_token_here" in actual_token:
        error_msg = "Telegram BOT_TOKEN is not configured in .env file. Please provide a valid bot token."
        logger.error(error_msg)
        raise ValueError(error_msg)
    return actual_token.strip()


def create_bot(token: Optional[str] = None) -> Bot:
    """Factory to create and configure the aiogram Bot instance."""
    bot_token = validate_bot_token(token)
    session = AiohttpSession(timeout=60.0)
    return Bot(
        token=bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )


def create_dispatcher() -> Dispatcher:
    """Factory to create and configure the aiogram Dispatcher."""
    dp = Dispatcher()
    dp.include_router(router)
    return dp


async def main() -> None:
    """Main entrypoint for local polling execution of UZEX AI Telegram Bot."""
    bot: Optional[Bot] = None
    try:
        bot = create_bot()
        dp = create_dispatcher()

        bot_info = await bot.get_me()
        logger.info(
            f"Starting UZEX AI Telegram Bot: @{bot_info.username} (ID: {bot_info.id})"
        )

        # Drop any pending updates accumulated while offline
        await bot.delete_webhook(drop_pending_updates=True)

        logger.info("Bot polling loop started. Press Ctrl+C to terminate.")
        await dp.start_polling(bot, polling_timeout=20)

    except ValueError as e:
        logger.error(f"Configuration error: {sanitize_secrets(str(e))}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Critical error in Telegram Bot loop: {sanitize_secrets(str(e))}")
        sys.exit(1)
    finally:
        if bot and bot.session:
            logger.info("Closing bot HTTP session...")
            await bot.session.close()
            logger.info("Bot HTTP session closed.")


if __name__ == "__main__":
    asyncio.run(main())
