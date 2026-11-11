# Alias: el módulo real es backend/logica/azar_fijo.py (Python puro; el backend no puede importar frontend/).
# Se registra el MISMO objeto módulo para que `frontend.azar_fijo` y `backend.logica.azar_fijo` compartan estado.
import sys

from backend.logica import azar_fijo as _real

sys.modules[__name__] = _real
