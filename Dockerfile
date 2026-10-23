FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY app ./app
COPY web ./web
RUN useradd -r -u 10001 zoku && mkdir -p /srv/data && chown zoku /srv/data
USER zoku
EXPOSE 8000
ENV ZOKU_HOST=0.0.0.0 PORT=8000 ZOKU_DB=/srv/data/zokuzoku.sqlite ZOKU_MEDIA_DIR=/srv/data/media
CMD ["python","-m","app"]
