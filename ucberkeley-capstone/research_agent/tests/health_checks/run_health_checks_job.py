#!/usr/bin/env python3
"""
Databricks Job Wrapper for Health Checks

Runs health checks and sends email alert on failure.

Usage in Databricks:
    1. Add as Python task to a scheduled workflow
    2. Configure job email notifications on failure
    3. Run daily at 8am

Environment variables required:
    DATABRICKS_TOKEN
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import health checks
from health_checks import main

if __name__ == "__main__":
    print("Starting daily health checks...")
    success = main()

    if not success:
        print("\n⚠️  Health checks FAILED - email alert should be triggered by Databricks job failure")
        sys.exit(1)
    else:
        print("\n✓ Health checks PASSED")
        sys.exit(0)
