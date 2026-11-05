import csv
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from src.config import settings
from src.db.database import create_connection, get_db_path
from src.db.schema import SCHEMA_SQL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def parse_date(date_str: Optional[str]) -> Optional[str]:
    """Converts DD.MM.YYYY to YYYY-MM-DD."""
    if not date_str or not date_str.strip():
        return None
    date_str = date_str.strip()
    try:
        parts = date_str.split(".")
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    except Exception:
        pass
    return None


def parse_number(val: Optional[str]) -> float:
    """
    Parses numeric string with spaces, non-breaking spaces (\\xa0, \\u202f, \\u2009, \\u200b),
    percent signs, and dots/commas.
    """
    if not val or not val.strip():
        return 0.0
    # Clean all Unicode whitespace variations and percent signs
    cleaned = (
        val.replace(" ", "")
        .replace("\xa0", "")
        .replace("\u00a0", "")
        .replace("\u202f", "")
        .replace("\u2009", "")
        .replace("\u200b", "")
        .replace("%", "")
        .strip()
    )
    if not cleaned:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        try:
            # Handle comma as decimal separator if present
            return float(cleaned.replace(",", "."))
        except ValueError:
            return 0.0


def parse_percent(val: Optional[str]) -> float:
    """Parses percentage string (e.g. '10 %', '5,5%')."""
    return parse_number(val)


def run_integrity_checks(conn) -> Dict[str, Any]:
    """
    Performs comprehensive database integrity and validation checks:
    1. Table row counts:
       - deals: exactly 500,000
       - contracts: exactly 6,616
       - participants: exactly 14,392
       - brokers: exactly 120
       - usd_rates: exactly 1,765
    2. Foreign key / referential integrity:
       - deals -> contracts
       - deals -> participants (seller and buyer)
       - deals -> brokers (seller and buyer)
       - deals -> usd_rates
    3. Date range boundaries:
       - 2022-01-03 to 2026-10-30
    4. FTS5 full-text search indexes sanity check.
    """
    logger.info("Running database integrity checks...")
    cursor = conn.cursor()
    report: Dict[str, Any] = {"status": "PASSED", "checks": {}}

    # 1. Row counts check
    expected_counts = {
        "deals": 500000,
        "contracts": 6616,
        "participants": 14392,
        "brokers": 120,
        "usd_rates": 1765,
    }
    row_count_results = {}
    row_count_ok = True
    for table, expected in expected_counts.items():
        cursor.execute(f"SELECT COUNT(*) FROM {table};")
        actual = cursor.fetchone()[0]
        match = (actual == expected)
        if not match:
            row_count_ok = False
        row_count_results[table] = {"expected": expected, "actual": actual, "passed": match}

    report["checks"]["row_counts"] = {"passed": row_count_ok, "details": row_count_results}

    # 2. Foreign key / referential integrity check
    fk_checks = {
        "deals_contracts": "SELECT COUNT(*) FROM deals d WHERE NOT EXISTS (SELECT 1 FROM contracts c WHERE c.contract_id = d.contract_id);",
        "deals_seller_participant": "SELECT COUNT(*) FROM deals d WHERE NOT EXISTS (SELECT 1 FROM participants p WHERE p.inn = d.seller_inn);",
        "deals_buyer_participant": "SELECT COUNT(*) FROM deals d WHERE NOT EXISTS (SELECT 1 FROM participants p WHERE p.inn = d.buyer_inn);",
        "deals_seller_broker": "SELECT COUNT(*) FROM deals d WHERE NOT EXISTS (SELECT 1 FROM brokers b WHERE b.broker_code = d.seller_broker);",
        "deals_buyer_broker": "SELECT COUNT(*) FROM deals d WHERE NOT EXISTS (SELECT 1 FROM brokers b WHERE b.broker_code = d.buyer_broker);",
        "deals_usd_rates": "SELECT COUNT(*) FROM deals d WHERE NOT EXISTS (SELECT 1 FROM usd_rates u WHERE u.rate_date = d.deal_date);",
    }
    fk_results = {}
    fk_ok = True
    for name, sql in fk_checks.items():
        cursor.execute(sql)
        orphans = cursor.fetchone()[0]
        passed = (orphans == 0)
        if not passed:
            fk_ok = False
        fk_results[name] = {"orphan_count": orphans, "passed": passed}

    report["checks"]["referential_integrity"] = {"passed": fk_ok, "details": fk_results}

    # 3. Date range boundary check
    cursor.execute("SELECT MIN(deal_date), MAX(deal_date) FROM deals;")
    min_date, max_date = cursor.fetchone()
    date_ok = (min_date == "2022-01-03" and max_date == "2026-10-30")
    report["checks"]["date_boundaries"] = {
        "passed": date_ok,
        "expected": ("2022-01-03", "2026-10-30"),
        "actual": (min_date, max_date),
    }

    # 4. FTS5 index sanity check
    fts_checks = {
        "participants_fts": "SELECT COUNT(*) FROM participants_fts WHERE participants_fts MATCH 'toshkent*';",
        "brokers_fts": "SELECT COUNT(*) FROM brokers_fts WHERE brokers_fts MATCH 'broker*';",
        "contracts_fts": "SELECT COUNT(*) FROM contracts_fts WHERE contracts_fts MATCH 'бензин*';",
        "products_fts": "SELECT COUNT(*) FROM products_fts WHERE products_fts MATCH 'бензин*';",
    }
    fts_results = {}
    fts_ok = True
    for name, sql in fts_checks.items():
        try:
            cursor.execute(sql)
            cnt = cursor.fetchone()[0]
            passed = (cnt > 0)
            if not passed:
                fts_ok = False
            fts_results[name] = {"matches": cnt, "passed": passed}
        except Exception as e:
            fts_ok = False
            fts_results[name] = {"error": str(e), "passed": False}

    report["checks"]["fts5_indexes"] = {"passed": fts_ok, "details": fts_results}

    overall_passed = row_count_ok and fk_ok and date_ok and fts_ok
    report["status"] = "PASSED" if overall_passed else "FAILED"
    logger.info(f"Integrity check completed with overall status: {report['status']}")
    return report


