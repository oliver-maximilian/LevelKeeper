FROM python:3.12-slim

RUN useradd --create-home --uid 1000 levelkeeper \
    && mkdir -p /app /data /config /archive \
    && chown -R levelkeeper:levelkeeper /app /data /config /archive

WORKDIR /app
COPY --chown=levelkeeper:levelkeeper levelkeeper ./levelkeeper

USER levelkeeper
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "levelkeeper"]
