#!/bin/bash
qgis2compat_version=$(grep -oP "qgis2compat_min_version = '\K[0-9\.]+" qfieldsync/__init__.py)
mkdir qgis2compat
echo "Downloading qgis2compat version from https://github.com/opengisch/qgis2compat/archive/v${qgis2compat_version}.tar.gz"
curl -L "https://github.com/opengisch/qgis2compat/archive/v${qgis2compat_version}.tar.gz" | tar -xzC qgis2compat --strip-components=1
rm -rf qgis2compat/test
