# Perspectiva atmosférica (puro, con tests; pulido visual Punto 6, M6.1 y M6.2).
#
# M6.1 Niebla: la de siempre iba lineal de 0 a 260 m con 65 % de máximo, pero el mapa chico mide ~150 m de lado: a 30 m
#      (plano medio) mezclaba un 7,5 % y el fondo casi nunca se fundía. Ahora llega al máximo a FIN_NIEBLA m con
#      INTENSIDAD_NIEBLA: a 30-40 m mezcla 16-21 % con el horizonte (pierde 11-15 % de croma) y desde ~120 m es casi horizonte.
# M6.2 Fondo: el horizonte (que también es el color de la niebla), las paradas bajas del degradado del cielo y los cerros
#      lejanos pierden saturación (×0,75 en el horizonte, menos al subir). Lo lejano queda apagado y el amarillo y el cian
#      quedan solo para lo interactivo (DISENO.md §1). Los tonos no cambian.
# Bandera: PERSPECTIVA_ATMOSFERICA = False o ALCALDE_PERSPECTIVA_ATMOSFERICA=0 -> niebla y cielo de siempre.

import colorsys
import os

PERSPECTIVA_ATMOSFERICA = True
FIN_NIEBLA_ANTES, INTENSIDAD_NIEBLA_ANTES = 260.0, 0.65
FIN_NIEBLA, INTENSIDAD_NIEBLA = 150.0, 0.80
# (elevación máxima, factor de saturación): las paradas del cielo hasta esa elevación (seno) se apagan con ese factor.
SATURACION_POR_ELEVACION = ((0.00, 0.75), (0.08, 0.85), (0.22, 0.93))
SATURACION_CERROS = 0.75


def activa(entorno=None):
    bruto = str((os.environ if entorno is None else entorno).get("ALCALDE_PERSPECTIVA_ATMOSFERICA", "")).strip().lower()
    if bruto in ("0", "false", "no", "off"):
        return False
    if bruto in ("1", "true", "si", "sí", "on"):
        return True
    return PERSPECTIVA_ATMOSFERICA


# (fin en m, intensidad 0-1) de la niebla base de la ciudad.
def parametros_niebla(con_perspectiva=None):
    if activa() if con_perspectiva is None else con_perspectiva:
        return FIN_NIEBLA, INTENSIDAD_NIEBLA
    return FIN_NIEBLA_ANTES, INTENSIDAD_NIEBLA_ANTES


# Fracción de mezcla con el color de niebla a `distancia` m (niebla lineal desde 0, como la usa Ursina).
def mezcla_niebla(distancia, fin, intensidad):
    if fin <= 0:
        return intensidad
    return intensidad * min(1.0, max(0.0, distancia / fin))


# Croma (max - min, 0-255): lo que el ojo lee como «colorido»; la saturación HLS de un color claro engaña.
def croma(rgb):
    return max(rgb) - min(rgb)


def saturacion(rgb):
    return colorsys.rgb_to_hls(*(c / 255 for c in rgb))[2]


# RGB 0-255 con la saturación multiplicada por `factor` (mismo tono y luminosidad). Devuelve enteros.
def desaturar(rgb, factor):
    h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
    return tuple(max(0, min(255, round(c * 255))) for c in colorsys.hls_to_rgb(h, l, s * factor))


def mezclar(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def factor_de_elevacion(elevacion):
    for tope, factor in SATURACION_POR_ELEVACION:
        if elevacion <= tope + 1e-9:
            return factor
    return 1.0


# Paradas ((elevación, rgb), ...) con las bajas apagadas.
def atenuar_paradas(paradas):
    return tuple((e, desaturar(c, factor_de_elevacion(e))) for e, c in paradas)


# Paleta del cielo (dict de ciclo_dia_calculos._paleta / cielo._paleta_tarde) con horizonte, paradas bajas y cerros apagados.
def atenuar_paleta(paleta):
    nueva = dict(paleta)
    nueva["horizonte"] = desaturar(paleta["horizonte"], factor_de_elevacion(0.0))
    nueva["paradas"] = atenuar_paradas(paleta["paradas"])
    if paleta.get("cerros"):
        nueva["cerros"] = tuple(desaturar(c, SATURACION_CERROS) for c in paleta["cerros"])
    return nueva
