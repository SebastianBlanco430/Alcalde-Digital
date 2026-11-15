# Rendimiento: recolector de basura de Python sin tirones durante el juego.
#
# El recolector de Python recorre de vez en cuando TODOS los objetos vivos (generación 2). Con el mundo cargado son
# millones (entidades, mallas, tablas de la favela), y esa pasada cae en medio de un frame: un tirón que se nota en el
# «1 % bajo». Aquí:
#   - al terminar de cargar (instalar(), desde main tras crear las escenas) se hace una recolección completa y
#     gc.freeze() pasa todo lo vivo a la generación permanente: las pasadas siguientes ya no lo recorren;
#   - los umbrales se suben (UMBRALES) para que las pasadas jóvenes sean menos frecuentes;
#   - recolectar_ahora() hace una pasada completa y vuelve a congelar (disponible para llamarla en un momento en que no
#     se note, p. ej. una transición; hoy no se engancha en ningún sitio).
# La memoria no crece sin control: los ciclos se siguen recogiendo, solo que en otro momento y sin recorrer lo congelado.
#
# BANDERA. GC_SUAVE = False, ALCALDE_SIN_GC_SUAVE=1 o ALCALDE_SIN_RENDIMIENTO=1: el recolector de siempre.

import gc
import os
import sys

GC_SUAVE = True
UMBRALES = (50000, 50, 100)     # por defecto en CPython 3.12: (700, 10, 10)

_estado = {"instalado": False, "umbrales_antes": None}


def activo():
    if os.environ.get("ALCALDE_SIN_RENDIMIENTO", "").strip() == "1":
        return False
    return GC_SUAVE and os.environ.get("ALCALDE_SIN_GC_SUAVE", "").strip() != "1"


def instalar():
    """Recolecta, congela lo cargado y sube los umbrales. Devuelve True si se aplicó. Nunca lanza."""
    if not activo() or _estado["instalado"]:
        return False
    try:
        _estado["umbrales_antes"] = gc.get_threshold()
        gc.collect()
        gc.freeze()
        gc.set_threshold(*UMBRALES)
        _estado["instalado"] = True
        return True
    except Exception as error:
        print(f"[gc_suave] no se pudo aplicar ({type(error).__name__}: {error})", file=sys.stderr)
        return False


def recolectar_ahora():
    """Pasada completa y nuevo congelado (en una transición, donde un tirón no se ve). Nada si no está instalado."""
    if not _estado["instalado"]:
        return
    try:
        gc.collect()
        gc.freeze()
    except Exception:
        pass


def desinstalar():
    """Deja el recolector como estaba (pruebas)."""
    if not _estado["instalado"]:
        return
    gc.unfreeze()
    if _estado["umbrales_antes"]:
        gc.set_threshold(*_estado["umbrales_antes"])
    _estado["instalado"] = False
