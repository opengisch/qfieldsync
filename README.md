[![Read the documentation](https://img.shields.io/badge/Read-the%20docs-green.svg)](https://docs.qfield.org/get-started/)
[![Release](https://img.shields.io/github/release/opengisch/QFieldSync.svg)](https://github.com/opengisch/QFieldSync/releases)
[![Build Status](https://travis-ci.org/opengisch/qfieldsync.svg?branch=master)](https://travis-ci.org/opengisch/qfieldsync)

# QFieldSync
This plugin facilitates packaging and synchronizing QGIS projects for use with [QField](http://www.qfield.org).

It analyses the QGIS project and suggests and performs actions needed to make the project working on QField.

More information can be found in the [QField documentation](https://docs.qfield.org/get-started/).

The plugin can be download on the [QGIS plugin repository](https://plugins.qgis.org/plugins/qfieldsync/).

## Development

1) Checkout [qfieldsync](https://github.com/opengisch/qfieldsync/) locally:

```
git clone --recurse-submodules git@github.com:opengisch/qfieldsync.git
```

2) Make a link of the QFieldSync checkout to qfieldsync directory in your current QGIS profile:

```
ln -s ${PWD}/qfieldsync/qfieldsync ${HOME}/.local/share/QGIS/QGIS3/profiles/default/python/plugins
```

3) Checkout [libqfieldsync](https://github.com/opengisch/libqfieldsync/) locally:

```
git clone git@github.com:opengisch/libqfieldsync.git
```

4) Install your local libqfieldsync as editable dependency (assuming you are in the same directory as step 3):

```
pip install -e libqfieldsync
```

NOTE On more recent Linux distributions you might get an error `error: externally-managed-environment` and you have to pass additional `--break-system-packages`.

Despite the name, we promise this is not going to break system packages.
