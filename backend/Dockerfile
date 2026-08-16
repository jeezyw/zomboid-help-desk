FROM node:20-slim AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json ./
RUN npm install

COPY frontend/index.html frontend/vite.config.ts ./
COPY frontend/src ./src
COPY frontend/public ./public
RUN npm run build


# The `docker` CLI, for optional in-process Docker control (see docker_control.py -
# start/stop/restart/stats for the Zomboid container). Baked in unconditionally:
# the binary is inert without /var/run/docker.sock actually being mounted, which is
# the real privilege boundary (opt-in via DOCKER_CONTROL_ENABLED, see
# docker-compose.yml) - no need for a build-arg-gated variant. Debian's apt-packaged
# docker.io turned out unreliable here (installed without error but left no working
# `docker` binary on PATH), so this pulls the CLI straight from Docker Inc.'s own
# minimal image instead - a static binary copy, no package manager involved.
FROM docker:cli AS dockercli


FROM python:3.12-slim

WORKDIR /app

COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=frontend-builder /frontend/dist ./frontend/dist

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "app.main:APP", "--host", "0.0.0.0", "--port", "8000"]
