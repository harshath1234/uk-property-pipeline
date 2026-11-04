# Pipeline image: Python 3.12 + Java 17 (for Spark) + the ppd package.
FROM python:3.12-slim-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends openjdk-17-jre-headless procps \
 && rm -rf /var/lib/apt/lists/*
# Spark finds `java` on PATH; no hard-coded JAVA_HOME, so the image also builds on ARM (Apple Silicon)

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PPD_ROOT=/app

WORKDIR /app

# install dependencies first so code edits don't invalidate this layer
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[dbt,quality,ons]"

COPY config ./config
COPY dbt ./dbt
COPY postgres ./postgres
COPY site ./site
COPY tests/fixtures ./tests/fixtures
COPY scripts ./scripts
COPY sql ./sql
RUN mkdir -p /app/reports

# run as a non-root user
RUN useradd --create-home --uid 1000 ppd && chown -R ppd /app
USER ppd

ENTRYPOINT ["ppd"]
CMD ["run-all"]
