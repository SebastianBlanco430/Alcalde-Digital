# Tutorial en viñetas (docs/PLAN_CLARIDAD_JUEGO.md §2.3). frontend/extensiones.py llama a registrar(); no se edita main.py.
#
#   - CUÁNDO: la primera vez que el mundo queda activo con una partida NUEVA (no al «Continuar»: registro_guardado marca
#     `conexion.partida_restaurada`; nunca en línea).
#   - QUÉ: backend/datos/tutorial_vinetas.json con el componente genérico de frontend/cinematica_final.crear_vinetas:
#     5 viñetas de cómic (historia, los 3 indicadores, el medidor y los finales) y un recorrido del HUD con viñetas «foco»
#     que señalan cada elemento REAL (si no está en pantalla, el bocadillo sale centrado, sin foco).
#   - Mientras está abierto es un bloqueador de la escena: controles congelados y el reloj no corre. Durante el recorrido
#     del HUD, `senalando_hud()` pide al brazalete, al medidor y al chip del reloj que NO se escondan por ese bloqueador.
#   - Espacio / Enter / clic avanzan, Escape lo salta. Se vuelve a ver desde la pausa: botón «Cómo se juega».
#
# BANDERA. TUTORIAL = False (o ALCALDE_TUTORIAL=0): nada de esto, el juego queda como antes.

import json
import os
import sys
from pathlib import Path

TUTORIAL = True
RUTA_VINETAS = Path(__file__).resolve().parent.parent / "backend" / "datos" / "tutorial_vinetas.json"
# Elementos del HUD que recorre la parte 2 (uno por viñeta «foco»).
ELEMENTOS_FOCO = ("panel_turno", "minimapa", "telefono_ui", "brazalete", "medidor", "reloj", "dinero", "aviso_e")
MAX_CARACTERES = 220
TEXTO_BOTON_PAUSA = "Cómo se juega"

_estado = {"entidad": None, "senalando": False}


