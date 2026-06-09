#!/usr/bin/env python3
"""
ETL Pipeline Modular — H&M Retail Analytics

Descarga el dataset de H&M desde Kaggle, lo transforma,
y lo carga en PostgreSQL de forma idempotente.

Uso:
    python pipeline_etl.py

Prerrequisito: configurar las credenciales de Kaggle y la conexión a la base
de datos en el archivo .env.
"""

import os
import zipfile
import random
import logging
import urllib.parse
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from kaggle.api.kaggle_api_extended import KaggleApi
from sqlalchemy import create_engine, text
# ==========================================
# 0. CONFIGURACIÓN INICIAL Y LOGGING
# ==========================================
load_dotenv()

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("ETL_Master")

DATASET_NOMBRE = "derrickmwiti/hm-personalized-fashion-recommendations"
RAW_DIR = "./data/raw"
INTERIM_DIR = "./data/interim"
RUTA_ZIP = os.path.join(RAW_DIR, "hm-dataset.zip")
SCHEMA = "hm_dwh"

# ==========================================
# 1. EXTRACT (Extracción Dinámica)
# ==========================================
def get_file_path(directory, keyword):
    """Busca dinámicamente el archivo correcto (csv o parquet) ignorando submissions."""
    for f in os.listdir(directory):
        if keyword in f.lower() and (f.endswith('.csv') or f.endswith('.parquet')):
            if "sample_submission" not in f.lower():
                return os.path.join(directory, f)
    raise FileNotFoundError(f"No se encontró archivo para '{keyword}' en {directory}")

def load_dataframe(filepath):
    """Carga el DataFrame dependiendo de su extensión."""
    if filepath.endswith('.parquet'):
        return pd.read_parquet(filepath)
    return pd.read_csv(filepath)

def extract_data():
    """Descarga datos de Kaggle, descomprime y carga a memoria con muestreo."""
    logger.info("1. INICIANDO EXTRACCIÓN...")
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(INTERIM_DIR, exist_ok=True)

    # 1.1 Descarga
    if not os.path.exists(RUTA_ZIP):
        logger.info("   📥 Descargando dataset de Kaggle...")
        api = KaggleApi()
        api.authenticate()
        api.dataset_download_files(DATASET_NOMBRE, path=RAW_DIR, unzip=False)
        nombre_original = f"{DATASET_NOMBRE.split('/')[1]}.zip"
        os.rename(os.path.join(RAW_DIR, nombre_original), RUTA_ZIP)
    
    # 1.2 Descompresión
    if len(os.listdir(INTERIM_DIR)) <= 1:
        logger.info("   📦 Descomprimiendo archivos...")
        with zipfile.ZipFile(RUTA_ZIP, 'r') as zip_ref:
            zip_ref.extractall(INTERIM_DIR)

    # 1.3 Búsqueda dinámica de archivos
    logger.info("   🔍 Buscando archivos en el directorio extraído...")
    ruta_trans = get_file_path(INTERIM_DIR, "transactions")
    ruta_clientes = get_file_path(INTERIM_DIR, "customers")
    ruta_articulos = get_file_path(INTERIM_DIR, "articles")

    # 1.4 Carga en memoria y filtrado
    logger.info(f"   🧠 Cargando transacciones a memoria desde: {os.path.basename(ruta_trans)}...")
    df_trans = load_dataframe(ruta_trans)
    df_trans['t_dat'] = pd.to_datetime(df_trans['t_dat'])
    df_trans = df_trans[df_trans['t_dat'].dt.year == 2019]
    
    # 1.5 Muestreo (5% de los clientes)
    logger.info("   🎯 Aplicando muestreo del 5%...")
    clientes_unicos = df_trans['customer_id'].unique()
    random.seed(42)
    clientes_muestra = random.sample(list(clientes_unicos), int(len(clientes_unicos) * 0.05))
    df_trans = df_trans[df_trans['customer_id'].isin(clientes_muestra)]

    logger.info("   🧠 Cargando dimensiones crudas (clientes y artículos)...")
    df_clientes = load_dataframe(ruta_clientes)
    df_articulos = load_dataframe(ruta_articulos)
    
    return df_trans, df_clientes, df_articulos

