#!/usr/bin/env python3
"""
Create Unity Catalog-enabled cluster for SQL workloads.

This script creates a Unity Catalog cluster configured for:
- Running SQL queries on commodity.bronze/silver/gold tables
- Executing data transformation SQL scripts
- Interactive data analysis and exploration

The cluster configuration is defined in databricks_unity_catalog_cluster.json
in this directory.

Usage:
    python research_agent/infrastructure/databricks/create_unity_catalog_cluster.py

Requirements:
    - DATABRICKS_HOST environment variable
    - DATABRICKS_TOKEN environment variable
    - databricks-sdk package installed
"""

import json
import time
import os
from pathlib import Path
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.compute import (
    State, AutoScale, AwsAttributes, AwsAvailability,
    DataSecurityMode, RuntimeEngine
)

def main():
    w = WorkspaceClient()

    # Load cluster config from same directory
    script_dir = Path(__file__).parent
    config_path = script_dir / "databricks_unity_catalog_cluster.json"

    print(f"Loading cluster config from: {config_path}")

    with open(config_path) as f:
        config = json.load(f)

    cluster_name = config['cluster_name']
    print(f"\nCluster name: {cluster_name}")

    # Check if cluster already exists
    existing_clusters = list(w.clusters.list())
    for cluster in existing_clusters:
        if cluster.cluster_name == cluster_name:
            print(f"\n✅ Cluster '{cluster_name}' already exists!")
            print(f"   ID: {cluster.cluster_id}")
            print(f"   State: {cluster.state}")

            if cluster.state == State.RUNNING:
                print("\n✅ Cluster is already running!")
                print(f"\nUse this cluster in Databricks UI:")
                print(f"1. Open SQL Editor or notebook")
                print(f"2. Select cluster: '{cluster_name}'")
                print(f"3. Run your SQL queries")
                return cluster.cluster_id
            elif cluster.state == State.TERMINATED:
                print(f"\n⏳ Starting existing cluster...")
                w.clusters.start(cluster_id=cluster.cluster_id)
                print(f"   Cluster is starting. Check status in Databricks UI.")
                return cluster.cluster_id
            else:
                print(f"\n⏳ Cluster state: {cluster.state}")
                print(f"   Wait for it to become RUNNING, then use it.")
                return cluster.cluster_id

    # Create new cluster
    print(f"\n⏳ Creating new Unity Catalog cluster...")

    # Convert autoscale config to AutoScale object
    autoscale = None
    if 'autoscale' in config:
        autoscale = AutoScale(
            min_workers=config['autoscale']['min_workers'],
            max_workers=config['autoscale']['max_workers']
        )

    # Convert aws_attributes to AwsAttributes object
    aws_attrs = None
    if 'aws_attributes' in config:
        aws_config = config['aws_attributes']
        # Convert availability string to enum
        availability = None
        if 'availability' in aws_config:
            availability = AwsAvailability(aws_config['availability'])

        aws_attrs = AwsAttributes(
            availability=availability,
            zone_id=aws_config.get('zone_id'),
            first_on_demand=aws_config.get('first_on_demand'),
            spot_bid_price_percent=aws_config.get('spot_bid_price_percent')
        )

    # Convert data_security_mode to enum
    data_security_mode = DataSecurityMode(config['data_security_mode'])

    # Convert runtime_engine to enum if present
    runtime_engine = None
    if 'runtime_engine' in config:
        runtime_engine = RuntimeEngine(config['runtime_engine'])

    response = w.clusters.create(
        cluster_name=config['cluster_name'],
        spark_version=config['spark_version'],
        node_type_id=config['node_type_id'],
        driver_node_type_id=config.get('driver_node_type_id'),
        num_workers=config.get('num_workers'),
        autoscale=autoscale,
        data_security_mode=data_security_mode,
        runtime_engine=runtime_engine,
        autotermination_minutes=config.get('autotermination_minutes', 30),
        enable_elastic_disk=config.get('enable_elastic_disk', True),
        spark_conf=config.get('spark_conf', {}),
        custom_tags=config.get('custom_tags', {}),
        spark_env_vars=config.get('spark_env_vars', {}),
        aws_attributes=aws_attrs,
        init_scripts=config.get('init_scripts', [])
    )

    cluster_id = response.cluster_id
    print(f"\n✅ Cluster created successfully!")
    print(f"   ID: {cluster_id}")
    print(f"   Name: {cluster_name}")

    # Wait for cluster to start
    print(f"\n⏳ Waiting for cluster to start (this takes 3-5 minutes)...")

    while True:
        cluster_info = w.clusters.get(cluster_id=cluster_id)
        state = cluster_info.state

        if state == State.RUNNING:
            print(f"\n✅ Cluster is RUNNING!")
            break
        elif state == State.ERROR or state == State.TERMINATED:
            print(f"\n❌ Cluster failed to start. State: {state}")
            if cluster_info.state_message:
                print(f"   Error: {cluster_info.state_message}")
            return None
        else:
            print(f"   Current state: {state}...")
            time.sleep(15)

    print(f"\n{'=' * 80}")
    print(f"✅ SUCCESS! Unity Catalog cluster is ready!")
    print(f"{'=' * 80}")
    print(f"\nUse this cluster in Databricks UI:")
    print(f"1. Open SQL Editor or notebook")
    print(f"2. Select cluster: '{cluster_name}'")
    print(f"3. Run your SQL queries (e.g., create_gold_unified_data.sql)")

    return cluster_id

if __name__ == "__main__":
    main()
