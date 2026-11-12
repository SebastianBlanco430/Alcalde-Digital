# Avisos del cierre de las misiones en el mundo (A2d paso 3 / A3). frontend/extensiones.py llama a registrar(); no se
# edita main.py. Un vigía cuelga del HUD del mundo (solo corre con el mundo a la vista) y, en cada frame, recoge del flujo:
#   - los pagos de misión pendientes (FlujoConEconomia.vaciar_pagos_recientes): un «Recibiste R$ N.» por CADA misión
#     cerrada, también cuando varias digitales se cierran en cadena;
#   - el último veredicto aplicado a la confianza (FlujoConGameState.ultimo_veredicto): «Rumor bien juzgado · Confianza
#     de Ciudadanos +2».
# Los muestra de uno en uno (veredicto_calculos.ColaAvisos) en un aviso propio en la parte alta de la pantalla, para no
# pisar los de «E» ni los de la economía. Mientras hay una cinemática (salir del edificio) espera.
#
# Con las notificaciones del teléfono (frontend/notificaciones.py, ALCALDE_NOTIF_TELEFONO) cada texto llega como mensaje
# al teléfono del jugador activo (banner con el teléfono cerrado, tarjeta bajo el minimapa con el teléfono abierto) y no
# se pinta nada en el centro. En hot-seat van al teléfono de QUIEN JUGÓ la misión: al recogerlos el turno ya pasó, así
# que el vigía recuerda quién era el activo en el frame anterior (`SeguimientoJugador`); si ya no es su turno, el mensaje
# queda sin leer en su teléfono y le sale al empezar el siguiente.
#
# Sin economía no hay pagos y sin GameState no hay veredictos: el vigía no encuentra nada y no pinta nada. En línea
# tampoco (el flujo en línea no tiene esos atributos).

import sys

from frontend import notificaciones, veredicto_calculos as vc

Y_AVISO = 0.30          # centro del aviso en camera.ui (bajo el panel de turno y el minimapa, sobre el centro)


def recoger(flujo, visto):
    """Textos nuevos que deja `flujo` (puro, para las pruebas). `visto`: dict mutable con el último veredicto ya avisado."""
    textos = []
    vaciar = getattr(flujo, "vaciar_pagos_recientes", None)
    if callable(vaciar):
        textos += [vc.texto_pago(pago) for pago in vaciar()]
    veredicto = getattr(flujo, "ultimo_veredicto", None)
    if veredicto is not visto.get("veredicto"):
        visto["veredicto"] = veredicto
        textos.append(vc.texto_veredicto(veredicto))
    return [t for t in textos if t]


class SeguimientoJugador:
    """Quién jugó la misión que se acaba de cerrar (puro). El cierre pasa el turno ANTES de que el vigía recoja los
    textos, así que el autor es el activo que se vio en el frame anterior. `autor(activo)` se llama una vez por frame."""

    def __init__(self):
        self._visto = None

    def reiniciar(self, activo=None):
        self._visto = activo

    def autor(self, activo):
        previo = self._visto if self._visto is not None else activo
        self._visto = activo
        return previo


def _activo_de(flujo):
    try:
        return flujo.jugador_activo()
    except Exception:
        return None


def tono_de(texto):
    """Tono de la notificación de un texto de pago o veredicto (puro)."""
    if texto.startswith(vc.TEXTO_FALLADA) or texto.startswith("Sin pago"):
        return "error"
    return "exito"


def _crear_vigia(escena_mundo):
    from ursina import Entity, time
    from frontend.hud import AvisoGenerico

    class VigiaVeredicto(Entity):

        def __init__(self, **opciones):
            super().__init__(**opciones)
            self.cola = vc.ColaAvisos()
            self.aviso = AvisoGenerico(parent=self)
            self.aviso.y_base = Y_AVISO
            self._visto = {"veredicto": None}
            self._flujo = None
            self.seguimiento = SeguimientoJugador()

        def update(self):
            self.avanzar(time.dt)

        def avanzar(self, dt):
            flujo = escena_mundo.flujo
            if flujo is not self._flujo:                 # otra partida: nada de la anterior se arrastra
                self._flujo = flujo
                self.cola.vaciar()
                self._visto["veredicto"] = getattr(flujo, "ultimo_veredicto", None)
                self.seguimiento.reiniciar(_activo_de(flujo) if flujo is not None else None)
                if callable(getattr(flujo, "vaciar_pagos_recientes", None)):
                    flujo.vaciar_pagos_recientes()
            if flujo is None:
                self.aviso.ocultar()
                return
            al_telefono = notificaciones.activo()
            autor = self.seguimiento.autor(_activo_de(flujo))      # quien jugó la misión (el turno ya pudo pasar)
            for texto in recoger(flujo, self._visto):
                if al_telefono:
                    notificaciones.notificar_evento(escena_mundo, texto, tono=tono_de(texto), jugador=autor)
                else:
                    self.cola.agregar(texto)
            if getattr(escena_mundo, "_cinematica", False):
                return                                    # que termine de salir por la puerta
            texto = self.cola.avanzar(dt)
            if texto is None:
                self.aviso.ocultar()
            else:
                self.aviso.mostrar(texto)
            self.aviso.avanzar(dt)

    return VigiaVeredicto(parent=escena_mundo.hud)


def registrar(gestor, conexion, escena_mundo):
    try:
        conexion.vigia_veredicto = _crear_vigia(escena_mundo)
        return conexion.vigia_veredicto
    except Exception as error:
        print(f"[veredicto] avisos no instalados ({type(error).__name__}: {error})", file=sys.stderr)
        return None
