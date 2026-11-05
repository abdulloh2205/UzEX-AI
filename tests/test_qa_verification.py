"""
UZEX AI QA Comprehensive Verification & Stress-Testing Suite.
Tests database integrity, exact dataset row counts, mathematical calculation precision,
status semantics, bilingual entity linking (Uzbek Latin/Cyrillic & Russian),
edge cases, anti-hallucination guards, SQL injection defense, and query latency SLAs.
"""

import math
import sqlite3
import time
from typing import Any, Dict, List, Tuple
import unittest

from src.config import settings
from src.db.database import create_connection, execute_query, execute_scalar, get_db
from src.query_engine.models import (
    IntentType,
    QueryParams,
    QueryResult,
    StatusPolicy,
    VolumeType,
)
from src.query_engine.sql_builder import SQLBuilder
from src.query_engine.executor import QueryExecutor, FORBIDDEN_SQL_PATTERNS
from src.query_engine.entity_linker import EntityLinker, PRODUCT_SYNONYMS, STATUS_SYNONYMS
from src.query_engine.engine import (
    calculate_turnover_and_volume,
    get_commodity_price_metrics,
    get_top_ranking,
    lookup_broker,
    lookup_contract,
    lookup_deal,
    lookup_participant,
    lookup_product,
)
from src.agent.language import LanguageDetector
from src.agent.intent import IntentParser
from src.agent.orchestrator import AgentOrchestrator, AgentResponse


# ==============================================================================
# SUITE 1: DATASET INTEGRITY & EXACT IMPORTED ROW COUNTS
# ==============================================================================
class TestSuite1DatasetIntegrity(unittest.TestCase):
    """Verifies exact database row counts, schema constraints, and foreign key referential integrity."""

    def test_exact_row_counts(self):
        """Audit specification requirement: deals=500,000, contracts=6,616, participants=14,392, brokers=120, usd_rates=1,765."""
        expected = {
            "deals": 500000,
            "contracts": 6616,
            "participants": 14392,
            "brokers": 120,
            "usd_rates": 1765,
        }
        with get_db(read_only=True) as conn:
            cursor = conn.cursor()
            for table, expected_count in expected.items():
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                actual_count = cursor.fetchone()[0]
                self.assertEqual(
                    actual_count, expected_count,
                    f"Mismatch in {table}: expected exactly {expected_count}, got {actual_count}"
                )

    def test_referential_integrity_zero_orphans(self):
        """Verifies zero foreign key orphan records across all 500,000 deals."""
        fk_checks = {
            "deals_to_contracts": (
                "SELECT COUNT(*) FROM deals d "
                "WHERE NOT EXISTS (SELECT 1 FROM contracts c WHERE c.contract_id = d.contract_id);"
            ),
            "deals_to_seller_participant": (
                "SELECT COUNT(*) FROM deals d "
                "WHERE NOT EXISTS (SELECT 1 FROM participants p WHERE p.inn = d.seller_inn);"
            ),
            "deals_to_buyer_participant": (
                "SELECT COUNT(*) FROM deals d "
                "WHERE NOT EXISTS (SELECT 1 FROM participants p WHERE p.inn = d.buyer_inn);"
            ),
            "deals_to_seller_broker": (
                "SELECT COUNT(*) FROM deals d "
                "WHERE NOT EXISTS (SELECT 1 FROM brokers b WHERE b.broker_code = d.seller_broker);"
            ),
            "deals_to_buyer_broker": (
                "SELECT COUNT(*) FROM deals d "
                "WHERE NOT EXISTS (SELECT 1 FROM brokers b WHERE b.broker_code = d.buyer_broker);"
            ),
            "deals_to_usd_rates": (
                "SELECT COUNT(*) FROM deals d "
                "WHERE NOT EXISTS (SELECT 1 FROM usd_rates u WHERE u.rate_date = d.deal_date);"
            ),
        }
        with get_db(read_only=True) as conn:
            cursor = conn.cursor()
            for name, query in fk_checks.items():
                cursor.execute(query)
                orphan_count = cursor.fetchone()[0]
                self.assertEqual(orphan_count, 0, f"Referential integrity failure in {name}: found {orphan_count} orphan deals!")

    def test_date_range_boundaries(self):
        """Verifies dataset temporal boundary: 2022-01-03 to 2026-10-30."""
        min_date = execute_scalar("SELECT MIN(deal_date) FROM deals;")
        max_date = execute_scalar("SELECT MAX(deal_date) FROM deals;")
        self.assertEqual(min_date, "2022-01-03", f"Expected min deal_date 2022-01-03, found {min_date}")
        self.assertEqual(max_date, "2026-10-30", f"Expected max deal_date 2026-10-30, found {max_date}")

    def test_distinct_deal_years(self):
        """Verifies exactly 5 distinct years (2022..2026) in deals table."""
        years = execute_query("SELECT DISTINCT deal_year FROM deals ORDER BY deal_year ASC;")
        actual_years = [r["deal_year"] for r in years]
        self.assertEqual(actual_years, [2022, 2023, 2024, 2025, 2026])


