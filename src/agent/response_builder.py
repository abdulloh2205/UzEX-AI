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

        # 2. General Chat (Greetings, small talk, gratitude)
        if params.intent == IntentType.GENERAL_CHAT:
            if lang == "uz":
                return "Assalomu alaykum! UZEX birja ma'lumotlari tahlilchisi xizmatingizda. Sizga qanday yordam bera olaman?"
            else:
                return "Здравствуйте! AI-ассистент по аналитике биржевых данных UZEX готов помочь. Какой вопрос вас интересует?"

        # 3. General Knowledge (Concepts, definitions)
        if params.intent == IntentType.GENERAL_KNOWLEDGE:
            if lang == "uz":
                return (
                    "Ushbu iqtisodiy tushuncha bo‘yicha umumiy ma'lumot. "
                    "Birja ma'lumotlar to‘plami bo‘yicha tahlil uchun tovar nomi yoki yilni ko‘rsatishingiz mumkin."
                )
            else:
                return (
                    "Это общее экономическое понятие. "
                    "Для аналитики по биржевому набору данных укажите интересующий товар или период (2022–2026)."
                )

        # 4. General Exchange Information / Capabilities / Persona
        if params.intent == IntentType.EXCHANGE_INFO:
            if lang == "uz":
                return (
                    "🏛 **UZEX AI haqida:**\n\n"
                    "Men O‘zbekiston tovar-xomashyo birjasi (UZEX) savdo ma'lumotlari bo‘yicha mustaqil analitik AI-yordamchisiman.\n\n"
                    "💡 **Asosiy imkoniyatlarim:**\n"
                    "• 2022–2026 yillardagi birja ma'lumotlar to‘plamini tahlil qilish;\n"
                    "• Tovar narxlari dinamikasi va o‘rtacha tortilgan narxlarni hisoblash;\n"
                    "• Tovar, sotuvchi, xaridor va brokerlar reytinglarini ko‘rsatish;\n"
                    "• Bitim va kontrakt raqamlari bo‘yicha ma'lumot berish.\n\n"
                    "📌 Namunaviy savollar uchun: **/help**"
                )
            else:
                return (
                    "🏛 **О проекте UZEX AI:**\n\n"
                    "Я — независимый аналитический AI-ассистент по данным торгов Узбекской республиканской товарно-сырьевой биржи (UZEX).\n\n"
                    "💡 **Что умеет аналитический помощник UZEX AI:**\n"
                    "• Анализировать подготовленный массив данных торгов за 2022–2026 годы;\n"
                    "• Рассчитывать средневзвешенные, минимальные и максимальные цены товаров;\n"
                    "• Формировать рейтинги товаров, участников торгов и брокеров;\n"
                    "• Находить параметры конкретных сделок и контрактов по номерам.\n\n"
                    "📌 Примеры запросов доступны по команде **/help**."
                )

        # 5. Unknown / Ambiguous query (Safety fallback — NO SQL aggregation on entire dataset!)
        if params.intent == IntentType.UNKNOWN:
            if lang == "uz":
                return (
                    "❓ **So‘rovingiz bo‘yicha aniq ma'lumot topilmadi.**\n\n"
                    "Iltimos, birja savdolari bo‘yicha savolingizni aniqlashtiring (masalan, tovar nomi, yil yoki bitim raqamini ko‘rsating).\n\n"
                    "📌 Savol namunalari bilan tanishish uchun **/help** buyrug‘idan foydalaning."
                )
            else:
                return (
                    "❓ **Не удалось однозначно определить параметры вашего вопроса.**\n\n"
                    "Пожалуйста, уточните запрос (например, укажите товар, интересующий год или номер сделки).\n\n"
                    "📌 Примеры корректных запросов доступны по команде **/help**."
                )

        # 4. No data found
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
        use_llm: bool = True,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Builds response dynamically.
        For conversational modes (GENERAL_CHAT, GENERAL_KNOWLEDGE, EXCHANGE_INFO, UNKNOWN):
            Gemini generates natural, non-repetitive dialogue while respecting UZEX context and Zero-Hallucination rules.
        For analytical modes (AGGREGATION, RANKING, PRICE_INQUIRY, etc.):
            SQL-backed verified facts are passed to Gemini for natural analytical presentation.
        If Gemini is unavailable or disabled, clean deterministic text is returned.
        """
        deterministic_text = cls.build_deterministic(params, result, lang)

        if not use_llm or not gemini_client.is_configured():
            return deterministic_text

        # If it's strictly out of bounds of the dataset (e.g. year 2021 or 2030), return exact date bounds
        if result.is_out_of_dataset or params.intent == IntentType.OUT_OF_SCOPE:
            return deterministic_text

        lang_name = "Uzbek (O'zbek tili)" if lang == "uz" else "Russian (Русский язык)"

        # 1. GENERAL_CHAT prompt
        if params.intent == IntentType.GENERAL_CHAT:
            system_prompt = (
                f"You are UZEX AI, an independent analytical AI assistant for Uzbek Commodity Exchange trade data.\n"
                f"Language: Respond naturally and concisely in {lang_name}.\n"
                f"Tone: Friendly, concise (1-2 sentences), natural. Do NOT use rigid templates or bullet points.\n"
                f"Never claim to be an official exchange representative or official spokesperson.\n"
                f"Offer help with commodity dataset analytics if relevant."
            )
            chat_messages = list(history or [])
            chat_messages.append({"role": "user", "content": user_question})
            try:
                chat_resp = await gemini_client.generate_chat_response(
                    messages=chat_messages,
                    system_instruction=system_prompt,
                    temperature=0.7,
                    timeout_seconds=15
                )
                if chat_resp and len(chat_resp.strip()) > 3:
                    return chat_resp.strip()
            except Exception as e:
                logger.warning(f"Gemini chat generation failed: {e}")
            return deterministic_text

        # 2. GENERAL_KNOWLEDGE prompt
        if params.intent == IntentType.GENERAL_KNOWLEDGE:
            system_prompt = (
                f"You are an economics and commodity markets expert assistant for UZEX AI (independent analytics project).\n"
                f"Language: Explain clearly, concisely, and educationally in {lang_name} (2-4 sentences).\n"
                f"Instruction: Explain the requested economic/market concept accurately. "
                f"Clarify that this is general financial terminology, not internal rules of UZEX."
            )
            chat_messages = list(history or [])
            chat_messages.append({"role": "user", "content": user_question})
            try:
                chat_resp = await gemini_client.generate_chat_response(
                    messages=chat_messages,
                    system_instruction=system_prompt,
                    temperature=0.4,
                    timeout_seconds=15
                )
                if chat_resp and len(chat_resp.strip()) > 10:
                    return chat_resp.strip()
            except Exception as e:
                logger.warning(f"Gemini general knowledge failed: {e}")
            return deterministic_text

        # 3. EXCHANGE_INFO prompt (Persona & Capabilities)
        if params.intent == IntentType.EXCHANGE_INFO:
            verified_uzex_facts = (
                "Context about UZEX AI:\n"
                "- Identity: Independent analytical AI assistant for UZEX (Uzbek Commodity Exchange) trading data.\n"
                "- NOT an official representative or spokesperson of the exchange.\n"
                "- Dataset: Project commodity dataset covering 2022-2026.\n"
                "- Key capabilities: Analyzing prices, trading volumes, turnover, rankings of goods/participants/brokers, and inspecting contract/deal details.\n"
                "- Commodities: Gasoline, diesel, cement, grain, copper, cotton, fertilizers, sugar, metals."
            )
            system_prompt = (
                f"You are UZEX AI, an independent analytical assistant for commodity exchange data.\n"
                f"Language: Answer in {lang_name}.\n"
                f"Style: Natural, concise (2-4 sentences or short readable paragraphs). Avoid overwhelming walls of text and static bullet checklists.\n"
                f"Important: Do NOT claim to be the official exchange or official service. You are an independent analytics project based on 2022-2026 dataset.\n\n"
                f"{verified_uzex_facts}"
            )
            chat_messages = list(history or [])
            chat_messages.append({"role": "user", "content": user_question})
            try:
                chat_resp = await gemini_client.generate_chat_response(
                    messages=chat_messages,
                    system_instruction=system_prompt,
                    temperature=0.5,
                    timeout_seconds=15
                )
                if chat_resp and len(chat_resp.strip()) > 10:
                    return chat_resp.strip()
            except Exception as e:
                logger.warning(f"Gemini exchange info failed: {e}")
            return deterministic_text

        # 4. UNKNOWN prompt
        if params.intent == IntentType.UNKNOWN:
            system_prompt = (
                f"You are UZEX AI, an independent assistant for commodity analytics.\n"
                f"Language: Respond politely and concisely in {lang_name} (1-2 sentences).\n"
                f"Situation: The query lacks specific parameters (commodity, year 2022-2026, deal ID).\n"
                f"Action: Ask the user to clarify what commodity or year they want to analyze. Mention command /help for examples.\n"
                f"ZERO HALLUCINATION: Do NOT invent trade numbers."
            )
            chat_messages = list(history or [])
            chat_messages.append({"role": "user", "content": user_question})
            try:
                chat_resp = await gemini_client.generate_chat_response(
                    messages=chat_messages,
                    system_instruction=system_prompt,
                    temperature=0.4,
                    timeout_seconds=15
                )
                if chat_resp and len(chat_resp.strip()) > 10:
                    return chat_resp.strip()
            except Exception as e:
                logger.warning(f"Gemini unknown fallback failed: {e}")
            return deterministic_text

        # 5. ANALYTICS & MIXED prompt (Strict Zero-Hallucination Presentation)
        system_prompt = (
            f"You are UZEX AI, an independent analytical assistant for Uzbek commodity trading data.\n"
            f"Language: Present the findings in {lang_name}.\n"
            f"ZERO HALLUCINATION POLICY (STRICT):\n"
            f"1. You MUST NEVER invent, extrapolate, or alter any numbers, prices, volumes, dates, or participants.\n"
            f"2. Use ONLY the verified data provided below. Do not add outside guesses or speculative reasons.\n"
            f"3. Do NOT claim the data is official exchange statistics; refer to it as the project dataset.\n"
            f"4. If no data was found, state clearly that it is absent in the dataset.\n"
            f"5. Maintain a professional, clear tone."
        )

        user_prompt = (
            f"User Question: {user_question}\n\n"
            f"Verified SQL Query Results:\n{deterministic_text}\n\n"
            f"Present this result naturally and concisely in {lang_name} adhering strictly to the verified data above."
        )

        chat_messages = list(history or [])
        chat_messages.append({"role": "user", "content": user_prompt})

        try:
            gemini_response = await gemini_client.generate_chat_response(
                messages=chat_messages,
                system_instruction=system_prompt,
                temperature=0.1,
                timeout_seconds=15
            )
            if gemini_response and len(gemini_response.strip()) > 15:
                return gemini_response.strip()
        except Exception as e:
            logger.warning(f"Gemini natural formatting failed, falling back to deterministic: {e}")

        return deterministic_text