def activo():
    """¿Hay tutorial? ALCALDE_TUTORIAL=1/0 manda sobre la constante."""
    valor = os.environ.get("ALCALDE_TUTORIAL", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(TUTORIAL)


def cargar_datos(ruta=None):
    """El JSON del tutorial: {"saltar", "continuar", "vinetas": [...]}. ValueError si falta algo."""
    with open(ruta or RUTA_VINETAS, encoding="utf-8") as archivo:
        datos = json.load(archivo)
    vinetas = datos.get("vinetas")
    if not isinstance(vinetas, list) or not vinetas:
        raise ValueError("tutorial_vinetas.json no trae viñetas.")
    for vineta in vinetas:
        if not str(vineta.get("titulo", "")).strip() or not str(vineta.get("texto", "")).strip():
            raise ValueError(f"Viñeta del tutorial sin título o sin texto: {vineta!r}")
        if vineta.get("tipo") == "foco" and vineta.get("elemento") not in ELEMENTOS_FOCO:
            raise ValueError(f"Viñeta «foco» con un elemento desconocido: {vineta.get('elemento')!r}")
    return datos


def cargar_vinetas(ruta=None):
    return list(cargar_datos(ruta)["vinetas"])


def abierto():
    """¿El tutorial está en pantalla?"""
    return _estado["entidad"] is not None


def senalando_hud():
    """True durante el recorrido del HUD: lo señalado tiene que verse aunque el tutorial sea un bloqueador."""
    return bool(_estado["senalando"]) and abierto()


def debe_abrirse(flujo, restaurada, en_linea):
    """¿Toca el tutorial para este flujo recién visto? Solo partida local nueva y en curso (puro)."""
    if flujo is None or restaurada or en_linea:
        return False
    try:
        return not flujo.partida_terminada()
    except Exception:
        return False


def _aviso(texto):
    print(f"[tutorial] {texto}", file=sys.stderr)


# ---------------------------------------------------------------- foco: rectángulo de un elemento real del HUD

def _a_la_vista(entidad):
    """La entidad y todos sus padres (hasta camera.ui) están activos."""
    from ursina import camera
    e = entidad
    while e is not None and e is not camera.ui and hasattr(e, "enabled"):
        if not e.enabled:
            return False
        e = getattr(e, "parent", None)
    return True


def rect_de_entidades(entidades):
    """(x, y, ancho, alto) en camera.ui que envuelve lo que se ve de `entidades`; None si alguna no está a la vista."""
    from ursina import camera
    x0 = y0 = float("inf")
    x1 = y1 = float("-inf")
    for entidad in entidades:
        if entidad is None or not _a_la_vista(entidad):
            return None
        limites = entidad.getTightBounds(camera.ui)
        if not limites:
            return None
        minimo, maximo = limites                    # ursina trabaja en Y-arriba: X a la derecha, Y arriba
        x0, x1 = min(x0, minimo.x), max(x1, maximo.x)
        y0, y1 = min(y0, minimo.y), max(y1, maximo.y)
    if x1 <= x0 or y1 <= y0:
        return None
    return ((x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0)


def _entidades_de(elemento, escena, conexion):
    """Las entidades reales de cada elemento del recorrido (None = no existe en esta partida)."""
    hud = escena.hud
    if elemento == "panel_turno":
        return [hud.panel_turno]
    if elemento == "minimapa":
        return [hud.minimapa.fondo]
    if elemento == "telefono_ui":
        return [hud.telefono_ui.icono]
    if elemento == "brazalete":
        return [conexion.vigia_manillas.vista.chip]
    if elemento == "medidor":
        return [conexion.etapas_final.medidor]
    if elemento == "reloj":
        return [conexion.vigia_reloj.vista.chip_entidad]
    if elemento == "dinero":
        return [escena.economia.chip]
    if elemento == "aviso_e":
        return [hud.aviso]
    return None


# ---------------------------------------------------------------- registro

def registrar(gestor, conexion, escena_mundo):
    if not activo():
        return None
    try:
        datos = cargar_datos()
    except (OSError, ValueError) as error:
        _aviso(f"no instalado ({type(error).__name__}: {error})")
        return None
    try:
        return _instalar(conexion, escena_mundo, datos)
    except Exception as error:
        _aviso(f"no instalado ({type(error).__name__}: {error})")
        return None


def _instalar(conexion, escena, datos):
    from ursina import Entity, destroy

    from frontend.componentes import BotonSecundario, a_unidades

    basura = []                                 # secuencias ya terminadas, por destruir

    def foco_de(elemento):
        try:
            entidades = _entidades_de(elemento, escena, conexion)
        except AttributeError:                  # ese módulo no está instalado (bandera apagada): sin foco
            return None
        return None if not entidades else rect_de_entidades(entidades)

    def _raton():
        try:
            escena._sincronizar_raton()
        except Exception:
            pass

    def al_terminar():
        if _estado["entidad"] is not None:
            basura.append(_estado["entidad"])
        _estado.update(entidad=None, senalando=False)
        _raton()

    def al_poner(vineta, indice):
        _estado["senalando"] = vineta.get("tipo") == "foco"

    def guardia():                              # Escape lo salta: que no deje la pausa abierta debajo
        if getattr(escena, "en_pausa", False):
            escena.alternar_pausa(False)

    def abrir():
        if abierto():
            return False
        from frontend.cinematica_final import crear_vinetas
        _estado["senalando"] = False
        _estado["entidad"] = crear_vinetas(datos["vinetas"], al_terminar, segundos=None, guardia=guardia, rotulos=datos,
                                           foco_de=foco_de, al_poner=al_poner, parent=escena.hud)
        _raton()
        return True

    def cerrar():
        entidad = _estado["entidad"]
        if entidad is not None:
            entidad.saltar()

    escena.registrar_bloqueador(abierto, cerrar)        # congela los controles y pausa el reloj (motivo PANEL)

    def ver_de_nuevo():
        escena.alternar_pausa(False)
        abrir()

    # Botón en la pausa, a la derecha del panel (el menú no tiene sitio dentro; solo con el ratón).
    try:
        from frontend import menu_pausa
        boton = BotonSecundario(TEXTO_BOTON_PAUSA, al_clic=ver_de_nuevo, ancho=0.30, alto=a_unidades(50), tamano_fuente_px=20,
                                parent=escena.menu_pausa, position=(menu_pausa.ANCHO / 2 + 0.04 + 0.15, 0.19, -0.001))
    except Exception as error:
        boton = None
        _aviso(f"botón de la pausa no instalado ({type(error).__name__}: {error})")

    class VigiaTutorial(Entity):
        """Solo corre con el mundo activo (cuelga del HUD): abre el tutorial al ver una partida nueva."""

        def __init__(self, **opciones):
            super().__init__(**opciones)
            self._flujo = None
            self._pendiente = False
            self.abrir, self.cerrar, self.boton = abrir, cerrar, boton
            self.veces = 0

        def update(self):
            while basura:
                destroy(basura.pop())
            flujo = escena.flujo
            if flujo is not self._flujo:
                self._flujo = flujo
                restaurada = bool(getattr(conexion, "partida_restaurada", False))
                conexion.partida_restaurada = False
                self._pendiente = debe_abrirse(flujo, restaurada, getattr(escena, "online", None) is not None)
            if self._pendiente and not getattr(escena, "_cinematica", False) and not escena.en_pausa:
                self._pendiente = False
                if abrir():
                    self.veces += 1

    conexion.tutorial = VigiaTutorial(parent=escena.hud)
    return conexion.tutorial
