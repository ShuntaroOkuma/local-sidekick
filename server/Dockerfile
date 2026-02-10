FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml .
COPY server/ server/
RUN pip install --no-cache-dir .

ENV PORT=8080
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8080"]
