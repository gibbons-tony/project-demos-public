#!/usr/bin/env python3
"""Debug GDELT join issue in gold.unified_data."""

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
warehouses = list(w.warehouses.list())
warehouse = warehouses[0]

print("Debugging GDELT Join")
print("=" * 80)

queries = [
    # 1. Check column names in gdelt_wide
    ("GDELT column names", "DESCRIBE commodity.silver.gdelt_wide"),

    # 2. Check if stack() produces any rows
    ("GDELT stack test", """
        SELECT COUNT(*) as cnt
        FROM (
            SELECT
                article_date as date,
                commodity,
                stack(7,
                  'SUPPLY',     group_SUPPLY_count,     group_SUPPLY_tone_avg,     group_SUPPLY_tone_positive,     group_SUPPLY_tone_negative,     group_SUPPLY_tone_polarity,
                  'LOGISTICS',  group_LOGISTICS_count,  group_LOGISTICS_tone_avg,  group_LOGISTICS_tone_positive,  group_LOGISTICS_tone_negative,  group_LOGISTICS_tone_polarity,
                  'TRADE',      group_TRADE_count,      group_TRADE_tone_avg,      group_TRADE_tone_positive,      group_TRADE_tone_negative,      group_TRADE_tone_polarity,
                  'MARKET',     group_MARKET_count,     group_MARKET_tone_avg,     group_MARKET_tone_positive,     group_MARKET_tone_negative,     group_MARKET_tone_polarity,
                  'POLICY',     group_POLICY_count,     group_POLICY_tone_avg,     group_POLICY_tone_positive,     group_POLICY_tone_negative,     group_POLICY_tone_polarity,
                  'CORE',       group_CORE_count,       group_CORE_tone_avg,       group_CORE_tone_positive,       group_CORE_tone_negative,       group_CORE_tone_polarity,
                  'OTHER',      group_OTHER_count,      group_OTHER_tone_avg,      group_OTHER_tone_positive,      group_OTHER_tone_negative,      group_OTHER_tone_polarity
                ) AS (theme_group, article_count, tone_avg, tone_positive, tone_negative, tone_polarity)
            FROM commodity.silver.gdelt_wide
        )
    """),

    # 3. Check if gdelt_array produces any rows
    ("GDELT array aggregation", """
        WITH gdelt_long AS (
            SELECT
                article_date as date,
                commodity,
                stack(7,
                  'SUPPLY',     group_SUPPLY_count,     group_SUPPLY_tone_avg,     group_SUPPLY_tone_positive,     group_SUPPLY_tone_negative,     group_SUPPLY_tone_polarity,
                  'LOGISTICS',  group_LOGISTICS_count,  group_LOGISTICS_tone_avg,  group_LOGISTICS_tone_positive,  group_LOGISTICS_tone_negative,  group_LOGISTICS_tone_polarity,
                  'TRADE',      group_TRADE_count,      group_TRADE_tone_avg,      group_TRADE_tone_positive,      group_TRADE_tone_negative,      group_TRADE_tone_polarity,
                  'MARKET',     group_MARKET_count,     group_MARKET_tone_avg,     group_MARKET_tone_positive,     group_MARKET_tone_negative,     group_MARKET_tone_polarity,
                  'POLICY',     group_POLICY_count,     group_POLICY_tone_avg,     group_POLICY_tone_positive,     group_POLICY_tone_negative,     group_POLICY_tone_polarity,
                  'CORE',       group_CORE_count,       group_CORE_tone_avg,       group_CORE_tone_positive,       group_CORE_tone_negative,       group_CORE_tone_polarity,
                  'OTHER',      group_OTHER_count,      group_OTHER_tone_avg,      group_OTHER_tone_positive,      group_OTHER_tone_negative,      group_OTHER_tone_polarity
                ) AS (theme_group, article_count, tone_avg, tone_positive, tone_negative, tone_polarity)
            FROM commodity.silver.gdelt_wide
        )
        SELECT COUNT(*) as array_count
        FROM (
            SELECT
                date,
                commodity,
                collect_list(
                  struct(
                    theme_group,
                    article_count,
                    tone_avg,
                    tone_positive,
                    tone_negative,
                    tone_polarity
                  )
                ) as gdelt_themes
            FROM gdelt_long
            GROUP BY date, commodity
        )
    """),

    # 4. Sample a gdelt_array row
    ("GDELT array sample", """
        WITH gdelt_long AS (
            SELECT
                article_date as date,
                commodity,
                stack(7,
                  'SUPPLY',     group_SUPPLY_count,     group_SUPPLY_tone_avg,     group_SUPPLY_tone_positive,     group_SUPPLY_tone_negative,     group_SUPPLY_tone_polarity,
                  'LOGISTICS',  group_LOGISTICS_count,  group_LOGISTICS_tone_avg,  group_LOGISTICS_tone_positive,  group_LOGISTICS_tone_negative,  group_LOGISTICS_tone_polarity,
                  'TRADE',      group_TRADE_count,      group_TRADE_tone_avg,      group_TRADE_tone_positive,      group_TRADE_tone_negative,      group_TRADE_tone_polarity,
                  'MARKET',     group_MARKET_count,     group_MARKET_tone_avg,     group_MARKET_tone_positive,     group_MARKET_tone_negative,     group_MARKET_tone_polarity,
                  'POLICY',     group_POLICY_count,     group_POLICY_tone_avg,     group_POLICY_tone_positive,     group_POLICY_tone_negative,     group_POLICY_tone_polarity,
                  'CORE',       group_CORE_count,       group_CORE_tone_avg,       group_CORE_tone_positive,       group_CORE_tone_negative,       group_CORE_tone_polarity,
                  'OTHER',      group_OTHER_count,      group_OTHER_tone_avg,      group_OTHER_tone_positive,      group_OTHER_tone_negative,      group_OTHER_tone_polarity
                ) AS (theme_group, article_count, tone_avg, tone_positive, tone_negative, tone_polarity)
            FROM commodity.silver.gdelt_wide
        ),
        gdelt_array AS (
            SELECT
                date,
                commodity,
                collect_list(
                  struct(
                    theme_group,
                    article_count,
                    tone_avg,
                    tone_positive,
                    tone_negative,
                    tone_polarity
                  )
                ) as gdelt_themes
            FROM gdelt_long
            GROUP BY date, commodity
        )
        SELECT date, commodity, size(gdelt_themes) as theme_count
        FROM gdelt_array
        LIMIT 5
    """),
]

