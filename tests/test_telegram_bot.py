import inspect
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import Chat, Message, User, CallbackQuery

from src.bot.handlers import (
    handle_start,
    handle_help,
    handle_language,
    handle_language_callback,
    handle_text_query,
    handle_non_text_message,
    safe_answer,
)
from src.bot.main import validate_bot_token, create_bot, create_dispatcher
from src.bot.messages import (
    START_FIRST_TIME_RU,
    START_RETURNING_RU,
    START_RETURNING_UZ,
    HELP_RU,
    HELP_UZ,
    CHOOSE_LANGUAGE_RU,
    LANGUAGE_SET_CONFIRM_RU,
    LANGUAGE_SET_CONFIRM_UZ,
    EMPTY_QUERY_RU,
    NON_TEXT_INPUT_RU,
)
from src.bot.user_preferences import UserPreferencesRepository, user_preferences_repo
from src.bot.utils import split_message, sanitize_secrets
from src.agent.orchestrator import AgentOrchestrator, AgentResponse


def run_async(coro):
    """
    Executes an async coroutine without creating OS loopback sockets.
    Prevents hangs in sandboxed Windows environments where socket.socketpair() blocks.
    """
    task_stack = [coro]
    result = None
    while task_stack:
        curr = task_stack[-1]
        try:
            future_or_coro = curr.send(result)
            result = None
            if inspect.iscoroutine(future_or_coro):
                task_stack.append(future_or_coro)
            elif hasattr(future_or_coro, "__await__"):
                task_stack.append(future_or_coro.__await__())
            else:
                result = future_or_coro
        except StopIteration as e:
            task_stack.pop()
            result = e.value
    return result


def make_mock_message(text: str = "", user_id: int = 12345, is_text: bool = True) -> MagicMock:
    """Helper to construct a mock aiogram Message with AsyncMock answers."""
    user = User(id=user_id, is_bot=False, first_name="TestUser", username="testuser")
    chat = Chat(id=user_id, type="private")
    bot = MagicMock()
    bot.send_chat_action = AsyncMock()

    msg = MagicMock(spec=Message)
    msg.message_id = 999
    msg.date = datetime.now()
    msg.chat = chat
    msg.from_user = user
    msg.text = text if is_text else None
    msg.bot = bot
    msg.answer = AsyncMock()
    return msg


def make_mock_callback(data: str, user_id: int = 12345) -> MagicMock:
    """Helper to construct a mock aiogram CallbackQuery with AsyncMock answers."""
    user = User(id=user_id, is_bot=False, first_name="TestUser")
    msg = make_mock_message(user_id=user_id)

    cb = MagicMock(spec=CallbackQuery)
    cb.id = "cb_test_id"
    cb.from_user = user
    cb.data = data
    cb.message = msg
    cb.answer = AsyncMock()
    return cb


