import json
import logging
import re
from typing import Optional
from src.agent.language import Language
from src.agent.llm_client import gemini_client
from src.query_engine.entity_linker import EntityLinker
from src.query_engine.models import IntentType, QueryParams, StatusPolicy, VolumeType

logger = logging.getLogger(__name__)

INTENT_EXTRACTION_PROMPT = """
You are an expert AI parser for the UZEX (Uzbek Commodity Exchange) dataset.
Analyze the user's question in Uzbek or Russian and output ONLY a JSON object conforming to the schema below.
The dataset covers deals from 2022-01-03 to 2026-10-30.

JSON Schema:
{
  "intent": "aggregation" | "ranking" | "price_inquiry" | "deal_lookup" | "contract_lookup" | "participant_lookup" | "broker_lookup" | "usd_rate_lookup" | "status_breakdown" | "exchange_info" | "out_of_scope" | "unknown",
  "product": string or null (in Russian canonical form, e.g. "бензин", "цемент", "пшеница", "катод медный"),
  "year": integer or null (e.g. 2022, 2023, 2024, 2025, 2026),
  "date_from": "YYYY-MM-DD" or null,
  "date_to": "YYYY-MM-DD" or null,
  "inn": string or null (9-digit INN),
  "broker_code": string or null (e.g. "BK001"),
  "deal_id": integer or null,
  "contract_id": string or null,
  "deal_status": string or null (e.g. "Исполнен", "Аннулирован(Не оплачен)"),
  "contract_type": "Внутренний" | "Экспортный" | null,
  "metric": "amount_uzs" | "volume" | "count" | "price",
  "ranking_entity": "product" | "seller" | "buyer" | "broker" | "region" | null,
  "limit": integer (default 5)
}

Output ONLY valid JSON. No conversational fluff or markdown.
"""


