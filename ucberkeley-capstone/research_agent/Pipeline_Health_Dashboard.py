# Databricks notebook source
# MAGIC %md
# MAGIC # Research Agent Pipeline Health Dashboard
# MAGIC
# MAGIC **Purpose**: Monitor data pipeline health, quality, and freshness
# MAGIC
# MAGIC **Features**:
# MAGIC - Data freshness monitoring (last update time)
# MAGIC - Null detection in Landing and Bronze layers
# MAGIC - Row count validation across layers
# MAGIC - Date gap detection
# MAGIC - Extensible design for adding new data sources
# MAGIC
# MAGIC **Last Updated**: 2025-11-01

# COMMAND ----------

# MAGIC %md
# MAGIC ## ⚙️ Dashboard Configuration

# COMMAND ----------

# Configuration: Add new data sources here
DATA_SOURCES = {
    'market_data': {
        'landing_table': 'commodity.landing.market_data_raw',
        'bronze_table': 'commodity.bronze.market_data',
        'silver_table': 'commodity.silver.market_data',
        'date_column': 'date',
        'key_columns': ['date', 'commodity'],
        'critical_columns': ['open', 'high', 'low', 'close', 'volume'],
        'expected_commodities': ['Coffee', 'Sugar'],
        'max_age_hours': 48  # Alert if data older than 48 hours
    },
    'weather_data': {
        'landing_table': 'commodity.landing.weather_data_raw',
        'bronze_table': 'commodity.bronze.weather_data',
        'silver_table': 'commodity.silver.weather_data',
        'date_column': 'date',
        'key_columns': ['date', 'region'],
        'critical_columns': ['temp_avg', 'humidity_avg', 'precipitation'],
        'expected_regions': 20,  # Coffee regions
        'max_age_hours': 48
    },
    'vix_data': {
        'landing_table': 'commodity.landing.vix_data_raw',
        'bronze_table': 'commodity.bronze.vix_data',
        'silver_table': 'commodity.silver.vix_data',
        'date_column': 'date',
        'key_columns': ['date'],
        'critical_columns': ['vix_close'],
        'max_age_hours': 48
    }
}

import pandas as pd
from datetime import datetime, timedelta

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1️⃣ Data Freshness Monitoring

# COMMAND ----------

# DBTITLE 1,Check Latest Data Timestamp for Each Source
def check_data_freshness(source_config, source_name):
    """
    Check when data was last updated.

    Returns:
    - Latest date in the table
    - Hours since last update
    - Status (OK/WARNING/CRITICAL)
    """
    results = []

    for layer in ['landing_table', 'bronze_table', 'silver_table']:
        if layer not in source_config:
            continue

        table = source_config[layer]
        date_col = source_config['date_column']

        try:
            query = f"""
            SELECT
                '{source_name}' as source,
                '{layer.replace('_table', '')}' as layer,
                MAX({date_col}) as latest_date,
                COUNT(*) as total_rows,
                COUNT(DISTINCT {date_col}) as distinct_dates
            FROM {table}
            """
            df = spark.sql(query).toPandas()

            if len(df) > 0 and df['latest_date'].iloc[0] is not None:
                latest_date = pd.to_datetime(df['latest_date'].iloc[0])
                hours_old = (datetime.now() - latest_date).total_seconds() / 3600

                # Determine status
                if hours_old > source_config['max_age_hours']:
                    status = '🔴 CRITICAL'
                elif hours_old > source_config['max_age_hours'] * 0.75:
                    status = '🟡 WARNING'
                else:
                    status = '🟢 OK'

                results.append({
                    'source': source_name,
                    'layer': layer.replace('_table', ''),
                    'latest_date': latest_date.strftime('%Y-%m-%d'),
                    'hours_old': round(hours_old, 1),
                    'total_rows': df['total_rows'].iloc[0],
                    'distinct_dates': df['distinct_dates'].iloc[0],
                    'status': status
                })
        except Exception as e:
            results.append({
                'source': source_name,
                'layer': layer.replace('_table', ''),
                'latest_date': 'ERROR',
                'hours_old': None,
                'total_rows': 0,
                'distinct_dates': 0,
                'status': f'❌ {str(e)[:50]}'
            })

    return pd.DataFrame(results)

# Check freshness for all sources
freshness_results = []
for source_name, config in DATA_SOURCES.items():
    freshness_results.append(check_data_freshness(config, source_name))

freshness_df = pd.concat(freshness_results, ignore_index=True)
display(freshness_df)

