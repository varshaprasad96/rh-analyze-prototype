FROM registry.access.redhat.com/ubi9/ubi-minimal:latest

RUN microdnf install -y nginx && microdnf clean all

COPY nginx.conf /etc/nginx/nginx.conf

RUN mkdir -p /app/.cache/nginx && chmod -R 777 /app/.cache

USER 1001

EXPOSE 8000

CMD mkdir -p /app/.cache/nginx/client_body /app/.cache/nginx/proxy_temp /app/.cache/nginx/fastcgi_temp /app/.cache/nginx/uwsgi_temp /app/.cache/nginx/scgi_temp && nginx -g 'daemon off;'

