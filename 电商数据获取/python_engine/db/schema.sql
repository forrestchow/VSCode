-- ============================================================
-- 电商数据获取 — 数据库表结构
-- 复用电商BI分析的星型模型，直接用于 PostgreSQL
-- ============================================================

-- 1. 日期维度表
CREATE TABLE IF NOT EXISTS dim_date (
    date_id       DATE PRIMARY KEY,
    year          SMALLINT NOT NULL,
    quarter       SMALLINT NOT NULL,
    month         SMALLINT NOT NULL,
    month_name    VARCHAR(10) NOT NULL,
    week_of_year  SMALLINT NOT NULL,
    day_of_week   SMALLINT NOT NULL,
    day_name      VARCHAR(10) NOT NULL,
    is_weekend    BOOLEAN NOT NULL DEFAULT FALSE,
    yyyymm        CHAR(6) NOT NULL,
    yyyyqw        CHAR(7) NOT NULL
);

-- 2. 产品维度表
CREATE TABLE IF NOT EXISTS dim_product (
    product_id    VARCHAR(50) PRIMARY KEY,
    product_name  VARCHAR(200) NOT NULL,
    short_name    VARCHAR(100),
    category      VARCHAR(50),
    sub_category  VARCHAR(50),
    brand         VARCHAR(50),
    platform      VARCHAR(20) NOT NULL,
    our_sku       VARCHAR(50),
    unit_cost     DECIMAL(10,2),
    created_date  DATE DEFAULT CURRENT_DATE,
    is_active     BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_product_platform ON dim_product(platform);
CREATE INDEX IF NOT EXISTS idx_product_sku ON dim_product(our_sku);
CREATE INDEX IF NOT EXISTS idx_product_category ON dim_product(category);

-- 3. 店铺维度表
CREATE TABLE IF NOT EXISTS dim_shop (
    shop_id       VARCHAR(50) PRIMARY KEY,
    shop_name     VARCHAR(100) NOT NULL,
    short_name    VARCHAR(50),
    platform      VARCHAR(20) NOT NULL,
    shop_type     VARCHAR(20),
    created_date  DATE DEFAULT CURRENT_DATE,
    is_active     BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_shop_platform ON dim_shop(platform);

-- 4. 销售事实表（核心）
CREATE TABLE IF NOT EXISTS fact_sales (
    date_id         DATE NOT NULL REFERENCES dim_date(date_id),
    product_id      VARCHAR(50) NOT NULL REFERENCES dim_product(product_id),
    shop_id         VARCHAR(50) NOT NULL REFERENCES dim_shop(shop_id),

    sales_amount    DECIMAL(12,2) NOT NULL DEFAULT 0,
    sales_volume    INT NOT NULL DEFAULT 0,
    order_count     INT NOT NULL DEFAULT 0,
    buyer_count     INT NOT NULL DEFAULT 0,

    avg_price       DECIMAL(10,2) NOT NULL DEFAULT 0,
    unit_price      DECIMAL(10,2) NOT NULL DEFAULT 0,

    refund_amount   DECIMAL(12,2) NOT NULL DEFAULT 0,
    refund_count    INT NOT NULL DEFAULT 0,

    data_source     VARCHAR(50),
    imported_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (date_id, product_id, shop_id)
);

CREATE INDEX IF NOT EXISTS idx_sales_date ON fact_sales(date_id);
CREATE INDEX IF NOT EXISTS idx_sales_product ON fact_sales(product_id);
CREATE INDEX IF NOT EXISTS idx_sales_shop ON fact_sales(shop_id);

-- 5. 流量事实表
CREATE TABLE IF NOT EXISTS fact_traffic (
    date_id         DATE NOT NULL REFERENCES dim_date(date_id),
    product_id      VARCHAR(50) NOT NULL REFERENCES dim_product(product_id),
    shop_id         VARCHAR(50) NOT NULL REFERENCES dim_shop(shop_id),

    impressions     INT NOT NULL DEFAULT 0,
    clicks          INT NOT NULL DEFAULT 0,
    visitors        INT NOT NULL DEFAULT 0,

    ctr             DECIMAL(6,4) DEFAULT 0,
    cvr             DECIMAL(6,4) DEFAULT 0,

    cost            DECIMAL(12,2) DEFAULT 0,
    cpc             DECIMAL(10,4) DEFAULT 0,
    cpm             DECIMAL(10,4) DEFAULT 0,

    data_source     VARCHAR(50),
    imported_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (date_id, product_id, shop_id)
);

CREATE INDEX IF NOT EXISTS idx_traffic_date ON fact_traffic(date_id);
CREATE INDEX IF NOT EXISTS idx_traffic_product ON fact_traffic(product_id);
