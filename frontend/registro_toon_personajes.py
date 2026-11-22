# Punto 5 del pulido: liga los uniforms del toon de los personajes (frontend/skinning_gpu.py) al ciclo de día del cielo.
# Lo llama frontend/extensiones.py. Cada PERIODO_TOON s (no cada frame) lee la hora de la MISMA fuente que el cielo
# (CieloDegradado._hora(): ALCALDE_HORA_CIELO o el reloj de la partida) y, solo si cambió el escalón de mezcla, reescribe
# los 5 uniforms con UN set_shader_input cada uno sobre `render`: todos los personajes los heredan; nada por personaje.
# Sin mundo visible (menú, interiores, cinemáticas fuera de la ciudad) o sin ciclo de día: la tarde de siempre.
# Sin el toon (apagado por defecto; ALCALDE_TOON_PERSONAJES=1 lo enciende) o con el skinning por CPU no se instala nada.

import sys

from frontend import toon_calculos as toon


def _aviso(texto):
    print(f"[toon_personajes] {texto}", file=sys.stderr)


# Hora que manda sobre los personajes: la del cielo si el mundo está a la vista y su ciclo de día funciona; si no, None.
def hora_de(escena_mundo):
    if not getattr(escena_mundo, "enabled", False):
        return None
    cielo = getattr(getattr(escena_mundo, "ciudad", None), "cielo", None)
    if cielo is None or getattr(cielo, "_paletas", None) is None:      # sin ciclo el cielo es la tarde fija
        return None
    try:
        return cielo._hora()
    except Exception:          # noqa: BLE001 — sin reloj legible, la tarde
        return None


def registrar(gestor, conexion, escena_mundo):
    from frontend import skinning_gpu
    if not (toon.activa() and skinning_gpu.activo()):
        return None
    try:
        from ursina import Entity, scene, time

        class RelojToon(Entity):
            def __init__(self):
                super().__init__(parent=scene, name="reloj_toon")
                self._t = 0.0
                self._clave = None

            def update(self):
                self._t -= time.dt
                if self._t > 0:
                    return
                self._t = toon.PERIODO_TOON
                if not skinning_gpu.revisar_toon():     # el toon no compiló (o no hay): nada que actualizar
                    return
                hora = hora_de(escena_mundo)
                clave = toon.clave_de_hora(hora)
                if clave != self._clave:
                    self._clave = clave
                    skinning_gpu.fijar_parametros(toon.parametros_de_mezcla(*clave))

        conexion.reloj_toon = RelojToon()
        return conexion.reloj_toon
    except Exception as error:      # noqa: BLE001 — sin reloj, los personajes quedan con la tarde
        _aviso(f"no instalado ({type(error).__name__}: {error}); los personajes quedan con la luz de la tarde")
        return None
