ARG QGIS_TEST_VERSION=latest
FROM  qgis/qgis:${QGIS_TEST_VERSION}
MAINTAINER Matthias Kuhn <matthias@opengis.ch>

RUN apt-get update \
    && apt-get install -y \
         python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /tmp/
RUN pip3 install --upgrade pip
RUN pip3 install -r /tmp/requirements.txt

ENV LANG=C.UTF-8

WORKDIR /