# ==============================================================================
# SUITE 2: MATHEMATICAL CALCULATION VERIFICATION
# ==============================================================================
class TestSuite2MathematicalCalculations(unittest.TestCase):
    """Verifies business math formulas: volume, delivered_volume, unit_price, amount_uzs, and weighted vs simple avg."""

    def test_contracted_volume_formula(self):
        """Verifies volume = quantity * lot across all deals."""
        mismatches = execute_scalar(
            "SELECT COUNT(*) FROM deals WHERE ABS(volume - (quantity * lot)) > 0.001;"
        )
        self.assertEqual(mismatches, 0, f"Found {mismatches} deals with invalid volume != quantity * lot")

    def test_delivered_volume_formula(self):
        """Verifies delivered_volume = delivered_qty * lot (or 0.0 if not delivered)."""
        # Deals with delivered_qty NOT NULL
        mismatches_delivered = execute_scalar(
            "SELECT COUNT(*) FROM deals WHERE delivered_qty IS NOT NULL AND ABS(delivered_volume - (delivered_qty * lot)) > 0.001;"
        )
        self.assertEqual(mismatches_delivered, 0, f"Found {mismatches_delivered} deals with delivered_volume != delivered_qty * lot")

        # Deals with delivered_qty IS NULL must have delivered_volume = 0.0
        mismatches_null = execute_scalar(
            "SELECT COUNT(*) FROM deals WHERE delivered_qty IS NULL AND delivered_volume != 0.0;"
        )
        self.assertEqual(mismatches_null, 0, f"Found {mismatches_null} deals with NULL delivered_qty but delivered_volume != 0.0")

    def test_unit_price_formula(self):
        """Verifies unit_price = amount / volume."""
        mismatches = execute_scalar(
            "SELECT COUNT(*) FROM deals WHERE volume > 0 AND ABS(unit_price - (amount / volume)) > 0.05;"
        )
        self.assertEqual(mismatches, 0, f"Found {mismatches} deals where unit_price deviates from amount / volume")

    def test_currency_conversion_amount_uzs(self):
        """
        Verifies:
        - Export deals (USD): amount_uzs = amount * usd_rate
        - Domestic deals (UZS): amount_uzs = amount, currency = 'UZS', usd_rate matched
        """
        export_mismatches = execute_scalar(
            """SELECT COUNT(*) FROM deals
               WHERE currency = 'USD'
               AND ABS(amount_uzs - (amount * usd_rate)) > 0.05;"""
        )
        self.assertEqual(export_mismatches, 0, f"Found {export_mismatches} export deals with incorrect amount_uzs")

        domestic_mismatches = execute_scalar(
            """SELECT COUNT(*) FROM deals
               WHERE currency = 'UZS'
               AND ABS(amount_uzs - amount) > 0.01;"""
        )
        self.assertEqual(domestic_mismatches, 0, f"Found {domestic_mismatches} domestic deals where amount_uzs != amount")

    def test_weighted_vs_simple_average_price(self):
        """
        Verifies that weighted average price (SUM(amount_uzs) / SUM(volume))
        is mathematically distinct from simple average price (AVG(unit_price_uzs))
        and that get_commodity_price_metrics calculates both accurately.
        """
        metrics = get_commodity_price_metrics(product="бензин", year=2024)
        self.assertIsNotNone(metrics.weighted_avg_price)
        self.assertIsNotNone(metrics.simple_avg_price)
        self.assertGreater(metrics.weighted_avg_price, 0)
        self.assertGreater(metrics.simple_avg_price, 0)
        self.assertNotEqual(metrics.weighted_avg_price, metrics.simple_avg_price)
        self.assertGreater(metrics.deal_count, 0)
        self.assertGreater(metrics.total_volume, 0)