class IntentParser:
    @classmethod
    def parse_deterministic(cls, text: str, lang: Language) -> QueryParams:
        # Normalize typographic apostrophes and accents (e.g. o‘, o’, oʻ, o`)
        normalized_text = re.sub(r"[‘’ʻ`]", "'", text)
        lower = normalized_text.lower()
        year = EntityLinker.extract_year(normalized_text)
        inn = EntityLinker.extract_inn(normalized_text)
        broker_code = EntityLinker.extract_broker_code(normalized_text)
        deal_id = EntityLinker.extract_deal_id(normalized_text)
        contract_id = EntityLinker.extract_contract_id(normalized_text)
        date = EntityLinker.extract_date(normalized_text)
        status = EntityLinker.extract_status(normalized_text)
        contract_type = EntityLinker.extract_contract_type(normalized_text)
        product, raw_prod = EntityLinker.resolve_product(normalized_text)

        # Determine status policy and volume type
        policy = StatusPolicy.NON_CANCELLED
        if status:
            if status == "Аннулирован(Не оплачен)":
                policy = StatusPolicy.CANCELLED
            elif status == "Исполнен":
                policy = StatusPolicy.EXECUTED
            elif status == "Исполнен(Частично)":
                policy = StatusPolicy.PARTIALLY_EXECUTED
            else:
                policy = StatusPolicy.REGISTERED
        elif any(w in lower for w in ["всего", "всех", "зарегистрирован", "реестр", "jami", "tuzilgan", "umumiy", "общий"]):
            policy = StatusPolicy.REGISTERED

        # Determine volume type (contracted vs physically delivered)
        vol_type = VolumeType.DELIVERED if any(w in lower for w in ["поставлен", "доставлен", "фактически", "yetkazib", "yetkazilgan"]) else VolumeType.CONTRACTED

        # Check out of dataset bounds
        if year and year not in {2022, 2023, 2024, 2025, 2026}:
            return QueryParams(
                intent=IntentType.OUT_OF_SCOPE,
                year=year,
                language=lang
            )

        if date and (date < "2022-01-03" or date > "2026-10-30"):
            return QueryParams(
                intent=IntentType.OUT_OF_SCOPE,
                date_from=date,
                language=lang
            )

        # Deal lookup
        if deal_id:
            return QueryParams(
                intent=IntentType.DEAL_LOOKUP,
                deal_id=deal_id,
                language=lang
            )

        # Contract lookup
        if contract_id:
            return QueryParams(
                intent=IntentType.CONTRACT_LOOKUP,
                contract_id=contract_id,
                language=lang
            )

        # Ranking intents (RU, UZ Latin, UZ Cyrillic)
        ranking_keywords = [
            "топ", "top", "лучш", "лидер", "лидир",
            "eng yirik", "eng ko'p", "eng kop", "eng faol", "reyting",
            "энг кўп", "энг йирик", "энг фаол", "рейтинг"
        ]
        is_ranking = any(w in lower for w in ranking_keywords)
        if is_ranking:
            ranking_entity = "product"
            if any(w in lower for w in ["продавец", "продавцов", "sotuvchi", "sotuvchilar", "сотувчи", "сотувчилар"]):
                ranking_entity = "seller"
            elif any(w in lower for w in ["покупатель", "покупателей", "xaridor", "xaridorlar", "харидор", "харидорлар"]):
                ranking_entity = "buyer"
            elif any(w in lower for w in ["брокер", "брокеров", "broker", "brokerlar", "брокерлар"]):
                ranking_entity = "broker"
            elif any(w in lower for w in ["регион", "област", "viloyat", "hudud", "вилоят", "ҳудуд"]):
                ranking_entity = "region"

            limit = 5
            # Patterns: top 5, топ-10, 5 товаров, 5 ta mahsulot, 5 та маҳсулот, пять товаров
            limit_match = re.search(r"\b(?:топ|top)\s*[-:]?\s*(\d{1,2})\b", lower)
            if not limit_match:
                limit_match = re.search(r"\b(\d{1,2})\s*(?:та\s+)?(?:товар|позици|наименован|mahsulot|tovar|маҳсулот)", lower)
            if limit_match:
                limit = int(limit_match.group(1))
            elif any(w in lower for w in ["пять товаров", "пяти товаров", "beshta mahsulot", "5 ta", "5 та"]):
                limit = 5

            return QueryParams(
                intent=IntentType.RANKING,
                ranking_entity=ranking_entity,
                product=product,
                year=year,
                deal_status=status,
                status_policy=policy,
                volume_type=vol_type,
                contract_type=contract_type,
                limit=limit,
                language=lang
            )

        # Price inquiry
        price_keywords = ["цена", "цены", "цену", "стоимость", "narx", "narxi", "narxlari", "narxlar"]
        if any(w in lower for w in price_keywords) or ("o'rtacha" in lower and product):
            # If price inquiry mentions price keywords, but no valid commodity could be linked:
            # mark as unknown/unresolved to prevent unbounded price queries across the whole exchange
            if not product and not any(w in lower for w in ["всех товаров", "всех продуктов", "barcha tovarlar"]):
                return QueryParams(
                    intent=IntentType.UNKNOWN,
                    language=lang
                )

            return QueryParams(
                intent=IntentType.PRICE_INQUIRY,
                product=product,
                year=year,
                date_from=date,
                deal_status=status,
                status_policy=policy,
                volume_type=vol_type,
                contract_type=contract_type,
                language=lang
            )

        # Participant lookup
        if inn:
            return QueryParams(
                intent=IntentType.PARTICIPANT_LOOKUP,
                inn=inn,
                year=year,
                status_policy=policy,
                volume_type=vol_type,
                language=lang
            )
        participant = EntityLinker.resolve_participant(text)
        if participant:
            return QueryParams(
                intent=IntentType.PARTICIPANT_LOOKUP,
                inn=participant["inn"],
                year=year,
                status_policy=policy,
                volume_type=vol_type,
                language=lang
            )
        elif any(w in lower for w in ["компани", "предприяти", "организаци", "завод", "комбинат", "kompaniya", "korxona", "tashkilot"]) and not is_ranking:
            return QueryParams(
                intent=IntentType.PARTICIPANT_LOOKUP,
                inn="000000000",
                year=year,
                status_policy=policy,
                volume_type=vol_type,
                language=lang
            )

        # Broker lookup
        if broker_code:
            return QueryParams(
                intent=IntentType.BROKER_LOOKUP,
                broker_code=broker_code,
                year=year,
                status_policy=policy,
                volume_type=vol_type,
                language=lang
            )
        broker = EntityLinker.resolve_broker(text)
        if broker:
            return QueryParams(
                intent=IntentType.BROKER_LOOKUP,
                broker_code=broker["broker_code"],
                year=year,
                status_policy=policy,
                volume_type=vol_type,
                language=lang
            )
        elif any(w in lower for w in ["брокер", "broker"]) and not is_ranking:
            return QueryParams(
                intent=IntentType.BROKER_LOOKUP,
                broker_code="BK999",
                year=year,
                status_policy=policy,
                volume_type=vol_type,
                language=lang
            )

        # Status breakdown
        if status and not product and any(w in lower for w in ["статус", "состояние", "holat", "bekor", "qancha", "nechta"]):
            return QueryParams(
                intent=IntentType.STATUS_BREAKDOWN,
                deal_status=status,
                year=year,
                language=lang
            )

        # Exchange Info / FAQ / Greetings / Help
        exchange_info_keywords = [
            "uzex", "узекс", "биржа", "birja", "o'zi nima", "ozi nima", "nima u", "nima bu",
            "что такое", "что это", "о бирже", "расскажи о", "как работает", "qanday ishlaydi",
            "vazifasi", "haqida ma'lumot", "haqida malumot", "привет", "здравствуй", "salom",
            "assalomu alaykum", "assalom", "что ты умеешь", "nima qila olasan", "imkoniyat",
            "yordam", "помощь", "справка", "imkoniyatlaring"
        ]
        is_exchange_info = any(w in lower for w in exchange_info_keywords)
        if is_exchange_info and not (year or product or inn or broker_code or deal_id or contract_id):
            return QueryParams(
                intent=IntentType.EXCHANGE_INFO,
                language=lang
            )

        # Explicit Aggregation markers (only if year/product/date/status or explicit aggregation tokens are present)
        aggregation_keywords = [
            "объем торгов", "объём торгов", "оборот", "сколько сделок", "всего сделок", "сумма торгов",
            "savdo hajmi", "aylanma", "nechta bitim", "qancha bitim", "savdo summasi", "umumiy savdo"
        ]
        has_agg_marker = any(w in lower for w in aggregation_keywords)

        if product or year or date or status or has_agg_marker:
            return QueryParams(
                intent=IntentType.AGGREGATION,
                product=product,
                product_raw=raw_prod,
                year=year,
                date_from=date,
                deal_status=status,
                status_policy=policy,
                volume_type=vol_type,
                contract_type=contract_type,
                language=lang
            )

        # Unknown / Unrecognized query — do NOT run SQL on the entire database
        return QueryParams(
            intent=IntentType.UNKNOWN,
            language=lang
        )

    @classmethod
    async def parse(cls, text: str, lang: Language, use_llm: bool = True) -> QueryParams:
        # Step 1: Run fast deterministic parser
        params = cls.parse_deterministic(text, lang)

        if not use_llm:
            return params

        # If deterministic parser matched a specific high-confidence intent, use it immediately
        if params.intent in {
            IntentType.DEAL_LOOKUP,
            IntentType.CONTRACT_LOOKUP,
            IntentType.OUT_OF_SCOPE,
            IntentType.RANKING,
            IntentType.PRICE_INQUIRY,
            IntentType.PARTICIPANT_LOOKUP,
            IntentType.BROKER_LOOKUP,
            IntentType.EXCHANGE_INFO,
        }:
            return params

        # If it's an aggregation with an identified product, year, or status, deterministic is already optimal
        if params.product or params.year or params.deal_status:
            return params

        # Step 2: If question is complex/ambiguous and Gemini is available, consult Gemini
        if gemini_client.is_configured():
            try:
                response = await gemini_client.extract_structured_json(
                    prompt=f"User question: {text}\nExtract parameters matching schema.",
                    system_instruction=INTENT_EXTRACTION_PROMPT,
                    timeout_seconds=4
                )
                if response:
                    data = json.loads(response)
                    intent_str = data.get("intent", "unknown")
                    try:
                        intent_enum = IntentType(intent_str)
                    except ValueError:
                        intent_enum = IntentType.UNKNOWN

                    return QueryParams(
                        intent=intent_enum,
                        product=data.get("product") or params.product,
                        year=data.get("year") or params.year,
                        date_from=data.get("date_from"),
                        date_to=data.get("date_to"),
                        inn=data.get("inn") or params.inn,
                        broker_code=data.get("broker_code") or params.broker_code,
                        deal_id=data.get("deal_id") or params.deal_id,
                        contract_id=data.get("contract_id") or params.contract_id,
                        deal_status=data.get("deal_status") or params.deal_status,
                        contract_type=data.get("contract_type") or params.contract_type,
                        metric=data.get("metric", "amount_uzs"),
                        ranking_entity=data.get("ranking_entity"),
                        limit=data.get("limit", 5),
                        language=lang
                    )
            except Exception as e:
                logger.warning(f"Gemini intent parsing failed, using deterministic: {e}")

        return params
