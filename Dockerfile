FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.lock ./backend/requirements.lock
RUN pip install --no-cache-dir -r backend/requirements.lock
COPY backend/app ./backend/app
COPY --from=frontend /build/dist ./frontend/dist
RUN useradd --create-home appuser && mkdir -p /app/runtime && chown appuser:appuser /app/runtime
USER appuser
WORKDIR /app/backend
EXPOSE 8000
CMD ["python", "-m", "app.cloud"]
