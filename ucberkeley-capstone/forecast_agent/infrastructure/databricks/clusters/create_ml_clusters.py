#!/usr/bin/env python3
"""
Create ML forecast training and testing clusters.

This script creates two clusters:
1. **ml-testing-cluster** (i3.xlarge, 1-2 workers)
   - For running validation notebooks
   - For testing end-to-end pipeline on small date ranges
   - Low cost, quick startup

2. **ml-training-cluster** (i3.2xlarge, 2-8 workers)
   - For full cross-validation training
   - For backfilling historical forecasts
   - For production model training

Usage:
    # Create both clusters
    python forecast_agent/infrastructure/databricks/clusters/create_ml_clusters.py

    # Create only testing cluster
    python forecast_agent/infrastructure/databricks/clusters/create_ml_clusters.py --cluster testing

    # Create only training cluster
    python forecast_agent/infrastructure/databricks/clusters/create_ml_clusters.py --cluster training

Requirements:
    - DATABRICKS_HOST environment variable
    - DATABRICKS_TOKEN environment variable
    - databricks-sdk package installed
"""

import json
import time
import os
import argparse
from pathlib import Path
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.compute import (
    State, AutoScale, AwsAttributes, AwsAvailability,
    DataSecurityMode, RuntimeEngine
)


def create_cluster_from_config(w: WorkspaceClient, config_path: Path, start: bool = True):
    """
    Create a Databricks cluster from a JSON config file.

    Args:
        w: WorkspaceClient instance
        config_path: Path to cluster JSON config
        start: Whether to wait for cluster to start (default: True)

    Returns:
        cluster_id or None if failed
    """
    print(f"\nLoading cluster config from: {config_path}")

    with open(config_path) as f:
        config = json.load(f)

    cluster_name = config['cluster_name']
    print(f"Cluster name: {cluster_name}")

    # Check if cluster already exists
    existing_clusters = list(w.clusters.list())
    for cluster in existing_clusters:
        if cluster.cluster_name == cluster_name:
            print(f"\n✅ Cluster '{cluster_name}' already exists!")
            print(f"   ID: {cluster.cluster_id}")
            print(f"   State: {cluster.state}")

            if cluster.state == State.RUNNING:
                print("\n✅ Cluster is already running!")
                return cluster.cluster_id
            elif cluster.state == State.TERMINATED:
                print(f"\n⏳ Starting existing cluster...")
                w.clusters.start(cluster_id=cluster.cluster_id)
                if start:
                    wait_for_cluster(w, cluster.cluster_id, cluster_name)
                else:
                    print(f"   Cluster is starting. Check status in Databricks UI.")
                return cluster.cluster_id
            else:
                print(f"\n⏳ Cluster state: {cluster.state}")
                print(f"   Wait for it to become RUNNING, then use it.")
                return cluster.cluster_id

    # Create new cluster
    print(f"\n⏳ Creating new cluster: {cluster_name}...")

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

    if start:
        wait_for_cluster(w, cluster_id, cluster_name)

    return cluster_id


def wait_for_cluster(w: WorkspaceClient, cluster_id: str, cluster_name: str):
    """Wait for cluster to reach RUNNING state."""
    print(f"\n⏳ Waiting for cluster to start (this takes 3-5 minutes)...")

    while True:
        cluster_info = w.clusters.get(cluster_id=cluster_id)
        state = cluster_info.state

        if state == State.RUNNING:
            print(f"\n✅ Cluster '{cluster_name}' is RUNNING!")
            break
        elif state == State.ERROR or state == State.TERMINATED:
            print(f"\n❌ Cluster failed to start. State: {state}")
            if cluster_info.state_message:
                print(f"   Error: {cluster_info.state_message}")
            return None
        else:
            print(f"   Current state: {state}...")
            time.sleep(15)


def print_cluster_info(cluster_type: str, config_path: Path):
    """Print cluster configuration summary."""
    with open(config_path) as f:
        config = json.load(f)

    print(f"\n{'=' * 80}")
    print(f"{cluster_type.upper()} CLUSTER")
    print(f"{'=' * 80}")
    print(f"Name: {config['cluster_name']}")
    print(f"Node Type: {config['node_type_id']}")
    if 'autoscale' in config:
        print(f"Workers: {config['autoscale']['min_workers']}-{config['autoscale']['max_workers']} (autoscale)")
    else:
        print(f"Workers: {config.get('num_workers', 'N/A')}")
    print(f"Spark Version: {config['spark_version']}")
    print(f"Auto-termination: {config.get('autotermination_minutes', 30)} minutes")
    print(f"Purpose: {config['custom_tags'].get('Purpose', 'N/A')}")


def main():
    parser = argparse.ArgumentParser(
        description="Create ML forecast training and testing clusters"
    )
    parser.add_argument(
        '--cluster',
        type=str,
        choices=['testing', 'training', 'both'],
        default='both',
        help='Which cluster(s) to create (default: both)'
    )
    parser.add_argument(
        '--no-start',
        action='store_true',
        help='Create clusters but do not wait for them to start'
    )

    args = parser.parse_args()

    # Initialize Databricks client
    w = WorkspaceClient()

    script_dir = Path(__file__).parent

    # Cluster configs
    testing_config = script_dir / "ml_testing_cluster.json"
    training_config = script_dir / "ml_training_cluster.json"

    print("=" * 80)
    print("ML CLUSTER CREATION")
    print("=" * 80)

    # Create testing cluster
    if args.cluster in ['testing', 'both']:
        print_cluster_info("Testing", testing_config)
        testing_id = create_cluster_from_config(w, testing_config, start=not args.no_start)

    # Create training cluster
    if args.cluster in ['training', 'both']:
        print_cluster_info("Training", training_config)
        training_id = create_cluster_from_config(w, training_config, start=not args.no_start)

    # Final summary
    print("\n" + "=" * 80)
    print("✅ CLUSTER CREATION COMPLETE")
    print("=" * 80)

    if args.cluster in ['testing', 'both']:
        print(f"\n📊 Testing Cluster:")
        print(f"   Name: ml-testing-cluster")
        print(f"   Size: i3.xlarge (1-2 workers)")
        print(f"   Use for:")
        print(f"     - Running validation notebooks")
        print(f"     - Testing end-to-end pipeline")
        print(f"     - Exploratory analysis")

    if args.cluster in ['training', 'both']:
        print(f"\n🚀 Training Cluster:")
        print(f"   Name: ml-training-cluster")
        print(f"   Size: i3.2xlarge (2-8 workers)")
        print(f"   Use for:")
        print(f"     - Full CV training (5-fold across all history)")
        print(f"     - Backfilling historical forecasts")
        print(f"     - Production model training")

    print(f"\n💡 Next Steps:")
    print(f"   1. Open Databricks workspace")
    print(f"   2. Select appropriate cluster for your workload")
    print(f"   3. Run notebooks/scripts:")
    print(f"      - Testing: examples/end_to_end_example.py")
    print(f"      - Training: train.py --commodity Coffee")


if __name__ == "__main__":
    main()
