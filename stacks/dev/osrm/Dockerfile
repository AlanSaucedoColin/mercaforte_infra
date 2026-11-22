FROM ghcr.io/project-osrm/osrm-backend:v26.11.0-debian

# La imagen oficial usa Debian; GDAL y Psycopg provienen de sus paquetes nativos
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv python3-psycopg python3-gdal \
        libpq5 wget ca-certificates \
    && python3 -m venv --system-site-packages /opt/routing-venv \
    && /opt/routing-venv/bin/python -m pip install --no-cache-dir osmium==4.1.1 \
    && rm -rf /var/lib/apt/lists/*

COPY coordinator.py elevation.py elevation_tiles.py /opt/routing/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 GDAL_CACHEMAX=64
ENTRYPOINT ["/opt/routing-venv/bin/python", "/opt/routing/coordinator.py"]
