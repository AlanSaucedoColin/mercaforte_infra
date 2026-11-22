# ==============================================================================
# Dockerfile - WildFly Base Image
# Construye una imagen WildFly endurecida con drivers PostgreSQL y ajustes de zona horaria.
# ==============================================================================

ARG WILDFLY_VERSION=42.0.0.Final-jdk21
ARG WILDFLY_DIGEST=sha256:2bef87441b6f76d388785d3163e894845655221451196f9d4d5b525262450e8e

FROM quay.io/wildfly/wildfly:${WILDFLY_VERSION}@${WILDFLY_DIGEST}

ARG TZ=America/Mexico_City

USER root

RUN microdnf install -y tzdata && \
    microdnf clean all && \
    cp /usr/share/zoneinfo/${TZ:-UTC} /etc/localtime && \
    echo "${TZ:-UTC}" > /etc/timezone

USER jboss

EXPOSE 8080
WORKDIR $JBOSS_HOME

# --- Instalación de Dependencias ---
COPY --chown=jboss:jboss ./wildfly/drivers/postgresql-42.7.8.jar /tmp/postgresql.jar
COPY --chown=jboss:jboss ./wildfly/init/init.cli ${JBOSS_HOME}/init.cli

# Ejecuta configuración offline (CLI) y limpia temporales
RUN $JBOSS_HOME/bin/jboss-cli.sh --file=$JBOSS_HOME/init.cli && \
    rm -rf /tmp/postgresql.jar && \
    rm -rf $JBOSS_HOME/standalone/configuration/standalone_xml_history \
    $JBOSS_HOME/standalone/tmp \
    $JBOSS_HOME/standalone/data

# --- Despliegues ---
# Copia los artefactos desde configs/deployments
COPY --chown=jboss:jboss --chmod=0755 ./configs/deployments/ ${JBOSS_HOME}/standalone/deployments/

# --- Configuración de Entorno ---
ENV TZ="${TZ}"
ENV SPRING_PROFILES_ACTIVE="prod"
# Mitigación temporal para Java4Shell hasta disponer de WildFly con Temurin 21.0.13.1+2 o posterior.
ENV JAVA_TOOL_OPTIONS="-Dfile.encoding=UTF-8 -Duser.timezone=${TZ} -XX:InitialRAMPercentage=75.0 -XX:MaxRAMPercentage=75.0 -XX:MinRAMPercentage=75.0 -XX:-UseBASE64Intrinsics"

STOPSIGNAL SIGTERM

# --- Healthcheck ---
# Nativo (HTTP Management Endpoint)
HEALTHCHECK --interval=30s --timeout=10s --start-period=110s --retries=3 \
    CMD ["curl","-fsS","http://127.0.0.1:9990/health/ready"]
