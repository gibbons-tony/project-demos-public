"""
Technical Indicator Calculations
Extracted from notebook 03_strategy_implementations.ipynb
"""

import numpy as np
import pandas as pd


def calculate_rsi(prices, period=14):
    """
    Calculate Relative Strength Index

    Args:
        prices: Array of historical prices
        period: RSI period (default 14)

    Returns:
        float: RSI value (0-100)
    """
    if len(prices) < period + 1:
        return 50.0

    deltas = np.diff(prices[-period-1:])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_adx(price_history, period=14):
    """
    Calculate Average Directional Index

    Args:
        price_history: DataFrame with 'price' column (and optionally 'high'/'low')
        period: ADX period (default 14)

    Returns:
        tuple: (adx, plus_di, minus_di)
    """
    if len(price_history) < period + 1:
        return 20.0, 0.0, 0.0

    if 'high' in price_history.columns and 'low' in price_history.columns:
        high = price_history['high'].values
        low = price_history['low'].values
    else:
        high = price_history['price'].values
        low = price_history['price'].values

    close = price_history['price'].values

    tr = np.maximum(high[1:] - low[1:],
                    np.maximum(abs(high[1:] - close[:-1]),
                              abs(low[1:] - close[:-1])))

    plus_dm = np.where((high[1:] - high[:-1]) > (low[:-1] - low[1:]),
                       np.maximum(high[1:] - high[:-1], 0), 0)
    minus_dm = np.where((low[:-1] - low[1:]) > (high[1:] - high[:-1]),
                        np.maximum(low[:-1] - low[1:], 0), 0)

    atr = np.mean(tr[-period:])
    if atr > 0:
        plus_di = 100 * np.mean(plus_dm[-period:]) / atr
        minus_di = 100 * np.mean(minus_dm[-period:]) / atr
    else:
        plus_di = 0.0
        minus_di = 0.0

    di_sum = plus_di + minus_di
    if di_sum > 0:
        dx = 100 * abs(plus_di - minus_di) / di_sum
        adx = dx
    else:
        adx = 0.0

    return adx, plus_di, minus_di


def calculate_std_dev_historical(prices, period=14):
    """
    Calculate standard deviation of recent price returns

    Args:
        prices: Array of historical prices
        period: Period for std dev calculation (default 14)

    Returns:
        float: Standard deviation of returns
    """
    if len(prices) < period + 1:
        return 0.10

    recent_prices = prices[-period:]
    returns = np.diff(recent_prices) / recent_prices[:-1]
    std_dev = np.std(returns)

    return std_dev


def calculate_prediction_confidence(predictions, horizon_day):
    """
    Calculate confidence from prediction ensemble using coefficient of variation

    Args:
        predictions: numpy array (n_paths, n_horizons)
        horizon_day: Which horizon to evaluate (0-indexed)

    Returns:
        float: Coefficient of variation (std_dev / median)
    """
    if predictions is None or predictions.size == 0:
        return 1.0

    if horizon_day >= predictions.shape[1]:
        horizon_day = predictions.shape[1] - 1

    day_predictions = predictions[:, horizon_day]
    median_pred = np.median(day_predictions)
    std_dev = np.std(day_predictions)

    cv = std_dev / median_pred if median_pred > 0 else 1.0

    return cv


def calculate_rsi_predicted(predictions, period=14):
    """
    Calculate RSI on predicted price trajectory

    Args:
        predictions: numpy array (n_paths, n_horizons)
        period: RSI period (default 14)

    Returns:
        float: RSI value (0-100)
    """
    if predictions is None or predictions.size == 0:
        return 50.0

    predicted_medians = np.array([np.median(predictions[:, h])
                                 for h in range(predictions.shape[1])])

    return calculate_rsi(predicted_medians, period=min(period, len(predicted_medians)-1))


def calculate_adx_predicted(predictions):
    """
    Calculate ADX on predicted price trajectory

    Args:
        predictions: numpy array (n_paths, n_horizons)

    Returns:
        tuple: (adx, plus_di, minus_di)
    """
    if predictions is None or predictions.size == 0:
        return 20.0, 0.0, 0.0

    predicted_medians = np.array([np.median(predictions[:, h])
                                 for h in range(predictions.shape[1])])

    pred_df = pd.DataFrame({'price': predicted_medians})

    return calculate_adx(pred_df, period=min(14, len(predicted_medians)-1))