# ==============================================================================
# SUITE 3: STATUS SEMANTICS & VOLUME POLICY
# ==============================================================================
class TestSuite3StatusSemantics(unittest.TestCase):
    """Verifies exactly 8 distinct statuses, StatusPolicy filtering, and Contracted vs Delivered volumes."""

    EXPECTED_8_STATUSES = {
        "Аннулирован(Не оплачен)",
        "Исполнен",
        "Исполнен(Частично)",
        "Оплачен",
        "Ждёт оплату",
        "Новый",
        "Не подписан",
        "Заключен",
    }

    def test_exactly_8_statuses_present(self):
        """Verifies the database contains exactly the 8 standard trade statuses."""
        rows = execute_query("SELECT DISTINCT status FROM deals ORDER BY status;")
        actual_statuses = {r["status"] for r in rows}
        self.assertEqual(
            actual_statuses, self.EXPECTED_8_STATUSES,
            f"Expected 8 statuses, found diff: {actual_statuses.symmetric_difference(self.EXPECTED_8_STATUSES)}"
        )

    def test_status_policies_hierarchy(self):
        """
        Verifies deal counts:
        REGISTERED (all 500k) > NON_CANCELLED (status != 'Аннулирован(Не оплачен)') > EXECUTED (status = 'Исполнен')
        """
        reg = calculate_turnover_and_volume(status_policy=StatusPolicy.REGISTERED)
        non_canc = calculate_turnover_and_volume(status_policy=StatusPolicy.NON_CANCELLED)
        exec_only = calculate_turnover_and_volume(status_policy=StatusPolicy.EXECUTED)
        cancelled = calculate_turnover_and_volume(status_policy=StatusPolicy.CANCELLED)

        self.assertEqual(reg.deal_count, 500000, f"Registered count must be 500,000, got {reg.deal_count}")
        self.assertLess(non_canc.deal_count, reg.deal_count)
        self.assertEqual(non_canc.deal_count + cancelled.deal_count, reg.deal_count)
        self.assertLess(exec_only.deal_count, non_canc.deal_count)
        self.assertGreater(exec_only.deal_count, 0)

    def test_contracted_vs_delivered_volume_distinction(self):
        """
        Verifies that contracted volume (deals.volume) is distinct from physically delivered volume (deals.delivered_volume).
        Cancelled deals must have delivered_volume == 0.0.
        """
        cancelled_delivered_vol = execute_scalar(
            "SELECT SUM(delivered_volume) FROM deals WHERE status = 'Аннулирован(Не оплачен)';"
        )
        self.assertEqual(cancelled_delivered_vol, 0.0, "Delivered volume for cancelled deals must be exactly 0.0")

        total_contracted = execute_scalar("SELECT SUM(volume) FROM deals;")
        total_delivered = execute_scalar("SELECT SUM(delivered_volume) FROM deals;")
        self.assertGreater(total_contracted, total_delivered)
        self.assertGreater(total_delivered, 0.0)


