# syntax = docker/dockerfile:1

FROM  --platform=$BUILDPLATFORM python:3.12 AS python-build

COPY . /app/

RUN pip install poetry && \
    cd /app && \
    apt-get update && \
    apt-get install -y libpython3-dev && \
    poetry install && \
    poetry build

FROM alpine:3.22

RUN --mount=from=python-build,source=/app/,target=/mnt \
    apk add --no-cache python3 tini && \
    apk add --no-cache --virtual .build-deps py3-pip linux-headers alpine-sdk python3-dev && \
    # NOTE: These flags are important, otherwise requests is removed with pip
    pip3 install --prefix /usr/local -I /mnt/dist/*.whl && \
    apk del --no-cache .build-deps && \
    rm -rf /root/.cache

ENV PYTHONPATH="/usr/local/lib/python3.12/site-packages"

ENTRYPOINT ["/sbin/tini", "--"]

CMD ["python3", "-u", "-m", "grocy_barcode_scanner.main"]
