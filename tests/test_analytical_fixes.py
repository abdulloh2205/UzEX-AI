import unittest
from src.agent.intent import IntentParser
from src.agent.language import LanguageDetector
from src.agent.orchestrator import AgentOrchestrator
from src.query_engine.executor import QueryExecutor
from src.query_engine.models import IntentType, QueryParams, StatusPolicy


class TestAnalyticalFixes(unittest.TestCase):
    def test_top5_russian_query_intent(self):
        """Проверка распознавания TOP-5 и limit=5 на русском языке."""
        q = "Какие 5 товаров лидируют по обороту в 2025 году?"
        lang = LanguageDetector.detect(q)
        self.assertEqual(lang, "ru")

        params = IntentParser.parse_deterministic(q, lang)
        self.assertEqual(params.intent, IntentType.RANKING)
        self.assertEqual(params.ranking_entity, "product")
        self.assertEqual(params.limit, 5)
        self.assertEqual(params.year, 2025)

        res = AgentOrchestrator.process_question_sync(q)
        self.assertEqual(res.language, "ru")
        self.assertIn("Топ самых торгуемых товаров", res.text)
        self.assertIn("Пшеница", res.text)
        self.assertIn("КАТОД МЕДНЫЙ", res.text)

    def test_top5_uzbek_latin_apostrophes(self):
        """Проверка распознавания TOP-5 с типографским апострофом (U+2018)."""
        q = "2025-yilda eng ko‘p sotilgan 5 ta mahsulotni ko‘rsat"
        lang = LanguageDetector.detect(q)
        self.assertEqual(lang, "uz")

        params = IntentParser.parse_deterministic(q, lang)
        self.assertEqual(params.intent, IntentType.RANKING)
        self.assertEqual(params.ranking_entity, "product")
        self.assertEqual(params.limit, 5)
        self.assertEqual(params.year, 2025)

        res = AgentOrchestrator.process_question_sync(q)
        self.assertEqual(res.language, "uz")
        self.assertIn("Eng ko‘p sotilgan tovarlar reytingi", res.text)
        self.assertIn("so‘m", res.text)

    def test_top5_uzbek_cyrillic(self):
        """Проверка распознавания TOP-5 на узбекской кириллице."""
        q = "2025 йилда энг кўп сотилган 5 та маҳсулотни кўрсат"
        lang = LanguageDetector.detect(q)
        self.assertEqual(lang, "uz")

        params = IntentParser.parse_deterministic(q, lang)
        self.assertEqual(params.intent, IntentType.RANKING)
        self.assertEqual(params.limit, 5)

        res = AgentOrchestrator.process_question_sync(q)
        self.assertEqual(res.language, "uz")
        self.assertIn("Eng ko‘p sotilgan tovarlar reytingi", res.text)

    def test_gasoline_units_segregation(self):
        """Проверка раздельного расчёта цен бензина в литрах и тоннах."""
        q = "Какова средневзвешенная цена бензина в 2025 году?"
        res = AgentOrchestrator.process_question_sync(q)

        # Должны присутствовать обе секции с отдельными единицами
        self.assertIn("литр", res.text)
        self.assertIn("тонна", res.text)

        # Цены не должны быть перемешаны: литр ~10 273, тонна ~13 629 868
        self.assertIn("10 273.88", res.text)
        self.assertIn("13 629 868.03", res.text)
        self.assertIn("20 231 065.00", res.text)

    def test_status_policy_consistency(self):
        """Проверка согласованности StatusPolicy для агрегатов."""
        # Без явных маркеров общего реестра дефолт — NON_CANCELLED
        p1 = IntentParser.parse_deterministic("Какой объем торгов был в 2025 году?", "ru")
        self.assertEqual(p1.status_policy, StatusPolicy.NON_CANCELLED)

        # С маркером "всего" / "общий" — REGISTERED
        p2 = IntentParser.parse_deterministic("Какой общий объем торгов был в 2025 году?", "ru")
        self.assertEqual(p2.status_policy, StatusPolicy.REGISTERED)


if __name__ == "__main__":
    unittest.main()
