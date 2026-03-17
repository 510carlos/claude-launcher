# Stage 1: Build frontend with Bun + Vite
FROM oven/bun:1.3-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/bun.lock* ./
RUN bun install --frozen-lockfile
COPY frontend/ .
RUN bun run build

# Stage 2: Python app
FROM python:3.12-slim

RUN apt-get update && apt-get install -y docker.io && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy app/ directory as a package so "from app.xxx import" works
COPY . ./app/

# Copy built frontend into the app
COPY --from=frontend /build/dist/ ./app/frontend/dist/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765"]
