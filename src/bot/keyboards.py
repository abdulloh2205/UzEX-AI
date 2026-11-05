from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_language_keyboard() -> InlineKeyboardMarkup:
    """Returns an inline keyboard with language selection buttons."""
    buttons = [
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang:ru"),
            InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="set_lang:uz"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