class DatabaseImporter:
    def __init__(self, raw_data_dir: Optional[Path] = None, db_path: Optional[Path] = None):
        self.raw_data_dir = raw_data_dir or settings.RAW_DATA_DIR
        self.db_path = db_path or get_db_path()
        self.usd_rates: Dict[str, float] = {}

    def init_schema(self, conn) -> None:
        logger.info("Initializing database schema and indexes...")
        conn.executescript(SCHEMA_SQL)
        conn.commit()

    def import_usd_rates(self, conn) -> None:
        path = self.raw_data_dir / "usd_rates.csv"
        logger.info(f"Importing USD rates from {path}...")
        rows_to_insert = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                iso_date = parse_date(row["Дата"])
                rate = float(row["Курс"])
                if iso_date:
                    self.usd_rates[iso_date] = rate
                    rows_to_insert.append((iso_date, rate))

        cursor = conn.cursor()
        cursor.executemany(
            "INSERT OR REPLACE INTO usd_rates (rate_date, rate) VALUES (?, ?);",
            rows_to_insert
        )
        conn.commit()
        logger.info(f"Imported {len(rows_to_insert)} USD rates.")

    def import_participants(self, conn) -> None:
        path = self.raw_data_dir / "participants.csv"
        logger.info(f"Importing participants from {path}...")
        rows = []
        fts_rows = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                inn = r["ИНН"].strip()
                name = r["Наименование"].strip()
                region = r["Регион"].strip()
                activity = r["Вид деятельности"].strip()
                role = r["Роль"].strip()
                is_vat = 1 if r["Плательщик НДС"].strip().lower() in ("да", "yes", "ha", "1") else 0
                rows.append((inn, name, region, activity, role, is_vat))
                fts_rows.append((inn, name, region))

        cursor = conn.cursor()
        cursor.executemany(
            "INSERT OR REPLACE INTO participants (inn, name, region, activity, role, is_vat_payer) VALUES (?, ?, ?, ?, ?, ?);",
            rows
        )
        cursor.executemany(
            "INSERT INTO participants_fts (inn, name, region) VALUES (?, ?, ?);",
            fts_rows
        )
        conn.commit()
        logger.info(f"Imported {len(rows)} participants.")

    def import_brokers(self, conn) -> None:
        path = self.raw_data_dir / "brokers.csv"
        logger.info(f"Importing brokers from {path}...")
        rows = []
        fts_rows = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                code = r["Код брокера"].strip()
                name = r["Наименование"].strip()
                inn = r["ИНН"].strip()
                region = r["Регион"].strip()
                rows.append((code, name, inn, region))
                fts_rows.append((code, name, region))

        cursor = conn.cursor()
        cursor.executemany(
            "INSERT OR REPLACE INTO brokers (broker_code, name, inn, region) VALUES (?, ?, ?, ?);",
            rows
        )
        cursor.executemany(
            "INSERT INTO brokers_fts (broker_code, name, region) VALUES (?, ?, ?);",
            fts_rows
        )
        conn.commit()
        logger.info(f"Imported {len(rows)} brokers.")

    def import_contracts(self, conn) -> None:
        path = self.raw_data_dir / "contracts.csv"
        logger.info(f"Importing contracts from {path}...")
        rows = []
        fts_rows = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                cid = r["Номер контракта"].strip()
                pname = r["Наименование продукта"].strip()
                brand = r["Марка товара"].strip()
                size = r["Размер товара"].strip()
                grade = r["Сорт товара"].strip()
                ctype = r["Тип товара"].strip()
                class_grade = r["Класс товара"].strip()
                tnved = r["Код ТН ВЭД"].strip()
                pgroup = r["Группа товара"].strip()
                pcat = r["Категория товара"].strip()
                ind = r["Отрасль промышленности"].strip()
                unit = r["Единица измерения"].strip()
                lot = parse_number(r["Лот"]) or 1.0
                curr = r["Валюта"].strip()
                base_price = parse_number(r["Базисная цена"])
                deposit = parse_percent(r["Сумма залога"])
                incoterms = r["Базис поставки"].strip()
                reg = r["Регион"].strip()
                wh = r["Адрес склада"].strip()
                auct = r["Тип торгов"].strip()
                con_type = r["Тип контракта"].strip()
                con_form = r["Форма контракта"].strip()
                pay_term = int(r["Срок оплаты"].strip()) if r["Срок оплаты"].strip().isdigit() else None
                del_term = int(r["Срок поставки"].strip()) if r["Срок поставки"].strip().isdigit() else None
                pack = r["Упаковка"].strip()
                seller_inn = r["ИНН продавца"].strip()
                reg_date = parse_date(r["Дата регистрации"])
                exp_date = parse_date(r["Действует до"])

                rows.append((
                    cid, pname, brand, size, grade, ctype, class_grade, tnved,
                    pgroup, pcat, ind, unit, lot, curr, base_price, deposit,
                    incoterms, reg, wh, auct, con_type, con_form,
                    pay_term, del_term, pack, seller_inn, reg_date, exp_date
                ))
                fts_rows.append((cid, pname, brand, pgroup, pcat, ind))

        cursor = conn.cursor()
        cursor.executemany(
            """INSERT OR REPLACE INTO contracts (
                contract_id, product_name, brand, size, grade, type, class_grade, tnved_code,
                product_group, product_category, industry, unit, lot, currency, base_price, deposit_percent,
                incoterms, region, warehouse_address, auction_type, contract_type, contract_form,
                payment_term_days, delivery_term_days, package, seller_inn, registration_date, expiration_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            rows
        )
        cursor.executemany(
            "INSERT INTO contracts_fts (contract_id, product_name, brand, product_group, product_category, industry) VALUES (?, ?, ?, ?, ?, ?);",
            fts_rows
        )
        conn.commit()
        logger.info(f"Imported {len(rows)} contracts.")

    def import_deals(self, conn) -> None:
        logger.info("Importing deals files (deals_2022.csv to deals_2026.csv)...")
        deal_files = [f"deals_{y}.csv" for y in (2022, 2023, 2024, 2025, 2026)]

        insert_sql = """INSERT INTO deals (
            deal_id, deal_date, deal_time, deal_year, deal_month, deal_day,
            auction_type, quantity, lot, volume, delivered_qty, delivered_volume,
            amount, currency, usd_rate, amount_uzs, start_price, unit_price,
            unit_price_uzs, contract_id, product_name, unit, region,
            contract_type, contract_form, status, seller_inn, buyer_inn,
            seller_broker, buyer_broker, payment_date, delivery_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"""

        total_imported = 0
        batch_size = 25000

        for fname in deal_files:
            file_path = self.raw_data_dir / fname
            if not file_path.exists():
                logger.warning(f"File {file_path} not found, skipping.")
                continue

            start_t = time.time()
            batch = []
            file_deals_count = 0

            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    deal_id = int(r["Номер сделки"])
                    deal_date = parse_date(r["Дата сделки"])
                    deal_time = r["Время сделки"].strip()
                    year, month, day = map(int, deal_date.split("-"))

                    auction_type = r["Тип торгов"].strip()
                    quantity = parse_number(r["Количество"])
                    lot = parse_number(r["Лот"]) or 1.0
                    volume = quantity * lot  # Contracted volume

                    # Physical delivered volume calculation
                    delivered_raw = r["Поставлено"].strip() if "Поставлено" in r and r["Поставлено"] else ""
                    delivered_qty = parse_number(delivered_raw) if delivered_raw else None
                    delivered_volume = (delivered_qty * lot) if delivered_qty is not None else 0.0

                    contract_type = r["Тип контракта"].strip()
                    currency = "USD" if contract_type == "Экспортный" else "UZS"

                    amount = parse_number(r["Сумма сделки"])
                    usd_rate = self.usd_rates.get(deal_date, 1.0)
                    amount_uzs = amount * usd_rate if currency == "USD" else amount

                    start_price = parse_number(r["Стартовая цена"])
                    unit_price = (amount / volume) if volume > 0 else 0.0
                    unit_price_uzs = (amount_uzs / volume) if volume > 0 else 0.0

                    contract_id = r["Номер контракта"].strip()
                    product_name = r["Наименование товара"].strip()
                    unit = r["Единица измерения"].strip()
                    region = r["Регион"].strip()
                    contract_form = r["Форма контракта"].strip()
                    status = r["Состояние сделки"].strip()

                    seller_inn = r["ИНН продавца"].strip()
                    buyer_inn = r["ИНН покупателя"].strip()
                    seller_broker = r["Брокер продавца"].strip()
                    buyer_broker = r["Брокер покупателя"].strip()

                    pay_date = parse_date(r["Дата оплаты"])
                    del_date = parse_date(r["Дата поставки"])

                    batch.append((
                        deal_id, deal_date, deal_time, year, month, day,
                        auction_type, quantity, lot, volume, delivered_qty, delivered_volume,
                        amount, currency, usd_rate, amount_uzs, start_price, unit_price,
                        unit_price_uzs, contract_id, product_name, unit, region,
                        contract_type, contract_form, status, seller_inn, buyer_inn,
                        seller_broker, buyer_broker, pay_date, del_date
                    ))

                    if len(batch) >= batch_size:
                        conn.executemany(insert_sql, batch)
                        conn.commit()
                        file_deals_count += len(batch)
                        batch = []

            if batch:
                conn.executemany(insert_sql, batch)
                conn.commit()
                file_deals_count += len(batch)

            total_imported += file_deals_count
            elapsed = time.time() - start_t
            logger.info(f"Imported {fname}: {file_deals_count} deals in {elapsed:.2f}s")

        logger.info(f"Total deals imported: {total_imported}")

    def populate_products_catalog(self, conn) -> None:
        logger.info("Populating product catalog and FTS search index...")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO products_catalog (product_name, category, product_group, industry, default_unit, total_deals)
            SELECT
                d.product_name,
                MAX(c.product_category),
                MAX(c.product_group),
                MAX(c.industry),
                MAX(d.unit),
                COUNT(d.deal_id)
            FROM deals d
            LEFT JOIN contracts c ON d.contract_id = c.contract_id
            GROUP BY d.product_name;
        """)

        cursor.execute("""
            INSERT INTO products_fts (product_name, category, product_group, industry)
            SELECT product_name, category, product_group, industry FROM products_catalog;
        """)
        conn.commit()
        logger.info("Product catalog and search index successfully populated.")

    def run(self) -> Dict[str, Any]:
        start_time = time.time()
        logger.info(f"Starting database build at {self.db_path}...")

        if self.db_path.exists():
            logger.info("Existing database found, removing for a clean rebuild...")
            self.db_path.unlink()

        conn = create_connection(self.db_path)
        try:
            conn.execute("PRAGMA synchronous = OFF;")
            conn.execute("PRAGMA journal_mode = MEMORY;")

            self.init_schema(conn)
            self.import_usd_rates(conn)
            self.import_participants(conn)
            self.import_brokers(conn)
            self.import_contracts(conn)
            self.import_deals(conn)
            self.populate_products_catalog(conn)

            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.commit()

            total_time = time.time() - start_time
            logger.info(f"Database build complete in {total_time:.2f}s!")

            # Run full integrity suite
            integrity_report = run_integrity_checks(conn)
            return integrity_report
        finally:
            conn.close()


if __name__ == "__main__":
    importer = DatabaseImporter()
    report = importer.run()
    print("Integrity Report:", report)
