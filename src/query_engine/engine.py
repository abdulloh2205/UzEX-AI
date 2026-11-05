"""
Deterministic Query Engine for UZEX AI.
Provides clean Python analytical query functions for lookup, turnover, prices,
rankings, period comparisons, USD rates, and status breakdowns.
All queries strictly use parameterized SQL bindings (? placeholders).
"""

from typing import Any, Dict, List, Optional, Tuple, Union
from src.db.database import execute_query, execute_scalar
from src.query_engine.models import (
    ComparisonResult,
    IntentType,
    PriceMetrics,
    QueryParams,
    QueryResult,
    StatusPolicy,
    TurnoverResult,
    VolumeType,
)
from src.query_engine.executor import QueryExecutor


def lookup_deal(deal_id: int) -> Optional[Dict[str, Any]]:
    """Look up full deal specification, joining contracts, participants, and brokers."""
    params = QueryParams(intent=IntentType.DEAL_LOOKUP, deal_id=deal_id)
    res = QueryExecutor.execute_params(params)
    return res.rows[0] if res.rows else None


def lookup_contract(contract_id: str) -> Optional[Dict[str, Any]]:
    """Look up contract specification and aggregated deal volume/turnover."""
    params = QueryParams(intent=IntentType.CONTRACT_LOOKUP, contract_id=contract_id)
    res = QueryExecutor.execute_params(params)
    return res.rows[0] if res.rows else None


def lookup_participant(inn_or_name: str) -> Optional[Dict[str, Any]]:
    """Look up exchange participant details, sales and purchase statistics."""
    inn = inn_or_name.strip()
    if not inn.isdigit() or len(inn) != 9:
        # Search via FTS5 if name passed
        fts_rows = execute_query(
            "SELECT inn FROM participants_fts WHERE participants_fts MATCH ? LIMIT 1;",
            (f'"{inn}"',)
        )
        if not fts_rows:
            return None
        inn = fts_rows[0]["inn"]

    params = QueryParams(intent=IntentType.PARTICIPANT_LOOKUP, inn=inn)
    res = QueryExecutor.execute_params(params)
    return res.rows[0] if res.rows else None


def lookup_broker(code_or_name: str) -> Optional[Dict[str, Any]]:
    """Look up brokerage firm details and trading turnover."""
    code = code_or_name.strip().upper()
    if not code.startswith("BK"):
        # Search via FTS5 if broker name passed
        fts_rows = execute_query(
            "SELECT broker_code FROM brokers_fts WHERE brokers_fts MATCH ? LIMIT 1;",
            (f'"{code}"',)
        )
        if not fts_rows:
            return None
        code = fts_rows[0]["broker_code"]

    params = QueryParams(intent=IntentType.BROKER_LOOKUP, broker_code=code)
    res = QueryExecutor.execute_params(params)
    return res.rows[0] if res.rows else None


