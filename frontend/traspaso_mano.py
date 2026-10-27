# Traspaso de mano a mano (Ursina): el vendedor entrega una bolsita y el jugador la recibe. Es solo presentación:
# la compra ya está hecha (frontend/vendedor_calle.py); saltar o cancelar no duplica ni pierde nada.
#
# Secuencia de frontend/traspaso_calculos.py (1,65 s, sin tomar la cámara): girar (se miran, el jugador se
# acerca a <= 1 m por la línea por la que llegó), estirar (gestos "dar"/"recibir"; aparece la bolsita en la mano
# del vendedor), volar (la bolsita va de una mano a la otra con un arco de 6 cm y un pequeño giro), recibir (pasa a
# ser hija de la mano del jugador) y recoger (los gestos vuelven a 0, la bolsita se encoge y se oculta).
# Si un personaje no tiene mano (muñeco procedural, ANIMACION_HUMANA=False o fallo de horneado) la bolsita vuela
# entre puntos a la altura del pecho; los gestos que no se puedan hacer se omiten.

import math
import sys

from panda3d.core import TransparencyAttrib
from ursina import Entity, Vec3, color

from frontend import traspaso_calculos as tc
from frontend.piezas import MASCARA_LUZ

ALTURA_PECHO = 1.2               # m sobre el suelo del punto de entrega sin mano
ADELANTE_PECHO = 0.45            # m delante del personaje del punto de entrega sin mano
SEPARACION_PALMA = (0.05, 0.035)  # (m hacia delante, m hacia arriba) de la muñeca a la palma
ALTURA_CADERA = 0.9
TAMANO = 1.3                      # factor sobre la bolsita de 9 x 12 cm (se lee bien a la distancia de la cámara)
COLOR_CUERPO = (235, 240, 250, 110)


# Bolsita transparente con un montoncito de polvo blanco opaco dentro. Un solo Entity reutilizable: escala 1 =
# 9 x 12 cm. Sin shader (como el resto de objetos pequeños de mano) y fuera del mapa de sombras.
def crear_bolsita(padre=None):
    raiz = Entity(parent=padre, enabled=False, name="bolsita_traspaso")
    k = TAMANO
    cuerpo = Entity(parent=raiz, model="cube", color=color.rgba32(*COLOR_CUERPO), scale=(0.09 * k, 0.12 * k, 0.03 * k),
                    position=(0 * k, 0 * k, 0 * k))
    cuello = Entity(parent=raiz, model="cube", color=color.rgba32(*COLOR_CUERPO), scale=(0.035 * k, 0.03 * k, 0.02 * k),
                    position=(0 * k, 0.075 * k, 0 * k))
    polvo = Entity(parent=raiz, model="sphere", color=color.rgb32(255, 255, 255), scale=(0.062 * k, 0.034 * k, 0.016 * k),
                   position=(0 * k, -0.038 * k, 0 * k))
    punta = Entity(parent=raiz, model="sphere", color=color.rgb32(255, 255, 255), scale=(0.03 * k, 0.026 * k, 0.014 * k),
                   position=(0.004 * k, -0.02 * k, 0 * k))
    for parte in (raiz, cuerpo, cuello, polvo, punta):
        parte.shader = None
        parte.clearShader()
        parte.setLightOff(1)
        parte.ignore = True
    for parte in (cuerpo, cuello):
        parte.setTransparency(TransparencyAttrib.M_alpha)
        parte.setDepthWrite(False)
        parte.setBin("fixed", 20)           # tras el polvo: se ve a través del plástico
    for parte in (polvo, punta):
        parte.setBin("fixed", 10)
    raiz.hide(MASCARA_LUZ)
    raiz.polvo = polvo
    return raiz


