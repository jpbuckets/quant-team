"""Entry point to run the dashboard server."""

import os

import uvicorn

if __name__ == "__main__":
    is_prod = os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("DATABASE_URL")
    uvicorn.run(
        "quant_team.api.app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=not is_prod,
    )
