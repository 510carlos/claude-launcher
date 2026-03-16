FROM python:3.12-slim

RUN apt-get update && apt-get install -y docker.io && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy app/ directory as a package so "from app.xxx import" works
COPY . ./app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765"]
