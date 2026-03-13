#!/bin/bash
# Automated deployment of GDELT Bronze and Silver tables to Databricks using curl

set -e

# Read Databricks configuration from ~/.databrickscfg
DATABRICKS_HOST=$(grep -A 2 "\[DEFAULT\]" ~/.databrickscfg | grep "^host" | cut -d'=' -f2 | tr -d ' ')
DATABRICKS_TOKEN=$(grep -A 2 "\[DEFAULT\]" ~/.databrickscfg | grep "^token" | cut -d'=' -f2 | tr -d ' ')

if [ -z "$DATABRICKS_HOST" ] || [ -z "$DATABRICKS_TOKEN" ]; then
    echo "Error: Could not read Databricks credentials from ~/.databrickscfg"
    exit 1
fi

echo "=========================================="
echo "Deploying GDELT Tables to Databricks"
echo "=========================================="
echo ""
echo "Host: $DATABRICKS_HOST"
echo ""

# Get first available SQL warehouse
echo "Getting SQL warehouse..."
WAREHOUSE_RESPONSE=$(curl -s -X GET \
    -H "Authorization: Bearer $DATABRICKS_TOKEN" \
    "$DATABRICKS_HOST/api/2.0/sql/warehouses")

WAREHOUSE_ID=$(echo "$WAREHOUSE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['warehouses'][0]['id'])" 2>/dev/null)

if [ -z "$WAREHOUSE_ID" ]; then
    echo "Error: Could not get warehouse ID"
    echo "Response: $WAREHOUSE_RESPONSE"
    exit 1
fi

echo "Using warehouse: $WAREHOUSE_ID"
echo ""

# Function to execute SQL and wait for completion
execute_sql() {
    local sql_file=$1
    local description=$2

    echo "$description..."

    # Read SQL file
    SQL_STATEMENT=$(cat "$sql_file")

    # Create JSON payload
    PAYLOAD=$(cat <<EOF
{
    "warehouse_id": "$WAREHOUSE_ID",
    "statement": $(echo "$SQL_STATEMENT" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read()))")
}
EOF
)

    # Execute statement
    RESPONSE=$(curl -s -X POST \
        -H "Authorization: Bearer $DATABRICKS_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" \
        "$DATABRICKS_HOST/api/2.0/sql/statements/")

    STATEMENT_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('statement_id', ''))" 2>/dev/null)

    if [ -z "$STATEMENT_ID" ]; then
        echo "Error: Failed to execute statement"
        echo "Response: $RESPONSE"
        exit 1
    fi

    # Poll for completion
    for i in {1..30}; do
        sleep 2
        STATUS_RESPONSE=$(curl -s -X GET \
            -H "Authorization: Bearer $DATABRICKS_TOKEN" \
            "$DATABRICKS_HOST/api/2.0/sql/statements/$STATEMENT_ID")

        STATE=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', {}).get('state', ''))" 2>/dev/null)

        if [ "$STATE" = "SUCCEEDED" ]; then
            echo "✓ $description completed successfully"
            return 0
        elif [ "$STATE" = "FAILED" ] || [ "$STATE" = "CANCELLED" ]; then
            echo "✗ $description failed"
            ERROR=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', {}).get('error', {}).get('message', 'Unknown error'))" 2>/dev/null)
            echo "Error: $ERROR"
            exit 1
        fi

        echo "  Status: $STATE (attempt $i/30)"
    done

    echo "Error: Timeout waiting for statement to complete"
    exit 1
}

# Execute Bronze table creation
execute_sql "gdelt_bronze_simple.sql" "Creating Bronze table"
echo ""

# Execute Silver table creation
execute_sql "gdelt_silver_simple.sql" "Creating Silver table"
echo ""

echo "=========================================="
echo "✓ Deployment Complete"
echo "=========================================="
echo ""
echo "Tables created:"
echo "  - commodity.bronze.gdelt_bronze"
echo "  - commodity.silver.gdelt_wide"
echo ""
echo "These tables now automatically read from:"
echo "  - s3://groundtruth-capstone/processed/gdelt/bronze/gdelt/"
echo "  - s3://groundtruth-capstone/processed/gdelt/silver/gdelt_wide/"
