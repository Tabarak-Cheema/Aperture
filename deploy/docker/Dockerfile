# Single-image Aperture — one process serving both API and (built) web app.
FROM node:20-alpine AS web-build
WORKDIR /web
COPY apps/web/package*.json ./
RUN npm ci || npm install
COPY apps/web ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY packages ./packages
COPY services ./services
COPY apps/server ./apps/server
COPY --from=web-build /web/dist ./apps/web/dist

ENV PYTHONPATH=/app/packages/aqir:/app/packages/catalog:/app/packages/llm_gateway:/app/services/compile:/app/services/query:/app/services/ingest:/app/services/insight:/app/apps/server
EXPOSE 8000

CMD ["uvicorn", "apps.server.aperture_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
