import unittest
from src.db.database import get_db, execute_scalar, execute_query


class TestDatabaseImport(unittest.TestCase):
    def test_row_counts(self):
        deals_count = execute_scalar("SELECT COUNT(*) FROM deals;")
        self.assertEqual(deals_count, 500000, f"Expected 500,000 deals, got {deals_count}")

        contracts_count = execute_scalar("SELECT COUNT(*) FROM contracts;")
        self.assertEqual(contracts_count, 6616, f"Expected 6,616 contracts, got {contracts_count}")

        participants_count = execute_scalar("SELECT COUNT(*) FROM participants;")
        self.assertEqual(participants_count, 14392, f"Expected 14,392 participants, got {participants_count}")

        brokers_count = execute_scalar("SELECT COUNT(*) FROM brokers;")
        self.assertEqual(brokers_count, 120, f"Expected 120 brokers, got {brokers_count}")

        rates_count = execute_scalar("SELECT COUNT(*) FROM usd_rates;")
        self.assertEqual(rates_count, 1765, f"Expected 1,765 USD rates, got {rates_count}")

    def test_deal_calculations(self):
        # Pick 5 sample deals and verify math
        deals = execute_query("SELECT * FROM deals LIMIT 5;")
        for d in deals:
            expected_vol = d["quantity"] * d["lot"]
            self.assertAlmostEqual(d["volume"], expected_vol, places=2)
            if expected_vol > 0:
                expected_unit_price = d["amount"] / expected_vol
                self.assertAlmostEqual(d["unit_price"], expected_unit_price, places=2)

            if d["currency"] == "USD":
                expected_uzs = d["amount"] * d["usd_rate"]
                self.assertAlmostEqual(d["amount_uzs"], expected_uzs, places=2)
            else:
                self.assertEqual(d["amount_uzs"], d["amount"])

    def test_fts_search(self):
        # Test product FTS
        res = execute_query("SELECT product_name FROM products_fts WHERE products_fts MATCH 'цемент' LIMIT 3;")
        self.assertTrue(len(res) > 0, "FTS for 'цемент' returned no results")

        # Test participants FTS
        res_p = execute_query("SELECT name FROM participants_fts WHERE participants_fts MATCH 'KIMYO' LIMIT 3;")
        self.assertTrue(len(res_p) > 0, "FTS for 'KIMYO' returned no results")

        # Test brokers FTS
        res_b = execute_query("SELECT name FROM brokers_fts WHERE brokers_fts MATCH 'BROKER' LIMIT 3;")
        self.assertTrue(len(res_b) > 0, "FTS for 'BROKER' returned no results")


if __name__ == "__main__":
    unittest.main()
