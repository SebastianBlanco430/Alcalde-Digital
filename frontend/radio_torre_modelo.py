# Torre de la Rádio Comunitária en el mundo 3D (Ursina; docs/RADIO_3D.md). Un mástil de celosía pintado a franjas rojas
# y blancas, con zapatas, plataforma, una antena de panel y la LUZ ROJA de aviso en la punta, que parpadea siempre (no
# solo en la emisión). Va junto al edificio de la radio, en el primer sitio libre que da frontend/radio_torre_calculos.py
# según las reglas del decorado (props_mundo.Reserva: ni edificios, ni caminos, ni calles, ni props) y entra al modelo
# como obstáculo (origen «radio_torre»). La emisión en 3D (frontend/radio3d_escena.py) orbita alrededor de ella.
#
# La crea frontend/ciudad_3d.py DESPUÉS de silenciar lo estático: la celosía es una sola malla y la luz es
# la única pieza con update().
# BANDERA: ALCALDE_RADIO3D (frontend/radio3d_camara_calculos.py). Con =0 no hay torre y la radio es la de 2D.

import sys

from ursina import Entity, color, time
from ursina.shaders import lit_with_shadows_shader

from backend.logica.mundo_ciudad import Obstaculo
from frontend import banderas_visuales
from frontend import radio3d_camara_calculos as r3c
from frontend import radio_torre_calculos as rtc
from frontend.piezas import MASCARA_LUZ
from frontend.props_mundo import Reserva, pendiente

ROJO_TORRE = (196, 48, 44)
BLANCO_TORRE = (236, 232, 224)
GRIS_HORMIGON = (150, 146, 140)
GRIS_ANTENA = (198, 202, 210)
ROJO_LUZ = (255, 40, 30)
FRANJAS = 5                     # franjas de pintura (rojo/blanco alternados de abajo arriba)
ORIGEN = "radio_torre"


def _rgb(tono, brillo=1.0, alfa=1.0):
    return color.rgba(tono[0] / 255 * brillo, tono[1] / 255 * brillo, tono[2] / 255 * brillo, alfa)


