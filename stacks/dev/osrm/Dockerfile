FROM ghcr.io/project-osrm/osrm-backend:v6.0.0

# La imagen publicada usa Alpine; GDAL y Psycopg provienen de sus paquetes nativos
RUN apk add --no-cache \
        python3 py3-pip py3-psycopg py3-gdal libpq wget ca-certificates expat libbz2 zlib \
    && apk add --no-cache --virtual .osmium-build-deps \
        g++ cmake ninja-is-really-ninja python3-dev boost-dev expat-dev bzip2-dev zlib-dev \
    && python3 -m venv --system-site-packages /opt/routing-venv \
    && CMAKE_BUILD_PARALLEL_LEVEL=1 /opt/routing-venv/bin/python -m pip install --no-cache-dir osmium==4.1.1 \
    && apk del .osmium-build-deps

COPY coordinator.py elevation.py /opt/routing/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["/opt/routing-venv/bin/python", "/opt/routing/coordinator.py"]
