# Bandera del modo ONLINE (cooperativo en tiempo real). Módulo mínimo y SIN importaciones:
# se puede leer desde main.py y las escenas sin arrastrar nada de la red.
#
# ONLINE = True (por defecto desde la ronda 5): el menú muestra el modo online. Se apaga con la variable de
# entorno ALCALDE_ONLINE=0: entonces el juego es el hot-seat de siempre y ningún módulo de backend/red ni de
# frontend/online_*.py se importa.

import os

ONLINE = os.environ.get("ALCALDE_ONLINE") != "0"

# Frecuencia (Hz) a la que BucleRed envía la posición local al anfitrión (el cliente de red además
# la coalesce a <= 20 Hz y manda un latido a 2 Hz si no cambia).
HZ_POS = 20.0

# Tope de eventos de red que BucleRed procesa por frame (el resto queda para el siguiente).
EVENTOS_POR_FRAME = 64

# Radio (m) de «llegué a la puerta»: igual que main.RADIO_INTERACCION y que el del anfitrión.
RADIO_INTERACCION = 2.0

# T9: bicis y motos en el modo online (montura exclusiva decidida por el anfitrión; los demás ven al piloto). False =
# los vehículos son locales como en el hot-seat y los remotos montados se dibujan como peatones. Se apaga con
# ALCALDE_VEHICULOS_ONLINE=0. TODOS los equipos de la sala deben usar el mismo valor.
VEHICULOS_ONLINE = os.environ.get("ALCALDE_VEHICULOS_ONLINE") != "0"
