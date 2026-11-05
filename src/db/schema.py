"""
Database Schema Definition for UZEX AI.
Defines tables for daily USD rates, participants, brokers, contracts, deals,
catalog tables, and FTS5 full-text search indexes.
"""

SCHEMA_SQL = """
-- Daily USD exchange rates
CREATE TABLE IF NOT EXISTS usd_rates (
    rate_date TEXT PRIMARY KEY,
    rate REAL NOT NULL
);

-- Exchange participants (buyers and sellers)
CREATE TABLE IF NOT EXISTS participants (
    inn TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    region TEXT,
    activity TEXT,
    role TEXT,
    is_vat_payer INTEGER NOT NULL DEFAULT 0
);

-- Brokerage firms
CREATE TABLE IF NOT EXISTS brokers (
    broker_code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    inn TEXT,
    region TEXT
);

-- Contract specifications
CREATE TABLE IF NOT EXISTS contracts (
    contract_id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    brand TEXT,
    size TEXT,
    grade TEXT,
    type TEXT,
    class_grade TEXT,
    tnved_code TEXT,
    product_group TEXT,
    product_category TEXT,
    industry TEXT,
    unit TEXT NOT NULL,
    lot REAL NOT NULL,
    currency TEXT NOT NULL,
    base_price REAL,
    deposit_percent REAL,
    incoterms TEXT,
    region TEXT,
    warehouse_address TEXT,
    auction_type TEXT,
    contract_type TEXT,
    contract_form TEXT,
    payment_term_days INTEGER,
    delivery_term_days INTEGER,
    package TEXT,
    seller_inn TEXT,
    registration_date TEXT,
    expiration_date TEXT
);

-- Spot/Forward/Futures transactions (Deals)
-- Stores both contracted volume (volume) and actual physically delivered volume (delivered_volume)
CREATE TABLE IF NOT EXISTS deals (
    deal_id INTEGER PRIMARY KEY,
    deal_date TEXT NOT NULL,
    deal_time TEXT NOT NULL,
    deal_year INTEGER NOT NULL,
    deal_month INTEGER NOT NULL,
    deal_day INTEGER NOT NULL,
    auction_type TEXT NOT NULL,
    quantity REAL NOT NULL,
    lot REAL NOT NULL,
    volume REAL NOT NULL,
    delivered_qty REAL,
    delivered_volume REAL NOT NULL DEFAULT 0.0,
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    usd_rate REAL NOT NULL,
    amount_uzs REAL NOT NULL,
    start_price REAL NOT NULL,
    unit_price REAL NOT NULL,
    unit_price_uzs REAL NOT NULL,
    contract_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    unit TEXT NOT NULL,
    region TEXT NOT NULL,
    contract_type TEXT NOT NULL,
    contract_form TEXT NOT NULL,
    status TEXT NOT NULL,
    seller_inn TEXT NOT NULL,
    buyer_inn TEXT NOT NULL,
    seller_broker TEXT NOT NULL,
    buyer_broker TEXT NOT NULL,
    payment_date TEXT,
    delivery_date TEXT
);

-- High-performance indexes for analytical queries
CREATE INDEX IF NOT EXISTS idx_deals_date ON deals(deal_date);
CREATE INDEX IF NOT EXISTS idx_deals_year_month ON deals(deal_year, deal_month);
CREATE INDEX IF NOT EXISTS idx_deals_contract_id ON deals(contract_id);
CREATE INDEX IF NOT EXISTS idx_deals_seller_inn ON deals(seller_inn);
CREATE INDEX IF NOT EXISTS idx_deals_buyer_inn ON deals(buyer_inn);
CREATE INDEX IF NOT EXISTS idx_deals_seller_broker ON deals(seller_broker);
CREATE INDEX IF NOT EXISTS idx_deals_buyer_broker ON deals(buyer_broker);
CREATE INDEX IF NOT EXISTS idx_deals_seller_broker_cov ON deals(seller_broker, amount_uzs, volume, delivered_volume);
CREATE INDEX IF NOT EXISTS idx_deals_buyer_broker_cov ON deals(buyer_broker, amount_uzs, volume, delivered_volume);
CREATE INDEX IF NOT EXISTS idx_deals_seller_inn_cov ON deals(seller_inn, amount_uzs, volume, delivered_volume);
CREATE INDEX IF NOT EXISTS idx_deals_buyer_inn_cov ON deals(buyer_inn, amount_uzs, volume, delivered_volume);
CREATE INDEX IF NOT EXISTS idx_deals_contract_id_cov ON deals(contract_id, amount_uzs, volume, delivered_volume);
CREATE INDEX IF NOT EXISTS idx_deals_status ON deals(status);
CREATE INDEX IF NOT EXISTS idx_deals_contract_type ON deals(contract_type);
CREATE INDEX IF NOT EXISTS idx_deals_region ON deals(region);
CREATE INDEX IF NOT EXISTS idx_deals_product_name ON deals(product_name);
CREATE INDEX IF NOT EXISTS idx_deals_year_product ON deals(deal_year, product_name);
CREATE INDEX IF NOT EXISTS idx_deals_year_seller ON deals(deal_year, seller_inn);
CREATE INDEX IF NOT EXISTS idx_deals_year_buyer ON deals(deal_year, buyer_inn);
CREATE INDEX IF NOT EXISTS idx_deals_status_year ON deals(status, deal_year);
CREATE INDEX IF NOT EXISTS idx_deals_status_product ON deals(status, product_name);

CREATE INDEX IF NOT EXISTS idx_contracts_seller ON contracts(seller_inn);
CREATE INDEX IF NOT EXISTS idx_contracts_category ON contracts(product_category);
CREATE INDEX IF NOT EXISTS idx_contracts_group ON contracts(product_group);
CREATE INDEX IF NOT EXISTS idx_contracts_industry ON contracts(industry);
CREATE INDEX IF NOT EXISTS idx_contracts_product ON contracts(product_name);

-- FTS5 full-text search tables for fuzzy entity resolution
CREATE VIRTUAL TABLE IF NOT EXISTS participants_fts USING fts5(
    inn UNINDEXED,
    name,
    region,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE VIRTUAL TABLE IF NOT EXISTS brokers_fts USING fts5(
    broker_code UNINDEXED,
    name,
    region,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE VIRTUAL TABLE IF NOT EXISTS contracts_fts USING fts5(
    contract_id UNINDEXED,
    product_name,
    brand,
    product_group,
    product_category,
    industry,
    tokenize = 'unicode61 remove_diacritics 2'
);

-- Distinct product catalog table for rapid product entity matching
CREATE TABLE IF NOT EXISTS products_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT UNIQUE NOT NULL,
    category TEXT,
    product_group TEXT,
    industry TEXT,
    default_unit TEXT,
    total_deals INTEGER DEFAULT 0
);

CREATE VIRTUAL TABLE IF NOT EXISTS products_fts USING fts5(
    product_name,
    category,
    product_group,
    industry,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""
