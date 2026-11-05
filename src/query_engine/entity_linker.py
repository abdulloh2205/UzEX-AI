import re
from typing import Dict, List, Optional, Tuple
from src.db.database import execute_query, execute_scalar

# Comprehensive Russian & Uzbek commodity translation and synonym dictionary
PRODUCT_SYNONYMS: Dict[str, str] = {
    # Uzbek Latin & variants
    "benzin": "бензин",
    "bug'doy": "пшеница",
    "bugdoy": "пшеница",
    "bug‘doy": "пшеница",
    "un": "мука",
    "shakar": "сахар",
    "sement": "цемент",
    "tsement": "цемент",
    "paxta": "хлопок",
    "paxta tolasi": "хлопок",
    "yog'": "масло",
    "yog": "масло",
    "yog‘": "масло",
    "paxta yog'i": "масло хлопковое",
    "paxta yog‘i": "масло хлопковое",
    "kungaboqar yog'i": "масло подсолнечное",
    "mis": "катод медный",
    "mis katodi": "катод медный",
    "mis katod": "катод медный",
    "armatura": "арматура",
    "shrot": "шрот",
    "selitra": "селитра",
    "ammiakli selitra": "аммиачная селитра",
    "karbamid": "карбамид",
    "dizel": "дизельное топливо",
    "diztoplivo": "дизельное топливо",
    "solyarka": "дизельное топливо",
    "ko'mir": "уголь",
    "kumir": "уголь",
    "ko‘mir": "уголь",
    "polietilen": "полиэтилен",
    "polipropilen": "полипропилен",
    "alyuminiy": "алюминий",
    "gips": "гипс",
    "ohak": "известь",
    "gaz": "газ",
    "suyultirilgan gaz": "газ сжиженный",
    "bitum": "битум",
    "spirt": "спирт",
    "oltingugurt": "сера",
    "kabel": "кабель",
    "shisha": "стекло",
    "g'isht": "кирпич",
    "gisht": "кирпич",
    "quvur": "труба",

    # Russian inflected forms and synonyms
    "бензина": "бензин",
    "бензину": "бензин",
    "бензином": "бензин",
    "пшеницы": "пшеница",
    "пшеницу": "пшеница",
    "пшеницей": "пшеница",
    "муки": "мука",
    "муку": "мука",
    "мукой": "мука",
    "сахара": "сахар",
    "сахару": "сахар",
    "сахаром": "сахар",
    "цемента": "цемент",
    "цементу": "цемент",
    "цементом": "цемент",
    "хлопка": "хлопок",
    "хлопку": "хлопок",
    "хлопок-сырец": "хлопок",
    "масла": "масло",
    "маслу": "масло",
    "маслом": "масло",
    "меди": "катод медный",
    "медь": "катод медный",
    "катодов": "катод",
    "катода": "катод",
    "катоды": "катод",
    "арматуры": "арматура",
    "арматуру": "арматура",
    "арматурой": "арматура",
    "шрота": "шрот",
    "селитры": "селитра",
    "карбамида": "карбамид",
    "дизеля": "дизельное топливо",
    "дизтоплива": "дизельное топливо",
    "дизтопливо": "дизельное топливо",
    "солярки": "дизельное топливо",
    "угля": "уголь",
    "полиэтилена": "полиэтилен",
    "полипропилена": "полипропилен",
    "алюминия": "алюминий",
    "профиля": "профиль алюминиевый",
}

