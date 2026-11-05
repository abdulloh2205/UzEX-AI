import logging
from typing import Any, Dict, List, Optional
from src.agent.language import Language
from src.agent.llm_client import gemini_client
from src.query_engine.models import IntentType, QueryParams, QueryResult

logger = logging.getLogger(__name__)


def format_num(val: Optional[float], decimals: int = 2) -> str:
    """Formats float with spaces as thousand separators and dot/comma."""
    if val is None:
        return "0"
    if decimals == 0:
        return f"{int(round(val)):,}".replace(",", " ")
    formatted = f"{val:,.{decimals}f}".replace(",", " ")
    return formatted


class ResponseBuilder:
    @classmethod
    def build_deterministic(
        cls,
        params: QueryParams,
        result: QueryResult,
        lang: Language
    ) -> str:
        """Constructs a deterministic, 100% mathematically accurate response in Uzbek or Russian."""
        # 1. Out of dataset bounds
        if result.is_out_of_dataset:
            return result.out_of_dataset_reason or (
                "Ko‘rsatilgan so‘rov UZEX ma'lumotlar to‘plami davri yoki doirasidan tashqarida."
                if lang == "uz"
                else "Запрошенные данные находятся за пределами диапазона или охвата датасета UZEX."
            )

        # 2. No data found
        if not result.has_data or (result.total_count == 0 and not result.rows):
            entity_desc = params.product or params.inn or params.broker_code or ""
            year_desc = f" ({params.year}-yil)" if params.year and lang == "uz" else (f" (за {params.year} год)" if params.year else "")
            if lang == "uz":
                return f"🔍 **UZEX ma'lumotlar to‘plamida so‘rovingiz bo‘yicha ma'lumot topilmadi**{year_desc}.\n\nTo‘plamda {entity_desc} bo‘yicha qayd etilgan bitimlar mavjud emas."
            else:
                return f"🔍 **В датасете UZEX по вашему запросу данных не найдено**{year_desc}.\n\nВ реестре отсутствуют зарегистрированные сделки по параметрам: {entity_desc}."

        intent = params.intent

        # 3. DEAL LOOKUP
        if intent == IntentType.DEAL_LOOKUP and result.rows:
            deal = result.rows[0]
            if lang == "uz":
                return (
                    f"📄 **Bitim №{deal['deal_id']} haqida ma'lumot:**\n\n"
                    f"• **Sana va vaqt:** {deal['deal_date']} {deal['deal_time']}\n"
                    f"• **Tovar:** {deal['product_name']}\n"
                    f"• **Hajm:** {format_num(deal['volume'])} {deal['unit']} ({format_num(deal['quantity'], 0)} lot × {deal['lot']})\n"
                    f"• **Bitim summasi:** {format_num(deal['amount'])} {deal['currency']}\n"
                    f"• **So‘mdagi qiymati:** {format_num(deal['amount_uzs'])} so‘m (kurs: {format_num(deal['usd_rate'])})\n"
                    f"• **Birlik narxi:** {format_num(deal['unit_price_uzs'])} so‘m / {deal['unit']}\n"
                    f"• **Boshlang‘ich narx:** {format_num(deal['start_price'])} {deal['currency']}\n"
                    f"• **Bitim holati:** {deal['status']}\n"
                    f"• **Savdo turi:** {deal['auction_type']} ({deal['contract_form']}, {deal['contract_type']})\n"
                    f"• **Sotuvchi:** {deal.get('seller_name') or deal['seller_inn']} (STIR: `{deal['seller_inn']}`)\n"
                    f"• **Xaridor:** {deal.get('buyer_name') or deal['buyer_inn']} (STIR: `{deal['buyer_inn']}`)\n"
                    f"• **Sotuvchi brokeri:** {deal.get('seller_broker_name') or deal['seller_broker']}\n"
                    f"• **Xaridor brokeri:** {deal.get('buyer_broker_name') or deal['buyer_broker']}\n"
                    f"• **Shartnoma:** №{deal['contract_id']}"
                )
            else:
                return (
                    f"📄 **Информация по сделке №{deal['deal_id']}:**\n\n"
                    f"• **Дата и время:** {deal['deal_date']} {deal['deal_time']}\n"
                    f"• **Товар:** {deal['product_name']}\n"
                    f"• **Объём:** {format_num(deal['volume'])} {deal['unit']} ({format_num(deal['quantity'], 0)} лотов × {deal['lot']})\n"
                    f"• **Сумма сделки:** {format_num(deal['amount'])} {deal['currency']}\n"
                    f"• **Сумма в сумах:** {format_num(deal['amount_uzs'])} сум (курс USD: {format_num(deal['usd_rate'])})\n"
                    f"• **Цена за единицу:** {format_num(deal['unit_price_uzs'])} сум / {deal['unit']}\n"
                    f"• **Стартовая цена:** {format_num(deal['start_price'])} {deal['currency']}\n"
                    f"• **Состояние сделки:** {deal['status']}\n"
                    f"• **Тип торгов:** {deal['auction_type']} ({deal['contract_form']}, {deal['contract_type']})\n"
                    f"• **Продавец:** {deal.get('seller_name') or deal['seller_inn']} (ИНН: `{deal['seller_inn']}`)\n"
                    f"• **Покупатель:** {deal.get('buyer_name') or deal['buyer_inn']} (ИНН: `{deal['buyer_inn']}`)\n"
                    f"• **Брокер продавца:** {deal.get('seller_broker_name') or deal['seller_broker']}\n"
                    f"• **Брокер покупателя:** {deal.get('buyer_broker_name') or deal['buyer_broker']}\n"
                    f"• **Контракт:** №{deal['contract_id']}"
                )

        # 4. CONTRACT LOOKUP
        if intent == IntentType.CONTRACT_LOOKUP and result.rows:
            c = result.rows[0]
            if lang == "uz":
                return (
                    f"📋 **Shartnoma №{c['contract_id']} kartochkasi:**\n\n"
                    f"• **Mahsulot:** {c['product_name']}\n"
                    f"• **Kategoriya:** {c['product_category']} | **Soha:** {c['industry']}\n"
                    f"• **Birlik / Lot:** {c['lot']} {c['unit']}\n"
                    f"• **Bazis narx:** {format_num(c['base_price'])} {c['currency']}\n"
                    f"• **Valyuta:** {c['currency']}\n"
                    f"• **Zalog summasi:** {c['deposit_percent']}%\n"
                    f"• **Yetkazib berish sharti:** {c['incoterms']} ({c['warehouse_address']})\n"
                    f"• **Sotuvchi:** {c.get('seller_name') or c['seller_inn']} (STIR: `{c['seller_inn']}`)\n"
                    f"• **Amal qilish muddati:** {c['registration_date']} dan {c['expiration_date']} gacha\n"
                    f"• **Tuzilgan bitimlar:** {format_num(c['total_deals'], 0)} ta\n"
                    f"• **Umumiy savdo aylanmasi:** {format_num(c['total_amount_uzs'])} so‘m"
                )
            else:
                return (
                    f"📋 **Карточка контракта №{c['contract_id']}:**\n\n"
                    f"• **Продукт:** {c['product_name']}\n"
                    f"• **Категория:** {c['product_category']} | **Отрасль:** {c['industry']}\n"
                    f"• **Единица / Лот:** {c['lot']} {c['unit']}\n"
                    f"• **Базисная цена:** {format_num(c['base_price'])} {c['currency']}\n"
                    f"• **Валюта контракта:** {c['currency']}\n"
                    f"• **Залог:** {c['deposit_percent']}%\n"
                    f"• **Базис поставки:** {c['incoterms']} ({c['warehouse_address']})\n"
                    f"• **Продавец:** {c.get('seller_name') or c['seller_inn']} (ИНН: `{c['seller_inn']}`)\n"
                    f"• **Срок действия:** с {c['registration_date']} по {c['expiration_date']}\n"
                    f"• **Всего сделок:** {format_num(c['total_deals'], 0)}\n"
                    f"• **Общий оборот:** {format_num(c['total_amount_uzs'])} сум"
                )

        # 5. PARTICIPANT LOOKUP
        if intent == IntentType.PARTICIPANT_LOOKUP and result.rows:
            p = result.rows[0]
            vat = "Ha" if p.get("is_vat_payer") else "Yo'q" if lang == "uz" else ("Да" if p.get("is_vat_payer") else "Нет")
            if lang == "uz":
                return (
                    f"🏢 **Kompaniya:** {p['name']}\n\n"
                    f"• **STIR (ИНН):** `{p['inn']}`\n"
                    f"• **Hudud:** {p['region']}\n"
                    f"• **Faoliyat turi:** {p['activity']}\n"
                    f"• **Rol:** {p['role']}\n"
                    f"• **QQS to‘lovchi:** {vat}\n\n"
                    f"📊 **Birjadagi faolligi:**\n"
                    f"• Sotuvchi sifatidagi bitimlar: {format_num(p.get('deals_as_seller', 0), 0)} ta\n"
                    f"• Xaridor sifatidagi bitimlar: {format_num(p.get('deals_as_buyer', 0), 0)} ta\n"
                    f"• Jami sotuv hajmi: {format_num(p.get('sales_sum_uzs', 0))} so‘m\n"
                    f"• Jami xarid hajmi: {format_num(p.get('purchase_sum_uzs', 0))} so‘m"
                )
            else:
                return (
                    f"🏢 **Компания:** {p['name']}\n\n"
                    f"• **ИНН:** `{p['inn']}`\n"
                    f"• **Регион:** {p['region']}\n"
                    f"• **Вид деятельности:** {p['activity']}\n"
                    f"• **Роль:** {p['role']}\n"
                    f"• **Плательщик НДС:** {vat}\n\n"
                    f"📊 **Активность на бирже:**\n"
                    f"• Сделок в качестве продавца: {format_num(p.get('deals_as_seller', 0), 0)}\n"
                    f"• Сделок в качестве покупателя: {format_num(p.get('deals_as_buyer', 0), 0)}\n"
                    f"• Общий объем продаж: {format_num(p.get('sales_sum_uzs', 0))} сум\n"
                    f"• Общий объем покупок: {format_num(p.get('purchase_sum_uzs', 0))} сум"
                )

        # 6. BROKER LOOKUP
        if intent == IntentType.BROKER_LOOKUP and result.rows:
            b = result.rows[0]
            if lang == "uz":
                return (
                    f"🏛 **Broker idorasi:** {b['name']}\n\n"
                    f"• **Broker kodi:** `{b['broker_code']}`\n"
                    f"• **STIR:** `{b.get('inn')}`\n"
                    f"• **Hudud:** {b['region']}\n\n"
                    f"📊 **Birjadagi aylanmasi:**\n"
                    f"• Jami ishtirok etgan bitimlar soni: {format_num(b.get('total_deals', 0), 0)} ta\n"
                    f"• Sotuvchi brokeri sifatida: {format_num(b.get('deals_as_seller_broker', 0), 0)} ta\n"
                    f"• Xaridor brokeri sifatida: {format_num(b.get('deals_as_buyer_broker', 0), 0)} ta\n"
                    f"• Umumiy aylanma summasi: {format_num(b.get('total_turnover_uzs', 0))} so‘m"
                )
            else:
                return (
                    f"🏛 **Брокерская контора:** {b['name']}\n\n"
                    f"• **Код брокера:** `{b['broker_code']}`\n"
                    f"• **ИНН:** `{b.get('inn')}`\n"
                    f"• **Регион:** {b['region']}\n\n"
                    f"📊 **Оборот на бирже:**\n"
                    f"• Всего сделок с участием брокера: {format_num(b.get('total_deals', 0), 0)}\n"
                    f"• В качестве брокера продавца: {format_num(b.get('deals_as_seller_broker', 0), 0)}\n"
                    f"• В качестве брокера покупателя: {format_num(b.get('deals_as_buyer_broker', 0), 0)}\n"
                    f"• Общий торговый оборот: {format_num(b.get('total_turnover_uzs', 0))} сум"
                )

        # 7. PRICE INQUIRY
        if intent == IntentType.PRICE_INQUIRY:
            period_uz = f"{params.year}-yil" if params.year else "butun davr"
            period_ru = f"за {params.year} год" if params.year else "за весь период"
            prod_name = params.product or ("ko‘rsatilgan mahsulot" if lang == "uz" else "указанный товар")

            # Check if we have multiple units (e.g. литр and тонна)
            if len(result.rows) > 1:
                sections = []
                if lang == "uz":
                    sections.append(f"💰 **«{prod_name.title()}» narxlari tahlili ({period_uz}):**\n")
                    for r in result.rows:
                        u = r.get("unit") or "birlik"
                        w_avg = format_num(r.get("weighted_avg_price_uzs"))
                        p_min = format_num(r.get("min_price_uzs"))
                        p_max = format_num(r.get("max_price_uzs"))
                        d_cnt = format_num(r.get("deal_count", 0), 0)
                        t_vol = format_num(r.get("total_volume"))
                        t_amt = format_num(r.get("total_amount_uzs"))
                        sections.append(
                            f"📦 **O‘lchov birligi: {u}**\n"
                            f"• **O‘rtacha tortilgan narxi:** **{w_avg}** so‘m / {u}\n"
                            f"• **Minimal narx:** {p_min} so‘m / {u}\n"
                            f"• **Maksimal narx:** {p_max} so‘m / {u}\n"
                            f"• **Tuzilgan bitimlar soni:** {d_cnt} ta\n"
                            f"• **Umumiy sotilgan hajm:** {t_vol} {u}\n"
                            f"• **Umumiy savdo summasi:** {t_amt} so‘m"
                        )
                else:
                    sections.append(f"💰 **Анализ цен на «{prod_name.title()}» ({period_ru}):**\n")
                    for r in result.rows:
                        u = r.get("unit") or "ед."
                        w_avg = format_num(r.get("weighted_avg_price_uzs"))
                        p_min = format_num(r.get("min_price_uzs"))
                        p_max = format_num(r.get("max_price_uzs"))
                        d_cnt = format_num(r.get("deal_count", 0), 0)
                        t_vol = format_num(r.get("total_volume"))
                        t_amt = format_num(r.get("total_amount_uzs"))
                        sections.append(
                            f"📦 **Единица измерения: {u}**\n"
                            f"• **Средневзвешенная цена:** **{w_avg}** сум / {u}\n"
                            f"• **Минимальная цена:** {p_min} сум / {u}\n"
                            f"• **Максимальная цена:** {p_max} сум / {u}\n"
                            f"• **Количество сделок:** {d_cnt}\n"
                            f"• **Общий объём:** {t_vol} {u}\n"
                            f"• **Общая сумма торгов:** {t_amt} сум"
                        )
                return "\n\n".join(sections)

            unit = result.unit or ("birlik" if lang == "uz" else "ед.")
            if lang == "uz":
                return (
                    f"💰 **«{prod_name.title()}» narxlari tahlili ({period_uz}):**\n\n"
                    f"• **O‘rtacha tortilgan narxi:** **{format_num(result.avg_price)}** so‘m / {unit}\n"
                    f"• **Minimal narx:** {format_num(result.min_price)} so‘m / {unit}\n"
                    f"• **Maksimal narx:** {format_num(result.max_price)} so‘m / {unit}\n"
                    f"• **Tuzilgan bitimlar soni:** {format_num(result.total_count, 0)} ta\n"
                    f"• **Umumiy sotilgan hajm:** {format_num(result.total_volume)} {unit}\n"
                    f"• **Umumiy savdo summasi:** {format_num(result.total_amount_uzs)} so‘m"
                )
            else:
                return (
                    f"💰 **Анализ цен на «{prod_name.title()}» ({period_ru}):**\n\n"
                    f"• **Средневзвешенная цена:** **{format_num(result.avg_price)}** сум / {unit}\n"
                    f"• **Минимальная цена:** {format_num(result.min_price)} сум / {unit}\n"
                    f"• **Максимальная цена:** {format_num(result.max_price)} сум / {unit}\n"
                    f"• **Количество сделок:** {format_num(result.total_count, 0)}\n"
                    f"• **Общий объём:** {format_num(result.total_volume)} {unit}\n"
                    f"• **Общая сумма торгов:** {format_num(result.total_amount_uzs)} сум"
                )

        # 8. RANKING
        if intent == IntentType.RANKING and result.rows:
            entity = params.ranking_entity or "product"
            year_str = f" ({params.year}-yil)" if params.year and lang == "uz" else (f" (за {params.year} год)" if params.year else "")

            lines = []
            if entity == "product":
                header = f"🏆 **Eng ko‘p sotilgan tovarlar reytingi{year_str}:**" if lang == "uz" else f"🏆 **Топ самых торгуемых товаров{year_str}:**"
                for i, r in enumerate(result.rows, 1):
                    vol = f"{format_num(r.get('total_volume'))} {r.get('unit', '')}"
                    summa = f"{format_num(r.get('total_amount_uzs'))} so‘m" if lang == "uz" else f"{format_num(r.get('total_amount_uzs'))} сум"
                    deals_cnt = f"{format_num(r.get('deal_count'), 0)} ta bitim" if lang == "uz" else f"{format_num(r.get('deal_count'), 0)} сделок"
                    lines.append(f"{i}. **{r['product_name']}** — {summa} ({vol}, {deals_cnt})")
            elif entity == "seller":
                header = f"🏆 **Eng yirik sotuvchilar (Top-{len(result.rows)}){year_str}:**" if lang == "uz" else f"🏆 **Топ-продавцов по объему торгов{year_str}:**"
                for i, r in enumerate(result.rows, 1):
                    name = r.get("company_name") or f"STIR {r['inn']}"
                    summa = f"{format_num(r.get('total_amount_uzs'))} so‘m" if lang == "uz" else f"{format_num(r.get('total_amount_uzs'))} сум"
                    lines.append(f"{i}. **{name}** (STIR: `{r['inn']}`) — {summa}")
            elif entity == "buyer":
                header = f"🏆 **Eng yirik xaridorlar (Top-{len(result.rows)}){year_str}:**" if lang == "uz" else f"🏆 **Топ-покупателей по объему торгов{year_str}:**"
                for i, r in enumerate(result.rows, 1):
                    name = r.get("company_name") or f"STIR {r['inn']}"
                    summa = f"{format_num(r.get('total_amount_uzs'))} so‘m" if lang == "uz" else f"{format_num(r.get('total_amount_uzs'))} сум"
                    lines.append(f"{i}. **{name}** (STIR: `{r['inn']}`) — {summa}")
            elif entity == "broker":
                header = f"🏆 **Eng faol brokerlar (Top-{len(result.rows)}){year_str}:**" if lang == "uz" else f"🏆 **Топ брокеров по объему торгов{year_str}:**"
                for i, r in enumerate(result.rows, 1):
                    name = r.get("broker_name") or r["broker_code"]
                    summa = f"{format_num(r.get('total_amount_uzs'))} so‘m" if lang == "uz" else f"{format_num(r.get('total_amount_uzs'))} сум"
                    lines.append(f"{i}. **{name}** (`{r['broker_code']}`) — {summa} ({format_num(r.get('deal_count'), 0)} ta bitim)")
            else:
                header = f"🏆 **Hududlar bo‘yicha taqsimot{year_str}:**" if lang == "uz" else f"🏆 **Топ регионов по объему торгов{year_str}:**"
                for i, r in enumerate(result.rows, 1):
                    summa = f"{format_num(r.get('total_amount_uzs'))} so‘m" if lang == "uz" else f"{format_num(r.get('total_amount_uzs'))} сум"
                    lines.append(f"{i}. **{r['region']}** — {summa} ({format_num(r.get('deal_count'), 0)} ta bitim)")

            return f"{header}\n\n" + "\n".join(lines)

        # 9. STATUS BREAKDOWN
        if intent == IntentType.STATUS_BREAKDOWN and result.rows:
            year_str = f" ({params.year}-yil)" if params.year and lang == "uz" else (f" (за {params.year} год)" if params.year else "")
            header = f"📊 **Bitimlar holati (statuslari) bo‘yicha taqsimot{year_str}:**" if lang == "uz" else f"📊 **Распределение сделок по состояниям{year_str}:**"
            lines = []
            for r in result.rows:
                cnt = format_num(r["count"], 0)
                amount = format_num(r["total_amount_uzs"])
                curr = "so‘m" if lang == "uz" else "сум"
                lines.append(f"• **{r['status']}:** {cnt} ta bitim ({amount} {curr})")
            return f"{header}\n\n" + "\n".join(lines)

        # 10. GENERAL AGGREGATION
        year_str = f" ({params.year}-yil)" if params.year and lang == "uz" else (f" (за {params.year} год)" if params.year else " (2022–2026)")
        prod_str = f" «{params.product}» bo‘yicha" if params.product and lang == "uz" else (f" по «{params.product}»" if params.product else "")
        status_str = f" [Status: {params.deal_status}]" if params.deal_status else ""
        unit_str = f" {result.unit}" if result.unit else ""

        if lang == "uz":
            res = (
                f"📊 **UZEX birja bitimlari ko‘rsatkichlari{prod_str}{year_str}{status_str}:**\n\n"
                f"• **Jami bitimlar soni:** **{format_num(result.total_count, 0)}** ta\n"
                f"• **Jami savdo hajmi:** **{format_num(result.total_volume)}**{unit_str}\n"
                f"• **Umumiy savdo summasi:** **{format_num(result.total_amount_uzs)}** so‘m"
            )
            if result.total_amount_usd and result.total_amount_usd > 0:
                res += f"\n• **Eksport bitimlari summasi:** **{format_num(result.total_amount_usd)}** USD"
            if result.avg_price and result.avg_price > 0:
                res += f"\n• **O‘rtacha narx:** **{format_num(result.avg_price)}** so‘m{unit_str}"
            return res
        else:
            res = (
                f"📊 **Показатели биржевых торгов UZEX{prod_str}{year_str}{status_str}:**\n\n"
                f"• **Количество сделок:** **{format_num(result.total_count, 0)}**\n"
                f"• **Общий объём торгов:** **{format_num(result.total_volume)}**{unit_str}\n"
                f"• **Общая сумма торгов:** **{format_num(result.total_amount_uzs)}** сум"
            )
            if result.total_amount_usd and result.total_amount_usd > 0:
                res += f"\n• **Сумма экспортных сделок:** **{format_num(result.total_amount_usd)}** USD"
            if result.avg_price and result.avg_price > 0:
                res += f"\n• **Средневзвешенная цена:** **{format_num(result.avg_price)}** сум{unit_str}"
            return res

    @classmethod
    async def build(
        cls,
        user_question: str,
        params: QueryParams,
        result: QueryResult,
        lang: Language,
        use_llm: bool = True
    ) -> str:
        """
        Builds response. First generates the deterministic verified fact summary.
        If LLM is available and use_llm is True, passes the verified summary to LLM for fluent presentation.
        If LLM is unavailable, disabled, or fails, returns the deterministic response directly.
        """
        deterministic_text = cls.build_deterministic(params, result, lang)

        if not use_llm or not gemini_client.is_configured():
            return deterministic_text

        # If it's out of bounds or simple single stat, deterministic text is already crisp and exact
        if result.is_out_of_dataset:
            return deterministic_text

        system_prompt = (
            f"You are the official bilingual AI assistant for the Uzbek Commodity Exchange (UZEX).\n"
            f"The user asked a question in {'Uzbek' if lang == 'uz' else 'Russian'}.\n"
            f"You are provided with deterministically calculated facts from the database.\n"
            f"CRITICAL ANTI-HALLUCINATION RULES:\n"
            f"1. You MUST use the exact numbers, amounts, and units provided in the facts.\n"
            f"2. Never calculate, estimate, or invent new numbers.\n"
            f"3. Respond clearly and politely in {'Uzbek' if lang == 'uz' else 'Russian'}.\n"
            f"4. Format prices and volumes cleanly with markdown bolding.\n"
            f"5. If no data exists, clearly state that no records match the criteria in the UZEX dataset."
        )

        user_prompt = (
            f"User Question: {user_question}\n\n"
            f"Verified Database Facts:\n{deterministic_text}\n\n"
            f"Write a concise, polished response in {'Uzbek' if lang == 'uz' else 'Russian'} conveying these facts."
        )

        try:
            gemini_response = await gemini_client.generate_text(
                prompt=user_prompt,
                system_instruction=system_prompt,
                temperature=0.1,
                timeout_seconds=4
            )
            if gemini_response and len(gemini_response.strip()) > 15:
                return gemini_response.strip()
        except Exception as e:
            logger.warning(f"Gemini natural formatting failed, falling back to deterministic: {e}")

        return deterministic_text
