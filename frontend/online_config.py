# Alias: el módulo real es backend/logica/online_config.py (Python puro; el backend no puede importar frontend/).
# Se registra el MISMO objeto módulo para que `frontend.online_config` y `backend.logica.online_config` compartan estado.
import sys

from backend.logica import online_config as _real

sys.modules[__name__] = _real
