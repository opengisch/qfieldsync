#!/bin/bash

set -e

METADATA_VERSION=v$(grep -Po "(?<=^version=).*" qfieldsync/metadata.txt)

if [ "$METADATA_VERSION" != "${TRAVIS_TAG}" ]; then
  echo -e "\e[31mVersion tag in metadata ($METADATA_VERSION) and in git tag ($TRAVIS_TAG) do not match.\e[0m"
  echo -e "\e[31mThis will not be deployed.\e[0m"
  exit -1
fi

# PLUGIN_NAME=$(echo $TRAVIS_REPO_SLUG | cut -d'/' -f 2)
PLUGIN_NAME=qfieldsync

echo -e " \e[33mExporting plugin version ${TRAVIS_TAG} from folder ${PLUGIN_NAME}"
git archive --prefix=${PLUGIN_NAME}/ -o package.zip ${TRAVIS_TAG}:${PLUGIN_NAME}

echo -e " \e[33mUploading plugin as ${OSGEO_USERNAME}"
./scripts/plugin_upload.py -u "${OSGEO_USERNAME}" -w "${OSGEO_PASSWORD}" package.zip