STATUS_SYNONYMS: Dict[str, str] = {
    # Cancelled / Annulled
    "аннулирован": "Аннулирован(Не оплачен)",
    "аннулированных": "Аннулирован(Не оплачен)",
    "аннулированная": "Аннулирован(Не оплачен)",
    "отменен": "Аннулирован(Не оплачен)",
    "отменена": "Аннулирован(Не оплачен)",
    "не оплачен": "Аннулирован(Не оплачен)",
    "bekor qilingan": "Аннулирован(Не оплачен)",
    "bekor bo'lgan": "Аннулирован(Не оплачен)",
    "bekor bo‘lgan": "Аннулирован(Не оплачен)",
    "bekor": "Аннулирован(Не оплачен)",
    "to'lanmagan": "Аннулирован(Не оплачен)",
    "to‘lanmagan": "Аннулирован(Не оплачен)",

    # Executed
    "исполнен": "Исполнен",
    "исполненных": "Исполнен",
    "исполнена": "Исполнен",
    "bajarilgan": "Исполнен",
    "amalga oshirilgan": "Исполнен",

    # Partially executed
    "частично": "Исполнен(Частично)",
    "qisman": "Исполнен(Частично)",
    "qisman bajarilgan": "Исполнен(Частично)",

    # Paid
    "оплачен": "Оплачен",
    "to'langan": "Оплачен",
    "to‘langan": "Оплачен",

    # Awaiting payment
    "ждет оплату": "Ждёт оплату",
    "ждёт оплату": "Ждёт оплату",
    "to'lov kutilmoqda": "Ждёт оплату",
    "to‘lov kutilmoqda": "Ждёт оплату",

    # New / Not signed
    "новый": "Новый",
    "yangi": "Новый",
    "не подписан": "Не подписан",
    "imzolanmagan": "Не подписан",

    # Concluded
    "статус заключен": "Заключен",
    "состояние заключен": "Заключен",
    "shartnoma tuzilgan": "Заключен",
}


