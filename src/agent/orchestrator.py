import logging
import time
from typing import Any, Dict, Optional
from pydantic import BaseModel
from src.agent.intent import IntentParser
from src.agent.language import LanguageDetector, Language
from src.agent.response_builder import ResponseBuilder
from src.query_engine.executor import QueryExecutor
from src.query_engine.models import QueryParams, QueryResult

logger = logging.getLogger(__name__)


class AgentResponse(BaseModel):
    text: str
    language: Language
    latency_ms: float
    sql_executed: Optional[str] = None
    query_params: Optional[Dict[str, Any]] = None
    has_data: bool = True
    is_out_of_dataset: bool = False


class AgentOrchestrator:
    @classmethod
    def process_question_sync(
        cls,
        user_message: str,
        user_id: Optional[int] = None,
        force_language: Optional[Language] = None,
    ) -> AgentResponse:
        """100% deterministic synchronous question processing pipeline."""
        start_t = time.perf_counter()
        cleaned_input = user_message.strip()

        # Step 1: Language Detection
        lang: Language = force_language or LanguageDetector.detect(cleaned_input)

        # Step 2: Intent and Parameter Extraction (Deterministic)
        params: QueryParams = IntentParser.parse_deterministic(cleaned_input, lang)

        # Step 3: Query Execution (Deterministic)
        result: QueryResult = QueryExecutor.execute_params(params)

        # Step 4: Bilingual Response Generation (Deterministic)
        response_text = ResponseBuilder.build_deterministic(params, result, lang)

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        return AgentResponse(
            text=response_text,
            language=lang,
            latency_ms=elapsed_ms,
            sql_executed=result.sql_executed,
            query_params=params.model_dump(),
            has_data=result.has_data,
            is_out_of_dataset=result.is_out_of_dataset
        )

    @classmethod
    async def process_question(
        cls,
        user_message: str,
        user_id: Optional[int] = None,
        force_language: Optional[Language] = None,
        use_llm: bool = True
    ) -> AgentResponse:
        """Asynchronous processing pipeline with Gemini presentation integration."""
        if not use_llm:
            return cls.process_question_sync(user_message, user_id=user_id, force_language=force_language)

        start_t = time.perf_counter()
        cleaned_input = user_message.strip()

        # Step 1: Language Detection
        lang: Language = force_language or LanguageDetector.detect(cleaned_input)

        # Step 2: Intent and Parameter Extraction
        params: QueryParams = await IntentParser.parse(cleaned_input, lang, use_llm=use_llm)

        # Step 3: Query Execution (Deterministic)
        result: QueryResult = QueryExecutor.execute_params(params)

        # Step 4: Retrieve conversation history for context if user_id is provided
        history = []
        if user_id:
            try:
                from src.bot.user_preferences import user_preferences_repo
                history = user_preferences_repo.get_history(user_id=user_id, limit=6)
            except Exception as e:
                logger.debug(f"Could not load conversation history: {e}")

        # Step 5: Bilingual Response Generation
        response_text = await ResponseBuilder.build(
            user_question=cleaned_input,
            params=params,
            result=result,
            lang=lang,
            use_llm=use_llm,
            history=history
        )

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        return AgentResponse(
            text=response_text,
            language=lang,
            latency_ms=elapsed_ms,
            sql_executed=result.sql_executed,
            query_params=params.model_dump(),
            has_data=result.has_data,
            is_out_of_dataset=result.is_out_of_dataset
        )
