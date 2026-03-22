"""Technical indicators computed on OHLCV data."""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger_bands(
    series: pd.Series, period: int = 20, std_dev: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    middle = sma(series, period)
    std = series.rolling(window=period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(window=period).mean()


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    plus_dm = df["high"].diff()
    minus_dm = -df["low"].diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    atr_val = atr(df, period)
    plus_di = 100 * ema(plus_dm, period) / atr_val
    minus_di = 100 * ema(minus_dm, period) / atr_val
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return ema(dx, period)


def obv(df: pd.DataFrame) -> pd.Series:
    volume_direction = np.where(df["close"] > df["close"].shift(), df["volume"], -df["volume"])
    volume_direction = np.where(df["close"] == df["close"].shift(), 0, volume_direction)
    return pd.Series(volume_direction, index=df.index).cumsum()


def stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> tuple[pd.Series, pd.Series]:
    lowest_low = df["low"].rolling(window=k_period).min()
    highest_high = df["high"].rolling(window=k_period).max()
    k = 100 * (df["close"] - lowest_low) / (highest_high - lowest_low)
    d = k.rolling(window=d_period).mean()
    return k, d


def compute_all(df: pd.DataFrame) -> str:
    """Compute all indicators and return a formatted text summary for agents."""
    close = df["close"]
    latest = close.iloc[-1]
    prev = close.iloc[-2]

    # Trend
    sma_20 = sma(close, 20).iloc[-1]
    sma_50 = sma(close, 50).iloc[-1]
    ema_12 = ema(close, 12).iloc[-1]
    ema_26 = ema(close, 26).iloc[-1]
    adx_val = adx(df).iloc[-1]

    # Momentum
    rsi_val = rsi(close).iloc[-1]
    macd_line, macd_signal, macd_hist = macd(close)
    stoch_k, stoch_d = stochastic(df)

    # Volatility
    bb_upper, bb_middle, bb_lower = bollinger_bands(close)
    atr_val = atr(df).iloc[-1]
    bb_pct_b = (latest - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1])

    # Volume
    obv_series = obv(df)
    obv_slope = (obv_series.iloc[-1] - obv_series.iloc[-5]) / 5 if len(obv_series) >= 5 else 0

    # Z-score from 20-day mean
    std_20 = close.rolling(20).std().iloc[-1]
    z_score = (latest - sma_20) / std_20 if std_20 > 0 else 0

    lines = [
        "# Technical Indicators",
        "",
        "## Trend",
        f"- Price: ${latest:,.2f} (prev close: ${prev:,.2f}, change: {(latest/prev - 1)*100:+.2f}%)",
        f"- SMA(20): ${sma_20:,.2f} ({'above' if latest > sma_20 else 'below'})",
        f"- SMA(50): ${sma_50:,.2f} ({'above' if latest > sma_50 else 'below'})",
        f"- EMA(12)/EMA(26): {'bullish crossover' if ema_12 > ema_26 else 'bearish crossover'}",
        f"- ADX: {adx_val:.1f} ({'strong trend' if adx_val > 25 else 'weak/no trend'})",
        "",
        "## Momentum",
        f"- RSI(14): {rsi_val:.1f} ({'OVERBOUGHT' if rsi_val > 70 else 'OVERSOLD' if rsi_val < 30 else 'neutral'})",
        f"- MACD: {macd_line.iloc[-1]:.2f} | Signal: {macd_signal.iloc[-1]:.2f} | Histogram: {macd_hist.iloc[-1]:.2f}",
        f"- Stochastic %K/%D: {stoch_k.iloc[-1]:.1f}/{stoch_d.iloc[-1]:.1f}",
        "",
        "## Volatility",
        f"- Bollinger Bands: ${bb_lower.iloc[-1]:,.2f} / ${bb_middle.iloc[-1]:,.2f} / ${bb_upper.iloc[-1]:,.2f}",
        f"- Bollinger %B: {bb_pct_b:.2f} ({'upper band' if bb_pct_b > 0.8 else 'lower band' if bb_pct_b < 0.2 else 'mid-range'})",
        f"- ATR(14): ${atr_val:,.2f} ({atr_val/latest*100:.2f}% of price)",
        "",
        "## Volume & Mean Reversion",
        f"- OBV Trend: {'rising' if obv_slope > 0 else 'falling'} (5-bar slope: {obv_slope:,.0f})",
        f"- Z-Score from 20d mean: {z_score:.2f} ({'extended' if abs(z_score) > 2 else 'normal range'})",
        "",
        "## Recent Price Action (last 5 candles)",
    ]

    for i in range(-5, 0):
        row = df.iloc[i]
        body = "green" if row["close"] > row["open"] else "red"
        lines.append(
            f"- {row.name.strftime('%Y-%m-%d')}: O=${row['open']:,.2f} H=${row['high']:,.2f} "
            f"L=${row['low']:,.2f} C=${row['close']:,.2f} V=${row['volume']:,.0f} ({body})"
        )

    return "\n".join(lines)
