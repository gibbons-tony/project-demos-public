"""
Cost Configuration for Small Farmer Reality

Based on research of actual small coffee farmer costs:
- Storage: 0.005% per day (quality degradation only, on-farm gunny sack storage)
- Transaction: 1% (local intermediary who pays immediate cash)

This represents the LOWEST reasonable costs for a small farmer:
- No warehouse fees, storing on-farm in traditional gunny sacks
- Selling to local buyer who comes to farm gate
- Main storage "cost" is quality degradation risk after 6 months
"""

# Override the aggressive costs with small farmer reality
SMALL_FARMER_COSTS = {
    'coffee': {
        'storage_cost_pct_per_day': 0.005,  # 0.005% per day = 0.15% per month
        'transaction_cost_pct': 0.01,       # 1% per transaction
    },
    'sugar': {
        'storage_cost_pct_per_day': 0.005,  # Same low-cost assumption
        'transaction_cost_pct': 0.01,       # Same local intermediary fee
    }
}

# For use in diagnostics - merge with main config
def get_small_farmer_config(base_config):
    """
    Override base config with small farmer costs

    Args:
        base_config: dict from COMMODITY_CONFIGS

    Returns:
        Updated config dict with realistic small farmer costs
    """
    config = base_config.copy()
    commodity = config['commodity']

    if commodity in SMALL_FARMER_COSTS:
        config.update(SMALL_FARMER_COSTS[commodity])

    return config
