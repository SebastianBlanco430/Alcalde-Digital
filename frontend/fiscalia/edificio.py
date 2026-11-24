# El edificio de la Fiscalía en el mundo (Ursina): la casa decorativa elegida (frontend/fiscalia/edificio_calculos.py)
# recibe un cartel «Fiscalía de Ciudad Nova» en la fachada (sin luz propia: se lee de día y de noche), un marco claro en
# la puerta, un marcador con nombre en el minimapa y una interacción (Protocol Interaccion de frontend/economia_mundo.py:
# prioridad, aviso, usar, actualizar) que con E delante de la puerta abre el caso.
#
# La casa en sí está fundida con el resto del barrio (frontend/casas_decorativas.py): aquí solo se le cuelgan piezas
# delante de la fachada, colgadas de la escena del mundo (se ocultan con ella).

import math

from ursina import Entity, Text, color

from backend.logica import fiscalia_bandera as fb
from frontend.componentes import rgb
from frontend.fiscalia import edificio_calculos as ec
from frontend.piezas import pieza, silenciar, texto_sin_tinta

PRIORIDAD = 9                      # por encima del computador y de los puestos cercanos
SEGUNDOS_MENSAJE = 3.0
COLOR_PLACA = (26, 30, 52)
COLOR_LETRAS = (255, 214, 102)
COLOR_MARCO = (236, 228, 206)
FUENTE_MINIMAPA = "fiscalia"


def sitio_en(mundo):
    """SitioFiscalia de la casa de la Fiscalía en `mundo` (MundoCiudad) o None si no hay casas decorativas."""
    from backend.datos.modelos_edificios import modelo_de
    from backend.logica.mundo_ciudad import CasaDecorativa
    casas = [o for o in mundo.obstaculos() if isinstance(o, CasaDecorativa)]
    casa = ec.casa_mas_cercana(casas, fb.CASA_FISCALIA)
    if casa is None:
        return None
    return ec.sitio_de(casa, modelo_de(casa.modelo))