def lookup_product(product_name: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Look up product records in catalog using FTS5 and category filters."""
    clean_name = product_name.strip().replace("'", "").replace('"', "")
    sql = """
        SELECT c.*
        FROM products_catalog c
        JOIN products_fts f ON c.product_name = f.product_name
        WHERE products_fts MATCH ?
    """
    args = [f"{clean_name}*"]
    if category:
        sql += " AND c.category = ?"
        args.append(category)
    sql += " ORDER BY c.total_deals DESC LIMIT 20;"

    return execute_query(sql, tuple(args))


def calculate_turnover_and_volume(
    product: Optional[str] = None,
    year: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    inn: Optional[str] = None,
    broker_code: Optional[str] = None,
    status_policy: StatusPolicy = StatusPolicy.NON_CANCELLED,
    volume_type: VolumeType = VolumeType.CONTRACTED,
) -> TurnoverResult:
    """
    Calculates total turnover (UZS), volume (contracted or delivered), and deal count.
    Enforces explicit status inclusion policy (defaults to NON_CANCELLED).
    """
    params = QueryParams(
        intent=IntentType.AGGREGATION,
        product=product,
        year=year,
        date_from=date_from,
        date_to=date_to,
        inn=inn,
        broker_code=broker_code,
        status_policy=status_policy,
        volume_type=volume_type,
    )
    res = QueryExecutor.execute_params(params)
    return TurnoverResult(
        total_amount_uzs=res.total_amount_uzs or 0.0,
        total_volume=res.total_volume or 0.0,
        volume_type=volume_type,
        status_policy=status_policy,
        deal_count=res.total_count,
        avg_price_uzs=res.avg_price,
        unit=res.unit,
    )


def calculate_prices(
    product: str,
    year: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status_policy: StatusPolicy = StatusPolicy.NON_CANCELLED,
) -> PriceMetrics:
    """
    Calculates price dynamics for a product:
    Weighted average price, simple average price, min price, max price, start price.
    """
    params = QueryParams(
        intent=IntentType.PRICE_INQUIRY,
        product=product,
        year=year,
        date_from=date_from,
        date_to=date_to,
        status_policy=status_policy,
    )
    res = QueryExecutor.execute_params(params)
    data = res.summary_data or (res.rows[0] if res.rows else {})
    return PriceMetrics(
        weighted_avg_price=data.get("weighted_avg_price_uzs"),
        simple_avg_price=data.get("simple_avg_price_uzs"),
        min_price=data.get("min_price_uzs"),
        max_price=data.get("max_price_uzs"),
        avg_start_price=data.get("avg_start_price"),
        unit=data.get("unit"),
        total_volume=data.get("total_volume") or 0.0,
        total_amount_uzs=data.get("total_amount_uzs") or 0.0,
        deal_count=data.get("deal_count") or 0,
    )


def get_top_rankings(
    ranking_entity: Optional[str] = None,  # 'product', 'seller', 'buyer', 'broker', 'region'
    metric: str = "amount_uzs",  # 'amount_uzs', 'volume', 'deals_count'
    year: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 5,
    status_policy: StatusPolicy = StatusPolicy.NON_CANCELLED,
    volume_type: VolumeType = VolumeType.CONTRACTED,
    entity_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Returns top rankings for entities sorted by specified metric."""
    target_entity = ranking_entity or entity_type or "product"
    params = QueryParams(
        intent=IntentType.RANKING,
        ranking_entity=target_entity,
        metric=metric,
        year=year,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        status_policy=status_policy,
        volume_type=volume_type,
    )
    res = QueryExecutor.execute_params(params)
    return res.rows


# Aliases for convenience and QA verification compatibility
get_top_ranking = get_top_rankings
get_commodity_price_metrics = calculate_prices


def compare_periods(
    period1: Dict[str, Any],  # e.g. {'year': 2023} or {'date_from': '...', 'date_to': '...'}
    period2: Dict[str, Any],  # e.g. {'year': 2024}
    product: Optional[str] = None,
    metric: str = "amount_uzs",  # 'amount_uzs', 'volume', 'deal_count'
    status_policy: StatusPolicy = StatusPolicy.NON_CANCELLED,
    volume_type: VolumeType = VolumeType.CONTRACTED,
) -> ComparisonResult:
    """
    Compares turnover, volume, or count between two distinct timeframes.
    Returns period values, absolute difference, and percentage difference.
    """
    # Period 1
    t1 = calculate_turnover_and_volume(
        product=product,
        year=period1.get("year"),
        date_from=period1.get("date_from"),
        date_to=period1.get("date_to"),
        status_policy=status_policy,
        volume_type=volume_type,
    )
    # Period 2
    t2 = calculate_turnover_and_volume(
        product=product,
        year=period2.get("year"),
        date_from=period2.get("date_from"),
        date_to=period2.get("date_to"),
        status_policy=status_policy,
        volume_type=volume_type,
    )

    if metric == "volume":
        v1, v2 = t1.total_volume, t2.total_volume
    elif metric in ("count", "deals_count"):
        v1, v2 = float(t1.deal_count), float(t2.deal_count)
    else:
        v1, v2 = t1.total_amount_uzs, t2.total_amount_uzs

    abs_diff = round(v2 - v1, 2)
    pct_diff = round(((v2 - v1) / v1 * 100.0), 2) if v1 != 0 else None

    p1_name = str(period1.get("year") or f"{period1.get('date_from')}_{period1.get('date_to')}")
    p2_name = str(period2.get("year") or f"{period2.get('date_from')}_{period2.get('date_to')}")

    return ComparisonResult(
        period1_name=p1_name,
        period2_name=p2_name,
        metric=metric,
        period1_value=v1,
        period2_value=v2,
        absolute_change=abs_diff,
        percentage_change=pct_diff,
    )


def get_usd_rate(date_or_range: Union[str, Tuple[str, str]]) -> Any:
    """Returns USD rate on a single date or list of daily rates over a date range."""
    if isinstance(date_or_range, tuple):
        date_from, date_to = date_or_range
        params = QueryParams(intent=IntentType.USD_RATE_LOOKUP, date_from=date_from, date_to=date_to)
        res = QueryExecutor.execute_params(params)
        return res.rows
    else:
        target_date = date_or_range
        params = QueryParams(intent=IntentType.USD_RATE_LOOKUP, date_from=target_date)
        res = QueryExecutor.execute_params(params)
        return res.rows[0]["rate"] if res.rows else None


def get_status_breakdown(
    product: Optional[str] = None,
    year: Optional[int] = None,
    inn: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Returns deal counts, turnover, and volume broken down by all deal statuses."""
    params = QueryParams(
        intent=IntentType.STATUS_BREAKDOWN,
        product=product,
        year=year,
        inn=inn,
    )
    res = QueryExecutor.execute_params(params)
    return res.rows
