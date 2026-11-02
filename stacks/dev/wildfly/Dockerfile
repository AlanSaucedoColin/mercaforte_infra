# ==============================================================================
# Dockerfile - WildFly Base Image
# Construye una imagen WildFly endurecida con drivers PostgreSQL y ajustes de zona horaria.
# ==============================================================================

ARG WILDFLY_VERSION=42.0.0.Final-jdk21
ARG WILDFLY_DIGEST=sha256:2bef87441b6f76d388785d3163e894845655221451196f9d4d5b525262450e8e

# --- STAGE 1: Builder (Drivers & Config) ---
FROM alpine:3.23.2@sha256:865b95f46d98cf867a156fe4a135ad3fe50d2056aa3f25ed31662dff6da4eb62 AS pgdriver

ARG PG_JDBC_VER=42.7.8
ARG ALPINE_CA_CERTIFICATES_VER=20261020-r0
ARG ALPINE_TZDATA_VER=2026e-r0
ARG MAVEN_BASE="https://repo1.maven.org/maven2/org/postgresql/postgresql/${PG_JDBC_VER}/postgresql-${PG_JDBC_VER}.jar"
ARG TZ=America/Mexico_City

# Descarga dependencias, configura Timezone y obtiene el driver JDBC
RUN apk add --no-cache ca-certificates=${ALPINE_CA_CERTIFICATES_VER} tzdata=${ALPINE_TZDATA_VER} && \
    cp /usr/share/zoneinfo/${TZ:-UTC} /etc/localtime && \
    echo "${TZ:-UTC}" > /etc/timezone && \
    wget -O /tmp/postgresql.jar "${MAVEN_BASE}"

# --- STAGE 2: Final Image ---
FROM quay.io/wildfly/wildfly:${WILDFLY_VERSION}@${WILDFLY_DIGEST}

ARG TZ=America/Mexico_City

USER root

RUN microdnf install -y tzdata && microdnf clean all

USER jboss

EXPOSE 8080
WORKDIR $JBOSS_HOME

# --- Instalación de Dependencias ---
COPY --from=pgdriver --chown=jboss:jboss /tmp/postgresql.jar /tmp/postgresql.jar
COPY --chown=jboss:jboss ./init/init.cli ${JBOSS_HOME}/init.cli

COPY --from=pgdriver /etc/localtime /etc/localtime
COPY --from=pgdriver /etc/timezone /etc/timezone

# Ejecuta configuración offline (CLI) y limpia temporales
RUN $JBOSS_HOME/bin/jboss-cli.sh --file=$JBOSS_HOME/init.cli && \
    rm -rf /tmp/postgresql.jar && \
    rm -rf $JBOSS_HOME/standalone/configuration/standalone_xml_history \
    $JBOSS_HOME/standalone/tmp \
    $JBOSS_HOME/standalone/data

# --- Despliegues ---
COPY --chown=jboss:jboss --chmod=0755 ./deployments/ ${JBOSS_HOME}/standalone/deployments/

# --- Configuración de Entorno ---
ENV TZ="${TZ}"
ENV JAVA_TOOL_OPTIONS="-Dfile.encoding=UTF-8 -Duser.timezone=${TZ} -XX:InitialRAMPercentage=75.0 -XX:MaxRAMPercentage=75.0 -XX:MinRAMPercentage=75.0"

STOPSIGNAL SIGTERM

# --- Healthcheck ---
# Nativo (HTTP Management Endpoint)
HEALTHCHECK --interval=30s --timeout=10s --start-period=110s --retries=3 \
    CMD ["curl","-fsS","http://127.0.0.1:9990/health/ready"]
