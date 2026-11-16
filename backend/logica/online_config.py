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

# Radio (m) de «llegué a la puerta». Módulo sin importaciones: el valor se repite aquí y un test
# (tests/test_ciclo_vida_misiones.py) exige que sea igual a backend.logica.misiones.RADIO_INTERACCION.
RADIO_INTERACCION = 2.0

# T9: bicis y motos en el modo online (montura exclusiva decidida por el anfitrión; los demás ven al piloto). False =
# los vehículos son locales como en el hot-seat y los remotos montados se dibujan como peatones. Se apaga con
# ALCALDE_VEHICULOS_ONLINE=0. TODOS los equipos de la sala deben usar el mismo valor.
VEHICULOS_ONLINE = os.environ.get("ALCALDE_VEHICULOS_ONLINE") != "0"

# Finales por etapas en línea (2026-11-15): la ciudad cambia de etapa (-3..+3: fuego, fiesta, tinte, música y medidor) con
# el índice que sale de los indicadores y la confianza por grupo que ya manda el anfitrión (FlujoEnLinea.indice_etapas). Es
# solo visual en cada equipo: no cambia el protocolo ni la huella de sala. Se apaga con ALCALDE_ETAPAS_ONLINE=0.
ETAPAS_ONLINE = os.environ.get("ALCALDE_ETAPAS_ONLINE") != "0"

# Minijuegos de verificar en línea (2026-11-15): las misiones con carta de misión abren el minijuego como en el hot-seat. Al
# terminar se deciden las cartas con las MISMAS llamadas que la pantalla de siempre (EstadoRemoto.decidir), así que el
# anfitrión recibe las decisiones de siempre: no cambia el protocolo. Se apaga con ALCALDE_MINIJUEGOS_ONLINE=0.
MINIJUEGOS_ONLINE = os.environ.get("ALCALDE_MINIJUEGOS_ONLINE") != "0"
