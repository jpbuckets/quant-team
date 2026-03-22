FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir .

RUN mkdir -p data

EXPOSE 8000

CMD uvicorn quant_team.api.app:app --host 0.0.0.0 --port ${PORT:-8000}
