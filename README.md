# 🛍️ H&M Retail Analytics: Análisis Demográfico y de Consumo de Moda

![Power BI](https://img.shields.io/badge/PowerBI-F2C811?style=for-the-badge&logo=Power%20BI&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![AWS](https://img.shields.io/badge/AWS_Aurora-232F3E?style=for-the-badge&logo=amazon-aws&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)

## 📌 1. Resumen Ejecutivo y Problema de Negocio
Este proyecto es una solución analítica de extremo a extremo (End-to-End) basada en el dataset público de recomendaciones de moda de H&M. El objetivo principal es dotar a los equipos de marketing y compras de insights basados en datos reales sobre el comportamiento del consumidor.

**Pregunta de Negocio Core:**
> *"¿Cómo varían los patrones de consumo de moda y la retención mensual entre las distintas generaciones de clientes (Gen Z, Millennials, Gen X, Boomers), y qué atributos específicos de las prendas impulsan el mayor volumen y rentabilidad en cada segmento y canal?"*

---

## 🏗️ 2. Arquitectura de Datos e Infraestructura
Para garantizar un pipeline robusto, escalable y automatizado, la infraestructura se montó en la nube utilizando los siguientes componentes:
* **Origen de Datos:** API de Kaggle (H&M Personalized Fashion Recommendations).
* **Almacenamiento / DWH:** Base de Datos Relacional alojada en **AWS Aurora PostgreSQL**.
* **Motor ETL:** Script de Python utilizando `pandas` y `SQLAlchemy`.
* **Capa Semántica y Visualización:** Vistas analíticas nativas conectadas vía DirectQuery/Import a **Power BI**.

---

## 📊 3. Modelo Dimensional (Esquema Estrella)
Se diseñó un esquema estrella optimizado para consultas analíticas rápidas dentro del esquema `hm_dwh`.

* **`fact_ventas`**: Tabla de hechos con el grano a nivel de *transacción por artículo*. Contiene métricas como el precio y llaves foráneas.
* **`dim_cliente`**: Incluye datos demográficos y la segmentación calculada de cohortes generacionales (Gen Z, Millennials, etc.).
* **`dim_articulo`**: Catálogo enriquecido de productos (grupos, departamentos, colores).
* **`dim_fecha`**: Dimensión de tiempo para el análisis de series temporales y estacionalidad.
* **`dim_canal`**: Diferenciador de compras In-Store vs Online.

*(Puedes ver el diagrama Entidad-Relación en la carpeta `images/diagrama_modelo.png`)*.

---

## ⚙️ 4. Ingeniería de Datos (Pipeline ETL)
El proceso ETL fue programado en Python garantizando calidad y resiliencia:
* **Extracción Dinámica:** Descarga automática de archivos comprimidos desde la API de Kaggle.
* **Idempotencia Absoluta:** Uso de lógicas `UPSERT` (`ON CONFLICT`) para dimensiones y eliminación en cascada (`DELETE FROM`) para fechas específicas en la tabla de hechos antes de la inserción, evitando duplicidad sin importar cuántas veces corra el script.
* **Manejo de Transacciones (ACID):** Commit solo si todo el bloque se procesa con éxito; Rollback inmediato ante fallas.
* **Validaciones Post-Carga:** Cruces de control que garantizan cero registros huérfanos.

---

## 🧠 5. Análisis Técnico Avanzado (SQL)
Para extraer valor directo a la base de datos se utilizaron consultas de SQL Avanzado empleando las siguientes técnicas:

1. **Window Functions (`LAG`, `DENSE_RANK`, `SUM OVER`):** - Cálculo de retención y crecimiento MoM (Month-over-Month).
   - Generación del Top 3 dinámico de productos por generación.
   - Suma acumulativa progresiva YTD (Year-To-Date).
2. **Expresiones Regulares (`REGEXP_MATCH`, `REGEXP_REPLACE`):** Limpieza de descripciones caóticas del catálogo, unificando familias de colores a tonos base (BLACK, WHITE, LIGHT, DARK).
3. **CTEs (Common Table Expressions):** Encadenamiento de subconsultas lógicas para calcular el ticket promedio y volumen post-agregación (usando `HAVING`).

*(Ver el código completo en `sql/02_vistas_analiticas.sql`)*.

---

## 💡 6. Hallazgos del Negocio (Business Insights)
A partir de los datos limpios en el DWH, el análisis reveló lo siguiente:

1. **El Santo Grial de las Ventas es Universal:** Contrario a la hipótesis inicial, no hay diferencia generacional en la necesidad básica. El Top 3 de prendas es idéntico para Boomers, Gen X, Millennials y Gen Z: **Pantalones (Trousers), Vestidos (Dress) y Suéteres (Sweater)** dominan tanto el volumen (ej. >107k pantalones) como la facturación bruta.
2. **Estacionalidad Agresiva (Efecto "Back to School"):** El negocio sufre una contracción severa en agosto (caídas de hasta -33% en compras de la Gen Z), seguido de un rebote explosivo en septiembre (Gen X creció +56% MoM). Las campañas deben centrar su presupuesto en el trimestre de otoño.
3. **Canal Digital vs Físico:** El análisis YTD demostró que las ventas en la tienda en línea (Canal 2) superan aplastantemente al canal físico (Canal 1). Ejemplo: En diciembre, los Millennials generaron un acumulado de ~8.1k de forma online, frente a solo ~2.1k presencial.

---

## 📈 7. Visualización (Dashboard)
Los hallazgos anteriores fueron empaquetados en un Dashboard interactivo en Power BI diseñado para los tomadores de decisiones.

![Dashboard de H&M Analytics](images/dashboard_main.png)
*(Reemplaza la ruta de arriba con la captura de pantalla real de tu dashboard)*

**Características del Dashboard:**
* KPIs de alto nivel (Ingresos Totales, Clientes Activos, Ticket Promedio).
* Gráfico de Áreas YTD ilustrando el dominio del E-commerce.
* Treemap interactivo accionado por la limpieza Regex de colores.
* Segmentadores de Fecha y Cohorte Generacional 100% sincronizados.

---

## 🚀 8. Reproducibilidad
Para correr este proyecto localmente:

1. Clona este repositorio: `git clone https://github.com/alexagaonaa/hm-retail-analytics.git`
2. Instala las dependencias: `pip install -r requirements.txt`
3. Configura tus credenciales en un archivo `.env` (Base de datos y API de Kaggle).
4. Ejecuta el ETL: `python src/pipeline_etl.py`
5. Abre el archivo `.pbix` en Power BI Desktop o visualiza el PDF exportado en `dashboard/`.
