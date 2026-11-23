# syntax=docker/dockerfile:1

FROM frappe/erpnext:v16.60.0

USER root
COPY --chown=frappe:0 app/ /home/frappe/frappe-bench/apps/mercaforte_erpnext/

USER frappe
RUN uv pip install \
      --python /home/frappe/frappe-bench/env/bin/python \
      --no-cache \
      --editable /home/frappe/frappe-bench/apps/mercaforte_erpnext \
    && rm -rf /home/frappe/frappe-bench/sites/assets \
    && cp -a /home/frappe/frappe-bench/assets /home/frappe/frappe-bench/sites/assets \
    && bench build --app mercaforte_erpnext \
    && rm -rf /home/frappe/frappe-bench/assets \
    && cp -a /home/frappe/frappe-bench/sites/assets /home/frappe/frappe-bench/assets \
    && ln -sfn \
      /home/frappe/frappe-bench/apps/mercaforte_erpnext/mercaforte_erpnext/public \
      /home/frappe/frappe-bench/assets/mercaforte_erpnext \
    && rm -rf /home/frappe/frappe-bench/sites/assets \
    && test -L /home/frappe/frappe-bench/assets/mercaforte_erpnext \
    && /home/frappe/frappe-bench/env/bin/python -c \
      "import mercaforte_erpnext; assert mercaforte_erpnext.__version__ == '0.2.0'"

LABEL org.opencontainers.image.title="Mercaforte ERPNext" \
      org.opencontainers.image.version="v16.60.0-app0.2.0" \
      com.mercaforte.frappe-app="mercaforte_erpnext" \
      com.mercaforte.frappe-app.version="0.2.0"
