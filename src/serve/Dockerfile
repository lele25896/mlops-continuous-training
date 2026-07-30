FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# main.py lands next to data.py so its bare sibling import (from data import
# ...) keeps working unchanged, no PYTHONPATH needed — same trick as jobs/Dockerfile.
COPY src/data.py .
COPY src/serve/main.py .

RUN useradd --create-home --uid 1000 appuser && chown -R appuser /app
USER appuser

EXPOSE 8080
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
