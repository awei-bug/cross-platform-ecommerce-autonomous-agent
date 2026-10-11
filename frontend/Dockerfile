# syntax=docker/dockerfile:1

# ---- 构建阶段 ----
FROM node:20-alpine AS build
RUN corepack enable && corepack prepare pnpm@9 --activate
WORKDIR /app

COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile || pnpm install

COPY . .
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN pnpm build

# ---- 运行阶段：Nginx 托管静态资源并反代 API ----
FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY infra/nginx.frontend.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
