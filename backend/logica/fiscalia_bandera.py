# Bandera y datos fijos de la Fiscalía v2 (modelo puro, sin motor gráfico): los comparten el backend (misiones, casos)
# y el frontend (frontend/fiscalia/). Sesión A del 2026-11-23.
#
# ALCALDE_FISCALIA_V2 (encendida por defecto). Con =0 el juego queda como en `0b7e148`: PC suelto junto al Mercado,
# sala digital, caso v1 y las tres misiones digitales de siempre. Se lee en cada llamada (los tests la cambian).

import os

VARIABLE = "ALCALDE_FISCALIA_V2"

NOMBRE_FISCALIA = "Fiscalía de Ciudad Nova"
# La Fiscalía es una casa del barrio (no uno de los 11 lugares del grafo, que ya son destino de misiones): la casa
# decorativa más cercana a este punto, de dos pisos, con la puerta hacia la Praça da Sé. El lugar del grafo que se usa
# como `destino` de sus misiones (ruta, pago, minimapa) es el de esa plaza; la baliza va a la puerta de la casa.
CASA_FISCALIA = (15.2, -1.1)
LUGAR_FISCALIA = "Praça da Sé"


def activa():
    return os.environ.get(VARIABLE, "").strip() != "0"
