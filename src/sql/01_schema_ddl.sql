-- =============================================================================
-- PROYECTO FINAL BI: H&M Retail Analytics
-- Esquema: hm_dwh
-- Modelo: Esquema Estrella
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS hm_dwh;
SET search_path TO hm_dwh;

-- -----------------------------------------------------------------------------
-- DIMENSIONES
-- -----------------------------------------------------------------------------

CREATE TABLE dim_cliente (
    customer_sk         SERIAL PRIMARY KEY,
    customer_id_nk      VARCHAR(255) NOT NULL UNIQUE, -- Añadido UNIQUE
    age                 INT,
    generation_cohort   VARCHAR(50), 
    club_member_status  VARCHAR(50),
    fashion_news_frequency VARCHAR(50),
    postal_code         VARCHAR(255)
);

CREATE TABLE dim_articulo (
    article_sk          SERIAL PRIMARY KEY,
    article_id_nk       VARCHAR(20) NOT NULL UNIQUE, -- Añadido UNIQUE
    product_type_name   VARCHAR(100),                -- Faltaba esta columna
    product_group_name  VARCHAR(100),
    colour_group_name   VARCHAR(100),
    department_name     VARCHAR(100),
    index_name          VARCHAR(100)
);

CREATE TABLE dim_fecha (
    date_sk             INT PRIMARY KEY,       
    full_date           DATE NOT NULL,
    year                INT NOT NULL,
    month               INT NOT NULL,
    day                 INT NOT NULL,
    quarter             INT NOT NULL,
    season              VARCHAR(20)            
);

CREATE TABLE dim_canal (
    channel_sk          SERIAL PRIMARY KEY,
    sales_channel_id    INT NOT NULL UNIQUE  
);

-- -----------------------------------------------------------------------------
-- FACT
-- -----------------------------------------------------------------------------

CREATE TABLE fact_ventas (
    ventas_id           SERIAL PRIMARY KEY,
    date_sk             INT REFERENCES dim_fecha(date_sk),
    customer_sk         INT REFERENCES dim_cliente(customer_sk),
    article_sk          INT REFERENCES dim_articulo(article_sk),
    channel_sk          INT REFERENCES dim_canal(channel_sk),
    price               NUMERIC(10, 6) NOT NULL
);

-- Índices para optimizar el dashboard
CREATE INDEX idx_fact_date ON fact_ventas(date_sk);
CREATE INDEX idx_fact_customer ON fact_ventas(customer_sk);
CREATE INDEX idx_fact_article ON fact_ventas(article_sk);