def _piezas_torre():
    """Datos de cada cubo de la torre (relativos a su base), que se unen en una malla."""
    piezas = []
    alto_franja = rtc.ALTO_TORRE / FRANJAS
    for p, q, grosor in rtc.piezas_celosia():
        centro, largo, giro, inclinacion = rtc.barra(p, q)
        franja = int(min(rtc.ALTO_TORRE - 1e-6, max(0.0, centro[1])) // alto_franja)
        tono = ROJO_TORRE if franja % 2 == 0 else BLANCO_TORRE
        piezas.append({"model": "cube", "color": _rgb(tono), "position": centro, "rotation": (inclinacion, giro, 0),
                       "scale": (grosor, grosor, largo + grosor)})
    # zapatas bajo cada pata (enterradas: absorben el desnivel de la ladera)
    for x, z in rtc.patas(0.0):
        piezas.append({"model": "cube", "color": _rgb(GRIS_HORMIGON), "position": (x, -rtc.ALTO_ZAPATA / 2 + 0.15, z),
                       "scale": (0.5, rtc.ALTO_ZAPATA + 0.3, 0.5)})
    # plataforma de servicio y antena de panel
    y_plat = rtc.ALTO_TORRE * rtc.ALTO_PLATAFORMA
    lado = rtc.lado_a(y_plat)
    piezas.append({"model": "cube", "color": _rgb(GRIS_ANTENA), "position": (0, y_plat, 0),
                   "scale": (lado + 0.5, 0.06, lado + 0.5)})
    piezas.append({"model": "cube", "color": _rgb(GRIS_ANTENA), "position": (0, y_plat + 0.7, lado / 2 + 0.12),
                   "scale": (0.35, 1.1, 0.08)})
    # mástil final que sostiene la luz
    px, py, pz = rtc.punta()
    piezas.append({"model": "cube", "color": _rgb(ROJO_TORRE), "position": (0, (rtc.ALTO_TORRE + py) / 2, 0),
                   "scale": (0.07, py - rtc.ALTO_TORRE + 0.1, 0.07)})
    return piezas


class TorreRadio(Entity):
    """La torre colocada: `centro` (x, z), `y_base`, `alto` y `punta_mundo` (x, y, z) para la cámara de la emisión."""

    def __init__(self, padre, x, z, y, **opciones):
        super().__init__(parent=padre, position=(x, y, z), name="radio_torre", **opciones)
        self.centro, self.y_base, self.alto = (x, z), y, rtc.ALTO_TORRE
        px, py, pz = rtc.punta()
        self.punta_mundo = (x + px, y + py, z + pz)
        # Una sola malla con normales (como los grupos de la ciudad): misma luz desde cualquier encuadre.
        self.celosia = Entity(parent=self, name="radio_torre_celosia")
        for datos in _piezas_torre():
            Entity(parent=self.celosia, **datos)
        self.celosia.combine(include_normals=True)
        self.celosia.shader = lit_with_shadows_shader
        # La luz no recibe sombreado ni entra al mapa de sombras: brilla sola, también de noche.
        self.luz = Entity(parent=self, model="sphere", position=(px, py, pz), scale=rtc.RADIO_LUZ * 2,
                          color=_rgb(ROJO_LUZ), shader=None, unlit=True, name="radio_torre_luz")
        self.halo = Entity(parent=self, model="sphere", position=(px, py, pz), scale=rtc.RADIO_HALO * 2,
                           color=_rgb(ROJO_LUZ, alfa=0.35), shader=None, unlit=True, name="radio_torre_halo")
        self.halo.setDepthWrite(False)
        for pieza_luz in (self.luz, self.halo):
            pieza_luz.hide(MASCARA_LUZ)
        self.t = 0.0
        self._reducir, self._t_reducir = False, 0.0

    def update(self):
        self.t += time.dt
        # «reducir movimiento» se consulta de vez en cuando (lee los ajustes), no en cada frame
        self._t_reducir -= time.dt
        if self._t_reducir <= 0:
            self._t_reducir = 2.0
            self._reducir = bool(banderas_visuales.reducir_movimiento())
        brillo = rtc.brillo_luz(self.t, self._reducir)
        self.luz.color = _rgb(ROJO_LUZ, 0.35 + 0.65 * brillo)
        self.halo.color = _rgb(ROJO_LUZ, alfa=0.45 * brillo)


def construir_torre(padre, mundo):
    """Pone la torre junto al edificio de la radio y la devuelve (None con la bandera apagada, sin edificio de la radio
    o sin sitio libre: la emisión cae entonces a la radio 2D)."""
    if not r3c.activo():
        return None
    try:
        edificio = mundo.edificio_de(rtc.LUGAR_RADIO)
    except Exception:                              # noqa: BLE001  mundo sin radio (pruebas, mapas viejos)
        return None
    try:
        reserva = Reserva(mundo)
        extra = list(mundo.obstaculos_extra()) if hasattr(mundo, "obstaculos_extra") else []

        def cabe(x, z, r):
            return reserva.cabe(x, z, r) and not any(o.choca(x, z, r) for o in extra)

        sitio = rtc.elegir_sitio(edificio.caja(), edificio.lado_puerta, cabe,
                                 desnivel=lambda x, z: pendiente(mundo.altura, x, z))
        if sitio is None:
            print("[radio3d] sin sitio libre para la torre junto a la radio", file=sys.stderr)
            return None
        x, z = sitio
        torre = TorreRadio(padre, x, z, mundo.altura(x, z))
        if hasattr(mundo, "agregar_obstaculos"):
            mundo.agregar_obstaculos([Obstaculo("radio_torre", x, z, radio=rtc.RADIO_CUERPO)], origen=ORIGEN)
        return torre
    except Exception as error:                     # noqa: BLE001  sin torre: la emisión usa la radio 2D
        print(f"[radio3d] torre omitida ({type(error).__name__}: {error})", file=sys.stderr)
        return None
