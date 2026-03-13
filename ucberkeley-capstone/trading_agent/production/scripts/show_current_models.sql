-- Check which models are actually loaded in predictions tables (CURRENT)

-- Coffee synthetic models
SELECT 'Coffee Synthetic' as source, model_version, COUNT(*) as prediction_count
FROM commodity.trading_agent.predictions_coffee
GROUP BY model_version
ORDER BY model_version;

-- Coffee real models from forecast.distributions
SELECT 'Coffee Real' as source, model_version, COUNT(*) as prediction_count
FROM commodity.forecast.distributions
WHERE commodity = 'Coffee' AND is_actuals = false
GROUP BY model_version
ORDER BY model_version;

-- Sugar synthetic models
SELECT 'Sugar Synthetic' as source, model_version, COUNT(*) as prediction_count
FROM commodity.trading_agent.predictions_sugar
GROUP BY model_version
ORDER BY model_version;

-- Sugar real models
SELECT 'Sugar Real' as source, model_version, COUNT(*) as prediction_count
FROM commodity.forecast.distributions
WHERE commodity = 'Sugar' AND is_actuals = false
GROUP BY model_version
ORDER BY model_version;
