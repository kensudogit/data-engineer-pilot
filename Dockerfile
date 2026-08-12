# 単一Railwayサービスで backend(FastAPI) と frontend(Next.js) を
# 同一コンテナ内の別プロセスとして起動する統合Dockerfile。
# frontend の next.config.ts の rewrites() が /api, /health を
# localhost:8000 (同一コンテナ内のbackend) へプロキシするため、
# ブラウザは常にフロントエンドの公開オリジンだけを見ればよい。
# ローカル開発用の docker-compose.yml（backend/frontendの2コンテナ構成）とは別経路。

FROM python:3.12-slim AS backend-build
WORKDIR /workspace/backend
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc gfortran \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

FROM node:20-bookworm-slim AS frontend-build
WORKDIR /workspace/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/. .
ENV INTERNAL_API_URL=http://localhost:8000
RUN npm run build

FROM python:3.12-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=backend-build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY backend/src backend/src
COPY backend/scripts backend/scripts

COPY --from=frontend-build /workspace/frontend/public frontend/public
COPY --from=frontend-build /workspace/frontend/.next frontend/.next
COPY --from=frontend-build /workspace/frontend/node_modules frontend/node_modules
COPY --from=frontend-build /workspace/frontend/package.json frontend/package.json
COPY --from=frontend-build /workspace/frontend/next.config.ts frontend/next.config.ts

COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend
ENV INTERNAL_API_URL=http://localhost:8000
ENV EXECUTION_MODE=demo

EXPOSE 3000
CMD ["/app/start.sh"]
