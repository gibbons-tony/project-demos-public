"""
List what pickle files actually exist in the trading_agent files directory
"""

import sys
import os

try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = os.getcwd()
    if 'trading_agent' not in script_dir:
        script_dir = '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/production/scripts'

trading_agent_dir = os.path.dirname(os.path.dirname(script_dir))
if trading_agent_dir not in sys.path:
    sys.path.insert(0, trading_agent_dir)

from pathlib import Path

print("=" * 80)
print("LISTING ACTUAL PICKLE FILES")
print("=" * 80)

pickle_dir = Path("/Volumes/commodity/trading_agent/files/")

print(f"\nDirectory: {pickle_dir}")
print(f"Exists: {pickle_dir.exists()}")

if pickle_dir.exists():
    all_files = sorted(list(pickle_dir.glob("*.pkl")))
    print(f"\nTotal pickle files: {len(all_files)}")

    # Show all files
    print("\n" + "=" * 80)
    print("ALL PICKLE FILES")
    print("=" * 80)
    for i, file_path in enumerate(all_files, 1):
        file_size = file_path.stat().st_size / (1024 * 1024)  # MB
        print(f"{i:3}. {file_path.name:<60} ({file_size:>8.2f} MB)")

    # Filter to detailed results
    detailed_files = [f for f in all_files if f.name.startswith("results_detailed_")]

    print("\n" + "=" * 80)
    print(f"DETAILED RESULTS FILES (results_detailed_*.pkl): {len(detailed_files)}")
    print("=" * 80)

    if detailed_files:
        for i, file_path in enumerate(detailed_files, 1):
            file_size = file_path.stat().st_size / (1024 * 1024)  # MB
            # Parse commodity and model from filename
            name = file_path.name.replace("results_detailed_", "").replace(".pkl", "")
            parts = name.split("_", 1)  # Split into commodity and rest
            if len(parts) == 2:
                commodity, model = parts
                print(f"{i:3}. {commodity:<10} {model:<30} ({file_size:>8.2f} MB)")
            else:
                print(f"{i:3}. {name:<60} ({file_size:>8.2f} MB)")
    else:
        print("\n⚠️  NO detailed results files found!")
        print("The batch_rigorous_analysis.py would have failed to load these files.")

    # Also check for other results files
    other_results = [f for f in all_files if f.name.startswith("results_") and not f.name.startswith("results_detailed_")]

    print("\n" + "=" * 80)
    print(f"OTHER RESULTS FILES: {len(other_results)}")
    print("=" * 80)

    if other_results:
        for i, file_path in enumerate(other_results, 1):
            file_size = file_path.stat().st_size / (1024 * 1024)  # MB
            print(f"{i:3}. {file_path.name:<60} ({file_size:>8.2f} MB)")

else:
    print("\n❌ ERROR: Directory does not exist!")
    print("This would explain why files can't be found.")

print("\n" + "=" * 80)
print("COMPLETE")
print("=" * 80)
