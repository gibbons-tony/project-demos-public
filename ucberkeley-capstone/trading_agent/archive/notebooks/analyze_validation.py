#!/usr/bin/env python3
"""
Analyze validation_results_full.pkl - extract key metrics without loading full DataFrames
"""
import pickle
import io

class DataFrameStubber:
    """Stub to replace pandas DataFrames during unpickling"""
    def __init__(self, *args, **kwargs):
        pass

# Stub out pandas imports that cause issues
import sys
class StubModule:
    def __getattr__(self, name):
        return DataFrameStubber

sys.modules['pandas.core.indexes.numeric'] = StubModule()

# Now load the pickle
with open('validation_results_full.pkl', 'rb') as f:
    data = pickle.load(f)

print("="*80)
print("V6 VALIDATION RESULTS ANALYSIS")
print("="*80)

print(f"\nGeneration: {data['generation_timestamp']}")
print(f"Config: {data['config']}")

print(f"\n{'='*80}")
print("100% ACCURATE SCENARIO - CRITICAL BUG FIX TEST")
print("="*80)

for commodity, validations in data['commodities'].items():
    for val in validations:
        if val['model_version'] == 'synthetic_acc100':
            mae = val['overall_mae']
            mape = val['overall_mape']

            print(f"\n{commodity.upper()}:")
            print(f"  Overall MAE: ${mae:.10f}")
            print(f"  Overall MAPE: {mape:.10f} ({mape*100:.6f}%)")

            if mape == 0.0 and mae == 0.0:
                print(f"  ✓✓✓ SUCCESS - Day alignment bug FIXED!")
                print(f"      100% accurate predictions show 0% error")
            elif mape < 0.001:
                print(f"  ⚠️  NEARLY FIXED - Very small error remains")
            else:
                print(f"  ❌ BUG PERSISTS - Still has {mape*100:.2f}% error")

print(f"\n{'='*80}")
print("ALL ACCURACY LEVELS SUMMARY")
print("="*80)

for commodity, validations in data['commodities'].items():
    print(f"\n{commodity.upper()}:")
    print(f"  {'Model':<20} {'Target MAPE':<12} {'Actual MAPE':<12} {'Coverage':<10} {'Status'}")
    print(f"  {'-'*20} {'-'*12} {'-'*12} {'-'*10} {'-'*10}")

    for val in validations:
        target_mape = (1.0 - val['target_accuracy']) * 100
        actual_mape = val['overall_mape'] * 100
        coverage = val['coverage_80'] * 100

        # Status check
        if target_mape == 0:
            status = '✓' if actual_mape == 0 else '❌'
        else:
            tolerance = target_mape * 0.20  # 20% tolerance
            status = '✓' if abs(actual_mape - target_mape) < tolerance else '⚠️'

        print(f"  {val['model_version']:<20} {target_mape:>10.1f}% {actual_mape:>10.1f}% {coverage:>8.0f}% {status:>10}")

print(f"\n{'='*80}")
print("CONCLUSION")
print("="*80)

all_perfect = True
for commodity, validations in data['commodities'].items():
    for val in validations:
        if val['model_version'] == 'synthetic_acc100':
            if val['overall_mape'] != 0.0:
                all_perfect = False
                break

if all_perfect:
    print("\n✓✓✓ V6 FIX VERIFIED: Day alignment bug is FIXED!")
    print("    All 100% accurate scenarios show perfect 0% MAPE")
else:
    print("\n❌ V6 FIX INCOMPLETE: Bug still exists")
    print("   100% accurate scenarios still show error")

print("\n" + "="*80)
