"""Market data API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...market.stock_data import StockMarketData
from ...market.indicators import compute_all

router = APIRouter(prefix="/api/market", tags=["market"])

_market = StockMarketData()


@router.get("/quote/{ticker}")
def get_quote(ticker: str):
    try:
        return _market.fetch_quote(ticker.upper())
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Could not fetch quote for {ticker}: {e}")


@router.get("/chart/{ticker}")
def get_chart(ticker: str, period: str = "3mo", interval: str = "1d"):
    try:
        df = _market.fetch_ohlcv(ticker.upper(), period, interval)
        # Convert to JSON-friendly format
        records = []
        for idx, row in df.iterrows():
            records.append({
                "date": idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx),
                "open": round(row["open"], 2),
                "high": round(row["high"], 2),
                "low": round(row["low"], 2),
                "close": round(row["close"], 2),
                "volume": int(row["volume"]),
            })

        # Compute indicators
        indicators_text = compute_all(df)

        return {"ticker": ticker.upper(), "data": records, "indicators": indicators_text}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Could not fetch chart for {ticker}: {e}")


@router.get("/options/{ticker}")
def get_options(ticker: str):
    try:
        return _market.fetch_options_chain(ticker.upper())
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Could not fetch options for {ticker}: {e}")
