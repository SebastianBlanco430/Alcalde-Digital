# Tamaño aparente de las etiquetas de nombre sobre los personajes (puro, con tests). La etiqueta es un Text 3D de
# tamaño fijo en el mundo (billboard): a 3 m de la cámara ocupaba el doble de pantalla que a 6 m y «Seu Zé» salía
# enorme. Se acota: de DISTANCIA_REFERENCIA hacia fuera se deja como siempre (se achica con la distancia); hacia
# dentro la escala baja con la distancia para que en pantalla nunca pase de lo que mide a esa referencia.

import os

DISTANCIA_REFERENCIA = 6.0     # m de la cámara a partir de los cuales la etiqueta mide su escala base
FACTOR_MINIMO = 0.25           # nunca por debajo de este tramo de la escala base (pegado a la cámara sigue legible)


def factor_etiqueta(distancia, referencia=DISTANCIA_REFERENCIA, minimo=FACTOR_MINIMO):
    if not isinstance(distancia, (int, float)) or distancia != distancia:
        return 1.0
    return min(1.0, max(minimo, distancia / referencia))


# Escala a la que dejar la etiqueta de `base` cuando la cámara está a `distancia` m.
def escala_limitada(base, distancia, referencia=DISTANCIA_REFERENCIA, minimo=FACTOR_MINIMO):
    return base * factor_etiqueta(distancia, referencia, minimo)


# -- M1.1 Etiqueta del propio jugador (D6) --
# El nombre del jugador activo (el propio: en hot-seat el del turno, en línea el local) ya no se dibuja: tapaba el
# centro de la pantalla. Los demás avatares de jugador conservan la suya, al 60 % del tamaño y desvaneciéndose con la
# distancia a la cámara. La distancia se mide desde la cámara (la orbital va de 3.5 a 12 m del propio jugador): hasta
# ALFA_CERCA la etiqueta es opaca, así un jugador al lado del tuyo se lee entero aun con el zoom al máximo.
# ALCALDE_ETIQUETA_JUGADOR=0 vuelve exactamente al comportamiento de antes.

ETIQUETA_JUGADOR = True         # constante por defecto de la bandera
ESCALA_OTROS = 0.6              # tramo del tamaño de antes para las etiquetas de los otros jugadores
ALFA_CERCA = 12.0               # m de la cámara: hasta aquí, opaca
ALFA_LEJOS = 28.0               # m de la cámara: desde aquí, invisible (alfa 0)


def _bandera(nombre, constante):
    valor = os.environ.get(nombre, "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(constante)


def etiqueta_jugador_activa():
    """¿Rige M1.1? ALCALDE_ETIQUETA_JUGADOR=1/0 manda sobre la constante."""
    return _bandera("ALCALDE_ETIQUETA_JUGADOR", ETIQUETA_JUGADOR)


def mostrar_etiqueta(es_activo, en_linea=False, activa=True):
    """¿Se dibuja la etiqueta de un avatar de jugador? Con la bandera apagada, siempre (como antes). Con ella, nunca la
    del propio jugador (`es_activo`), ni en hot-seat ni en línea (`en_linea` no cambia la regla: se deja explícito)."""
    if not activa:
        return True
    return not es_activo


def alfa_por_distancia(distancia, cerca=ALFA_CERCA, lejos=ALFA_LEJOS):
    """Opacidad (0..1) de la etiqueta de otro jugador a `distancia` m de la cámara: 1 hasta `cerca`, baja lineal a 0
    en `lejos`. Distancia no numérica o NaN -> 1 (no esconder por un dato malo); negativa -> 1 (está encima)."""
    if isinstance(distancia, bool) or not isinstance(distancia, (int, float)) or distancia != distancia:
        return 1.0
    if distancia <= cerca:
        return 1.0
    if distancia >= lejos or lejos <= cerca:
        return 0.0
    return 1.0 - (distancia - cerca) / (lejos - cerca)

