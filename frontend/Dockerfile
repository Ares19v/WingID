# ─────────────────────────────────────────────────────────────────────────────
# WingID — Frontend Dockerfile
# Builds the React/Vite app and serves it with Nginx
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Build ──────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

LABEL maintainer="Devansh Tyagi"
LABEL description="WingID React frontend — build stage"

WORKDIR /app

# Install dependencies (ci is faster and reproducible vs npm install)
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy source and build
COPY frontend/ .
RUN npm run build

# ── Stage 2: Serve ──────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

LABEL description="WingID React frontend — production server"

# Remove default Nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy Vite build output
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx config: serve SPA with fallback to index.html for client-side routing
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
