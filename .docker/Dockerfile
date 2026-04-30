ARG QGIS_TEST_VERSION=latest
FROM  qgis/qgis:${QGIS_TEST_VERSION}

RUN apt update \
    && apt install -y \
        glibc-tools \
    && rm -rf /var/lib/apt/lists/*

# Install uv from the official image, which is a lot faster than installing it with pip
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV LANG=C.UTF-8

# Add crashes dump to STDERR
ENV LD_PRELOAD="/lib/x86_64-linux-gnu/libSegFault.so"
ENV SEGFAULT_SIGNALS="abrt segv"
ENV LIBC_FATAL_STDERR_=1

COPY . /usr/src

RUN uv venv --system-site-packages

WORKDIR /usr/src
