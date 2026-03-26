FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY quant_team/ quant_team/
COPY run.py .

RUN pip install --no-cache-dir -e .

RUN mkdir -p data
COPY data/teams/ data/teams/

EXPOSE 8000

CMD uvicorn quant_team.api.app:app --host 0.0.0.0 --port ${PORT:-8000}
