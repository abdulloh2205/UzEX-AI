import re
from typing import List

# Default limit leaves margin for Markdown wrappers and markup safety
TELEGRAM_MAX_MESSAGE_LENGTH = 4000

# Pattern for Telegram Bot Token: e.g. 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ_1234
BOT_TOKEN_PATTERN = re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,50}\b")
# Pattern for common API Keys like AIzaSy...
API_KEY_PATTERN = re.compile(r"\bAIza[0-9A-Za-z-_]{35}\b")


def sanitize_secrets(text: str) -> str:
    """Masks bot tokens and API keys in strings to prevent sensitive leakages in logs."""
    if not text:
        return ""
    sanitized = BOT_TOKEN_PATTERN.sub("[REDACTED_BOT_TOKEN]", text)
    sanitized = API_KEY_PATTERN.sub("[REDACTED_API_KEY]", sanitized)
    return sanitized


def split_message(text: str, max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> List[str]:
    """
    Splits text into chunks not exceeding max_length characters.
    Splits by logical boundaries: paragraphs (\n\n), then lines (\n),
    then words, ensuring numbers and words are not broken apart.
    """
    if not text:
        return []

    if len(text) <= max_length:
        return [text]

    chunks: List[str] = []
    current_chunk = ""

    # Split by double newline (paragraphs) first
    paragraphs = text.split("\n\n")

    for paragraph in paragraphs:
        if len(paragraph) > max_length:
            # Paragraph is too long; split by single newline
            lines = paragraph.split("\n")
            for line in lines:
                if len(line) > max_length:
                    # Line is still too long; split by words
                    words = line.split(" ")
                    for word in words:
                        if len(word) > max_length:
                            # Hard split ultra-long indivisible words
                            for i in range(0, len(word), max_length):
                                sub = word[i:i + max_length]
                                if current_chunk:
                                    chunks.append(current_chunk)
                                    current_chunk = ""
                                chunks.append(sub)
                        elif not current_chunk:
                            current_chunk = word
                        elif len(current_chunk) + 1 + len(word) <= max_length:
                            current_chunk += " " + word
                        else:
                            chunks.append(current_chunk)
                            current_chunk = word
                else:
                    if not current_chunk:
                        current_chunk = line
                    elif len(current_chunk) + 1 + len(line) <= max_length:
                        current_chunk += "\n" + line
                    else:
                        chunks.append(current_chunk)
                        current_chunk = line
        else:
            if not current_chunk:
                current_chunk = paragraph
            elif len(current_chunk) + 2 + len(paragraph) <= max_length:
                current_chunk += "\n\n" + paragraph
            else:
                chunks.append(current_chunk)
                current_chunk = paragraph

    if current_chunk:
        chunks.append(current_chunk)

    return chunks
