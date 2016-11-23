# sync options
OFFLINE   = "offline"
# No action will in general leave the source untouched.
# For file based layers, the source
# - will be made relative
# - the file(s) will be copied
NO_ACTION = "no_action"
REMOVE    = "remove"

# Layer properties
LAYER_ACTION = 'QFieldSync/action'

# Project properties
BASE_MAP_TYPE              = 'baseMapType'
BASE_MAP_TYPE_SINGLE_LAYER = 'singleLayer'
BASE_MAP_TYPE_MAP_THEME    = 'mapTheme'
CREATE_BASE_MAP            = '/createBaseMap'
BASE_MAP_THEME             = '/baseMapTheme'
BASE_MAP_LAYER             = '/baseMapLayer'
BASE_MAP_TILE_SIZE         = '/baseMapTileSize'
BASE_MAP_MUPP              = '/baseMapMupp'

# GUI messages options
LOG_TAG = "QFieldSync"
MSG_DURATION_SECS = 10

# QSettings tags
EXPORT_DIRECTORY_SETTING = "QFieldSync/exportDirectory"
IMPORT_DIRECTORY_SETTING = "QFieldSync/importDirectory"
