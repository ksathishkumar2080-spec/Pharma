FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir fastapi uvicorn sqlalchemy asyncpg anthropic elasticsearch neo4j httpx
COPY . .
CMD ["uvicorn", "services.intelligence.main:app", "--host", "0.0.0.0", "--port", "8002"]