class EntityLinker:
    @staticmethod
    def extract_year(text: str) -> Optional[int]:
        match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def extract_inn(text: str) -> Optional[str]:
        # 9 digit participant INN
        match = re.search(r"\b([1-9]\d{8})\b", text)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def extract_broker_code(text: str) -> Optional[str]:
        # Format BK followed by 3 digits
        match = re.search(r"\b(BK\d{3})\b", text, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return None

    @staticmethod
    def extract_deal_id(text: str) -> Optional[int]:
        # Deal ID (e.g. №999999, сделка #123456, bitim 100001)
        match = re.search(r"(?:сделка|сделки|сделке|bitim|bitimning|deal|№)\s*#?(\d{5,8})\b", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        match_standalone = re.search(r"\b(\d{5,8})\b", text)
        if match_standalone:
            candidate = int(match_standalone.group(1))
            exists = execute_scalar("SELECT 1 FROM deals WHERE deal_id = ? LIMIT 1;", (candidate,))
            if exists:
                return candidate
        return None

    @staticmethod
    def extract_contract_id(text: str) -> Optional[str]:
        match = re.search(r"(?:контракт|контракта|контракту|shartnoma|shartnomaning|contract)\s*#?([A-Za-z0-9_-]{5,20})\b", text, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def extract_date(text: str) -> Optional[str]:
        # DD.MM.YYYY
        match = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-]((?:19|20)\d{2})\b", text)
        if match:
            d, m, y = match.group(1).zfill(2), match.group(2).zfill(2), match.group(3)
            return f"{y}-{m}-{d}"
        # YYYY-MM-DD
        match_iso = re.search(r"\b((?:19|20)\d{2})[./-](\d{1,2})[./-](\d{1,2})\b", text)
        if match_iso:
            y, m, d = match_iso.group(1), match_iso.group(2).zfill(2), match_iso.group(3).zfill(2)
            return f"{y}-{m}-{d}"
        return None

    @staticmethod
    def extract_status(text: str) -> Optional[str]:
        lower = text.lower()
        for phrase, canonical in STATUS_SYNONYMS.items():
            if phrase in lower:
                return canonical
        return None

    @staticmethod
    def extract_contract_type(text: str) -> Optional[str]:
        lower = text.lower()
        if any(w in lower for w in ["экспорт", "eksport", "export"]):
            return "Экспортный"
        if any(w in lower for w in ["внутренний", "ichki", "internal"]):
            return "Внутренний"
        return None

    @staticmethod
    def extract_contract_form(text: str) -> Optional[str]:
        lower = text.lower()
        if "спот" in lower or "spot" in lower:
            return "Спот"
        if "форвард" in lower or "forward" in lower or "forvard" in lower:
            return "Форвард"
        if "фьючерс" in lower or "futures" in lower or "fyuchers" in lower:
            return "Фьючерс"
        return None

    @classmethod
    def resolve_product(cls, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Resolves a commodity mention into (canonical_search_term, raw_matched_term).
        Handles Uzbek case suffixes, apostrophe variants, and FTS5 fallback.
        """
        norm_text = text.lower().replace("‘", "'").replace("’", "'").replace("`", "'")

        # Direct phrase match in synonyms (longest match first)
        sorted_synonyms = sorted(PRODUCT_SYNONYMS.keys(), key=lambda x: len(x), reverse=True)
        for syn in sorted_synonyms:
            syn_norm = syn.replace("‘", "'").replace("’", "'").replace("`", "'")
            # Uzbek and Russian nominal case suffixes
            pattern = (
                r"(?:\b|^)"
                + re.escape(syn_norm)
                + r"(?:ning|ni|ga|ka|qa|da|dan|lar|lari|i|si|larining|lariga|lardan|а|я|у|ю|ом|ем|е|ы|и|ов|ев|ам|ям|ами|ями|ах|ях)?"
                + r"(?:\b|$)"
            )
            if re.search(pattern, norm_text):
                return PRODUCT_SYNONYMS[syn], syn

        # FTS5 search against products_catalog
        words = re.findall(r"[a-zA-Zа-яА-ЯёЁўқғҳЎҚҒҲ']{3,}", norm_text)
        stopwords = {
            "god", "yil", "yili", "yildagi", "narxi", "qancha", "qaysi", "eng",
            "sotilgan", "bitim", "bitimlar", "narx", "boyicha", "haqida", "jami", "tashkil",
            "qildi", "ortacha", "o'rtacha", "tovar", "tovarlar", "mahsulot", "mahsulotlar",
            "reyting", "reytingi", "товар", "товара", "товары", "товаров", "товаром",
            "продукт", "продукта", "продукты", "продуктов", "продукция", "назови", "покажи",
            "самых", "самый", "продаваемых", "популярных", "объем", "объём", "сумма",
            "сделок", "сделка", "сделки", "торгов", "торги", "какой", "какая", "сколько",
            "года", "году", "годе", "годов", "было", "была", "были", "активные",
            "действующие", "лидер", "лидеры", "топ", "текст", "сообщение", "слово",
            "вопрос", "неизвестный", "бессмысленный", "тест", "gap", "soz", "matn", "savol",
            "iltimos", "salom", "qanday", "nima", "qanaqa", "спот", "spot"
        }
        for w in words:
            w_clean = w.replace("'", "")
            if w_clean in stopwords:
                continue
            rows = execute_query(
                "SELECT product_name FROM products_fts WHERE products_fts MATCH ? LIMIT 1;",
                (f"{w_clean}*",)
            )
            if rows:
                return rows[0]["product_name"], w

        return None, None

    @classmethod
    def resolve_participant(cls, text: str) -> Optional[Dict[str, str]]:
        inn = cls.extract_inn(text)
        if inn:
            p = execute_query("SELECT inn, name, region FROM participants WHERE inn = ? LIMIT 1;", (inn,))
            if p:
                return p[0]

        # Extract quoted entity names
        quoted = re.findall(r'["«“]([^"»”]+)["»”]', text)
        if quoted:
            for cand in quoted:
                cand_clean = cand.replace("'", "").replace('"', "").replace("`", "").strip()
                if cand_clean:
                    rows = execute_query(
                        "SELECT inn, name, region FROM participants_fts WHERE participants_fts MATCH ? LIMIT 1;",
                        (f'"{cand_clean}"',)
                    )
                    if rows:
                        return rows[0]

        return None

    @classmethod
    def resolve_broker(cls, text: str) -> Optional[Dict[str, str]]:
        code = cls.extract_broker_code(text)
        if code:
            b = execute_query("SELECT broker_code, name, region FROM brokers WHERE broker_code = ? LIMIT 1;", (code,))
            if b:
                return b[0]

        quoted = re.findall(r'["«“]([^"»”]+)["»”]', text)
        for cand in quoted:
            rows = execute_query(
                "SELECT broker_code, name, region FROM brokers_fts WHERE brokers_fts MATCH ? LIMIT 1;",
                (f'"{cand}"',)
            )
            if rows:
                return rows[0]

        return None
