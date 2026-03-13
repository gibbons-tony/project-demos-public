"""
Multi-horizon forecasting models.

Provides strategies for generating 14-day forecasts from single-output models:
1. Direct strategy: Train 14 separate models (one per horizon)
2. Recursive strategy: Use day_i forecast as input for day_i+1
3. Multi-output wrapper: Single model with 14 outputs

For now, we use the **Direct strategy** which is most robust for
independent predictions and works well with cross-validation.
