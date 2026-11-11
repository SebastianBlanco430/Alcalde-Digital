# Alias: el módulo real es backend/logica/vehiculo_calculos.py (Python puro; el backend no puede importar frontend/).
# Se registra el MISMO objeto módulo para que `frontend.vehiculo_calculos` y `backend.logica.vehiculo_calculos` compartan estado.
import sys

from backend.logica import vehiculo_calculos as _real

sys.modules[__name__] = _real
