-- ============================================================================
-- PROYECTO FINAL BI: SCRIPT DE CONSULTAS ANALÍTICAS PURAS
-- Esquema: hm_dwh
-- Técnicas: CTEs, Window Functions, String/Date Functions, Regex
-- ============================================================================

-- Le indicamos a PostgreSQL en qué esquema buscar las tablas para evitar errores
SET search_path TO hm_dwh, public;

-- ----------------------------------------------------------------------------
-- CONSULTA 1: Crecimiento MoM (Mes a Mes) por Generación
-- Responde a: ¿Cómo se comporta la retención mensual de los clientes?
-- Técnicas: CTEs, Funciones de Fecha (DATE_TRUNC), Window Function (LAG)
-- ----------------------------------------------------------------------------
WITH VentasMensuales AS (
    SELECT 
        DATE_TRUNC('month', df.full_date) AS mes_venta,
        dc.generation_cohort,
        COUNT(DISTINCT fv.customer_sk) AS clientes_activos,
        SUM(fv.price) AS ingresos_totales
    FROM fact_ventas fv
    JOIN dim_fecha df ON fv.date_sk = df.date_sk
    JOIN dim_cliente dc ON fv.customer_sk = dc.customer_sk
    WHERE dc.generation_cohort IS NOT NULL
    GROUP BY 1, 2
)
SELECT 
    mes_venta,
    generation_cohort,
    clientes_activos,
    ingresos_totales,
    LAG(ingresos_totales) OVER (PARTITION BY generation_cohort ORDER BY mes_venta) AS ingresos_mes_anterior,
    ROUND(
        (ingresos_totales - LAG(ingresos_totales) OVER (PARTITION BY generation_cohort ORDER BY mes_venta)) / 
        NULLIF(LAG(ingresos_totales) OVER (PARTITION BY generation_cohort ORDER BY mes_venta), 0) * 100, 
    2) AS porcentaje_crecimiento
FROM VentasMensuales
ORDER BY generation_cohort, mes_venta DESC;

-- ----------------------------------------------------------------------------
-- CONSULTA 2: Atributos de Moda Rentables
-- Responde a: ¿Qué características de prendas generan más valor?
-- Técnicas: String Functions (UPPER, TRIM, INITCAP), HAVING, Aggregations
-- ----------------------------------------------------------------------------
SELECT 
    -- Limpieza de texto para estandarizar las agrupaciones y tipos de producto
    UPPER(TRIM(da.product_group_name)) AS grupo_producto,
    INITCAP(TRIM(da.product_type_name)) AS tipo_producto,
    AVG(fv.price) AS ticket_promedio,
    SUM(fv.price) AS ingresos_totales,
    COUNT(fv.ventas_id) AS volumen_transacciones
FROM fact_ventas fv
JOIN dim_articulo da ON fv.article_sk = da.article_sk
WHERE da.product_group_name IS NOT NULL
GROUP BY 1, 2
-- Filtrado post-agregación: Solo traemos combinaciones con volumen significativo (>50)
HAVING COUNT(fv.ventas_id) > 50
ORDER BY ingresos_totales DESC;

-- ----------------------------------------------------------------------------
-- CONSULTA 3: Extracción y Limpieza de Catálogo con Regex
-- Responde a: Limpieza de descripciones sucias en el DWH
-- Técnicas: REGEXP_MATCH, REGEXP_REPLACE
-- ----------------------------------------------------------------------------
SELECT 
    article_sk,
    article_id_nk,
    colour_group_name,
    department_name,
    -- Extrae únicamente la primera palabra del color (ej. "Light Pink" -> "Light")
    (REGEXP_MATCH(UPPER(colour_group_name), '^([A-Z]+)'))[1] AS tono_principal,
    -- Reemplaza cualquier carácter especial del departamento dejándolo limpio
    REGEXP_REPLACE(department_name, '[^a-zA-Z0-9\s]', '', 'g') AS departamento_limpio
FROM dim_articulo
WHERE colour_group_name IS NOT NULL
LIMIT 100;

-- ----------------------------------------------------------------------------
-- CONSULTA 4: Ranking Top 3 Tipos de Producto por Cohorte Generacional
-- Responde a: ¿Cuáles son los productos favoritos de cada generación?
-- Técnicas: CTEs en cadena, Window Function de Ranking (DENSE_RANK)
-- ----------------------------------------------------------------------------
WITH CohorteVentas AS (
    SELECT 
        dc.generation_cohort,
        UPPER(TRIM(da.product_type_name)) AS tipo_prenda,
        SUM(fv.price) AS total_vendido
    FROM fact_ventas fv
    JOIN dim_cliente dc ON fv.customer_sk = dc.customer_sk
    JOIN dim_articulo da ON fv.article_sk = da.article_sk
    WHERE dc.generation_cohort IS NOT NULL
    GROUP BY 1, 2
),
RankingProductos AS (
    SELECT 
        generation_cohort,
        tipo_prenda,
        total_vendido,
        -- Ranquea los productos del más vendido al menos vendido por cada generación
        DENSE_RANK() OVER (PARTITION BY generation_cohort ORDER BY total_vendido DESC) AS ranking_ventas
    FROM CohorteVentas
)
-- Extraemos únicamente el Top 3
SELECT * FROM RankingProductos 
WHERE ranking_ventas <= 3
ORDER BY generation_cohort, ranking_ventas;

-- ----------------------------------------------------------------------------
-- CONSULTA 5: Acumulado de Ventas YTD (Year-To-Date) por Canal
-- Responde a: ¿Cómo se acumulan los ingresos por canal a lo largo del año?
-- Técnicas: Window Function de Agregación pura (SUM OVER)
-- ----------------------------------------------------------------------------
SELECT 
    df.year AS anio,
    df.month AS mes,
    dc.generation_cohort,
    dcan.sales_channel_id,
    SUM(fv.price) AS ingresos_mes,
    -- Suma acumulada progresiva particionada por año, cohorte y canal
    SUM(SUM(fv.price)) OVER (
        PARTITION BY df.year, dc.generation_cohort, dcan.sales_channel_id 
        ORDER BY df.month
    ) AS ingresos_acumulados_ytd
FROM fact_ventas fv
JOIN dim_fecha df ON fv.date_sk = df.date_sk
JOIN dim_cliente dc ON fv.customer_sk = dc.customer_sk
JOIN dim_canal dcan ON fv.channel_sk = dcan.channel_sk
WHERE dc.generation_cohort IS NOT NULL
GROUP BY 1, 2, 3, 4
ORDER BY anio DESC, mes DESC, generation_cohort, sales_channel_id;