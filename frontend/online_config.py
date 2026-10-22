# Bandera del modo ONLINE (cooperativo en tiempo real). Módulo mínimo y SIN importaciones:
# se puede leer desde main.py y las escenas sin arrastrar nada de la red.
#
# ONLINE = False (por defecto): el juego es el hot-seat de siempre y ningún módulo de
# backend/red ni de frontend/online_*.py se importa. T7/T8 conectarán esta bandera a las escenas.
# Se puede forzar con la variable de entorno ALCALDE_ONLINE=1 (solo para pruebas a mano).

import os

ONLINE = os.environ.get("ALCALDE_ONLINE") == "1"

# Frecuencia (Hz) a la que BucleRed envía la posición local al anfitrión (el cliente de red además
# la coalesce a <= 20 Hz y manda un latido a 2 Hz si no cambia).
HZ_POS = 20.0

# Tope de eventos de red que BucleRed procesa por frame (el resto queda para el siguiente).
EVENTOS_POR_FRAME = 64

# Radio (m) de «llegué a la puerta»: igual que main.RADIO_INTERACCION y que el del anfitrión.
RADIO_INTERACCION = 2.0
