# syntax=docker/dockerfile:1

# SmartRoute frontend: production Vite build served by nginx.
# nginx forwards /api to the backend service (single origin, no CORS) - see nginx.conf.

FROM node:24-slim AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
RUN npm run build


FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

# Backend address for the /api proxy (compose service name by default).
ENV BACKEND_UPSTREAM=backend:8000

COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:8080/ || exit 1
