ARG QGIS_TEST_VERSION=latest
FROM  qgis/qgis:${QGIS_TEST_VERSION}
MAINTAINER Matthias Kuhn <matthias@opengis.ch>

RUN apt-get update \
    && apt-get install -y python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /tmp/

# Upgrading `pip` fixes: "WARNING: Generating metadata for package libqfieldsync produced metadata for project name unknown. Fix your #egg=libqfieldsync fragments."
# However, in QGIS>=3.38, this command fail as `pip` is Debian installed and protected, hence we have `|| true`.
RUN pip3 install --upgrade pip || true

# images for QGIS<=3.34 uses much older `pip` that does not support `--break-system-packages`
RUN pip3 install -r /tmp/requirements.txt || pip3 install -r /tmp/requirements.txt --break-system-packages

ENV LANG=C.UTF-8

WORKDIR /
