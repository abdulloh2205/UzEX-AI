import asyncio
import logging
from typing import Any, Dict, List, Optional
from src.config import settings

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Official Google Gemini API client utilizing the google-genai SDK.
    Supports asynchronous generation, structured JSON output, and automatic fallback.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        self.api_key = api_key if api_key is not None else (settings.GEMINI_API_KEY or settings.LLM_API_KEY)
        self.model = model or settings.GEMINI_MODEL
        self.temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        self._client = None

    def is_configured(self) -> bool:
        """Returns True if a valid API key is present."""
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def _get_client(self):
        if self._client is None and self.is_configured():
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize google-genai client: {e}")
                self._client = None
        return self._client

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        timeout_seconds: int = 8,
    ) -> Optional[str]:
        """Generates text asynchronously using google-genai."""
        if not self.is_configured():
            return None

        client = self._get_client()
        if not client:
            return None

        from google.genai import types

        config = types.GenerateContentConfig(
            temperature=self.temperature if temperature is None else temperature,
            system_instruction=system_instruction if system_instruction else None,
        )

        try:
            # Run asynchronous generate_content with a strict timeout
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                ),
                timeout=timeout_seconds,
            )
            if response and response.text:
                return response.text.strip()
            return None
        except asyncio.TimeoutError:
            logger.warning(f"Gemini API timed out after {timeout_seconds}s. Using deterministic fallback.")
            return None
        except Exception as e:
            logger.warning(f"Gemini API request failed ({e}). Using deterministic fallback.")
            return None

    async def extract_structured_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        timeout_seconds: int = 8,
    ) -> Optional[str]:
        """Requests structured JSON output from Gemini."""
        if not self.is_configured():
            return None

        client = self._get_client()
        if not client:
            return None

        from google.genai import types

        config = types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
            system_instruction=system_instruction if system_instruction else None,
        )

        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                ),
                timeout=timeout_seconds,
            )
            if response and response.text:
                return response.text.strip()
            return None
        except asyncio.TimeoutError:
            logger.warning(f"Gemini JSON API timed out after {timeout_seconds}s.")
            return None
        except Exception as e:
            logger.warning(f"Gemini JSON request failed ({e}).")
            return None


gemini_client = GeminiClient()
# Aliases for backward compatibility
LLMClient = GeminiClient
llm_client = gemini_client
