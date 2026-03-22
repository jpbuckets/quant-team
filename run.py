"""Entry point to run the dashboard server."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "quant_team.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
