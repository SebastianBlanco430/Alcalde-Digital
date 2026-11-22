# Parámetros del sombreado «toon» de los personajes .glb (Python puro: NO importa ursina ni panda3d).
#
# El shader (frontend/skinning_gpu.py, versión toon) multiplica el color de siempre por:
#   - una banda de LUZ (×~1,0: no oscurece a los personajes) donde la normal mira al sol, y
#   - una banda de SOMBRA (×~0,78 con un tinte frío leve) donde no; el paso entre las dos es un smoothstep estrecho;
# y le suma un BORDE DE LUZ (rim fresnel: pow(1 - N·V, potencia)) sutil, que no toca el casco de tinta (casi negro).
#
# Los valores cambian con la hora del cielo (frontend/ciclo_dia_calculos.py, tramos noche / amanecer / mañana / tarde):
# de noche la sombra es más fría y el borde más tenue. Hora None = la tarde de siempre. La mezcla entre tramos sale de
# ciclo_dia_calculos.mezcla_de_hora (escalones de 1/PASOS_MEZCLA): los uniforms solo se reescriben si cambia el escalón.
#
# Espacio del shader: el MUNDO (p3d_ModelMatrix). OJO: Ursina pone `coordinate-system y-up-left` en Panda
# (ursina/window.py), así que ese mundo YA está en coordenadas de Ursina (y arriba): la dirección del sol va tal cual,
# sin cambiar ejes. Medido con un fragment de depuración: la normal de la espalda y el vector a la cámara salen en ejes
# de Ursina (convertir a z arriba invertía la luz: todo el personaje caía en la sombra desde cualquier lado).
# Bandera: TOON_PERSONAJES o ALCALDE_TOON_PERSONAJES=0/1. Apagada, los personajes usan el shader de antes (texto idéntico).

import math
import os

from frontend import ciclo_dia_calculos as ciclo
from frontend.luz_horneada_calculos import DIRECCION_SOL_POR_DEFECTO

# Apagada por defecto (2026-11-21): con las cámaras del juego el sol suele quedar a la espalda de la cámara y la mejora se
# ve, pero es sutil (medidas/m5_on_* frente a m5_off_*); la regla del dueño es «si es dudoso, apagada».
# ALCALDE_TOON_PERSONAJES=1 la enciende sin tocar el código. Rendimiento medido sin coste (medidas/m5.json, m5off.json).
TOON_PERSONAJES = False
PERIODO_TOON = 0.5               # s reales entre dos lecturas de la hora (como el cielo)

# La de frontend/cielo.DIRECCION_SOL (Ursina, hacia donde APUNTA la luz). cielo.py importa ursina, así que aquí se usa la
# copia pura de luz_horneada_calculos; tests/test_toon_calculos.py comprueba que siguen siendo iguales.
DIRECCION_SOL = DIRECCION_SOL_POR_DEFECTO

# Paso luz/sombra: smoothstep(centro - semiancho, centro + semiancho, N·L). Centro algo negativo: un poco más de la
# mitad del cuerpo queda en la banda de luz (el sol está a ~43° de altura y la cámara suele mirar contra él).
CENTRO_BANDA = -0.10
SEMIANCHO_BANDA = 0.06

# Por paleta del cielo: multiplicador de la banda de luz (RGB), factor y tinte de la sombra, color del borde, fuerza y
# potencia del borde. tinte × factor = multiplicador final de la sombra.
PARAMETROS = {
    "tarde":    {"luz": (1.02, 1.00, 0.97), "factor_sombra": 0.78, "tinte_sombra": (0.95, 0.97, 1.06),
                 "color_rim": (1.00, 0.86, 0.66), "fuerza_rim": 0.16, "potencia_rim": 3.0},
    "manana":   {"luz": (1.00, 1.00, 1.00), "factor_sombra": 0.80, "tinte_sombra": (0.95, 0.98, 1.05),
                 "color_rim": (1.00, 0.97, 0.90), "fuerza_rim": 0.14, "potencia_rim": 3.0},
    "amanecer": {"luz": (1.02, 0.99, 0.96), "factor_sombra": 0.78, "tinte_sombra": (0.96, 0.96, 1.06),
                 "color_rim": (1.00, 0.82, 0.72), "fuerza_rim": 0.14, "potencia_rim": 3.0},
    "noche":    {"luz": (0.97, 0.98, 1.02), "factor_sombra": 0.72, "tinte_sombra": (0.88, 0.94, 1.12),
                 "color_rim": (0.70, 0.80, 1.00), "fuerza_rim": 0.07, "potencia_rim": 3.5},
}


def activa():
    valor = os.environ.get("ALCALDE_TOON_PERSONAJES", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(TOON_PERSONAJES)


# Dirección unitaria HACIA el sol en el mundo del shader (= ejes de Ursina, y arriba), la que usa para N·L.
def direccion_hacia_sol(direccion_luz=DIRECCION_SOL):
    x, y, z = direccion_luz
    largo = math.sqrt(x * x + y * y + z * z)
    if largo <= 1e-9:
        x, y, z = DIRECCION_SOL
        largo = math.sqrt(x * x + y * y + z * z)
    return (-x / largo, -y / largo, -z / largo)


def _mezclar(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(len(a)))


# Valores ya listos para el shader de UNA paleta.
def _uniforms_de_paleta(nombre):
    p = PARAMETROS[nombre]
    sombra = tuple(p["factor_sombra"] * c for c in p["tinte_sombra"])
    rim = tuple(p["fuerza_rim"] * c for c in p["color_rim"])
    return {"luz": tuple(p["luz"]), "sombra": sombra, "rim": rim + (p["potencia_rim"],)}


# Uniforms del shader para la mezcla (a, b, t) de ciclo_dia_calculos.mezcla_de_hora.
def parametros_de_mezcla(a, b, t):
    ua, ub = _uniforms_de_paleta(a), _uniforms_de_paleta(b)
    t = min(1.0, max(0.0, float(t)))
    return {"direccion": direccion_hacia_sol(), "banda": (CENTRO_BANDA, SEMIANCHO_BANDA),
            "luz": _mezclar(ua["luz"], ub["luz"], t), "sombra": _mezclar(ua["sombra"], ub["sombra"], t),
            "rim": _mezclar(ua["rim"], ub["rim"], t)}


# Uniforms del shader a esa hora (0..24; None = la tarde de siempre). Claves: direccion (vec3, hacia el sol, y arriba),
# banda (centro, semiancho), luz (vec3), sombra (vec3), rim (rgb × fuerza, potencia).
def parametros_toon(hora):
    return parametros_de_mezcla(*ciclo.mezcla_de_hora(hora))


# Clave del escalón vigente: si no cambia, no hace falta reescribir los uniforms.
def clave_de_hora(hora):
    return ciclo.mezcla_de_hora(hora)
