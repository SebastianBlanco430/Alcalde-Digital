# Piel BOTW de las pantallas de la persona B: la parte PURA (no importa ursina; se prueba en tests/test_b_ui_botw.py).
# El menú de inicio ya tiene el aspecto de Zelda BOTW (frontend/menu_botw.py); la persona A rediseña la base compartida
# (estilo.py, componentes.py) y aquí se ajusta la COMPOSICIÓN de las pantallas de B (trabajos, parkour, paneles de final
# y de la semana, propagación, grafo, red social y todo el multijugador en línea) con las mismas reglas: títulos en
# cursiva con sombra plana de tinta, velo violeta detrás del contenido, la flecha amarilla junto al control enfocado y
# entrada escalonada (sin movimiento con «reducir movimiento»). La parte visual está en frontend/ui_botw_b.py.
#
# Colores y medidas: NO se inventan. Primero los que publique A en frontend/ui_botw_calculos.py (si existe); si no, los
# del menú BOTW (menu_botw_calculos: TINTA, VELO, AMARILLO, BLANCO) y los de estilo.py. Solo es propio lo que no existe
# en ninguno de los tres (las medidas de composición de abajo).
#
# Bandera compartida ALCALDE_UI_BOTW (por defecto encendida): =0 deja las pantallas de B como estaban. Se lee del
# entorno, sin importar nada de A.
#
#   activa()                  ¿piel BOTW?
#   paleta()                  {"tinta", "velo", "amarillo", "blanco", "texto", "tenue"} (RGB 0-255)
#   u(px)                     píxeles a 720p -> unidades de camera.ui
#   entrada(t, indice, reducido)  (alfa, desplazamiento x) de la pieza `indice` de una pantalla que entra
#   x_flecha(x_izq, ancho_flecha) x del centro de la flecha a la izquierda de un control

import os

from frontend import estilo
from frontend import menu_botw_calculos as menu

UI_BOTW = True
_NO = ("0", "false", "no", "off")
_SI = ("1", "true", "si", "sí", "on")

# Composición propia (no existe en estilo ni en el menú): sombra de los títulos de panel, alfa del velo detrás de un
# panel y separación de la flecha del control enfocado, en px a 720p.
SOMBRA_TITULO_PX = 2
ALFA_VELO_PANEL = 0.55
SEPARACION_FLECHA_PX = 10
# La de la opción seleccionada del menú BOTW
FUENTE_TITULO = "AtkinsonHyperlegible-BoldItalic.ttf"


def activa():
    """¿Piel BOTW? ALCALDE_UI_BOTW=1/0 manda sobre UI_BOTW (se lee en cada llamada)."""
    valor = os.environ.get("ALCALDE_UI_BOTW", "").strip().lower()
    if valor in _NO:
        return False
    if valor in _SI:
        return True
    return bool(UI_BOTW)


def _de_a():
    """El módulo de constantes BOTW de la persona A, o None si aún no está en este árbol."""
    try:
        from frontend import ui_botw_calculos
        return ui_botw_calculos
    except ImportError:
        return None


# La paleta BOTW que publicó la persona A en estilo.py (constantes BOTW_*, docs/ESTILO_BOTW.md); si en este árbol aún
# no está, las del menú de inicio (menu_botw_calculos) y las de siempre de estilo.py.
_DE_ESTILO = {"tinta": "BOTW_TINTA", "velo": "BOTW_VELO", "amarillo": "BOTW_ACENTO", "blanco": "BOTW_TEXTO",
              "texto": "BOTW_TEXTO", "tenue": "BOTW_TEXTO_TENUE"}


def paleta():
    """Colores de la piel: los BOTW_* de estilo.py (de A), o los nombres de ui_botw_calculos si los publicara, o los del
    menú BOTW y de estilo.py."""
    a = _de_a()
    base = {"tinta": menu.TINTA, "velo": menu.VELO, "amarillo": menu.AMARILLO, "blanco": menu.BLANCO,
            "texto": estilo.COLOR_TEXTO, "tenue": estilo.COLOR_TEXTO_TENUE}
    for clave, nombre in _DE_ESTILO.items():
        valor = getattr(estilo, nombre, None)
        if isinstance(valor, tuple) and len(valor) >= 3:
            base[clave] = tuple(valor[:3])
    nombres = {"tinta": "TINTA", "velo": "VELO", "amarillo": "AMARILLO", "blanco": "BLANCO", "texto": "COLOR_TEXTO",
               "tenue": "COLOR_TEXTO_TENUE"}
    if a is not None:
        for clave, nombre in nombres.items():
            valor = getattr(a, nombre, None)
            if isinstance(valor, tuple) and len(valor) >= 3:
                base[clave] = tuple(valor[:3])
    return base


def u(px):
    return menu.u(px)


def entrada(t, indice, reducido=False):
    """(alfa, desplazamiento x en UI) de la pieza `indice`: la misma entrada escalonada de las opciones del menú."""
    return menu.entrada_opcion(t, indice, reducido)


def entrada_terminada(t, n, reducido=False):
    return menu.entrada_terminada(t, n, reducido)


def x_flecha(x_izq, ancho_flecha):
    """Centro x de la flecha que va a la izquierda de un control cuyo borde izquierdo está en `x_izq`."""
    return x_izq - u(SEPARACION_FLECHA_PX) - ancho_flecha / 2