class TraspasoMano:

    # escena: EscenaMundo (avatar_de). vendedor: VendedorCalle (npc, x, z, bolsita). jugador: el que compra.
    # al_terminar: callback sin argumentos al acabar (también al saltar).
    def __init__(self, escena, vendedor, jugador, al_terminar=None):
        self._escena = escena
        self._vendedor = vendedor
        self._jugador = jugador
        self._al_terminar = al_terminar
        self._npc = vendedor.npc
        self._avatar = escena.avatar_de(jugador)
        self._bolsita = vendedor.bolsita
        self._activo = False
        self._t = 0.0
        self._fase = None
        self._en_mano = False
        self._inicio = (jugador.x, jugador.z)
        self._final = self._inicio
        self._mano_v = None
        self._mano_j = None

    @property
    def activo(self):
        return self._activo

    def iniciar(self):
        if self._activo or self._avatar is None or self._npc is None:
            return False
        self._activo = True
        self._t = 0.0
        self._fase = None
        self._en_mano = False
        v = (self._vendedor.x, self._vendedor.z)
        self._inicio = (self._jugador.x, self._jugador.z)
        self._final = tc.posicion_jugador(v, self._inicio)
        self._npc.mirar_hacia(tc.rumbo_hacia(v, self._final))
        self._avatar.mirar_hacia(tc.rumbo_hacia(self._final, v))
        self._avatar.fijar_velocidad(0.0)
        self._mano_v = self._mano(self._npc, "d")
        self._mano_j = self._mano(self._avatar, "i")
        self._bolsita.enabled = False
        self._bolsita.setScale(0.001)
        return True

    @staticmethod
    def _mano(personaje, lado):
        try:
            return personaje.mano(lado)
        except Exception as error:
            print(f"[assets] traspaso: sin mano ({error})", file=sys.stderr)
            return None

    # -- Puntos de entrega --

    def _palma(self, personaje, mano):
        rumbo = math.radians(personaje.rumbo)
        adelante = Vec3(math.sin(rumbo), 0, math.cos(rumbo))
        if mano is not None:
            return _mundo(mano) + adelante * SEPARACION_PALMA[0] + Vec3(0, SEPARACION_PALMA[1], 0)
        base = personaje.world_position
        return Vec3(base.x, base.y + ALTURA_PECHO, base.z) + adelante * ADELANTE_PECHO

    # -- Avance --

    def avanzar(self, dt):
        if not self._activo:
            return
        self._t += max(0.0, min(float(dt), 0.1))
        fase, k = tc.fase_en(self._t)
        if fase != self._fase:
            self._entrar(fase)
        self._aplicar(fase, k)
        if self._t >= tc.duracion_total():
            self._terminar()

    def saltar(self):
        if self._activo:
            self._terminar()

    def _entrar(self, fase):
        self._fase = fase
        if fase == "estirar":
            self._npc.fijar_gesto("dar")
            self._avatar.fijar_gesto("recibir")
            self._bolsita.enabled = True
        elif fase == "recibir":
            if self._mano_j is not None:
                self._bolsita.wrtReparentTo(self._mano_j)
                self._en_mano = True
        elif fase == "recoger":
            self._npc.fijar_gesto(None)
            self._avatar.fijar_gesto(None)

    def _aplicar(self, fase, k):
        if fase == "girar":
            s = k * k * (3 - 2 * k)
            x = self._inicio[0] + (self._final[0] - self._inicio[0]) * s
            z = self._inicio[1] + (self._final[1] - self._inicio[1]) * s
            self._avatar.colocar(x, z)
            return
        escala = tc.escala_bolsita(fase, k)
        self._bolsita.setScale(_render(), max(0.001, escala))
        if fase == "estirar":
            self._poner(self._palma(self._npc, self._mano_v))
        elif fase == "volar":
            origen = self._palma(self._npc, self._mano_v)
            destino = self._palma(self._avatar, self._mano_j)
            self._poner(Vec3(*tc.posicion_bolsita(k, tuple(origen), tuple(destino))))
            self._bolsita.setR(_render(), tc.giro_bolsita(k))
        elif fase == "recibir":
            if not self._en_mano:
                self._poner(self._palma(self._avatar, self._mano_j))
        elif fase == "recoger" and not self._en_mano:
            base = self._avatar.world_position
            palma = self._palma(self._avatar, None)
            cadera = Vec3(base.x, base.y + ALTURA_CADERA, base.z)
            s = k * k * (3 - 2 * k)
            self._poner(palma + (cadera - palma) * s)

    def _poner(self, posicion):
        self._bolsita.setPos(_render(), posicion[0], posicion[1], posicion[2])

    def _terminar(self):
        self._activo = False
        for personaje in (self._npc, self._avatar):
            try:
                personaje.fijar_gesto(None)
            except Exception:
                pass
        self._bolsita.wrtReparentTo(self._escena)
        self._bolsita.enabled = False
        self._bolsita.setR(0)
        x, z = self._final
        self._avatar.colocar(x, z)
        self._jugador.x, self._jugador.z = x, z          # el modelo queda donde el avatar se acercó
        actualizar = getattr(getattr(self._escena, "flujo", None), "actualizar_posicion", None)
        if callable(actualizar):
            try:
                actualizar(x, z)
            except Exception as error:
                print(f"[assets] traspaso: no se pudo actualizar la posición ({error})", file=sys.stderr)
        if self._al_terminar is not None:
            self._al_terminar()


def _render():
    from ursina import scene
    return scene


def _mundo(nodo):
    p = nodo.getPos(_render())
    return Vec3(p[0], p[1], p[2])