# COMMAND ----------

# DBTITLE 1,Visualize Data Freshness
import plotly.graph_objects as go

def plot_data_age(freshness_df):
    """
    Bar chart showing hours since last update.

    Color-coded by status.
    """
    fig = go.Figure()

    # Filter out errors
    valid_df = freshness_df[freshness_df['hours_old'].notna()]

    colors = valid_df['status'].map({
        '🟢 OK': 'green',
        '🟡 WARNING': 'orange',
        '🔴 CRITICAL': 'red'
    })

    fig.add_trace(go.Bar(
        x=[f"{row['source']}_{row['layer']}" for _, row in valid_df.iterrows()],
        y=valid_df['hours_old'],
        marker_color=colors,
        text=valid_df['status'],
        textposition='outside'
    ))

    fig.update_layout(
        title="Data Freshness (Hours Since Last Update)",
        xaxis_title="Data Source",
        yaxis_title="Hours Old",
        height=400,
        showlegend=False
    )

    fig.add_hline(y=48, line_dash="dash", line_color="red",
                  annotation_text="Max Age Threshold")

    return fig

fig = plot_data_age(freshness_df)
fig.show()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2️⃣ Null Detection & Data Quality

# COMMAND ----------

# DBTITLE 1,Detect Nulls in Critical Columns
def check_null_rates(source_config, source_name):
    """
    Calculate null percentage for critical columns.

    Identifies data quality issues.
    """
    results = []

    for layer in ['landing_table', 'bronze_table']:
        if layer not in source_config:
            continue

        table = source_config[layer]
        critical_cols = source_config.get('critical_columns', [])

        if not critical_cols:
            continue

        try:
            # Build null check query
            null_checks = ', '.join([
                f"SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as {col}_null_pct"
                for col in critical_cols
            ])

            query = f"""
            SELECT
                COUNT(*) as total_rows,
                {null_checks}
            FROM {table}
            """

            df = spark.sql(query).toPandas()

            if len(df) > 0:
                for col in critical_cols:
                    null_pct = df[f'{col}_null_pct'].iloc[0]

                    # Determine status
                    if null_pct > 10:
                        status = '🔴 HIGH'
                    elif null_pct > 1:
                        status = '🟡 MODERATE'
                    elif null_pct > 0:
                        status = '🟢 LOW'
                    else:
                        status = '✅ NONE'

                    results.append({
                        'source': source_name,
                        'layer': layer.replace('_table', ''),
                        'column': col,
                        'null_pct': round(null_pct, 2),
                        'total_rows': df['total_rows'].iloc[0],
                        'status': status
                    })
        except Exception as e:
            results.append({
                'source': source_name,
                'layer': layer.replace('_table', ''),
                'column': 'ERROR',
                'null_pct': None,
                'total_rows': 0,
                'status': f'❌ {str(e)[:30]}'
            })

    return pd.DataFrame(results)

# Check nulls for all sources
null_results = []
for source_name, config in DATA_SOURCES.items():
    null_results.append(check_null_rates(config, source_name))

null_df = pd.concat(null_results, ignore_index=True)

# Filter to show only issues
issues_df = null_df[null_df['null_pct'] > 0]
display(issues_df if len(issues_df) > 0 else null_df.head(10))

# COMMAND ----------

# DBTITLE 1,Visualize Null Rates
def plot_null_heatmap(null_df):
    """
    Heatmap of null percentages.

    Highlights problematic columns.
    """
    pivot = null_df.pivot_table(
        values='null_pct',
        index='column',
        columns=['source', 'layer'],
        aggfunc='first',
        fill_value=0
    )

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=[f"{col[0]}_{col[1]}" for col in pivot.columns],
        y=pivot.index,
        colorscale='RdYlGn_r',
        reversescale=False,
        text=pivot.values.round(2),
        texttemplate='%{text}%',
        textfont={"size": 10},
        colorbar=dict(title="Null %")
    ))

    fig.update_layout(
        title="Null Percentage Heatmap (Lower is Better)",
        xaxis_title="Data Source & Layer",
        yaxis_title="Column",
        height=400
    )

    return fig

if len(null_df) > 0:
    fig = plot_null_heatmap(null_df)
    fig.show()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3️⃣ Row Count Validation

# COMMAND ----------

