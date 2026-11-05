"""
Localization messages and templates for UZEX AI Telegram Bot.
Supports Russian and Uzbek languages.
"""

START_FIRST_TIME_RU = (
    "👋 **Здравствуйте! Добро пожаловать в UZEX AI.**\n\n"
    "Я — официальный интеллектуальный аналитический помощник по биржевым торгам "
    "Узбекской республиканской товарно-сырьевой биржи (UZEX).\n\n"
    "📊 **Что я умею:**\n"
    "• Предоставлять статистику торгов за 2022–2026 годы (более 500 000 сделок).\n"
    "• Рассчитывать средневзвешенные цены и объёмы ключевых биржевых товаров.\n"
    "• Анализировать активность брокеров и участников рынка.\n"
    "• Предоставлять точную информацию по номерам сделок и контрактов.\n\n"
    "🌐 Пожалуйста, выберите предпочтительный язык общения:\n"
    "Iltimos, muloqot tilini tanlang:"
)

START_RETURNING_RU = (
    "👋 **С возвращением в UZEX AI!**\n\n"
    "Я готов ответить на ваши вопросы по биржевым торгам UZEX за 2022–2026 годы.\n\n"
    "💡 Задайте любой вопрос прямо в чат или воспользуйтесь командой /help для просмотра примеров.\n"
    "Сменить язык можно в любой момент командой /language."
)

START_RETURNING_UZ = (
    "👋 **UZEX AI tizimiga qayta xush kelibsiz!**\n\n"
    "Men O‘zbekiston tovar-xomashyo birjasining 2022–2026 yillardagi savdo ma'lumotlari bo‘yicha savollaringizga javob berishga tayyorman.\n\n"
    "💡 Savolingizni to‘g‘ridan-to‘g‘ri yozing yoki namunalar uchun /help buyrug‘idan foydalaning.\n"
    "Muloqot tilini istalgan vaqtda /language buyrug‘i orqali o‘zgartirishingiz mumkin."
)

HELP_RU = (
    "ℹ️ **Справка по возможностям UZEX AI**\n\n"
    "Я предоставляю доступ к проверенным аналитическим данным биржевых торгов UZEX (2022–2026 гг.):\n\n"
    "📌 **Примеры запросов:**\n"
    "• *Какой объём торгов был в 2025 году?*\n"
    "• *Какие товары лидировали по обороту?*\n"
    "• *Какова средневзвешенная цена бензина?*\n"
    "• *Покажи сделку №100001.*\n"
    "• *Какой брокер имеет наибольший оборот?*\n\n"
    "⚙️ **Доступные команды:**\n"
    "/start — Начать работу или перезапустить бота\n"
    "/help — Справка и примеры запросов\n"
    "/language — Изменить язык интерфейса (🇷🇺 / 🇺🇿)"
)

HELP_UZ = (
    "ℹ️ **UZEX AI imkoniyatlari bo‘yicha ma'lumot**\n\n"
    "Men UZEX birja savdolari (2022–2026 yillar) bo‘yicha aniq analitik ma'lumotlarni taqdim etaman:\n\n"
    "📌 **Savol namunalari:**\n"
    "• *2025-yilda savdo hajmi qancha bo'lgan?*\n"
    "• *Eng ko'p sotilgan mahsulotlar qaysilar?*\n"
    "• *Benzinning o'rtacha narxi qancha?*\n"
    "• *100001-sonli bitimni ko'rsat.*\n"
    "• *Qaysi broker eng katta aylanmaga ega?*\n\n"
    "⚙️ **Mavjud buyruqlar:**\n"
    "/start — Botni ishga tushirish yoki yangilash\n"
    "/help — Qo‘llanma va savol namunalari\n"
    "/language — Muloqot tilini o‘zgartirish (🇷🇺 / 🇺🇿)"
)

CHOOSE_LANGUAGE_RU = (
    "🌐 **Выбор языка интерфейса**\n\n"
    "Пожалуйста, выберите удобный для вас язык:"
)

CHOOSE_LANGUAGE_UZ = (
    "🌐 **Muloqot tilini tanlash**\n\n"
    "Iltimos, o‘zingizga qulay tilni tanlang:"
)

LANGUAGE_SET_CONFIRM_RU = (
    "✅ **Язык успешно изменён на русский!**\n\n"
    "Теперь вы можете задать интересующий вас вопрос по биржевым торгам UZEX."
)

LANGUAGE_SET_CONFIRM_UZ = (
    "✅ **Muloqot tili o'zbek tiliga muvaffaqiyatli o'zgartirildi!**\n\n"
    "Endi UZEX birja savdolari bo‘yicha o‘zingizni qiziqtirgan savolni berishingiz mumkin."
)

EMPTY_QUERY_RU = (
    "⚠️ Пожалуйста, введите текстовый вопрос о биржевых торгах UZEX.\n"
    "Примеры запросов можно посмотреть с помощью команды /help."
)

EMPTY_QUERY_UZ = (
    "⚠️ Iltimos, UZEX birja savdolari bo‘yicha matnli savol kiriting.\n"
    "Savol namunalarini ko‘rish uchun /help buyrug‘idan foydalanishingiz mumkin."
)

NON_TEXT_INPUT_RU = (
    "ℹ️ UZEX AI обрабатывает текстовые запросы о биржевых торгах.\n"
    "Пожалуйста, напишите ваш вопрос текстом или воспользуйтесь /help."
)

NON_TEXT_INPUT_UZ = (
    "ℹ️ UZEX AI faqat birja savdolari bo‘yicha matnli savollarni qabul qiladi.\n"
    "Iltimos, savolingizni matn ko‘rinishida yuboring yoki /help buyrug‘idan foydalaning."
)

GENERIC_ERROR_RU = (
    "⚠️ Произошла ошибка при обработке вашего запроса.\n"
    "Пожалуйста, попробуйте повторить запрос позже или уточните формулировку."
)

GENERIC_ERROR_UZ = (
    "⚠️ So‘rovingizni qayta ishlashda xatolik yuz berdi.\n"
    "Iltimos, so‘rovni keyinroq qayta yuboring yoki savolni aniqlashtiring."
)
