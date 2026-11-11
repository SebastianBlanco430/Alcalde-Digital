# Alias: el módulo real es backend/logica/mundo_config.py (Python puro; el backend no puede importar frontend/).
# Se registra el MISMO objeto módulo para que `frontend.mundo_config` y `backend.logica.mundo_config` compartan estado.
import sys

from backend.logica import mundo_config as _real

sys.modules[__name__] = _real
