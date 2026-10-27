# Paradas de mototáxi del mapa grande (Ursina): en cada parada de backend/logica/viaje_rapido.PARADAS hay un puesto con
# toldo a cuadros amarillo y negro, un letrero «MOTOTÁXI», un banco y un conductor con su nombre. «E: Pedir un mototáxi»
# abre el menú de destinos (el mismo panel modal que la tienda, con precio en R$); al elegir uno se cobra de la billetera
# y frontend/viaje_rapido.py hace el viaje (fundido a negro de 8-15 s con «Viajando en mototáxi…» y reubicación).
#
# Mismo patrón que frontend/comercios_mundo.py (se reutilizan su pincel local, el NPC dependiente y el control de nivel de
# detalle del NPC): TODOS los puestos van fundidos en UNA malla, un Text por letrero y un NPC por conductor; sin colisión.
# Solo existe con el mapa grande y la bandera economia_config.TRANSPORTE (ver frontend/transporte_mundo.py).

import math

from ursina import Text

from backend.logica import viaje_rapido
from backend.logica.comercios import Comercio
from backend.logica.perfil_economia import perfil_de
from frontend import estilo, tienda_calculos as calc, viaje_calculos as vc
from frontend.comercios_mundo import (INDICE_NPC_BASE, ComercioMundo, _Local, _crear_dependiente, es_dependienta,
                                      indice_vestido)
from frontend.componentes import rgb
from frontend.props_mundo import Malla
from frontend.tienda_ui import ALTO, ANCHO, PanelTienda, _caja, _texto
from frontend import diseno_adaptable

AMARILLO = (250, 200, 30)
NEGRO = (34, 34, 40)
MADERA = (150, 104, 66)
INDICE_NPC_PARADA = INDICE_NPC_BASE + 40       # los comercios usan 101..~115; las paradas, desde 141
PRIORIDAD = 9                                  # por encima de los comercios (8)
ANCHO_LETRERO = 2.0                            # m del tablero (el texto se ajusta)


class PanelViaje(PanelTienda):
    """Menú de destinos: el PanelTienda con otros textos al pie."""

    def _pie(self, d):
        c = self.control
        abajo = -ALTO / 2
        izq = -ANCHO / 2 + 0.03
        ancho = ANCHO - 0.06
        _caja(d, ancho, 0.003, estilo.COLOR_BARRA_FONDO, (0, abajo + 0.128))
        _texto(d, calc.texto_saldo(c.saldo()), 18, estilo.COLOR_TEXTO, (izq, abajo + 0.104), negrita=True)
        if c.mensaje:
            tono = (240, 110, 110) if c.error else estilo.ESTADO_EXITO
            m = _texto(d, c.mensaje, 14, tono, (izq, abajo + 0.066), negrita=True)
            diseno_adaptable.ajustar_texto(m, ancho, escala_min=0.6)
        a = _texto(d, "Flechas elegir · Enter viajar · Esc cierra", 12, estilo.COLOR_TEXTO_TENUE, (izq, abajo + 0.026))
        diseno_adaptable.ajustar_texto(a, ancho, escala_min=0.6)


# -- Decorado de una parada (todo en una Malla) ---------------------------------------------------------


def dibujar_parada(malla, x, y, z, rumbo, tablero=AMARILLO, letras=NEGRO):
    """Puesto de mototáxi con el conductor de pie en (x, z): toldo a cuadros, dos postes, banco, tablero y bidón de casco."""
    L = _Local(malla, x, y, z, rumbo)
    L.caja(0, 0.05, -0.55, 3.0, 0.1, 1.9, (170, 170, 176), grad=(0.85, 1.0), ruido=0.1)               # losa de cemento
    for da in (-1.4, 1.4):
        L.cilindro(da, 0.0, -0.95, 0.09, 2.7, (96, 96, 104), 6)
        L.cilindro(da, 0.0, 0.1, 0.09, 2.5, (96, 96, 104), 6)
    for k in range(8):                                                                                  # toldo a cuadros
        L.caja(-1.4 + k * 0.4, 2.62, -0.42, 0.4, 0.07, 1.35, (AMARILLO, NEGRO)[k % 2], incl=-6.0, grad=(0.9, 1.05))
    for k in range(8):                                                                                  # volante
        L.caja(-1.4 + k * 0.4, 2.42, 0.26, 0.4, 0.2, 0.03, (NEGRO, AMARILLO)[k % 2])
    L.caja(0, 1.45, -0.98, 2.9, 2.5, 0.06, (120, 126, 140), grad=(0.9, 1.05))                          # pared del fondo
    L.caja(1.0, 0.42, -0.72, 1.1, 0.07, 0.42, MADERA)                                                   # banco
    L.caja(1.0, 0.2, -0.72, 1.0, 0.4, 0.34, (110, 76, 50))
    L.caja(-1.0, 0.25, -0.7, 0.4, 0.5, 0.4, (216, 60, 56))                                              # bidón de cascos
    L.esfera(-1.0, 0.62, -0.7, 0.28, 0.2, 0.28, (250, 200, 30))
    L.caja(0, 3.0, 0.3, ANCHO_LETRERO + 0.2, 0.5, 0.07, tablero, grad=(0.95, 1.0))                     # tablero del letrero
    L.caja(0, 3.0, 0.265, ANCHO_LETRERO + 0.3, 0.58, 0.03, (255, 255, 255), grad=(0.95, 1.0))
    for da in (-0.9, 0.9):
        L.cilindro(da, 2.66, 0.3, 0.04, 0.25, (90, 70, 52), 6)