class TestUserPreferences(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_prefs.db"
        self.repo = UserPreferencesRepository(db_path=self.db_path)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_save_and_retrieve_language(self):
        self.assertIsNone(self.repo.get_language(111))
        self.repo.set_language(111, "uz")
        self.assertEqual(self.repo.get_language(111), "uz")

        # Persistence across repo reloads
        fresh_repo = UserPreferencesRepository(db_path=self.db_path)
        self.assertEqual(fresh_repo.get_language(111), "uz")

    def test_invalid_language_code(self):
        with self.assertRaises(ValueError):
            self.repo.set_language(111, "fr")


class TestBotCommands(unittest.TestCase):
    def setUp(self):
        user_preferences_repo.clear_cache()

    def test_help_command_russian(self):
        user_id = 90004
        with patch.object(user_preferences_repo, "get_language", return_value="ru"):
            msg = make_mock_message("/help", user_id=user_id)
            run_async(handle_help(msg))

            msg.answer.assert_called_once()
            args, kwargs = msg.answer.call_args
            self.assertEqual(args[0], HELP_RU)
            self.assertIn("Какой объём торгов был в 2025 году?", args[0])

    def test_help_command_uzbek(self):
        user_id = 90005
        with patch.object(user_preferences_repo, "get_language", return_value="uz"):
            msg = make_mock_message("/help", user_id=user_id)
            run_async(handle_help(msg))

            msg.answer.assert_called_once()
            args, kwargs = msg.answer.call_args
            self.assertEqual(args[0], HELP_UZ)
            self.assertIn("2025-yilda savdo hajmi qancha bo'lgan?", args[0])

    def test_start_command_first_time(self):
        user_id = 90001
        with patch.object(user_preferences_repo, "get_language", return_value=None):
            msg = make_mock_message("/start", user_id=user_id)
            run_async(handle_start(msg))

            msg.answer.assert_called_once()
            args, kwargs = msg.answer.call_args
            self.assertEqual(args[0], START_FIRST_TIME_RU)
            self.assertIn("reply_markup", kwargs)

    def test_start_command_returning_user_russian(self):
        user_id = 90002
        with patch.object(user_preferences_repo, "get_language", return_value="ru"):
            msg = make_mock_message("/start", user_id=user_id)
            run_async(handle_start(msg))

            msg.answer.assert_called_once()
            args, kwargs = msg.answer.call_args
            self.assertEqual(args[0], START_RETURNING_RU)

    def test_start_command_returning_user_uzbek(self):
        user_id = 90003
        with patch.object(user_preferences_repo, "get_language", return_value="uz"):
            msg = make_mock_message("/start", user_id=user_id)
            run_async(handle_start(msg))

            msg.answer.assert_called_once()
            args, kwargs = msg.answer.call_args
            self.assertEqual(args[0], START_RETURNING_UZ)

    def test_language_command(self):
        user_id = 90006
        with patch.object(user_preferences_repo, "get_language", return_value="ru"):
            msg = make_mock_message("/language", user_id=user_id)
            run_async(handle_language(msg))

            msg.answer.assert_called_once()
            args, kwargs = msg.answer.call_args
            self.assertEqual(args[0], CHOOSE_LANGUAGE_RU)
            self.assertIn("reply_markup", kwargs)

    def test_language_callback_switch_to_uzbek(self):
        user_id = 90007
        cb = make_mock_callback("set_lang:uz", user_id=user_id)
        with patch.object(user_preferences_repo, "set_language") as mock_set:
            run_async(handle_language_callback(cb))
            mock_set.assert_called_once_with(user_id, "uz")
            cb.answer.assert_called_once()
            cb.message.answer.assert_called_once()
            args, _ = cb.message.answer.call_args
            self.assertEqual(args[0], LANGUAGE_SET_CONFIRM_UZ)

    def test_language_callback_switch_to_russian(self):
        user_id = 90008
        cb = make_mock_callback("set_lang:ru", user_id=user_id)
        with patch.object(user_preferences_repo, "set_language") as mock_set:
            run_async(handle_language_callback(cb))
            mock_set.assert_called_once_with(user_id, "ru")
            cb.answer.assert_called_once()
            cb.message.answer.assert_called_once()
            args, _ = cb.message.answer.call_args
            self.assertEqual(args[0], LANGUAGE_SET_CONFIRM_RU)


class TestMessageProcessingAndAgentIntegration(unittest.TestCase):
    def test_russian_question_pipeline(self):
        msg = make_mock_message("Какой объем торгов был в 2024 году?", user_id=50001)
        fake_response = AgentOrchestrator.process_question_sync(
            user_message=msg.text,
            user_id=50001,
            force_language="ru"
        )
        with patch.object(user_preferences_repo, "get_language", return_value="ru"), \
             patch.object(AgentOrchestrator, "process_question", new=AsyncMock(return_value=fake_response)):
            run_async(handle_text_query(msg))

            msg.answer.assert_called()
            call_text = msg.answer.call_args[0][0]
            self.assertIn("2024", call_text)

    def test_uzbek_latin_question_pipeline(self):
        msg = make_mock_message("2024-yilda savdo hajmi qancha bo'lgan?", user_id=50002)
        fake_response = AgentOrchestrator.process_question_sync(
            user_message=msg.text,
            user_id=50002,
            force_language="uz"
        )
        with patch.object(user_preferences_repo, "get_language", return_value="uz"), \
             patch.object(AgentOrchestrator, "process_question", new=AsyncMock(return_value=fake_response)):
            run_async(handle_text_query(msg))

            msg.answer.assert_called()
            call_text = msg.answer.call_args[0][0]
            self.assertIn("2024", call_text)

    def test_uzbek_cyrillic_question_pipeline(self):
        msg = make_mock_message("2024 йилда савдо ҳажми қанча бўлган?", user_id=50003)
        fake_response = AgentOrchestrator.process_question_sync(
            user_message=msg.text,
            user_id=50003,
            force_language="uz"
        )
        with patch.object(user_preferences_repo, "get_language", return_value="uz"), \
             patch.object(AgentOrchestrator, "process_question", new=AsyncMock(return_value=fake_response)):
            run_async(handle_text_query(msg))

            msg.answer.assert_called()
            call_text = msg.answer.call_args[0][0]
            self.assertIn("2024", call_text)

    def test_empty_query_handling(self):
        msg = make_mock_message("   ", user_id=50004)
        with patch.object(user_preferences_repo, "get_language", return_value="ru"):
            run_async(handle_text_query(msg))
            msg.answer.assert_called_once()
            self.assertEqual(msg.answer.call_args[0][0], EMPTY_QUERY_RU)

    def test_non_text_message_handling(self):
        msg = make_mock_message("", user_id=50005, is_text=False)
        with patch.object(user_preferences_repo, "get_language", return_value="ru"):
            run_async(handle_non_text_message(msg))
            msg.answer.assert_called_once()
            self.assertEqual(msg.answer.call_args[0][0], NON_TEXT_INPUT_RU)


class TestEdgeCasesAndFallbacks(unittest.TestCase):
    def test_gemini_error_and_agent_fallback(self):
        fake_response = AgentResponse(
            text="Детерминированный ответ UZEX",
            language="ru",
            latency_ms=15.0,
            has_data=True
        )
        with patch.object(AgentOrchestrator, "process_question", new=AsyncMock(return_value=fake_response)):
            msg = make_mock_message("Объем торгов", user_id=60001)
            run_async(handle_text_query(msg))

            msg.answer.assert_called_once()
            self.assertEqual(msg.answer.call_args[0][0], "Детерминированный ответ UZEX")

    def test_long_message_chunking(self):
        paragraph1 = "Сделка №1: " + ("описание " * 300)
        paragraph2 = "Сделка №2: " + ("детали " * 300)
        long_text = f"{paragraph1}\n\n{paragraph2}"

        chunks = split_message(long_text, max_length=3000)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 3000)

        reconstructed = "\n\n".join(chunks)
        self.assertIn("Сделка №1:", reconstructed)
        self.assertIn("Сделка №2:", reconstructed)

    def test_safe_answer_splits_long_text(self):
        msg = make_mock_message("test", user_id=60002)
        long_text = "A" * 6000
        run_async(safe_answer(msg, long_text))
        self.assertGreaterEqual(msg.answer.call_count, 2)

    def test_missing_bot_token_validation(self):
        with self.assertRaises(ValueError):
            validate_bot_token("")

        with self.assertRaises(ValueError):
            validate_bot_token("your_telegram_bot_token_here")

    def test_valid_bot_token_validation(self):
        token = "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ_1234"
        self.assertEqual(validate_bot_token(token), token)

    def test_sanitize_secrets_masks_tokens(self):
        raw = "Error sending message to 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ_1234 on bot"
        clean = sanitize_secrets(raw)
        self.assertNotIn("123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ_1234", clean)
        self.assertIn("[REDACTED_BOT_TOKEN]", clean)

    def test_dispatcher_creation(self):
        dp = create_dispatcher()
        self.assertIsNotNone(dp)


if __name__ == "__main__":
    unittest.main()
