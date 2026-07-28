FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_BASE_URL=/api
ARG VITE_USE_DEMO_DATA=false
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_USE_DEMO_DATA=${VITE_USE_DEMO_DATA}

RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html

RUN rm -f /etc/nginx/conf.d/default.conf \
    && printf '%s\n' \
        'server {' \
        '    listen 80;' \
        '    server_name _;' \
        '    access_log off;' \
        '    server_tokens off;' \
        '' \
        '    location = /healthz {' \
        '        return 204;' \
        '    }' \
        '' \
        '    location /api/ {' \
        '        proxy_pass http://api:8000/api/;' \
        '        proxy_http_version 1.1;' \
        '        proxy_set_header Host $host;' \
        '        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;' \
        '        proxy_set_header X-Forwarded-Proto $scheme;' \
        '    }' \
        '' \
        '    location / {' \
        '        try_files $uri $uri/ /index.html;' \
        '    }' \
        '}' \
        > /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1
