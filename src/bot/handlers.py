import asyncio
import logging
from typing import Optional
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ChatAction, ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest

from src.agent.orchestrator import AgentOrchestrator, AgentResponse
from src.bot.keyboards import get_language_keyboard
from src.bot.messages import (
    START_FIRST_TIME_RU,
    START_RETURNING_RU,
    START_RETURNING_UZ,
    HELP_RU,
    HELP_UZ,
    CHOOSE_LANGUAGE_RU,
    CHOOSE_LANGUAGE_UZ,
    LANGUAGE_SET_CONFIRM_RU,
    LANGUAGE_SET_CONFIRM_UZ,
    EMPTY_QUERY_RU,
    EMPTY_QUERY_UZ,
    NON_TEXT_INPUT_RU,
    NON_TEXT_INPUT_UZ,
    GENERIC_ERROR_RU,
    GENERIC_ERROR_UZ,
)
from src.bot.user_preferences import user_preferences_repo
from src.bot.utils import split_message, sanitize_secrets

logger = logging.getLogger(__name__)

router = Router(name="uzex_bot_router")


async def send_typing_action(message: Message) -> None:
    """Best-effort typing indicator that doesn't fail if unsupported in test environment."""
    try:
        if message.bot:
            await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    except Exception as e:
        logger.debug(f"Could not send typing action: {sanitize_secrets(str(e))}")


async def safe_answer(message: Message, text: str) -> None:
    """
    Sends message chunks respecting Telegram limits and handles Markdown parsing fallbacks.
    """
    chunks = split_message(text)
    for chunk in chunks:
        try:
            await message.answer(chunk, parse_mode=ParseMode.MARKDOWN)
        except TelegramBadRequest:
            # Fallback to plain text if Markdown format is slightly invalid
            await message.answer(chunk, parse_mode=None)


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    saved_lang = user_preferences_repo.get_language(user_id)

    if saved_lang:
        # Returning user: keep saved language, show returning welcome
        welcome_text = START_RETURNING_UZ if saved_lang == "uz" else START_RETURNING_RU
        await message.answer(welcome_text, parse_mode=ParseMode.MARKDOWN)
    else:
        # First-time user: greeting + language selection buttons
        await message.answer(
            START_FIRST_TIME_RU,
            reply_markup=get_language_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    saved_lang = user_preferences_repo.get_language(user_id) or "ru"
    help_text = HELP_UZ if saved_lang == "uz" else HELP_RU
    await message.answer(help_text, parse_mode=ParseMode.MARKDOWN)


@router.message(Command("language"))
async def handle_language(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    saved_lang = user_preferences_repo.get_language(user_id) or "ru"
    choose_text = CHOOSE_LANGUAGE_UZ if saved_lang == "uz" else CHOOSE_LANGUAGE_RU
    await message.answer(
        choose_text,
        reply_markup=get_language_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )


@router.callback_query(F.data.startswith("set_lang:"))
async def handle_language_callback(callback: CallbackQuery) -> None:
    if not callback.data:
        return

    lang_code = callback.data.split(":", 1)[1]
    if lang_code not in ("ru", "uz"):
        await callback.answer()
        return

    user_id = callback.from_user.id if callback.from_user else 0
    user_preferences_repo.set_language(user_id, lang_code)

    try:
        await callback.answer()
    except Exception as e:
        logger.debug(f"Failed to answer callback query: {sanitize_secrets(str(e))}")

    confirm_text = LANGUAGE_SET_CONFIRM_UZ if lang_code == "uz" else LANGUAGE_SET_CONFIRM_RU
    if callback.message:
        await callback.message.answer(confirm_text, parse_mode=ParseMode.MARKDOWN)


@router.message(F.text)
async def handle_text_query(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    saved_lang = user_preferences_repo.get_language(user_id)

    raw_text = (message.text or "").strip()
    if not raw_text:
        empty_hint = EMPTY_QUERY_UZ if saved_lang == "uz" else EMPTY_QUERY_RU
        await message.answer(empty_hint, parse_mode=ParseMode.MARKDOWN)
        return

    # Trigger typing indicator
    await send_typing_action(message)

    try:
        # For analytical queries, the question's natural language has priority.
        # Fall back to saved_lang if query language is ambiguous.
        from src.agent.language import LanguageDetector
        detected_lang = LanguageDetector.detect(raw_text)
        query_lang = detected_lang or saved_lang or "ru"

        # Delegate directly to the existing AgentOrchestrator
        response: AgentResponse = await AgentOrchestrator.process_question(
            user_message=raw_text,
            user_id=user_id,
            force_language=query_lang,
            use_llm=True
        )

        # If user had no preference set, auto-record language detected by Agent Core
        if not saved_lang and response.language in ("ru", "uz"):
            user_preferences_repo.set_language(user_id, response.language)

        await safe_answer(message, response.text)

    except asyncio.TimeoutError:
        logger.warning(f"Request timeout processing message for user {user_id}")
        timeout_msg = (
            "⏳ So‘rovni bajarish vaqti tugadi. Iltimos, so‘rovingizni soddaroq shaklda bering."
            if saved_lang == "uz"
            else "⏳ Время ожидания ответа истекло. Пожалуйста, попробуйте упростить запрос."
        )
        await message.answer(timeout_msg, parse_mode=ParseMode.MARKDOWN)

    except TelegramAPIError as e:
        logger.error(f"Telegram API error while answering user {user_id}: {sanitize_secrets(str(e))}")

    except Exception as e:
        logger.error(
            f"Unexpected error processing user {user_id} message: {type(e).__name__}: {sanitize_secrets(str(e))}",
            exc_info=False
        )
        error_msg = GENERIC_ERROR_UZ if saved_lang == "uz" else GENERIC_ERROR_RU
        await message.answer(error_msg, parse_mode=ParseMode.MARKDOWN)


@router.message(~F.text)
async def handle_non_text_message(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    saved_lang = user_preferences_repo.get_language(user_id) or "ru"
    non_text_msg = NON_TEXT_INPUT_UZ if saved_lang == "uz" else NON_TEXT_INPUT_RU
    await message.answer(non_text_msg, parse_mode=ParseMode.MARKDOWN)