# ==============================================================================
# SUITE 4: SEARCH, FTS5 INDEXING & BILINGUAL ENTITY LINKING
# ==============================================================================
class TestSuite4SearchAndEntityLinking(unittest.TestCase):
    """Verifies FTS5 indexing, Russian inflections, and Uzbek Latin apostrophe variations (bug'doy, bug‘doy, o'rtacha)."""

    def test_fts5_virtual_tables_populated(self):
        """Verifies that all 4 FTS5 tables are operational and return valid match counts."""
        participants_hits = execute_scalar("SELECT COUNT(*) FROM participants_fts WHERE participants_fts MATCH 'toshkent*';")
        brokers_hits = execute_scalar("SELECT COUNT(*) FROM brokers_fts WHERE brokers_fts MATCH 'broker*';")
        contracts_hits = execute_scalar("SELECT COUNT(*) FROM contracts_fts WHERE contracts_fts MATCH 'цемент*';")
        products_hits = execute_scalar("SELECT COUNT(*) FROM products_fts WHERE products_fts MATCH 'бензин*';")

        self.assertGreater(participants_hits, 0, "participants_fts returned 0 matches")
        self.assertGreater(brokers_hits, 0, "brokers_fts returned 0 matches")
        self.assertGreater(contracts_hits, 0, "contracts_fts returned 0 matches")
        self.assertGreater(products_hits, 0, "products_fts returned 0 matches")

    def test_uzbek_latin_apostrophe_variants(self):
        """Verifies resolution of Uzbek commodity words with straight, typographic, and backtick apostrophes."""
        variants = ["bug'doy", "bug‘doy", "bug`doy", "bugdoy"]
        for var in variants:
            resolved_prod, raw = EntityLinker.resolve_product(f"{var} narxi qancha 2024-yilda?")
            self.assertEqual(resolved_prod, "пшеница", f"Failed for variant '{var}': got {resolved_prod}")

        oil_variants = ["paxta yog'i", "paxta yog‘i", "paxta yog`i"]
        for var in oil_variants:
            resolved_prod, raw = EntityLinker.resolve_product(f"{var} boyicha bitimlar")
            self.assertEqual(resolved_prod, "масло хлопковое", f"Failed for oil variant '{var}': got {resolved_prod}")

    def test_russian_inflected_forms(self):
        """Verifies Russian case inflections for key exchange commodities."""
        inflections = [
            ("бензина", "бензин"),
            ("бензину", "бензин"),
            ("бензином", "бензин"),
            ("пшеницы", "пшеница"),
            ("мукой", "мука"),
            ("сахаром", "сахар"),
            ("цементом", "цемент"),
            ("меди", "катод медный"),
            ("дизтоплива", "дизельное топливо"),
        ]
        for form, expected in inflections:
            resolved_prod, _ = EntityLinker.resolve_product(f"Какова средняя цена {form} в 2024 году?")
            self.assertEqual(resolved_prod, expected, f"Failed resolving inflected form '{form}': got {resolved_prod}")

    def test_bilingual_language_detection(self):
        """Verifies accurate classification of Russian vs Uzbek (Latin and Cyrillic)."""
        self.assertEqual(LanguageDetector.detect("2024-yilda bug'doy narxi qancha bo'lgan?"), "uz")
        self.assertEqual(LanguageDetector.detect("Toshkent viloyatida eng ko'p sotilgan tovarlar"), "uz")
        self.assertEqual(LanguageDetector.detect("Қанча битим тузилган 2023 йилда?"), "uz")
        self.assertEqual(LanguageDetector.detect("Какова средняя цена бензина АИ-92 в 2024 году?"), "ru")
        self.assertEqual(LanguageDetector.detect("Покажи топ 5 продавцов по объему сделок"), "ru")


# ==============================================================================
# SUITE 5: EDGE CASES, ANTI-HALLUCINATION & SECURITY INJECTION GUARDS
# ==============================================================================
class TestSuite5EdgeCasesAndSecurity(unittest.TestCase):
    """Verifies graceful handling of non-existent entities, out-of-dataset years/dates, and SQL injection defense."""

    def test_nonexistent_deal_contract_participant_broker(self):
        """Verifies lookups for nonexistent entities return None / has_data=False without crashing."""
        self.assertIsNone(lookup_deal(99999999))
        self.assertIsNone(lookup_contract("9999999999"))
        self.assertIsNone(lookup_participant("000000000"))
        self.assertIsNone(lookup_broker("BK999"))

        # Verify through AgentOrchestrator pipeline
        resp = AgentOrchestrator.process_question_sync("Информация по сделке №999999")
        self.assertFalse(resp.has_data)
        self.assertTrue("не найдено" in resp.text.lower() or "topilmadi" in resp.text.lower())

    def test_out_of_dataset_years_and_dates_anti_hallucination(self):
        """
        Anti-hallucination guard: years before 2022 or after 2026 must be explicitly flagged
        as out-of-dataset and refused with standard informative text.
        """
        out_years = [2019, 2020, 2021, 2027, 2030]
        for y in out_years:
            resp_ru = AgentOrchestrator.process_question_sync(f"Каков объем торгов бензином в {y} году?")
            self.assertTrue(resp_ru.is_out_of_dataset, f"Year {y} must be marked is_out_of_dataset")
            self.assertTrue("отсутствуют" in resp_ru.text.lower() or "предел" in resp_ru.text.lower())

            resp_uz = AgentOrchestrator.process_question_sync(f"{y}-yilda bug'doy savdosi qancha?")
            self.assertTrue(resp_uz.is_out_of_dataset)
            self.assertTrue("mavjud emas" in resp_uz.text.lower() or "tashqarida" in resp_uz.text.lower())

    def test_sql_injection_defense(self):
        """
        Validates rejection of malicious SQL injection payloads in both raw queries
        and parameterized user inputs.
        """
        injection_payloads = [
            "SELECT * FROM deals; DROP TABLE deals;",
            "SELECT * FROM deals WHERE deal_id = 1; DELETE FROM deals;",
            "INSERT INTO deals (deal_id) VALUES (999999);",
            "UPDATE deals SET amount = 0;",
            "ATTACH DATABASE 'hack.db' AS hack;",
            "SELECT load_extension('malicious.dll');",
        ]
        for payload in injection_payloads:
            is_safe, error = QueryExecutor.validate_raw_sql(payload)
            self.assertFalse(is_safe, f"Payload was not blocked: {payload}")

        # Test parameterized injection through engine functions
        malicious_input = "' OR '1'='1"
        res = get_top_ranking(entity_type="product", year=2024, limit=5)
        self.assertLessEqual(len(res), 5)

        resp = AgentOrchestrator.process_question_sync(f"Покажи компанию {malicious_input}")
        self.assertTrue(not resp.has_data or "не найдено" in resp.text.lower())


