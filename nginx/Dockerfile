ARG NGINX_BASE_IMAGE=nginx:1.30.7-alpine
FROM ${NGINX_BASE_IMAGE}

COPY ./nginx/templates/default.conf.template /etc/nginx/templates/default.conf.template
COPY ./config/dist/ /usr/share/nginx/html/

EXPOSE 80
