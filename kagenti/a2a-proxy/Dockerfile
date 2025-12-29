FROM registry.access.redhat.com/ubi9/ubi-minimal:latest

RUN microdnf install -y nginx && microdnf clean all

# OpenShift runs with an arbitrary UID (often group 0). Make required paths writable.
RUN chgrp -R 0 /etc/nginx /usr/share/nginx && \
    chmod -R g=u /etc/nginx /usr/share/nginx

COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 8000

CMD ["/bin/sh", "-lc", "mkdir -p /app/.cache/nginx/{client_body,proxy_temp,fastcgi_temp,uwsgi_temp,scgi_temp} && exec nginx -g 'daemon off;'"]