# DBTITLE 1,Compare Row Counts Across Layers
def check_row_count_consistency(source_config, source_name):
    """
    Ensure row counts are consistent across layers.

    Large discrepancies indicate data loss in pipeline.
    """
    layers = ['landing_table', 'bronze_table', 'silver_table']
    counts = {}

    for layer in layers:
        if layer not in source_config:
            continue

        table = source_config[layer]

        try:
            query = f"SELECT COUNT(*) as row_count FROM {table}"
            df = spark.sql(query).toPandas()
            counts[layer.replace('_table', '')] = df['row_count'].iloc[0]
        except:
            counts[layer.replace('_table', '')] = 0

    # Calculate retention rates
    landing_count = counts.get('landing', 1)
    results = []

    for layer, count in counts.items():
        retention_pct = (count / landing_count * 100) if landing_count > 0 else 0

        results.append({
            'source': source_name,
            'layer': layer,
            'row_count': count,
            'retention_from_landing_pct': round(retention_pct, 1)
        })

    return pd.DataFrame(results)

# Check row counts for all sources
rowcount_results = []
for source_name, config in DATA_SOURCES.items():
    rowcount_results.append(check_row_count_consistency(config, source_name))

rowcount_df = pd.concat(rowcount_results, ignore_index=True)
display(rowcount_df)

# COMMAND ----------

# DBTITLE 1,Visualize Data Flow Through Pipeline
def plot_data_flow(rowcount_df):
    """
    Sankey diagram showing data flow through layers.

    Visualizes data retention/loss.
    """
    import plotly.graph_objects as go

    fig = go.Figure()

    for source in rowcount_df['source'].unique():
        source_df = rowcount_df[rowcount_df['source'] == source]

        fig.add_trace(go.Bar(
            name=source,
            x=source_df['layer'],
            y=source_df['row_count'],
            text=source_df['row_count'],
            textposition='auto'
        ))

    fig.update_layout(
        title="Data Flow Through Pipeline Layers",
        xaxis_title="Layer",
        yaxis_title="Row Count",
        barmode='group',
        height=400
    )

    return fig

fig = plot_data_flow(rowcount_df)
fig.show()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4️⃣ Date Gap Detection

# COMMAND ----------

# DBTITLE 1,Identify Missing Dates
def detect_date_gaps(source_config, source_name, max_gap_days=7):
    """
    Find gaps in date sequences.

    Indicates missing data loads.
    """
    if 'silver_table' not in source_config:
        return pd.DataFrame()

    table = source_config['silver_table']
    date_col = source_config['date_column']

    try:
        query = f"""
        WITH dates AS (
          SELECT DISTINCT {date_col} as date
          FROM {table}
          ORDER BY {date_col}
        ),
        lagged AS (
          SELECT
            date,
            LAG(date) OVER (ORDER BY date) as prev_date,
            DATEDIFF(date, LAG(date) OVER (ORDER BY date)) as gap_days
          FROM dates
        )
        SELECT
            '{source_name}' as source,
            prev_date,
            date as next_date,
            gap_days
        FROM lagged
        WHERE gap_days > {max_gap_days}
        ORDER BY date DESC
        LIMIT 20
        """

        df = spark.sql(query).toPandas()
        return df

    except Exception as e:
        return pd.DataFrame([{
            'source': source_name,
            'prev_date': 'ERROR',
            'next_date': str(e)[:50],
            'gap_days': None
        }])

# Detect gaps for all sources
gap_results = []
for source_name, config in DATA_SOURCES.items():
    gap_results.append(detect_date_gaps(config, source_name))

gaps_df = pd.concat(gap_results, ignore_index=True)

if len(gaps_df) > 0:
    display(gaps_df)
else:
    print("✅ No date gaps detected!")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5️⃣ Coverage Validation

# COMMAND ----------

# DBTITLE 1,Check Entity Coverage (Commodities, Regions, etc.)
def check_entity_coverage(source_config, source_name):
    """
    Validate expected entities are present.

    Example: Ensure all commodities/regions have data.
    """
    results = []

    if 'expected_commodities' in source_config:
        table = source_config.get('silver_table', source_config.get('bronze_table'))
        if not table:
            return pd.DataFrame()

        try:
            query = f"""
            SELECT
                commodity,
                COUNT(*) as row_count,
                MAX({source_config['date_column']}) as latest_date
            FROM {table}
            GROUP BY commodity
            """
            df = spark.sql(query).toPandas()

            expected = set(source_config['expected_commodities'])
            actual = set(df['commodity'].tolist())
            missing = expected - actual

            for commodity in expected:
                if commodity in actual:
                    commodity_data = df[df['commodity'] == commodity].iloc[0]
                    results.append({
                        'source': source_name,
                        'entity_type': 'commodity',
                        'entity': commodity,
                        'row_count': commodity_data['row_count'],
                        'latest_date': commodity_data['latest_date'],
                        'status': '✅ PRESENT'
                    })
                else:
                    results.append({
                        'source': source_name,
                        'entity_type': 'commodity',
                        'entity': commodity,
                        'row_count': 0,
                        'latest_date': None,
                        'status': '❌ MISSING'
                    })

        except Exception as e:
            results.append({
                'source': source_name,
                'entity_type': 'commodity',
                'entity': 'ERROR',
                'row_count': 0,
                'latest_date': None,
                'status': str(e)[:50]
            })

    return pd.DataFrame(results)

