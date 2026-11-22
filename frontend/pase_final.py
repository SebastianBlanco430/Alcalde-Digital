# Pase final único (T3 + M6): conecta la TINTA de pantalla y el GRADING de salud al FiltroPantalla de frontend/daltonismo.py
# (mismo shader que el daltonismo, mismo FilterManager que el pixelado). Los cálculos están en
# frontend/pase_final_calculos.py (puro, con pruebas). Lo instala daltonismo.instalar(); no hace falta tocar main.py ni
# frontend/extensiones.py.
#
#   - Ajuste «Tinta» (campo `tinta_pantalla`: «contornos» | «comic»), en vivo: Cómic = tinta de pantalla además de los
#     contornos de casco; Contornos = solo los de casco.
#   - Una tarea de Panda por frame copia al shader lo que cambia: plano cercano/lejano de base.camLens y el tamaño de
#     la ventana (para el paso del Sobel). Cada PERIODO_UNIFORMES s lee la niebla (scene.fog_color/fog_density, que
#     ciudad_viva mantiene) y el Ambiente (SOLO ambiente_vivo.obtener()). El grading solo se aplica con el mundo a la vista
#     (ambiente_vivo se alimenta: su versión sube); en menús e interiores va neutro (1, (1, 1, 1)).
# Con ALCALDE_TINTA_PANTALLA=0 y ALCALDE_SATURACION_SALUD=0 no se instala nada (el pase es el de siempre).

import sys

from frontend import pase_final_calculos as calc

_estado = {"filtro": None, "t": 0.0, "version": None, "tarea": None}


def _modo_tinta(ajustes):
    return getattr(ajustes, "tinta_pantalla", "comic")


def ui_sin_niebla():
    """R2: la niebla del mundo no llega al UI (camera.ui_render: fog_color nulo con prioridad alta). True si se aplicó."""
    if not calc.ui_sin_niebla_activa():
        return False
    try:
        from panda3d.core import LVecBase4f
        from ursina import camera
        camera.ui_render.set_shader_input("fog_color", LVecBase4f(*calc.NIEBLA_NULA), calc.PRIORIDAD_UI_SIN_NIEBLA)
        return True
    except Exception as error:      # pragma: no cover
        print(f"[pase_final] el UI sigue con niebla ({error})", file=sys.stderr)
        return False


def instalar(gestor, filtro):
    """Engancha el pase final al `filtro` (daltonismo.FiltroPantalla). Devuelve True si quedó instalado."""
    con_tinta, con_grading = calc.tinta_activa(), calc.saturacion_activa()
    if not con_tinta and not con_grading:
        return False
    _estado["filtro"] = filtro

    def reaccionar(ajustes, cambiadas):
        if "tinta_pantalla" in cambiadas:
            filtro.fijar_post(calc.tinta_en_pantalla(con_tinta, _modo_tinta(ajustes)), con_grading)
            _actualizar(forzar=True)

    gestor.suscribir(reaccionar)
    if con_tinta:
        try:
            from frontend import hud_ajustes
            hud_ajustes.registrar()      # fila «Tinta» en la pestaña «Interfaz» (idempotente)
        except Exception as error:      # pragma: no cover
            print(f"[pase_final] sin fila «Tinta» en Ajustes ({error})", file=sys.stderr)
    try:
        from ursina import application
        if _estado["tarea"] is None:
            _estado["tarea"] = application.base.taskMgr.add(_tarea, "pase-final", sort=45)
    except Exception as error:      # pragma: no cover - sin ventana (pruebas)
        print(f"[pase_final] sin tarea de uniformes ({error})", file=sys.stderr)
    return True


def _tarea(task):
    try:
        from panda3d.core import ClockObject
        dt = ClockObject.getGlobalClock().getDt()
        _estado["t"] -= dt
        _actualizar(forzar=_estado["t"] <= 0)
    except Exception as error:      # pragma: no cover
        print(f"[pase_final] {type(error).__name__}: {error}", file=sys.stderr)
        return task.done
    return task.cont


def _actualizar(forzar=False):
    filtro = _estado["filtro"]
    if filtro is None or not filtro.activo:
        return
    from ursina import application
    base = application.base
    lente = base.camLens
    valores = {}
    if lente is not None:
        orto = 1.0 if type(lente).__name__ == "OrthographicLens" else 0.0
        valores["camara"] = (round(float(lente.getNear()), 4), round(float(lente.getFar()), 3), orto)
    # El paso va en píxeles de la VENTANA (no del búfer del mundo): con pixelado la línea sigue midiendo 1 px a 720p
    # y no un píxel gordo del mundo reducido.
    ventana = base.win
    if ventana is not None and ventana.getYSize() > 0:
        valores["paso"] = calc.paso_texel_con_grosor(ventana.getXSize(), ventana.getYSize(),
                                                     calc.grosor_tinta(calc.tinta_gruesa_activa()))
    if forzar:
        _estado["t"] = calc.PERIODO_UNIFORMES
        valores.update(_lentos())
    filtro.fijar_uniformes(valores)


def _lentos():
    from ursina import scene
    from frontend import ambiente_vivo
    rgb, fuerza, fin = calc.niebla_de(scene.fog_color, scene.fog_density)
    version = ambiente_vivo.version()
    en_mundo = _estado["version"] is not None and version != _estado["version"]
    _estado["version"] = version
    sat, tinte = calc.uniformes_grading(ambiente_vivo.obtener(), en_mundo, calc.saturacion_activa())
    return {
        "niebla": (*[round(c, 4) for c in rgb], round(fuerza, 4)),
        "rango": (round(fin, 2), calc.UMBRAL_ALTO, calc.DESVANECE_INICIO, calc.DESVANECE_FIN),
        "tinta": (*calc.COLOR_TINTA, calc.UMBRAL_BAJO),
        "saturacion": sat,
        "tinte": tinte,
        "extra": calc.uniformes_r5(calc.pliegues_activos(), calc.sombra_lejos_activa()),
    }