# ==========================================
# 2. TRANSFORM (Transformación)
# ==========================================
def transform_dimensions(df_trans, df_clientes, df_articulos):
    """Limpia y estructura las dimensiones (sin generar SKs, eso lo hace la BD)."""
    logger.info("2. INICIANDO TRANSFORMACIÓN DE DIMENSIONES...")
    
    # --- DIM CANAL ---
    dim_canal = pd.DataFrame({'sales_channel_id': df_trans['sales_channel_id'].unique()})
    
    # --- DIM FECHA ---
    fechas_unicas = df_trans['t_dat'].dt.date.unique()
    dim_fecha = pd.DataFrame({'full_date': fechas_unicas})
    dim_fecha['full_date'] = pd.to_datetime(dim_fecha['full_date'])
    dim_fecha['date_sk'] = dim_fecha['full_date'].dt.strftime('%Y%m%d').astype(int)
    dim_fecha['year'] = dim_fecha['full_date'].dt.year
    dim_fecha['month'] = dim_fecha['full_date'].dt.month
    dim_fecha['day'] = dim_fecha['full_date'].dt.day
    dim_fecha['quarter'] = dim_fecha['full_date'].dt.quarter
    dim_fecha['season'] = np.select(
        [dim_fecha['month'].isin([3, 4, 5]), dim_fecha['month'].isin([6, 7, 8]), dim_fecha['month'].isin([9, 10, 11])],
        ['Primavera', 'Verano', 'Otoño'], default='Invierno'
    )

    # --- DIM CLIENTE ---
    dim_cliente = df_clientes[df_clientes['customer_id'].isin(df_trans['customer_id'])].copy()
    dim_cliente['age'] = dim_cliente['age'].fillna(dim_cliente['age'].median())
    dim_cliente['generation_cohort'] = np.select(
        [(dim_cliente['age'] < 25), (dim_cliente['age'] <= 40), (dim_cliente['age'] <= 59)],
        ['Gen Z', 'Millennial', 'Gen X'], default='Boomer'
    )
    dim_cliente = dim_cliente.rename(columns={'customer_id': 'customer_id_nk'})
    cols_cliente = ['customer_id_nk', 'age', 'generation_cohort', 'club_member_status', 'fashion_news_frequency', 'postal_code']
    
    # --- DIM ARTICULO ---
    dim_articulo = df_articulos[df_articulos['article_id'].isin(df_trans['article_id'])].copy()
    dim_articulo['article_id_nk'] = dim_articulo['article_id'].astype(str).str.zfill(10)
    cols_articulo = ['article_id_nk', 'product_type_name', 'product_group_name', 'colour_group_name', 'department_name', 'index_name']

    return dim_fecha, dim_canal, dim_cliente[cols_cliente], dim_articulo[cols_articulo]

def transform_facts(df_trans, conn):
    """Recupera las SKs de la BD y mapea la tabla de hechos."""
    logger.info("   🧩 Mapeando Llaves Subrogadas (SKs) para Tabla de Hechos...")
    
    db_clientes = pd.read_sql(f"SELECT customer_sk, customer_id_nk FROM {SCHEMA}.dim_cliente", conn)
    db_articulos = pd.read_sql(f"SELECT article_sk, article_id_nk FROM {SCHEMA}.dim_articulo", conn)
    db_canales = pd.read_sql(f"SELECT channel_sk, sales_channel_id FROM {SCHEMA}.dim_canal", conn)
    
    fact_ventas = df_trans.copy()
    fact_ventas['date_sk'] = fact_ventas['t_dat'].dt.strftime('%Y%m%d').astype(int)
    fact_ventas['article_id_str'] = fact_ventas['article_id'].astype(str).str.zfill(10)
    
    # Cruces (Inner Join) para obtener las llaves de la BD
    fact_ventas = fact_ventas.merge(db_clientes, left_on='customer_id', right_on='customer_id_nk', how='inner')
    fact_ventas = fact_ventas.merge(db_articulos, left_on='article_id_str', right_on='article_id_nk', how='inner')
    fact_ventas = fact_ventas.merge(db_canales, on='sales_channel_id', how='inner')
    
    return fact_ventas[['date_sk', 'customer_sk', 'article_sk', 'channel_sk', 'price']]

# ==========================================
# 3. LOAD (Carga e Idempotencia)
# ==========================================
def upsert_dimension(conn, df, table_name, nk_col, update_cols=None):
    """Carga dimensiones usando el patrón Upsert (Staging Tables)."""
    stg_table = f"stg_{table_name}"
    
    # 1. Subir a Staging (Pasamos 'conn' directamente, no 'conn.connection')
    df.to_sql(stg_table, conn, schema=SCHEMA, if_exists="replace", index=False)
    
    # 2. Query ON CONFLICT
    if update_cols:
        set_clause = ", ".join([f"{col} = EXCLUDED.{col}" for col in update_cols])
        sql = f"""
            INSERT INTO {SCHEMA}.{table_name} ({', '.join(df.columns)})
            SELECT {', '.join(df.columns)} FROM {SCHEMA}.{stg_table}
            ON CONFLICT ({nk_col}) DO UPDATE SET {set_clause};
        """
    else:
        sql = f"""
            INSERT INTO {SCHEMA}.{table_name} ({', '.join(df.columns)})
            SELECT {', '.join(df.columns)} FROM {SCHEMA}.{stg_table}
            ON CONFLICT ({nk_col}) DO NOTHING;
        """
    
    # 3. Ejecutar y limpiar
    conn.execute(text(sql))
    conn.execute(text(f"DROP TABLE IF EXISTS {SCHEMA}.{stg_table};"))
    logger.info(f"   ✅ Upsert completado en {table_name}.")

