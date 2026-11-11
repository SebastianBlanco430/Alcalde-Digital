# Guardado de la partida local en el juego (A5). frontend/extensiones.py llama a registrar(); no se edita main.py.
#   - Autoguardado: un vigía bajo el HUD del mundo guarda cada INTERVALO s y cada vez que cambia la misión o el turno,
#     siempre en un punto seguro (backend/logica/guardado.se_puede_guardar). Al terminar la partida borra el guardado.
#   - «Continuar»: si hay un guardado de ESTE mundo (mismo mapa y semilla), el menú de inicio ofrece continuarlo.
# Solo la partida local (hot-seat): el flujo en línea no es guardable y se ignora. Un guardado que no se puede restaurar
# se avisa por stderr, se borra y se sigue al flujo normal de «Empezar»: nunca impide jugar.

import sys

from backend.logica import guardado, mundo_config

INTERVALO = 10.0        # s entre dos autoguardados


def _mundo_id(mundo):
    return ("grande" if mundo_config.es_mundo_grande(mundo) else "chico"), getattr(mundo, "semilla", None)


def guardar_ahora(escena_mundo):
    """Guarda la partida del mundo si es un punto seguro. True si se escribió."""
    flujo = escena_mundo.flujo
    if flujo is None or getattr(escena_mundo, "online", None) is not None:
        return False
    mapa, semilla = _mundo_id(escena_mundo._mundo)
    return guardado.guardar(guardado.capturar(flujo, mapa, semilla))


def _crear_vigia(escena_mundo):
    from ursina import Entity, time

    class Autoguardado(Entity):

        def __init__(self, **opciones):
            super().__init__(**opciones)
            self._resta = INTERVALO
            self._clave = None
            self.guardados = 0

        def update(self):
            self.avanzar(time.dt)

        def avanzar(self, dt):
            flujo = escena_mundo.flujo
            if flujo is None or getattr(escena_mundo, "online", None) is not None or not hasattr(flujo, "misiones_a_dict"):
                return
            if flujo.partida_terminada():
                if self._clave != "fin":
                    self._clave = "fin"
                    guardado.borrar()             # la partida acabó: no hay nada que continuar
                return
            mision = flujo.mision_actual()
            clave = (id(flujo), flujo.sesion.numero_turno(), getattr(mision, "id", None))
            self._resta -= dt
            if clave != self._clave or self._resta <= 0.0:
                if guardar_ahora(escena_mundo):
                    self.guardados += 1
                    self._clave = clave
                self._resta = INTERVALO

    return Autoguardado(parent=escena_mundo.hud)


def registrar(gestor, conexion, escena_mundo):
    if not guardado.activo():
        return None
    try:
        from backend.datos.ciudad_3d import ESCALA_MUNDO
        from backend.datos.noticias_semilla import construir_arboles
        from backend.logica.estado_partida import EstadoPartida
        from frontend.conexion_flujo import INICIO

        mapa, semilla = _mundo_id(escena_mundo._mundo)

        def guardado_vigente():
            datos = guardado.cargar()
            return datos if guardado.compatible(datos, mapa, semilla) else None

        def continuar():
            datos = guardado_vigente()
            if datos is None:
                return conexion.ir_a_seleccion()
            try:
                flujo = guardado.restaurar(datos, EstadoPartida(*construir_arboles()), conexion._fabrica_flujo,
                                           ESCALA_MUNDO, mapa, semilla)
            except ValueError as error:
                print(f"[guardado] no se pudo continuar ({error}); se empieza una partida nueva", file=sys.stderr)
                guardado.borrar()
                return conexion.ir_a_seleccion()
            conexion.flujo = flujo
            conexion._volver_al_mundo()

        conexion.continuar_partida = continuar
        conexion.autoguardado = _crear_vigia(escena_mundo)
        inicio = gestor._escenas.get(INICIO)
        if inicio is not None and hasattr(inicio, "ofrecer_continuar"):
            inicio.ofrecer_continuar(continuar, lambda: guardado.resumen(guardado_vigente()) if guardado_vigente() else "")
        return conexion.autoguardado
    except Exception as error:
        print(f"[guardado] no instalado ({type(error).__name__}: {error})", file=sys.stderr)
        return None
