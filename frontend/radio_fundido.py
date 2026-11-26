# Fundido a negro alrededor de la emisión de la Rádio Comunitária (frontend/radio_emision.py la crea a través de aquí).
# Antes la cámara saltaba de golpe del jugador a la torre y de vuelta. Ahora, con el jugador ya quieto (la emisión es
# bloqueador de la escena desde el primer frame: reloj y controles parados):
#   1. «entrando»: la pantalla funde a negro (SEGUNDOS_FUNDIDO);
#   2. con todo negro se crea la emisión 3D (frontend/radio3d_escena.py) y el negro se abre sobre ella;
#   3. al terminar la emisión (sola, con Escape o «Saltar») vuelve a fundir a negro ANTES de que devuelva cámara y HUD;
#   4. con todo negro la emisión se cierra, el negro se abre sobre el juego y solo entonces se avisa al_terminar (el
#      jugador recupera los controles con la imagen ya limpia).
# Mismo contrato que la emisión: `.terminada`, `.saltar()`; al_poner y al_terminar pasan tal cual.
# La cuenta de la opacidad es pura (alfa_fundido) y tiene test. BANDERA: ALCALDE_RADIO_FUNDIDO=0 lo quita (corte seco).
# Con «reducir movimiento» el fundido es más corto, no desaparece (un corte seco también molesta).

import os
import sys

SEGUNDOS_FUNDIDO = 0.45
SEGUNDOS_FUNDIDO_REDUCIDO = 0.2
SEGUNDOS_NEGRO = 0.12           # pausa con la pantalla negra entre cerrar una cosa y abrir la otra
DT_MAXIMO = 0.1                 # un frame largo (crear la emisión 3D) no se come el fundido
Z_FUNDIDO = -0.99               # delante de la emisión (Z_UI = -0.95) y del HUD
_NO = ("0", "false", "no", "off")


def activo():
    return os.environ.get("ALCALDE_RADIO_FUNDIDO", "").strip().lower() not in _NO


def alfa_fundido(t, duracion, hacia_negro):
    """Opacidad del negro a los `t` s de un fundido de `duracion` s (suavizado). hacia_negro: 0 -> 1; si no, 1 -> 0."""
    if duracion <= 0:
        x = 1.0
    else:
        x = min(1.0, max(0.0, t / duracion))
    x = x * x * (3 - 2 * x)
    return x if hacia_negro else 1.0 - x


def crear(escena_mundo, crear_interior, al_terminar, guardia=None):
    """`crear_interior(al_terminar_interior)` crea la emisión de verdad. Devuelve la entidad del fundido (o, si el
    fundido no se puede montar, la emisión directamente)."""
    if not activo():
        return crear_interior(al_terminar)
    try:
        return _clase()(escena_mundo, crear_interior, al_terminar, guardia)
    except Exception as error:                  # noqa: BLE001  sin fundido: la emisión con su corte de siempre
        print(f"[radio] fundido omitido ({type(error).__name__}: {error})", file=sys.stderr)
        return crear_interior(al_terminar)


_CLASE = None


def _clase():
    global _CLASE
    if _CLASE is not None:
        return _CLASE
    from ursina import Entity, camera, color, destroy, time

    from frontend import banderas_visuales

    class FundidoRadio(Entity):

        def __init__(self, escena_mundo, crear_interior, al_terminar, guardia):
            # «fundido» en el nombre: la radio 3D no esconde las capas de camera.ui que lo llevan
            super().__init__(parent=camera.ui, name="radio_fundido", model="quad", scale=(9, 3), z=Z_FUNDIDO,
                             color=color.rgba(0, 0, 0, 0))
            self.escena = escena_mundo
            self._crear_interior, self._al_terminar, self._guardia = crear_interior, al_terminar, guardia
            self.interior = None
            self.terminada = False
            self._saltar_pendiente = False
            reducir = bool(getattr(banderas_visuales, "reducir_movimiento", lambda: False)())
            self.duracion = SEGUNDOS_FUNDIDO_REDUCIDO if reducir else SEGUNDOS_FUNDIDO
            self.fase, self.t = "entrando", 0.0
            self._cerrar_interior = None          # el _terminar original de la emisión, mientras se funde a negro

        def _alfa(self, a):
            self.color = color.rgba(0, 0, 0, max(0.0, min(1.0, a)))

        # -- Contrato --

        def saltar(self):
            if self.terminada:
                return
            if self.interior is None:
                self._saltar_pendiente = True
            elif not getattr(self.interior, "terminada", True):
                self.interior.saltar()

        # -- Pasos --

        def _abrir_interior(self):
            self.interior = self._crear_interior(self._fin_interior)
            # La emisión devuelve cámara y HUD dentro de su _terminar: se retrasa hasta que la pantalla esté negra.
            original = self.interior._terminar

            def terminar_con_fundido():
                if self.fase in ("abriendo", "en_emision"):
                    self._cerrar_interior = original
                    self.fase, self.t = "cerrando", 0.0
            self.interior._terminar = terminar_con_fundido
            self.fase, self.t = "abriendo", 0.0
            if self._saltar_pendiente:
                self.saltar()

        def _fin_interior(self):
            # la emisión ya devolvió cámara y HUD (con la pantalla negra): se abre el negro sobre el juego
            self.fase, self.t = "negro_salida", 0.0

        def _terminar(self):
            self.terminada = True
            al_terminar, self._al_terminar = self._al_terminar, None
            try:
                if al_terminar is not None:
                    al_terminar()
            finally:
                destroy(self)

        # -- Frame --

        def update(self):
            if self._guardia is not None:
                try:
                    self._guardia()
                except Exception:
                    pass
            dt = min(time.dt, DT_MAXIMO)
            self.t += dt
            fase = self.fase
            try:
                if fase == "entrando":
                    self._alfa(alfa_fundido(self.t, self.duracion, True))
                    if self.t >= self.duracion + SEGUNDOS_NEGRO:
                        self._abrir_interior()
                elif fase == "abriendo":
                    self._alfa(alfa_fundido(self.t, self.duracion, False))
                    if self.t >= self.duracion:
                        self.fase = "en_emision"
                elif fase == "en_emision":
                    self._alfa(0)
                elif fase == "cerrando":
                    self._alfa(alfa_fundido(self.t, self.duracion, True))
                    if self.t >= self.duracion + SEGUNDOS_NEGRO:
                        cerrar, self._cerrar_interior = self._cerrar_interior, None
                        self.fase = "esperando"
                        cerrar()                         # devuelve cámara y HUD y llama a _fin_interior
                elif fase == "negro_salida":
                    self._alfa(alfa_fundido(self.t, self.duracion, False))
                    if self.t >= self.duracion:
                        self._terminar()
            except Exception as error:                  # noqa: BLE001  el fundido nunca deja la pantalla negra
                print(f"[radio] fundido cortado ({type(error).__name__}: {error})", file=sys.stderr)
                self._alfa(0)
                if not self.terminada:
                    self._terminar()

    _CLASE = FundidoRadio
    return _CLASE
