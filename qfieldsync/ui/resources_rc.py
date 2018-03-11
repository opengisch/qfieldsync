from qgis.PyQt.QtCore import qVersion
if qVersion()[0] == '4':
    from ..resources_rc4 import *
else:
    from ..resources_rc5 import *