import re
from typing import Literal

Language = Literal["ru", "uz"]

# Distinctive Uzbek tokens and suffixes
UZBEK_LATIN_INDICATORS = [
    r"\bo['`‘]r", r"\bo['`‘]rtacha\b", r"\bqancha\b", r"\bqanday\b", r"\bqaysi\b",
    r"\bhaqida\b", r"\bbo['`‘]yicha\b", r"\bsotilgan\b", r"\bbitim\b", r"\bbitimlar\b",
    r"\btovar\b", r"\bnarx\b", r"\bnarxi\b", r"\byil\b", r"\byilda\b", r"\byildagi\b",
    r"\bshartnoma\b", r"\bkim\b", r"\beng\b", r"\bko['`‘]p\b", r"\bo['`‘]tgan\b",
    r"\bbekor\b", r"\bqilingan\b", r"\bichki\b", r"\beksport\b", r"\bxaridor\b",
    r"\bsotuvchi\b", r"\bso['`‘]m\b", r"\baylanma\b", r"\bhajmi\b", r"\bnechta\b"
]

UZBEK_CYRILLIC_INDICATORS = [
    r"\bқанча\b", r"\bқандай\b", r"\bқайси\b", r"\bҳақида\b", r"\bбўйича\b",
    r"\bсотилган\b", r"\bбитим\b", r"\bбитимлар\b", r"\bтовар\b", r"\bнарх\b",
    r"\bнархи\b", r"\bйил\b", r"\bйилда\b", r"\bшартнома\b", r"\bким\b",
    r"\bэнг\b", r"\bкўп\b", r"\bбекор\b", r"\bқилинган\b", r"\bхаридор\b",
    r"\bсотувчи\b", r"\bсўм\b", r"\bнечта\b", r"[ўқғҳЎҚҒҲ]"
]

RUSSIAN_INDICATORS = [
    r"\bкакой\b", r"\bкакая\b", r"\bкакое\b", r"\bкакие\b", r"\bсколько\b",
    r"\bкакова\b", r"\bцена\b", r"\bцены\b", r"\bсделка\b", r"\bсделки\b",
    r"\bсделок\b", r"\bконтракт\b", r"\bконтракты\b", r"\bпродано\b", r"\bкуплено\b",
    r"\bобъем\b", r"\bобъём\b", r"\bсумма\b", r"\bтоп\b", r"\bгоду\b",
    r"\bгода\b", r"\bгоде\b", r"\bсредняя\b", r"\bсредний\b", r"\bкто\b",
    r"\bсамый\b", r"\bсамая\b", r"\bсамое\b", r"\bброкер\b", r"\bпокупатель\b",
    r"\bпродавец\b", r"\bаннулирован\b", r"\bисполнен\b", r"\bруб\b"
]


class LanguageDetector:
    @classmethod
    def detect(cls, text: str) -> Language:
        lower = text.lower()

        uz_score = 0
        for pattern in UZBEK_LATIN_INDICATORS + UZBEK_CYRILLIC_INDICATORS:
            if re.search(pattern, lower):
                uz_score += 2

        ru_score = 0
        for pattern in RUSSIAN_INDICATORS:
            if re.search(pattern, lower):
                ru_score += 2

        # Check Latin alphabet preference vs Cyrillic
        latin_count = len(re.findall(r"[a-zA-Z]", text))
        cyrillic_count = len(re.findall(r"[а-яА-ЯёЁ]", text))

        if uz_score > ru_score:
            return "uz"
        elif ru_score > uz_score:
            return "ru"
        else:
            # Tie breaker: if text is largely Latin characters, prefer Uzbek (since official UZEX query language in Latin is Uzbek)
            if latin_count > cyrillic_count:
                return "uz"
            return "ru"