# Check coverage for all sources
coverage_results = []
for source_name, config in DATA_SOURCES.items():
    coverage_results.append(check_entity_coverage(config, source_name))

coverage_df = pd.concat(coverage_results, ignore_index=True)

if len(coverage_df) > 0:
    display(coverage_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6️⃣ Overall Health Summary

# COMMAND ----------

# DBTITLE 1,Generate Pipeline Health Score
def calculate_health_score():
    """
    Aggregate health score (0-100).

    Criteria:
    - Data freshness: 40 points
    - Null rates: 30 points
    - Row count consistency: 20 points
    - Entity coverage: 10 points
    """
    scores = {}

    # Freshness score (40 points)
    freshness_ok = len(freshness_df[freshness_df['status'] == '🟢 OK'])
    freshness_total = len(freshness_df[freshness_df['hours_old'].notna()])
    freshness_score = (freshness_ok / freshness_total * 40) if freshness_total > 0 else 0

    # Null score (30 points) - inverse of null rate
    avg_null_pct = null_df['null_pct'].mean() if len(null_df) > 0 else 0
    null_score = max(0, 30 * (1 - avg_null_pct / 100))

    # Retention score (20 points)
    silver_retention = rowcount_df[rowcount_df['layer'] == 'silver']['retention_from_landing_pct'].mean()
    retention_score = (silver_retention / 100 * 20) if silver_retention > 0 else 0

    # Coverage score (10 points)
    coverage_ok = len(coverage_df[coverage_df['status'] == '✅ PRESENT']) if len(coverage_df) > 0 else 0
    coverage_total = len(coverage_df) if len(coverage_df) > 0 else 1
    coverage_score = (coverage_ok / coverage_total * 10)

    total_score = freshness_score + null_score + retention_score + coverage_score

    return {
        'total_score': round(total_score, 1),
        'freshness_score': round(freshness_score, 1),
        'null_score': round(null_score, 1),
        'retention_score': round(retention_score, 1),
        'coverage_score': round(coverage_score, 1)
    }

health_score = calculate_health_score()

print("="*60)
print(f"PIPELINE HEALTH SCORE: {health_score['total_score']}/100")
print("="*60)
print(f"  Data Freshness:    {health_score['freshness_score']}/40")
print(f"  Data Quality (Nulls): {health_score['null_score']}/30")
print(f"  Data Retention:    {health_score['retention_score']}/20")
print(f"  Entity Coverage:   {health_score['coverage_score']}/10")
print("="*60)

if health_score['total_score'] >= 90:
    print("✅ EXCELLENT - Pipeline healthy")
elif health_score['total_score'] >= 75:
    print("🟡 GOOD - Minor issues detected")
elif health_score['total_score'] >= 50:
    print("🟠 WARNING - Multiple issues need attention")
else:
    print("🔴 CRITICAL - Urgent action required")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🔄 Adding New Data Sources
# MAGIC
# MAGIC **To add a new data source:**
# MAGIC 1. Add entry to `DATA_SOURCES` dict in Config cell with:
# MAGIC    - `landing_table`, `bronze_table`, `silver_table`
# MAGIC    - `date_column`, `key_columns`, `critical_columns`
# MAGIC    - `max_age_hours`, any entity expectations
# MAGIC 2. Re-run all cells
# MAGIC
# MAGIC **To add new checks:**
# MAGIC - Create new function following existing patterns
# MAGIC - Add to health score calculation
# MAGIC
# MAGIC All visualizations will automatically update!
# MAGIC
# MAGIC **Scheduling Recommendations:**
# MAGIC - Run daily at 3 AM UTC (after Lambda runs)
# MAGIC - Alert on health_score < 75
# MAGIC - Alert on any 🔴 CRITICAL statuses
