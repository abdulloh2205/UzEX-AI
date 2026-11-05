import unittest
from src.query_engine.models import IntentType, QueryParams, StatusPolicy, VolumeType
from src.query_engine.entity_linker import EntityLinker
from src.query_engine.executor import QueryExecutor
from src.query_engine.engine import (
    calculate_prices,
    calculate_turnover_and_volume,
    compare_periods,
    get_top_rankings,
    get_usd_rate,
    lookup_broker,
    lookup_deal,
    lookup_participant,
)


class TestQueryEngine(unittest.TestCase):
    def test_entity_linker_uzbek(self):
        prod, raw = EntityLinker.resolve_product("2024-yilda qancha benzin sotilgan?")
        self.assertEqual(prod, "бензин")

        prod2, raw2 = EntityLinker.resolve_product("bug'doyning o'rtacha narxi qancha?")
        self.assertEqual(prod2, "пшеница")

        prod3, raw3 = EntityLinker.resolve_product("mis katodi bo'yicha bitimlar")
        self.assertEqual(prod3, "катод медный")

        code = EntityLinker.extract_broker_code("BK001 brokerining aylanmasi")
        self.assertEqual(code, "BK001")

        year = EntityLinker.extract_year("2025 yildagi natijalar")
        self.assertEqual(year, 2025)

        status = EntityLinker.extract_status("bekor qilingan bitimlar")
        self.assertEqual(status, "Аннулирован(Не оплачен)")

    def test_aggregation_query_latency(self):
        res = calculate_turnover_and_volume(year=2024, status_policy=StatusPolicy.NON_CANCELLED)
        self.assertGreater(res.deal_count, 0)
        self.assertGreater(res.total_amount_uzs, 0)
        self.assertGreater(res.total_volume, 0)

    def test_delivered_vs_contracted_volume(self):
        contracted = calculate_turnover_and_volume(
            product="бензин",
            year=2023,
            volume_type=VolumeType.CONTRACTED
        )
        delivered = calculate_turnover_and_volume(
            product="бензин",
            year=2023,
            volume_type=VolumeType.DELIVERED
        )
        # Contracted volume should be greater than or equal to physical delivered volume
        self.assertGreaterEqual(contracted.total_volume, delivered.total_volume)

    def test_product_ranking_query(self):
        rankings = get_top_rankings(
            ranking_entity="product",
            metric="amount_uzs",
            year=2023,
            limit=5
        )
        self.assertEqual(len(rankings), 5)
        self.assertIn("product_name", rankings[0])
        self.assertIn("total_amount_uzs", rankings[0])

    def test_price_inquiry(self):
        prices = calculate_prices(product="бензин", year=2024)
        self.assertIsNotNone(prices.weighted_avg_price)
        self.assertGreater(prices.weighted_avg_price, 0)
        self.assertGreater(prices.max_price, prices.min_price)

    def test_deal_lookup(self):
        deal = lookup_deal(deal_id=100001)
        self.assertIsNotNone(deal)
        self.assertEqual(deal["deal_id"], 100001)
        self.assertIn("delivered_volume", deal)

    def test_period_comparison(self):
        comp = compare_periods(
            period1={"year": 2023},
            period2={"year": 2024},
            product="бензин",
            metric="amount_uzs"
        )
        self.assertEqual(comp.period1_name, "2023")
        self.assertEqual(comp.period2_name, "2024")
        self.assertIsNotNone(comp.absolute_change)

    def test_out_of_dataset_detection(self):
        params = QueryParams(
            intent=IntentType.AGGREGATION,
            year=2027,
            language="ru"
        )
        res = QueryExecutor.execute_params(params)
        self.assertTrue(res.is_out_of_dataset)
        self.assertFalse(res.has_data)
        self.assertIn("2027", res.out_of_dataset_reason)

    def test_sql_injection_defense(self):
        malicious_sql = "DROP TABLE deals; SELECT * FROM participants;"
        res = QueryExecutor.execute_raw_sql(malicious_sql)
        self.assertFalse(res.success)
        self.assertIn("Security rejection", res.out_of_dataset_reason)


if __name__ == "__main__":
    unittest.main()
