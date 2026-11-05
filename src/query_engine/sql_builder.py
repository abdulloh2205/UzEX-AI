from typing import Any, List, Optional, Tuple
from src.query_engine.models import IntentType, QueryParams, StatusPolicy, VolumeType


class SQLBuilder:
    @classmethod
    def apply_status_policy(cls, policy: StatusPolicy) -> Tuple[Optional[str], List[Any]]:
        """
        Enforces explicit deal status inclusion:
        - REGISTERED: all 8 statuses
        - NON_CANCELLED: status != 'Аннулирован(Не оплачен)'
        - EXECUTED: status = 'Исполнен'
        - PARTIALLY_EXECUTED: status = 'Исполнен(Частично)'
        - CANCELLED: status = 'Аннулирован(Не оплачен)'
        """
        if policy == StatusPolicy.NON_CANCELLED:
            return "status != ?", ["Аннулирован(Не оплачен)"]
        elif policy == StatusPolicy.EXECUTED:
            return "status = ?", ["Исполнен"]
        elif policy == StatusPolicy.PARTIALLY_EXECUTED:
            return "status = ?", ["Исполнен(Частично)"]
        elif policy == StatusPolicy.CANCELLED:
            return "status = ?", ["Аннулирован(Не оплачен)"]
        elif policy == StatusPolicy.REGISTERED:
            return None, []
        return None, []

    @classmethod
    def get_volume_column(cls, volume_type: VolumeType) -> str:
        """Returns the appropriate volume column depending on contracted vs delivered volume."""
        return "delivered_volume" if volume_type == VolumeType.DELIVERED else "volume"

    @classmethod
    def build_where_clause(
        cls,
        params: QueryParams,
        prefix: str = "",
        apply_status: bool = True
    ) -> Tuple[str, List[Any]]:
        conditions: List[str] = []
        sql_params: List[Any] = []
        p = f"{prefix}." if prefix else ""

        if params.year:
            conditions.append(f"{p}deal_year = ?")
            sql_params.append(params.year)

        if params.date_from:
            conditions.append(f"{p}deal_date >= ?")
            sql_params.append(params.date_from)

        if params.date_to:
            conditions.append(f"{p}deal_date <= ?")
            sql_params.append(params.date_to)

        if params.product:
            conditions.append(f"lower({p}product_name) LIKE lower(?)")
            sql_params.append(f"%{params.product}%")

        if params.deal_status:
            conditions.append(f"{p}status = ?")
            sql_params.append(params.deal_status)
        elif apply_status and params.status_policy:
            status_clause, status_p = cls.apply_status_policy(params.status_policy)
            if status_clause:
                conditions.append(f"{p}{status_clause}")
                sql_params.extend(status_p)

        if params.contract_type:
            conditions.append(f"{p}contract_type = ?")
            sql_params.append(params.contract_type)

        if params.currency:
            conditions.append(f"{p}currency = ?")
            sql_params.append(params.currency)

        if params.inn:
            if params.role == "seller":
                conditions.append(f"{p}seller_inn = ?")
                sql_params.append(params.inn)
            elif params.role == "buyer":
                conditions.append(f"{p}buyer_inn = ?")
                sql_params.append(params.inn)
            else:
                conditions.append(f"({p}seller_inn = ? OR {p}buyer_inn = ?)")
                sql_params.extend([params.inn, params.inn])

        if params.broker_code:
            conditions.append(f"({p}seller_broker = ? OR {p}buyer_broker = ?)")
            sql_params.extend([params.broker_code, params.broker_code])

        where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        return where_sql, sql_params

    @classmethod
    def build_query(cls, params: QueryParams) -> Tuple[str, List[Any]]:
        intent = params.intent
        vol_col = cls.get_volume_column(params.volume_type)

        if intent == IntentType.DEAL_LOOKUP:
            sql = """
                SELECT
                    d.*,
                    c.product_category, c.product_group, c.industry,
                    sp.name as seller_name, sp.region as seller_region,
                    bp.name as buyer_name, bp.region as buyer_region,
                    sb.name as seller_broker_name,
                    bb.name as buyer_broker_name
                FROM deals d
                LEFT JOIN contracts c ON d.contract_id = c.contract_id
                LEFT JOIN participants sp ON d.seller_inn = sp.inn
                LEFT JOIN participants bp ON d.buyer_inn = bp.inn
                LEFT JOIN brokers sb ON d.seller_broker = sb.broker_code
                LEFT JOIN brokers bb ON d.buyer_broker = bb.broker_code
                WHERE d.deal_id = ?;
            """
            return sql, [params.deal_id]

        elif intent == IntentType.CONTRACT_LOOKUP:
            sql = f"""
                WITH deal_stats AS (
                    SELECT COUNT(*) as total_deals, COALESCE(SUM(amount_uzs), 0) as total_amount_uzs, COALESCE(SUM({vol_col}), 0) as total_volume
                    FROM deals WHERE contract_id = ?
                )
                SELECT
                    c.*,
                    p.name as seller_name, p.region as seller_region,
                    s.total_deals, s.total_amount_uzs, s.total_volume
                FROM contracts c, deal_stats s
                LEFT JOIN participants p ON c.seller_inn = p.inn
                WHERE c.contract_id = ?;
            """
            return sql, [params.contract_id, params.contract_id]

        elif intent == IntentType.PARTICIPANT_LOOKUP:
            sql = f"""
                WITH seller_stats AS (
                    SELECT COUNT(*) as deals_seller, COALESCE(SUM(amount_uzs), 0) as sales_sum, COALESCE(SUM({vol_col}), 0) as sales_vol
                    FROM deals WHERE seller_inn = ?
                ),
                buyer_stats AS (
                    SELECT COUNT(*) as deals_buyer, COALESCE(SUM(amount_uzs), 0) as purchase_sum, COALESCE(SUM({vol_col}), 0) as purchase_vol
                    FROM deals WHERE buyer_inn = ?
                )
                SELECT
                    p.*,
                    s.deals_seller as deals_as_seller,
                    b.deals_buyer as deals_as_buyer,
                    s.sales_sum as sales_sum_uzs,
                    b.purchase_sum as purchase_sum_uzs,
                    s.sales_vol as sales_volume,
                    b.purchase_vol as purchase_volume
                FROM participants p, seller_stats s, buyer_stats b
                WHERE p.inn = ?;
            """
            return sql, [params.inn, params.inn, params.inn]

        elif intent == IntentType.BROKER_LOOKUP:
            sql = f"""
                WITH seller_stats AS (
                    SELECT COUNT(*) as deals_seller, COALESCE(SUM(amount_uzs), 0) as turnover_seller, COALESCE(SUM({vol_col}), 0) as vol_seller
                    FROM deals WHERE seller_broker = ?
                ),
                buyer_stats AS (
                    SELECT COUNT(*) as deals_buyer, COALESCE(SUM(amount_uzs), 0) as turnover_buyer, COALESCE(SUM({vol_col}), 0) as vol_buyer
                    FROM deals WHERE buyer_broker = ?
                )
                SELECT
                    b.*,
                    s.deals_seller as deals_as_seller_broker,
                    bu.deals_buyer as deals_as_buyer_broker,
                    (s.deals_seller + bu.deals_buyer) as total_deals,
                    (s.turnover_seller + bu.turnover_buyer) as total_turnover_uzs,
                    (s.vol_seller + bu.vol_buyer) as total_volume
                FROM brokers b, seller_stats s, buyer_stats bu
                WHERE b.broker_code = ?;
            """
            return sql, [params.broker_code, params.broker_code, params.broker_code]

        elif intent == IntentType.USD_RATE_LOOKUP:
            if params.date_from and params.date_to and params.date_from != params.date_to:
                sql = "SELECT rate_date, rate FROM usd_rates WHERE rate_date >= ? AND rate_date <= ? ORDER BY rate_date ASC;"
                return sql, [params.date_from, params.date_to]
            target_date = params.date_from or "2026-10-30"
            sql = "SELECT rate_date, rate FROM usd_rates WHERE rate_date = ?;"
            return sql, [target_date]

        elif intent == IntentType.STATUS_BREAKDOWN:
            where_sql, sql_params = cls.build_where_clause(params, apply_status=False)
            sql = f"""
                SELECT
                    status,
                    COUNT(*) as count,
                    ROUND(SUM(amount_uzs), 2) as total_amount_uzs,
                    ROUND(SUM({vol_col}), 2) as total_volume
                FROM deals
                {where_sql}
                GROUP BY status
                ORDER BY count DESC;
            """
            return sql, sql_params

        elif intent in {IntentType.EXCHANGE_INFO, IntentType.UNKNOWN, IntentType.OUT_OF_SCOPE}:
            # Non-analytical or informational requests do not execute SQL queries
            return "", []

        elif intent == IntentType.PRICE_INQUIRY:
            where_sql, sql_params = cls.build_where_clause(params)
            sql = f"""
                SELECT
                    COUNT(*) as deal_count,
                    ROUND(SUM(amount_uzs) / NULLIF(SUM({vol_col}), 0), 2) as weighted_avg_price_uzs,
                    ROUND(AVG(unit_price_uzs), 2) as simple_avg_price_uzs,
                    ROUND(MIN(unit_price_uzs), 2) as min_price_uzs,
                    ROUND(MAX(unit_price_uzs), 2) as max_price_uzs,
                    ROUND(AVG(start_price), 2) as avg_start_price,
                    unit,
                    ROUND(SUM({vol_col}), 2) as total_volume,
                    ROUND(SUM(amount_uzs), 2) as total_amount_uzs
                FROM deals
                {where_sql}
                GROUP BY unit
                ORDER BY deal_count DESC;
            """
            return sql, sql_params

        elif intent == IntentType.RANKING:
            where_sql, sql_params = cls.build_where_clause(params, prefix="d")
            limit = params.limit or 5

            # Order column
            if params.metric == "volume":
                order_col = "total_volume"
            elif params.metric in ("count", "deals_count"):
                order_col = "deal_count"
            else:
                order_col = "total_amount_uzs"

            if params.ranking_entity == "seller":
                sql = f"""
                    SELECT
                        d.seller_inn as inn,
                        p.name as company_name,
                        p.region,
                        COUNT(*) as deal_count,
                        ROUND(SUM(d.amount_uzs), 2) as total_amount_uzs,
                        ROUND(SUM(d.{vol_col}), 2) as total_volume
                    FROM deals d
                    LEFT JOIN participants p ON d.seller_inn = p.inn
                    {where_sql}
                    GROUP BY d.seller_inn
                    ORDER BY {order_col} DESC
                    LIMIT {limit};
                """
                return sql, sql_params

            elif params.ranking_entity == "buyer":
                sql = f"""
                    SELECT
                        d.buyer_inn as inn,
                        p.name as company_name,
                        p.region,
                        COUNT(*) as deal_count,
                        ROUND(SUM(d.amount_uzs), 2) as total_amount_uzs,
                        ROUND(SUM(d.{vol_col}), 2) as total_volume
                    FROM deals d
                    LEFT JOIN participants p ON d.buyer_inn = p.inn
                    {where_sql}
                    GROUP BY d.buyer_inn
                    ORDER BY {order_col} DESC
                    LIMIT {limit};
                """
                return sql, sql_params

            elif params.ranking_entity == "broker":
                sql = f"""
                    SELECT
                        d.seller_broker as broker_code,
                        b.name as broker_name,
                        b.region,
                        COUNT(*) as deal_count,
                        ROUND(SUM(d.amount_uzs), 2) as total_amount_uzs,
                        ROUND(SUM(d.{vol_col}), 2) as total_volume
                    FROM deals d
                    LEFT JOIN brokers b ON d.seller_broker = b.broker_code
                    {where_sql}
                    GROUP BY d.seller_broker
                    ORDER BY {order_col} DESC
                    LIMIT {limit};
                """
                return sql, sql_params

            elif params.ranking_entity == "region":
                where_region, r_params = cls.build_where_clause(params)
                sql = f"""
                    SELECT
                        region,
                        COUNT(*) as deal_count,
                        ROUND(SUM(amount_uzs), 2) as total_amount_uzs,
                        ROUND(SUM({vol_col}), 2) as total_volume
                    FROM deals
                    {where_region}
                    GROUP BY region
                    ORDER BY {order_col} DESC
                    LIMIT {limit};
                """
                return sql, r_params

            else:
                # Default: product ranking
                where_prod, p_params = cls.build_where_clause(params)
                sql = f"""
                    SELECT
                        product_name,
                        unit,
                        COUNT(*) as deal_count,
                        ROUND(SUM(amount_uzs), 2) as total_amount_uzs,
                        ROUND(SUM({vol_col}), 2) as total_volume,
                        ROUND(SUM(amount_uzs) / NULLIF(SUM({vol_col}), 0), 2) as avg_price_uzs
                    FROM deals
                    {where_prod}
                    GROUP BY product_name
                    ORDER BY {order_col} DESC
                    LIMIT {limit};
                """
                return sql, p_params

        else:
            # Default: AGGREGATION
            where_sql, sql_params = cls.build_where_clause(params)
            sql = f"""
                SELECT
                    COUNT(*) as total_count,
                    ROUND(SUM({vol_col}), 2) as total_volume,
                    ROUND(SUM(amount_uzs), 2) as total_amount_uzs,
                    ROUND(SUM(CASE WHEN currency = 'USD' THEN amount ELSE 0 END), 2) as total_amount_usd,
                    MAX(unit) as unit,
                    ROUND(SUM(amount_uzs) / NULLIF(SUM({vol_col}), 0), 2) as avg_price_uzs
                FROM deals
                {where_sql};
            """
            return sql, sql_params
