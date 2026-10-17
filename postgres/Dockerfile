FROM postgres:16

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-cron \
    && rm -rf /var/lib/apt/lists/*

COPY init-pg-cron.sql /docker-entrypoint-initdb.d/10-pg-cron.sql
