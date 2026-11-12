# Rutas de misión por personaje (docs/PLAN_CLARIDAD_JUEGO.md §2.4): lógica pura, sin ursina ni frontend.
#
# Cada rol recorre una RUTA que mezcla todo: sus misiones de verificar (en orden de catálogo), luego las genéricas, y
# entre ellas las digitales: la 2.ª misión es el parkour y la 4.ª la investigación (mundo digital). Las digitales son las
# MISMAS para todos (ids compartidos): como `SistemaMisiones._completadas` es global, en hot-seat la que ya hizo otro
# jugador se salta sola. Sin misiones digitales en el catálogo (en línea o sin GameState) la ruta es el orden de siempre.
#
# BANDERA. RUTAS = False (o ALCALDE_RUTAS=0): `SistemaMisiones._buscar_pendiente` usa el orden de antes.
#
# `mision` se usa por duck typing (rol, tipo): este módulo no importa misiones.py (misiones.py lo importa a él).

import os

RUTAS = True

# Posición (1-based) de cada misión digital en la ruta de un rol.
POSICIONES_DIGITALES = {"parkour": 2, "investigacion": 4}

_SI = ("1", "true", "si", "sí", "on")
_NO = ("0", "false", "no", "off")


def activo():
    """¿Hay rutas por personaje? ALCALDE_RUTAS=1/0 manda sobre la constante (se lee en cada llamada)."""
    valor = os.environ.get("ALCALDE_RUTAS", "").strip().lower()
    if valor in _SI:
        return True
    if valor in _NO:
        return False
    return bool(RUTAS)


def ruta_de_rol(catalogo, rol):
    """Lista de misiones de la ruta del rol: las suyas en orden de catálogo, luego las genéricas (rol None), con la
    primera de cada tipo de POSICIONES_DIGITALES movida a su posición (si la ruta es más corta, al final)."""
    propias = [m for m in catalogo if m.rol == rol]
    genericas = [m for m in catalogo if m.rol is None] if rol is not None else []
    ruta = propias + genericas
    for tipo, posicion in sorted(POSICIONES_DIGITALES.items(), key=lambda par: par[1]):
        digital = next((m for m in ruta if m.tipo == tipo), None)
        if digital is None:
            continue
        ruta.remove(digital)
        ruta.insert(min(posicion - 1, len(ruta)), digital)
    return ruta
