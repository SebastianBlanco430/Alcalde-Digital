# Suavizado de bordes (MSAA) del mundo 3D. Los cálculos puros están en frontend/suavizado_calculos.py.
#
#   1. configurar_antes_de_ventana(ajustes): ANTES de Ursina(...) carga en Panda «framebuffer-multisample 1» y
#      «multisamples N» para que la ventana nazca con un búfer multimuestra (no se puede cambiar sin reabrirla: por eso
#      el ajuste «Suavizado» se aplica al reiniciar).
#   2. aplicar_tras_ventana(): con la ventana abierta pone AntialiasAttrib.MAuto SOLO en `render` (el mundo, `scene`).
#      La interfaz (camera.ui, que cuelga de otra raíz) no lo lleva: sin el atributo Panda apaga GL_MULTISAMPLE al
#      dibujarla, así el texto del HUD sale idéntico, nítido. Si la ventana no obtuvo MSAA avisa una vez y sigue.
#   3. propiedades_filtro(): FrameBufferProperties para el búfer del FilterManager (daltonismo/pixelado dibujan el mundo
#      ahí y el MSAA de la ventana no llega). Si ese búfer falla, desactivar_filtro() deja el modo sin MSAA (un aviso).
#
# Banderas reversibles: MSAA = False en el código o ALCALDE_MSAA=0 -> no se carga el prc ni se toca `render`: todo
# exactamente como antes. ALCALDE_MSAA=2/4 fuerza el valor (para medir) sin mirar el ajuste.

import os

from frontend import suavizado_calculos as calc

MSAA = True                 # bandera reversible: False = sin suavizado, pase lo que pase con el ajuste

_pedidas = 0                # muestras pedidas a la ventana (0 = no se cargó nada)
_obtenidas = None           # VIS-009: muestras de la VENTANA (None = aún sin ventana; 0 = sin MSAA)
_muestras_filtro = None     # VIS-009 (ajustes Feria): muestras del búfer del pase final donde se dibuja el mundo
                            # (None = no hay pase: el mundo va directo a la ventana)
_ventana_ok = False         # la ventana obtuvo un búfer multimuestra
_filtro_ok = True           # el búfer del filtro de pantalla puede pedir MSAA (False tras un fallo)
_avisados = set()


def _avisar(clave, texto):
    if clave not in _avisados:
        _avisados.add(clave)
        print(f"[Suavizado] {texto}", flush=True)


# VIS-009 · Muestras que de verdad tiene el MUNDO. En Windows (wgl) la ventana recibe el formato de píxel con más muestras
# que da el driver (8× en una RX 7600 aunque se pidan 2 o 4: «multisamples» es un mínimo), pero con el pase final (tinta
# y grading por salud, siempre puestos con los ajustes de serie) el mundo NO se dibuja en la ventana sino en el búfer
# fuera de pantalla del FilterManager, que es un FBO y recibe EXACTAMENTE las muestras pedidas (medido: 2 -> 2, 4 -> 4).
# La ventana ya solo recibe el cuadro final y la interfaz (que va sin MSAA). Así que lo que se aplica es lo de ese búfer;
# solo sin pase (banderas de desarrollo apagadas) el mundo usa la ventana y su MSAA.
def obtenidas():
    if _obtenidas is None:
        return None
    return calc.muestras_del_mundo(_obtenidas, _muestras_filtro)


def registrar_filtro(muestras):
    """Lo llama el pase de pantalla (frontend/daltonismo.py) al montarse (muestras de su búfer del mundo) y al
    desmontarse (None)."""
    global _muestras_filtro
    _muestras_filtro = None if muestras is None else max(0, int(muestras))


def pedidas():
    return _pedidas


def activo():
    return _pedidas > 0 and _ventana_ok


# Antes de abrir la ventana. `ajustes` = backend.logica.ajustes.Ajustes (o None). Devuelve las muestras pedidas.
def configurar_antes_de_ventana(ajustes=None):
    global _pedidas
    _pedidas = 0
    if not MSAA:
        return 0
    muestras = calc.muestras_pedidas(os.environ.get("ALCALDE_MSAA"), getattr(ajustes, "suavizado", 0))
    lineas = calc.lineas_prc(muestras)
    if lineas:
        from panda3d.core import loadPrcFileData
        for linea in lineas:
            loadPrcFileData("", linea)
        _pedidas = muestras
    return _pedidas


# Con la ventana ya abierta (y antes de crear entidades). Nunca lanza.
def aplicar_tras_ventana():
    global _ventana_ok, _obtenidas
    _ventana_ok = False
    _obtenidas = 0
    if _pedidas <= 0:
        return False
    try:
        from panda3d.core import AntialiasAttrib
        from ursina import application
        base = application.base
        obtenidas = base.win.getFbProperties().getMultisamples()
        if not calc.ventana_tiene_msaa(obtenidas):
            _avisar("ventana", f"la ventana no obtuvo MSAA {_pedidas}x (tiene {obtenidas}); sigo sin suavizado.")
            return False
        base.render.setAntialias(AntialiasAttrib.MMultisample)
        _ventana_ok = True
        _obtenidas = int(obtenidas)
        print(f"[Suavizado] MSAA {obtenidas}x en el mundo.", flush=True)
        return True
    except Exception as error:      # noqa: BLE001  el suavizado nunca impide arrancar
        _avisar("ventana", f"no se pudo activar ({error}); sigo sin suavizado.")
        return False


# FrameBufferProperties para un búfer del FilterManager, o None si el prc de MSAA no se cargó (llamada idéntica a la de
# siempre). Con el prc cargado SIEMPRE se fija el número explícito: FrameBufferProperties.getDefault() ya lleva las
# muestras del prc y, sin fijarlo, todos los búferes del filtro las pedirían. `con_msaa` = este búfer las quiere.
def propiedades_filtro(con_msaa=True):
    if _pedidas <= 0:
        return None
    from panda3d.core import FrameBufferProperties
    propiedades = FrameBufferProperties()
    muestras = _pedidas if (con_msaa and _ventana_ok and _filtro_ok) else 0
    propiedades.setMultisamples(muestras)
    return propiedades


def filtro_con_msaa():
    return _pedidas > 0 and _ventana_ok and _filtro_ok


# El búfer multimuestra del filtro falló: desde ahora el filtro va sin MSAA (un único aviso).
def desactivar_filtro(motivo):
    global _filtro_ok
    _filtro_ok = False
    _avisar("filtro", f"el filtro de pantalla no admite MSAA ({motivo}); ese modo sigue sin suavizado.")
