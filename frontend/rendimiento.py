# Ajustes de rendimiento generales (medidos con PStats en Windows; ver frontend/skinning_gpu.py para el
# de los personajes). Todo es opcional: cada bandera en False (o su variable de entorno) deja el
# comportamiento de siempre. ALCALDE_SIN_RENDIMIENTO=1 apaga los tres a la vez.
#
# 1. RECOLECTAR_ESTADOS = False: Panda 1.10 barre su caché de RenderState/TransformState cada frame
#    («garbageCollectStates» ~5 ms/frame con los ~3500 estados de la favela). Con la opción apagada los
#    estados se liberan al soltarse (lo que hacía Panda 1.9): sin barrido periódico. Se fija con
#    loadPrcFileData ANTES de abrir la ventana (configurar_panda()). ALCALDE_RECOLECTAR_ESTADOS=1 lo deja como antes.
#
# 2. SilenciadorAutomatico: el bucle de Ursina recorre en Python TODAS las entidades cada frame y, para las
#    que no tienen ignore=True, sube por sus padres (has_disabled_ancestor). Este silenciador marca
#    ignore=True, por tandas, a las entidades pasivas: sin update(), sin input()/text_input(), sin scripts, sin
#    animaciones atadas y cuyo shader no pide entradas continuas (o que están ocultas bajo un padre apagado).
#    Ursina usa `ignore` para saltar update(), input(), text_input(), scripts y entradas continuas; por eso las
#    entidades con input() nunca se silencian. Si una silenciada por él deja de ser pasiva, le devuelve
#    ignore=False. Nunca toca las que silenció otro código. ALCALDE_SIN_SILENCIADOR=1 lo apaga.

import os
import sys

from panda3d.core import loadPrcFileData
from ursina import Entity, scene

RECOLECTAR_ESTADOS = False
SILENCIADOR = True
TANDA = 120               # entidades revisadas por frame (la lista completa se recorre en pocos frames)


def _variable(nombre):
    return os.environ.get(nombre, "").strip() == "1"


def _todo_apagado():
    return _variable("ALCALDE_SIN_RENDIMIENTO")


def configurar_panda():
    if not RECOLECTAR_ESTADOS and not _variable("ALCALDE_RECOLECTAR_ESTADOS") and not _todo_apagado():
        loadPrcFileData("", "garbage-collect-states #f")


# Sin update(), input(), text_input(), scripts ni animaciones atadas. Las entradas continuas del shader (la
# posición de la cámara para la niebla) solo importan si la entidad se dibuja: con un ancestro apagado no se
# ve, así que también se puede silenciar; al volver a verse, revisar() la reactiva en la siguiente vuelta.
def _es_pasiva(e):
    for metodo in ("update", "input", "text_input"):
        if callable(getattr(e, metodo, None)):
            return False
    if getattr(e, "scripts", None):
        return False
    if getattr(e, "animations", None):
        return False
    shader = getattr(e, "shader", None)
    if shader is not None and getattr(shader, "continuous_input", None):
        return e.has_disabled_ancestor()
    return True


class SilenciadorAutomatico(Entity):

    def __init__(self, tanda=TANDA, **opciones):
        super().__init__(ignore_paused=True, **opciones)
        self.tanda = tanda
        self.silenciadas = set()      # ids de las que silenció ESTE objeto (las únicas que puede reactivar)
        self._indice = 0

    # Revisa una tanda de entidades (los tests pueden llamarlo a mano).
    def revisar(self, cantidad=None):
        entidades = scene.entities
        total = len(entidades)
        if not total:
            return
        for _ in range(min(total, cantidad or self.tanda)):
            if self._indice >= len(entidades):
                self._indice = 0
            e = entidades[self._indice]
            self._indice += 1
            if e is self or not e:
                continue
            clave = id(e)
            if clave in self.silenciadas:
                if not _es_pasiva(e):            # dejó de ser pasiva: vuelve a correr
                    e.ignore = False
                    self.silenciadas.discard(clave)
            elif not e.ignore and _es_pasiva(e):
                e.ignore = True
                self.silenciadas.add(clave)

    def update(self):
        self.revisar()


# 3. PICKING_SOLO_CON_CURSOR: cada frame Ursina lanza un rayo del ratón contra la UI y el mundo y, si no toca
#    nada, recorre TODAS las entidades buscando cuál quitar de «hover». Con el ratón capturado (cámara del
#    mundo: cursor oculto y fijo) no hay nada que señalar; se salta el picking con mouse.update_step (lo que
#    Ursina ofrece para eso) y vuelve a 1 en cuanto el cursor se libera (teléfono, pausa, menús). La
#    velocidad del ratón, que mueve la cámara, se sigue calculando: va antes del picking en mouse.update().
#    ALCALDE_CON_PICKING=1 lo apaga.
PICKING_SOLO_CON_CURSOR = True
_SIN_PICKING = 10 ** 9


class PickingSoloConCursor(Entity):

    def __init__(self, **opciones):
        super().__init__(ignore_paused=True, **opciones)

    def update(self):
        from ursina import mouse
        paso = _SIN_PICKING if mouse.locked else 1
        if mouse.update_step != paso:
            if paso == _SIN_PICKING:
                soltar_hover(mouse)
            mouse.update_step = paso


# Antes de dejar de hacer picking hay que soltar lo que el cursor señalaba: hovered_entity y `hovered` solo los
# limpia el picking, y mouse.input('left mouse down') llama a hovered_entity.on_click() sin más comprobación.
# Sin esto, el botón que cerró un menú (y capturó el ratón) se volvería a pulsar con el siguiente clic en el mundo.
def soltar_hover(mouse):
    mouse.hovered_entity = None
    mouse.collision = None
    mouse.unhover_everything_not_hit()     # con hovered_entity = None des-señala a todas (y llama on_mouse_exit)


def activo():
    return SILENCIADOR and not _variable("ALCALDE_SIN_SILENCIADOR") and not _todo_apagado()


def picking_activo():
    return PICKING_SOLO_CON_CURSOR and not _variable("ALCALDE_CON_PICKING") and not _todo_apagado()


# Lo llama main.crear_aplicacion() con la ventana ya abierta. Devuelve el silenciador (o None). Nunca lanza:
# si algo falla, se avisa y el juego sigue como siempre.
def instalar():
    try:
        if picking_activo():
            PickingSoloConCursor()
        return SilenciadorAutomatico() if activo() else None
    except Exception as error:      # noqa: BLE001 — una optimización nunca debe impedir jugar
        print(f"[rendimiento] no se pudo instalar ({error}); se sigue sin estas optimizaciones.", file=sys.stderr)
        return None
