import re
import time
from typing import Any, Dict, List, Optional, Tuple
from src.db.database import get_db
from src.query_engine.models import IntentType, QueryParams, QueryResult
from src.query_engine.sql_builder import SQLBuilder

# Strict read-only DDL/DML rejection blacklist
FORBIDDEN_SQL_PATTERNS = [
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|PRAGMA|REPLACE|TRUNCATE)\b",
    r"\b(EXEC|EXECUTE|SYSTEM|LOAD_EXTENSION)\b",
    r";.*\S+",  # Multi-statement injection defense
]


class QueryExecutor:
    DATASET_START_DATE = "2022-01-03"
    DATASET_END_DATE = "2026-10-30"
    DATASET_YEARS = {2022, 2023, 2024, 2025, 2026}

    @classmethod
    def check_out_of_dataset(cls, params: QueryParams) -> Optional[str]:
        """Checks if requested date or year falls outside the UZEX spot dataset bounds."""
        if params.year and params.year not in cls.DATASET_YEARS:
            if params.language == "uz":
                return f"UZEX ma'lumotlar to‘plamida {params.year}-yil ma'lumotlari mavjud emas. To‘plam faqat 2022-yil 3-yanvardan 2026-yil 30-oktabrgacha bo‘lgan davrni qamrab oladi."
            else:
                return f"В датасете UZEX отсутствуют данные за {params.year} год. Набор данных содержит сделки только с 3 января 2022 года по 30 октября 2026 года."

        if params.date_from and (params.date_from < cls.DATASET_START_DATE or params.date_from > cls.DATASET_END_DATE):
            if params.language == "uz":
                return f"Ko‘rsatilgan sana ({params.date_from}) ma'lumotlar to‘plami davridan (03.01.2022 – 30.10.2026) tashqarida."
            else:
                return f"Указанная дата ({params.date_from}) находится за пределами диапазона датасета (03.01.2022 – 30.10.2026)."

        if params.date_to and (params.date_to < cls.DATASET_START_DATE or params.date_to > cls.DATASET_END_DATE):
            if params.language == "uz":
                return f"Ko‘rsatilgan sana ({params.date_to}) ma'lumotlar to‘plami davridan (03.01.2022 – 30.10.2026) tashqarida."
            else:
                return f"Указанная дата ({params.date_to}) находится за пределами диапазона датасета (03.01.2022 – 30.10.2026)."

        return None

    @classmethod
    def validate_raw_sql(cls, sql: str) -> Tuple[bool, Optional[str]]:
        """Validates that a SQL query is read-only, safe, and single-statement."""
        cleaned = sql.strip()
        if not (cleaned.upper().startswith("SELECT") or cleaned.upper().startswith("WITH")):
            return False, "Query must start with SELECT or WITH"

        for pattern in FORBIDDEN_SQL_PATTERNS:
            if re.search(pattern, cleaned, re.IGNORECASE):
                return False, f"Forbidden SQL token detected matching pattern: {pattern}"

        return True, None

    @classmethod
    def execute_params(cls, params: QueryParams) -> QueryResult:
        """Executes a query built deterministically from QueryParams with parameter binding."""
        out_reason = cls.check_out_of_dataset(params)
        if out_reason:
            return QueryResult(
                success=True,
                has_data=False,
                is_out_of_dataset=True,
                out_of_dataset_reason=out_reason
            )

        sql, sql_params = SQLBuilder.build_query(params)
        return cls._execute_sql(sql, tuple(sql_params), params)

    @classmethod
    def execute_raw_sql(cls, sql: str, params: Optional[QueryParams] = None) -> QueryResult:
        """Executes a validated read-only SQL query."""
        is_safe, error_msg = cls.validate_raw_sql(sql)
        if not is_safe:
            return QueryResult(
                success=False,
                has_data=False,
                out_of_dataset_reason=f"Security rejection: {error_msg}"
            )

        return cls._execute_sql(sql, (), params)

    @classmethod
    def _execute_sql(
        cls,
        sql: str,
        sql_params: Tuple[Any, ...],
        params: Optional[QueryParams] = None
    ) -> QueryResult:
        start_t = time.perf_counter()

        with get_db(read_only=True) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, sql_params)
                rows = [dict(r) for r in cursor.fetchall()]
            except Exception as e:
                elapsed = (time.perf_counter() - start_t) * 1000.0
                return QueryResult(
                    success=False,
                    has_data=False,
                    sql_executed=sql,
                    execution_time_ms=elapsed,
                    out_of_dataset_reason=str(e)
                )

        elapsed = (time.perf_counter() - start_t) * 1000.0

        if not rows:
            return QueryResult(
                success=True,
                has_data=False,
                sql_executed=sql,
                execution_time_ms=elapsed,
                rows=[]
            )

        first_row = rows[0]
        has_data = True

        total_count = first_row.get("total_count", first_row.get("deal_count", len(rows)))
        if total_count == 0 and len(rows) == 1 and (
            "total_volume" in first_row or "total_amount_uzs" in first_row or "weighted_avg_price_uzs" in first_row
        ):
            has_data = False

        total_volume = first_row.get("total_volume")
        total_amount_uzs = first_row.get("total_amount_uzs")
        total_amount_usd = first_row.get("total_amount_usd")
        unit = first_row.get("unit")
        avg_price = first_row.get("weighted_avg_price_uzs") or first_row.get("avg_price_uzs")
        min_price = first_row.get("min_price_uzs")
        max_price = first_row.get("max_price_uzs")

        return QueryResult(
            success=True,
            has_data=has_data,
            total_count=total_count,
            total_volume=total_volume,
            total_amount_uzs=total_amount_uzs,
            total_amount_usd=total_amount_usd,
            unit=unit,
            avg_price=avg_price,
            min_price=min_price,
            max_price=max_price,
            rows=rows,
            sql_executed=sql,
            execution_time_ms=elapsed,
            summary_data=first_row if len(rows) == 1 else {}
        )