def load_facts(conn, fact_ventas):
    """Carga la tabla de hechos de manera IDEMPOTENTE (Borra antes de insertar)."""
    logger.info("3. INICIANDO CARGA DE TABLA DE HECHOS...")
    
    # IDEMPOTENCIA: Borrar los hechos de las fechas que estamos a punto de cargar
    fechas_a_cargar = fact_ventas['date_sk'].unique()
    fechas_str = ", ".join(map(str, fechas_a_cargar))
    
    logger.info("   🧹 Limpiando particiones de fechas existentes para evitar duplicados...")
    conn.execute(text(f"DELETE FROM {SCHEMA}.fact_ventas WHERE date_sk IN ({fechas_str});"))
    
    # CARGA
    logger.info(f"   💾 Insertando {len(fact_ventas):,} registros a fact_ventas...")
    fact_ventas.to_sql(
        "fact_ventas", 
        conn, 
        schema=SCHEMA, 
        if_exists="append", 
        index=False, 
        method="multi", 
        chunksize=10000
    )

# ==========================================
# 4. VALIDATE (Auditoría)
# ==========================================
def validate_post_load(conn, filas_origen):
    """Auditoría de calidad de datos y conteos finales."""
    logger.info("4. INICIANDO VALIDACIONES POST-CARGA...")
    
    # A. Validación de Conteos
    filas_destino = conn.execute(text(f"SELECT COUNT(*) FROM {SCHEMA}.fact_ventas")).scalar()
    
    if filas_destino >= filas_origen: 
        logger.info(f"   ✅ Conteo exitoso. Total en BD: {filas_destino:,} | Procesados hoy: {filas_origen:,}.")
    else:
        logger.warning(f"   ⚠️ Alerta: Hay menos datos en la BD ({filas_destino}) que en el origen procesado ({filas_origen}).")

    # B. Validación de Integridad Referencial (Huérfanos)
    huerfanos = conn.execute(text(f"""
        SELECT COUNT(*) 
        FROM {SCHEMA}.fact_ventas f
        LEFT JOIN {SCHEMA}.dim_articulo a ON f.article_sk = a.article_sk
        WHERE a.article_sk IS NULL;
    """)).scalar()
    
    if huerfanos == 0:
        logger.info("   ✅ Integridad Referencial confirmada: 0 registros huérfanos.")
    else:
        logger.error(f"   ❌ FATAL: {huerfanos} registros en fact_ventas sin artículo válido.")
        raise ValueError("Fallo de integridad referencial post-carga.")

# ==========================================
# ORQUESTADOR PRINCIPAL
# ==========================================
def main():
    try:
        logger.info("=== INICIANDO PIPELINE ETL ===")
        
        # 1. EXTRACT
        df_trans, df_clientes, df_articulos = extract_data()
        filas_origen = len(df_trans)
        
        # 2. TRANSFORM (Dimensiones)
        dim_fecha, dim_canal, dim_cliente, dim_articulo = transform_dimensions(df_trans, df_clientes, df_articulos)
        
       # CONEXIÓN (Manejo Transaccional ACID)
        
        # 1. Codificamos la contraseña por si tiene caracteres especiales
        password_seguro = urllib.parse.quote_plus(os.getenv('DB_PASS'))
        
        # 2. Armamos la URL agregando '?sslmode=require' al final
        db_url = f"postgresql+psycopg2://{os.getenv('DB_USER')}:{password_seguro}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}?sslmode=require"
        
        engine = create_engine(db_url)
        
        # Usar un bloque "begin" asegura que si algo falla, se hace ROLLBACK completo automáticamente
        with engine.begin() as conn:
            
            # 3. LOAD (Upsert Dimensiones)
            logger.info("Sincronizando Dimensiones hacia Aurora...")
            upsert_dimension(conn, dim_fecha, 'dim_fecha', 'date_sk')
            upsert_dimension(conn, dim_canal, 'dim_canal', 'sales_channel_id')
            
            cols_upd_cli = ['age', 'generation_cohort', 'club_member_status', 'fashion_news_frequency', 'postal_code']
            upsert_dimension(conn, dim_cliente, 'dim_cliente', 'customer_id_nk', update_cols=cols_upd_cli)
            
            cols_upd_art = ['product_type_name', 'product_group_name', 'colour_group_name', 'department_name', 'index_name']
            upsert_dimension(conn, dim_articulo, 'dim_articulo', 'article_id_nk', update_cols=cols_upd_art)
            
            # 4. TRANSFORM & LOAD (Hechos)
            fact_ventas = transform_facts(df_trans, conn)
            load_facts(conn, fact_ventas)
            
            # 5. VALIDACIONES
            validate_post_load(conn, filas_origen)
            
        logger.info("🏆 ¡ETL COMPLETADO EXITOSAMENTE!")
        logger.info("==============================")
        
    except Exception as e:
        logger.error(f"❌ FALLO CRÍTICO EN EL ETL. Operación cancelada. Detalle: {e}")

if __name__ == "__main__":
    main()