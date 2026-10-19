FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 mewtube
WORKDIR /app
COPY --chown=mewtube:mewtube mewtube ./mewtube
COPY --chown=mewtube:mewtube web ./web
COPY --chown=mewtube:mewtube scripts ./scripts
RUN mkdir /app/data && chown mewtube:mewtube /app/data
USER mewtube
ENV DATA_DIR=/app/data PORT=3000
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:3000/healthz',timeout=3)"
CMD ["python", "-m", "mewtube.server"]