class EdificioFiscalia:

    prioridad = PRIORIDAD

    # escena: EscenaMundo. abrir(jugador) -> str | None: abre el caso (None) o devuelve el texto a mostrar.
    def __init__(self, escena, sitio, abrir):
        self._escena, self.sitio, self._abrir = escena, sitio, abrir
        self._mensaje, self._t_mensaje = None, 0.0
        self.raiz = self._construir()
        self._poner_en_minimapa()

    # -- Piezas --

    def _construir(self):
        s = self.sitio
        mundo = self._escena._mundo
        suelo = mundo.altura(*s.puerta)
        raiz = Entity(parent=self._escena, position=(s.cartel[0], suelo, s.cartel[1]), rotation_y=s.rumbo,
                      name="fiscalia_cartel")
        # placa (oscura, con borde dorado) y letras: +z local hacia la calle; las letras miran a la calle (rotation 180)
        pieza(parent=raiz, model="cube", color=rgb(COLOR_LETRAS), position=(0, s.y_cartel, 0.0),
              scale=(s.ancho_cartel + 0.08, ec.ALTO_CARTEL + 0.08, 0.05))
        pieza(parent=raiz, model="cube", color=rgb(COLOR_PLACA), position=(0, s.y_cartel, 0.03),
              scale=(s.ancho_cartel, ec.ALTO_CARTEL, 0.05), shader=None)
        escala = ec.escala_texto_cartel(fb.NOMBRE_FISCALIA.upper(), s.ancho_cartel - 0.3)
        letras = Text(fb.NOMBRE_FISCALIA.upper(), parent=raiz, origin=(0, 0), position=(0, s.y_cartel + 0.02, 0.07),
                      scale=escala, color=rgb(COLOR_LETRAS), rotation_y=180)
        texto_sin_tinta(letras)
        # marco claro de la puerta (en la misma fachada): se ve cuál es la entrada
        dx = (s.puerta[0] - s.cartel[0]) * math.cos(math.radians(s.rumbo)) - (s.puerta[1] - s.cartel[1]) * math.sin(
            math.radians(s.rumbo))
        for (x, y, sx, sy) in ((dx - s.ancho_puerta / 2 - 0.05, s.alto_puerta / 2, 0.1, s.alto_puerta + 0.1),
                               (dx + s.ancho_puerta / 2 + 0.05, s.alto_puerta / 2, 0.1, s.alto_puerta + 0.1),
                               (dx, s.alto_puerta + 0.05, s.ancho_puerta + 0.2, 0.1)):
            pieza(parent=raiz, model="cube", color=rgb(COLOR_MARCO), position=(x, y, -0.04), scale=(sx, sy, 0.08))
        # escudo sobre el dintel (balanza estilizada)
        pieza(parent=raiz, model="cube", color=rgb(COLOR_LETRAS), position=(dx, s.alto_puerta + 0.24, -0.02),
              scale=(0.36, 0.05, 0.04), shader=None)
        pieza(parent=raiz, model="cube", color=rgb(COLOR_LETRAS), position=(dx, s.alto_puerta + 0.17, -0.02),
              scale=(0.05, 0.2, 0.04), shader=None)
        silenciar(raiz)
        return raiz

    def _poner_en_minimapa(self):
        try:
            from frontend import minimapa_calculos as mm
            mm.registro().poner_marcador(mm.MarcadorMinimapa("objetivo", self.sitio.fuera[0], self.sitio.fuera[1],
                                                             etiqueta=fb.NOMBRE_FISCALIA, id="fiscalia"),
                                         fuente=FUENTE_MINIMAPA)
        except Exception:                # noqa: BLE001  sin marcador: la baliza sigue llevando a la puerta
            pass

    # -- Protocol Interaccion --

    def aviso(self, jugador, x, z):
        if not ec.cerca_de_puerta(self.sitio, x, z):
            return None
        if self._mensaje:
            return self._mensaje
        return f"E: entrar a la {fb.NOMBRE_FISCALIA}"

    def usar(self, jugador, economia=None):
        if not ec.cerca_de_puerta(self.sitio, jugador.x, jugador.z):
            return False
        texto = self._abrir(jugador)
        if texto:
            self.decir(texto)
        return True

    def actualizar(self, dt):
        if self._mensaje:
            self._t_mensaje -= dt
            if self._t_mensaje <= 0:
                self._mensaje = None

    def decir(self, texto):
        self._mensaje, self._t_mensaje = texto, SEGUNDOS_MENSAJE

    def destruir(self):
        from frontend.componentes import destruir_arbol
        destruir_arbol(self.raiz)
        self._quitar_del_minimapa()

    def _quitar_del_minimapa(self):
        try:
            from frontend import minimapa_calculos as mm
            mm.registro().limpiar_fuente(FUENTE_MINIMAPA)
        except Exception:                # noqa: BLE001
            pass


RADIO_GUIA = 9.0           # m de la puerta del destino (Praça da Sé) en que se explica a dónde ir


class GuiaFiscalia:
    """Interacción solo informativa: en la puerta de la Praça da Sé, con una misión de la Fiscalía, dice que el caso se
    juega en la casa rotulada de al lado (la baliza ya lleva allí). No consume la E."""

    prioridad = 1

    def __init__(self, escena, sitio):
        self._escena, self.sitio = escena, sitio

    def aviso(self, jugador, x, z):
        try:
            flujo = self._escena.flujo
            mision = flujo.mision_actual() if flujo is not None else None
            if mision is None or getattr(mision, "tipo", None) != "investigacion":
                return None
            px, pz = self._escena._mundo.punto_interaccion(mision.destino)
        except Exception:                # noqa: BLE001
            return None
        if math.hypot(x - px, z - pz) > RADIO_GUIA or ec.cerca_de_puerta(self.sitio, x, z, ec.RADIO_PUERTA + 1.0):
            return None
        metros = int(round(math.hypot(x - self.sitio.fuera[0], z - self.sitio.fuera[1])))
        return f"El caso se resuelve en la {fb.NOMBRE_FISCALIA}: sigue la baliza ({metros} m) y pulsa E en su puerta"

    def usar(self, jugador, economia=None):
        return False

    def actualizar(self, dt):
        pass