for description, sql_query in queries:
    print(f"\n{description}:")
    try:
        statement = w.statement_execution.execute_statement(
            warehouse_id=warehouse.id,
            statement=sql_query,
            wait_timeout="50s"
        )

        if statement.status.state.value == "SUCCEEDED":
            if statement.result and statement.result.data_array:
                results = statement.result.data_array

                if "column names" in description.lower():
                    print(f"  Columns in gdelt_wide:")
                    for row in results[:20]:  # Show first 20 columns
                        print(f"    - {row[0]}: {row[1]}")
                elif "count" in description.lower() or "cnt" in str(results[0][0]):
                    count = int(results[0][0])
                    print(f"  ✅ {count:,} rows")
                    if count == 0:
                        print(f"  ⚠️  WARNING: Stack/aggregation produced 0 rows - schema mismatch likely!")
                else:
                    print(f"  Results:")
                    for row in results:
                        print(f"    {row}")
            else:
                print(f"  ℹ️  No results")
        else:
            print(f"  ❌ Query failed: {statement.status.state}")
            if statement.status.error:
                error_msg = statement.status.error.message
                print(f"     Error: {error_msg}")
                if "cannot resolve" in error_msg.lower():
                    print(f"     🔍 Column name mismatch detected!")
    except Exception as e:
        error_str = str(e)
        print(f"  ❌ Error: {error_str}")
        if "cannot resolve" in error_str.lower():
            print(f"     🔍 Column name mismatch detected!")

print("\n" + "=" * 80)
