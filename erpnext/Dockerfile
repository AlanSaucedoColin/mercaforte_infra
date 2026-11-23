# syntax=docker/dockerfile:1

FROM frappe/erpnext:v16.60.0

COPY --chown=frappe:0 app/ /home/frappe/frappe-bench/apps/mercaforte_erpnext/

USER frappe
RUN uv pip install --python env/bin/python --no-cache --editable ./apps/mercaforte_erpnext \
    && ln -s /home/frappe/frappe-bench/apps/mercaforte_erpnext/mercaforte_erpnext/public assets/mercaforte_erpnext \
    && env/bin/python -c "import mercaforte_erpnext.hooks" \
    && test -f assets/mercaforte_erpnext/js/customer_quick_entry.js \
    && test -r assets/mercaforte_erpnext/js/customer_quick_entry.js
