#!/usr/bin/env python3
"""
List all Databricks clusters and show Unity Catalog compatibility.

This utility helps identify which clusters can be used for different workloads:
- Unity Catalog queries (requires SINGLE_USER mode + UC enabled)
- S3 ingestion (requires instance profile)
- General compute

Usage:
    python research_agent/infrastructure/databricks/list_databricks_clusters.py

Requirements:
    - DATABRICKS_HOST environment variable
    - DATABRICKS_TOKEN environment variable
    - databricks-sdk package installed
"""

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.compute import DataSecurityMode

def main():
    # Uses DATABRICKS_HOST and DATABRICKS_TOKEN from environment
    w = WorkspaceClient()

    print("Databricks Clusters")
    print("=" * 100)
    print(f"{'Name':<40} {'State':<12} {'Access Mode':<15} {'Unity Catalog':<15}")
    print("=" * 100)

    clusters = list(w.clusters.list())

    if not clusters:
        print("No clusters found!")
        return

    # Separate into running and terminated
    running_clusters = []
    terminated_clusters = []

    for cluster in clusters:
        # Check if Unity Catalog is enabled
        uc_enabled = False
        if cluster.spark_conf and 'spark.databricks.unityCatalog.enabled' in cluster.spark_conf:
            uc_enabled = cluster.spark_conf['spark.databricks.unityCatalog.enabled'] == 'true'

        # Determine access mode display
        access_mode = str(cluster.data_security_mode) if cluster.data_security_mode else "None"
        if "SINGLE_USER" in access_mode:
            access_mode = "SINGLE_USER"

        # UC status
        uc_status = "✅ ENABLED" if uc_enabled else "❌ DISABLED"

        cluster_info = {
            'name': cluster.cluster_name or "(unnamed)",
            'id': cluster.cluster_id,
            'state': str(cluster.state),
            'access_mode': access_mode,
            'uc_status': uc_status,
            'uc_enabled': uc_enabled
        }

        if "RUNNING" in cluster_info['state']:
            running_clusters.append(cluster_info)
        else:
            terminated_clusters.append(cluster_info)

    # Print running clusters first
    if running_clusters:
        print("\n🟢 RUNNING CLUSTERS:")
        for c in running_clusters:
            state = c['state'].replace('State.', '')
            print(f"{c['name']:<40} {state:<12} {c['access_mode']:<15} {c['uc_status']:<15}")

    # Print terminated clusters
    if terminated_clusters:
        print("\n🔴 TERMINATED CLUSTERS:")
        for c in terminated_clusters[:10]:  # Show only first 10 terminated
            state = c['state'].replace('State.', '')
            print(f"{c['name']:<40} {state:<12} {c['access_mode']:<15} {c['uc_status']:<15}")

        if len(terminated_clusters) > 10:
            print(f"\n... and {len(terminated_clusters) - 10} more terminated clusters")

    print("\n" + "=" * 100)
    print("\n📋 Cluster Requirements by Use Case:")
    print("  Unity Catalog queries:  Access Mode = SINGLE_USER + Unity Catalog = ✅ ENABLED")
    print("  S3 ingestion:           Access Mode = None + Instance Profile configured")
    print("  General compute:        Any cluster type")

    # Recommend unity-catalog-cluster if it exists
    unity_cluster = next((c for c in running_clusters if 'unity-catalog' in c['name'].lower()), None)
    if unity_cluster:
        print(f"\n✅ Recommended for SQL queries: '{unity_cluster['name']}' (currently running)")
    else:
        print(f"\n⚠️  No 'unity-catalog-cluster' found running.")
        print(f"   Create one with: python research_agent/infrastructure/databricks/create_unity_catalog_cluster.py")

if __name__ == "__main__":
    main()
