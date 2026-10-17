FROM python:3.15-slim

RUN useradd --create-home --uid 1000 levelkeeper \
    && mkdir -p /app /data /config /archive \
    && chown -R levelkeeper:levelkeeper /app /data /config /archive

WORKDIR /app
COPY --chown=levelkeeper:levelkeeper levelkeeper ./levelkeeper

USER levelkeeper
ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=5m --timeout=10s --start-period=15m \
    CMD ["python", "-m", "levelkeeper", "--healthcheck"]

ENTRYPOINT ["python", "-m", "levelkeeper"]
