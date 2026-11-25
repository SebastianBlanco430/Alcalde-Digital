# Rádio Comunitária EN LÍNEA (paridad del multijugador). La radio de la partida local (frontend/radio_registro.py, de la
# persona A) no hace nada en línea porque allí no había reloj. Con el reloj de la sala (backend/red/multi_reloj.py y
# frontend/multi_reloj_linea.py) cada cliente pone SU radio a la vez que los demás:
#
#   - Mañana y noche salen en todos los clientes: la hora la manda el anfitrión, así que todos llegan a las 20:00 juntos.
#   - La noche: al ponerse la viñeta de la mañana la radio llama a flujo.pasar_noche(); en línea eso avisa al anfitrión
#     («noche_lista») y la noche pasa cuando todos la cerraron o a los 20 s (multi_reloj.PLAZO_NOCHE).
#   - Tras la noche fija el contexto de los NPC (tema del día y resultado de la sala: globos.fijar_contexto_hilo), igual
#     que en la local; el diario es el de toda la sala (llega con el mensaje «reloj» de la noche).
#
# No se edita la radio de A: se usa su clase pública Radio con el mismo constructor y radio_emision.crear_emision tal
# cual; solo cambia la condición de «en línea» del frame. El puente del final no se emite en línea (el final en línea
# tiene su propio camino). Si algo falla, la radio en línea se apaga y la noche la pasa el plazo del anfitrión.
#
# Bandera ALCALDE_MULTI_PARIDAD (backend/red/multi_reloj.activo); también la apagan ALCALDE_HILO_RADIO=0 / ALCALDE_HILO=0.

import sys

from backend.red import multi_reloj


def _avisar(texto):
    print(f"[radio en línea] {texto}", file=sys.stderr)


def con_reloj_sala(escena):
    """¿Partida en línea con el reloj de la sala? (lo único en lo que esta radio actúa)."""
    flujo = getattr(escena, "flujo", None)
    return getattr(escena, "online", None) is not None and getattr(flujo, "tiempo_en_linea", None) is not None


def crear_radio(escena_mundo, conexion):
    """La Radio de A para la partida en línea; None si la radio está apagada o no se puede crear."""
    from backend.logica import radio_guion
    from frontend import radio_registro
    if not radio_guion.activo():
        return None

    class RadioLinea(radio_registro.Radio):
        def avanzar(self, dt):
            if self.apagada or not con_reloj_sala(self.escena):
                return
            flujo = self.escena.flujo
            if not getattr(flujo, "tiempo_en_linea").reloj.recibido:
                # Aún no llegó la hora del anfitrión
                return
            try:
                self._avanzar(flujo, dt)
            except Exception as error:                   # noqa: BLE001
                self.apagada = True
                # sin radio, el reloj en línea avisa solo de la noche (multi_reloj_linea.TiempoEnLinea.avanzar_tiempo)
                flujo.retener_noches(False)
                _avisar(f"apagada ({type(error).__name__}: {error}); la noche la pasa el anfitrión")

        def puente(self, flujo):
            return False

    return RadioLinea(escena_mundo, conexion, radio_guion.GuionRadio())


def registrar(escena_mundo, conexion):
    """Vigía en el HUD del mundo que crea la radio en línea la primera vez que hace falta. Nunca lanza."""
    if not multi_reloj.activo():
        return None
    try:
        from ursina import Entity, time

        class VigiaRadioLinea(Entity):
            radio = None
            rota = False

            def update(self):
                if self.rota or not con_reloj_sala(escena_mundo):
                    return
                if self.radio is None:
                    try:
                        self.radio = crear_radio(escena_mundo, conexion)
                    except Exception as error:           # noqa: BLE001
                        _avisar(f"no instalada ({type(error).__name__}: {error})")
                        self.radio = None
                    if self.radio is None:
                        self.rota = True
                        return
                    escena_mundo.registrar_bloqueador(self.radio.abierta, self.radio.saltar)
                self.radio.avanzar(min(time.dt, 0.1))

        return VigiaRadioLinea(parent=escena_mundo.hud)
    except Exception as error:                           # noqa: BLE001
        _avisar(f"no instalada ({type(error).__name__}: {error})")
        return None