def _poner_letrero(escena, x, y, z, rumbo):
    L = _Local(Malla(), x, y, z, rumbo)
    texto = Text("MOTOTÁXI", parent=escena, origin=(0, 0), position=L.p(0, 3.0, 0.34), rotation_y=rumbo + 180,
                 scale=6.0, color=rgb(NEGRO))
    try:
        if texto.width > ANCHO_LETRERO:
            texto.scale = 6.0 * ANCHO_LETRERO / texto.width
    except Exception:
        pass
    texto.ignore = True
    return texto


# -- Interacción ---------------------------------------------------------------------------------------


class ParadaMototaxi(ComercioMundo):
    """Una parada como Interaccion de frontend/economia_mundo.py: «E: Pedir un mototáxi» abre el menú de destinos."""

    prioridad = PRIORIDAD

    def __init__(self, escena, parada, x, z, rumbo, npc, panel, viaje):
        comercio = Comercio(f"mototaxi_{parada.id}", parada.nombre, "puesto_trabajo", dict(parada.ancla),
                            npc=parada.conductor, lugar_ancla=parada.lugar)
        super().__init__(escena, comercio, x, z, rumbo, npc, panel)
        self.parada = parada
        self.viaje = viaje

    def titulo_panel(self):
        return (self.parada.nombre, self.nombre)

    def texto_aviso(self):
        return f"E: Pedir un mototáxi ({self.nombre})"

    def usar(self, jugador, economia):
        if not self._cerca(jugador.x, jugador.z):
            return False
        mundo = self._escena._mundo
        perfil = perfil_de(jugador, economia.catalogo)
        filas = vc.filas_de_parada(mundo, self.parada.id)
        control = vc.ControlViaje(perfil, filas, lambda fila: self.viaje.pedir(fila.destino, jugador, perfil))
        self.panel.comercio_actual = self
        return bool(economia.abrir_modal(self.panel, control))


def crear_panel(economia):
    """El menú de destinos (UNO para paradas y estaciones), registrado como modal de la economía."""
    panel = PanelViaje(None, titulo_fn=lambda: _titulo(panel), parent=economia.escena.hud)
    panel.comercio_actual = None
    economia.modales.append(panel)
    return panel


def instalar(economia, viaje, panel, crear_npc=None):
    """Pone las paradas (puesto, letrero y conductor) y las registra en la economía. Devuelve la lista de ParadaMototaxi."""
    escena = economia.escena
    mundo = escena._mundo
    suelo = mundo.altura
    puestos = []
    malla = Malla()
    for orden, parada in enumerate(viaje_rapido.PARADAS.values()):
        x, z, rumbo = viaje_rapido.posicion_de_parada(mundo, parada.id)
        dibujar_parada(malla, x, suelo(x, z), z, rumbo)
        puestos.append((orden, parada, x, z, rumbo))
    mesh = malla.mesh()
    if mesh is not None:
        from frontend.piezas import pieza
        economia.paradas_malla = pieza(parent=escena, model=mesh, name="paradas_mototaxi")
    registrados = []
    usados = set()
    for orden, parada, x, z, rumbo in puestos:
        _poner_letrero(escena, x, suelo(x, z), z, rumbo)
        indice = indice_vestido(INDICE_NPC_PARADA + orden, usados, es_dependienta(parada.conductor))
        usados.add(indice)
        npc = _crear_dependiente(escena, indice, parada.conductor, x, z, rumbo, crear_npc)
        registrados.append(economia.registrar(ParadaMototaxi(escena, parada, x, z, rumbo, npc, panel, viaje)))
    economia.paradas_mototaxi = registrados
    return registrados


def _titulo(panel):
    actual = getattr(panel, "comercio_actual", None)
    if actual is None:
        return ("", "")
    return actual.titulo_panel()
