FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps chromium

COPY . .

EXPOSE 5000

CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 app:app