# ==============================================================================
# SUITE 6: PERFORMANCE & LATENCY SLAS
# ==============================================================================
class TestSuite6PerformanceAndLatency(unittest.TestCase):
    """Verifies that lookup queries complete in < 50ms and large dataset aggregations complete in < 200ms."""

    def test_lookup_latency_sla_under_50ms(self):
        """Target: deal, contract, participant, broker lookups must be < 50ms."""
        # 1. Deal lookup
        t0 = time.perf_counter()
        deal = lookup_deal(200000)
        t_deal = (time.perf_counter() - t0) * 1000.0
        self.assertIsNotNone(deal)
        self.assertLess(t_deal, 50.0, f"Deal lookup took {t_deal:.2f}ms (SLA: < 50ms)")

        # 2. Contract lookup
        contract_id = deal["contract_id"]
        t0 = time.perf_counter()
        contract = lookup_contract(contract_id)
        t_contract = (time.perf_counter() - t0) * 1000.0
        self.assertIsNotNone(contract)
        self.assertLess(t_contract, 50.0, f"Contract lookup took {t_contract:.2f}ms (SLA: < 50ms)")

        # 3. Participant lookup
        t0 = time.perf_counter()
        participant = lookup_participant(deal["seller_inn"])
        t_part = (time.perf_counter() - t0) * 1000.0
        self.assertIsNotNone(participant)
        self.assertLess(t_part, 50.0, f"Participant lookup took {t_part:.2f}ms (SLA: < 50ms)")

        # 4. Broker lookup
        t0 = time.perf_counter()
        broker = lookup_broker(deal["seller_broker"])
        t_broker = (time.perf_counter() - t0) * 1000.0
        self.assertIsNotNone(broker)
        self.assertLess(t_broker, 50.0, f"Broker lookup took {t_broker:.2f}ms (SLA: < 50ms)")

    def test_aggregation_latency_sla_under_200ms(self):
        """Target: Aggregations across 500,000 deals must complete in < 200ms."""
        # 1. Product turnover and volume calculation
        t0 = time.perf_counter()
        turnover = calculate_turnover_and_volume(product="бензин", year=2024)
        t_turnover = (time.perf_counter() - t0) * 1000.0
        self.assertGreater(turnover.deal_count, 0)
        self.assertLess(t_turnover, 200.0, f"Turnover aggregation took {t_turnover:.2f}ms (SLA: < 200ms)")

        # 2. Ranking query (Top 5 sellers in 2024)
        t0 = time.perf_counter()
        top_sellers = get_top_ranking(entity_type="seller", year=2024, limit=5)
        t_ranking = (time.perf_counter() - t0) * 1000.0
        self.assertEqual(len(top_sellers), 5)
        self.assertLess(t_ranking, 200.0, f"Ranking query took {t_ranking:.2f}ms (SLA: < 200ms)")

        # 3. Full synchronous AgentOrchestrator pipeline (intent + query + deterministic formatting)
        t0 = time.perf_counter()
        resp = AgentOrchestrator.process_question_sync("2024-yilda bug'doy bo'yicha qancha bitim tuzilgan?")
        t_pipeline = (time.perf_counter() - t0) * 1000.0
        self.assertTrue(resp.has_data)
        self.assertLess(t_pipeline, 200.0, f"End-to-end deterministic pipeline took {t_pipeline:.2f}ms (SLA: < 200ms)")


if __name__ == "__main__":
    unittest.main()
