# Build context: frontend/  →  docker build -f frontend/Dockerfile frontend/
# NEXT_PUBLIC_API is baked in at build time (Next.js limitation for public vars).
# Override at build: --build-arg NEXT_PUBLIC_API=https://api.yourdomain.com

FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API=http://localhost:8000
ENV NEXT_PUBLIC_API=$NEXT_PUBLIC_API
RUN npm run build

FROM node:20-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
# standalone output bundles only what's needed (~10× smaller image)
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000
ENV PORT=3000 HOSTNAME=0.0.0.0

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -qO- http://localhost:3000/ | grep -q "." || exit 1

CMD ["node", "server.js"]
