import unittest
from src.agent.orchestrator import AgentOrchestrator
from src.agent.language import LanguageDetector


class TestBilingualAgent(unittest.TestCase):
    def test_language_detection(self):
        self.assertEqual(LanguageDetector.detect("2024-yilda qancha benzin sotilgan?"), "uz")
        self.assertEqual(LanguageDetector.detect("Bug'doyning o'rtacha narxi qancha?"), "uz")
        self.assertEqual(LanguageDetector.detect("Bekor qilingan bitimlar soni nechta?"), "uz")
        self.assertEqual(LanguageDetector.detect("Какой объем торгов был в 2024 году?"), "ru")
        self.assertEqual(LanguageDetector.detect("Назови топ-5 продавцов цемента"), "ru")
        self.assertEqual(LanguageDetector.detect("Какова средняя цена меди в 2023 году?"), "ru")

    def test_russian_volume_2024(self):
        res = AgentOrchestrator.process_question_sync("Какой общий объем торгов был в 2024 году?")
        self.assertEqual(res.language, "ru")
        self.assertTrue(res.has_data)
        self.assertFalse(res.is_out_of_dataset)
        self.assertIn("106 647", res.text)
        self.assertIn("сум", res.text.lower())
        self.assertLess(res.latency_ms, 2000)

    def test_uzbek_volume_2024(self):
        res = AgentOrchestrator.process_question_sync("2024-yilda jami qancha bitim tuzilgan?")
        self.assertEqual(res.language, "uz")
        self.assertTrue(res.has_data)
        self.assertIn("106 647", res.text)
        self.assertIn("so‘m", res.text.lower())

    def test_russian_top_products(self):
        res = AgentOrchestrator.process_question_sync("Назови топ-5 самых продаваемых товаров в 2023 году")
        self.assertEqual(res.language, "ru")
        self.assertIn("1.", res.text)
        self.assertIn("2.", res.text)
        self.assertIn("3.", res.text)

    def test_uzbek_top_products(self):
        res = AgentOrchestrator.process_question_sync("2023-yilda eng ko'p sotilgan tovarlar reytingi")
        self.assertEqual(res.language, "uz")
        self.assertIn("1.", res.text)
        self.assertIn("2.", res.text)

    def test_russian_price_inquiry(self):
        res = AgentOrchestrator.process_question_sync("Какова средняя цена бензина в 2024 году?")
        self.assertEqual(res.language, "ru")
        self.assertIn("сум", res.text.lower())
        self.assertIn("Средневзвешенная цена", res.text)

    def test_uzbek_price_inquiry(self):
        res = AgentOrchestrator.process_question_sync("2024-yilda bug'doyning o'rtacha narxi qancha bo'lgan?")
        self.assertEqual(res.language, "uz")
        self.assertIn("so‘m", res.text.lower())

    def test_deal_lookup(self):
        res = AgentOrchestrator.process_question_sync("Расскажи о сделке №100001")
        self.assertTrue(res.has_data)
        self.assertIn("100001", res.text)
        self.assertIn("Шрот хлопковых семян", res.text)

    def test_broker_lookup(self):
        res = AgentOrchestrator.process_question_sync("BK001 brokeri haqida ma'lumot bering")
        self.assertTrue(res.has_data)
        self.assertIn("BK001", res.text)

    def test_out_of_bounds_year_russian(self):
        res = AgentOrchestrator.process_question_sync("Сколько сделок было в 2027 году?")
        self.assertTrue(res.is_out_of_dataset)
        self.assertIn("2027", res.text)
        self.assertIn("отсутствуют", res.text.lower())

    def test_out_of_bounds_year_uzbek(self):
        res = AgentOrchestrator.process_question_sync("2021-yilda qanday bitimlar bo'lgan?")
        self.assertTrue(res.is_out_of_dataset)
        self.assertIn("2021", res.text)
        self.assertIn("mavjud emas", res.text.lower())


if __name__ == "__main__":
    unittest.main()
