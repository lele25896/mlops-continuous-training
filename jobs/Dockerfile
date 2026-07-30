FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# run_job.py lands next to train.py/promote.py/data.py so their bare sibling
# imports (from data import ...) keep working unchanged, no PYTHONPATH needed.
COPY src/ ./
COPY jobs/run_job.py .

CMD ["python", "run_job.py"]
