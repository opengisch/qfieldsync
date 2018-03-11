#!/bin/bash

ROOT_DIR=$(git rev-parse --show-toplevel)

autopep8 -r --in-place --ignore=E261,E265,E402,E501 $ROOT_DIR/qfieldsync/core
autopep8 -r --in-place --ignore=E261,E265,E402,E501 $ROOT_DIR/qfieldsync/dialogs
