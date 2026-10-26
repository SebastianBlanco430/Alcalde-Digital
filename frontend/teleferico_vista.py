# Teleférico del mapa grande (Ursina): el cable entre la Estação do Teleférico y la Estação Alto do Morro con sus torres,
# dos cabinas decorativas que suben y bajan siempre (una cruza a la otra), los postes de embarque con su aviso
# «E: Subir al teleférico» y la cabina del TRAYECTO ANIMADO que lleva frontend/viaje_rapido.py (cámara sobre el barrio ~40 s,
# saltable con Espacio). El trazado y los tiempos son datos puros de backend/datos/teleferico.py.
#
# Rendimiento: cable, torres y postes en UNA malla fundida (~60 cajas, sin colisión, 1 Entity); cada cabina es una Entity con
# su malla (unos cientos de vértices). Las cabinas se mueven en update() con dos asignaciones de posición.
# Solo existe con el mapa grande y economia_config.TRANSPORTE (ver frontend/transporte_mundo.py).

import math
import time as reloj

from ursina import Entity, Text

from backend.datos import teleferico as td
from backend.logica import viaje_rapido
from backend.logica.perfil_economia import perfil_de
from frontend import viaje_calculos as vc
from frontend.comercios_mundo import _Local
from frontend.componentes import rgb
from frontend.props_mundo import Malla

RADIO_EMBARQUE = 2.8           # m del punto de embarque a los que se oye la E
PRIORIDAD = 9
ACERO = (150, 154, 164)
ACERO_OSCURO = (74, 78, 90)
CABLE = (38, 38, 44)
ROJO = (214, 52, 48)
CREMA = (240, 236, 226)
SEPARACION_CABLES = 0.9        # m a cada lado del eje del trazado
PASO_CABLE = 9.0               # m entre vértices del cable (sigue la comba)
GROSOR_CABLE = 0.1
Y_CENTRO_CABINA = -2.15        # m bajo el cable: centro de la cabina (el pivote de la cámara del trayecto)


# -- Mallas ----------------------------------------------------------------------------------------------


def _segmento(malla, a, b, grosor, color, lado=0.0):
    """Barra delgada de `a` a `b` (puntos x, y, z) desplazada `lado` m en horizontal perpendicular a su rumbo."""
    dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    horizontal = math.hypot(dx, dz)
    largo = math.sqrt(dx * dx + dy * dy + dz * dz)
    if largo < 1e-6:
        return
    giro = math.degrees(math.atan2(dx, dz))
    inclinacion = -math.degrees(math.atan2(dy, horizontal))     # + inclina el extremo +z hacia abajo (Malla.agregar)
    px, pz = (dz / horizontal, -dx / horizontal) if horizontal > 1e-9 else (1.0, 0.0)
    centro = ((a[0] + b[0]) / 2 + px * lado, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2 + pz * lado)
    from frontend.props_mundo import caja
    malla.agregar(caja(), centro, (grosor, grosor, largo), giro, color, (0.9, 1.05), 0.0, inclinacion)


def dibujar_cable(malla, trazado, suelo):
    """Cable doble, torres (dos postes rojos y blancos, travesaños y cruceta) y casetas de polea en las estaciones."""
    n = max(2, int(math.ceil(trazado.largo / PASO_CABLE)))
    puntos = [trazado.posicion(i / n) for i in range(n + 1)]
    for lado in (-SEPARACION_CABLES, SEPARACION_CABLES):
        for a, b in zip(puntos, puntos[1:]):
            _segmento(malla, a, b, GROSOR_CABLE, CABLE, lado)
    torres = trazado.torres
    for i, (x, y, z) in enumerate(torres):
        rumbo = trazado.rumbo(max(0.0, trazado._acum[i] / trazado.largo - 1e-4))
        L = _Local(malla, x, 0.0, z, rumbo)
        if i in (0, len(torres) - 1):                   # estación: caseta de polea sobre el techo
            L.caja(0, y - 0.7, 0, 3.4, 1.4, 2.2, ACERO_OSCURO, grad=(0.85, 1.05))
            L.caja(0, y - 1.5, 0, 3.0, 0.2, 1.8, ACERO)
            continue
        base = float(suelo(x, z)) - 0.8
        alto = y - base - 0.3
        trozos = max(2, int(alto // 4.0))
        for da in (-1.5, 1.5):
            for k in range(trozos):
                h = alto / trozos
                L.cilindro(da, base + k * h, 0, 0.42, h + 0.02, (ROJO, CREMA)[k % 2], 6)
        for nivel in (0.35, 0.7):                                                       # travesaños
            L.caja(0, base + alto * nivel, 0, 3.2, 0.22, 0.26, ACERO)
        L.caja(0, y - 0.2, 0, 4.0, 0.26, 0.5, ACERO_OSCURO)                              # cruceta bajo el cable
        L.caja(-SEPARACION_CABLES, y - 0.02, 0, 0.3, 0.22, 0.5, ACERO)                   # sillines de polea
        L.caja(SEPARACION_CABLES, y - 0.02, 0, 0.3, 0.22, 0.5, ACERO)


def dibujar_cabina(malla):
    """Cabina colgante con el origen en el agarre del cable (la cabina cuelga hacia -y): percha, caja roja con franja
    crema, ventanas azules y techo."""
    L = _Local(malla, 0.0, 0.0, 0.0, 0.0)
    L.cilindro(0, -1.45, 0, 0.12, 1.45, (60, 60, 68), 6)
    L.caja(0, -0.08, 0, 0.55, 0.3, 1.0, ACERO_OSCURO)                                    # agarre al cable
    L.caja(0, -2.15, 0, 2.4, 1.5, 1.9, ROJO, grad=(0.85, 1.05))                          # cuerpo
    L.caja(0, -1.36, 0, 2.62, 0.14, 2.12, CREMA)                                         # techo
    L.caja(0, -2.72, 0, 2.44, 0.26, 1.94, CREMA)                                         # franja baja
    for lado in (-1.0, 1.0):
        L.caja(lado * 1.21, -2.0, 0.0, 0.04, 0.72, 1.55, (72, 124, 176))                 # ventanas laterales
    for lado in (-1.0, 1.0):
        L.caja(0.0, -2.0, lado * 0.96, 1.9, 0.72, 0.04, (72, 124, 176))                  # frente y atrás
    L.caja(0, -2.95, 0, 2.5, 0.1, 2.0, (60, 60, 68))                                     # suelo


def dibujar_embarque(malla, x, y, z, rumbo):
    """Poste de embarque: base, mástil y tablero rojo del letrero (las letras van en un Text)."""
    L = _Local(malla, x, y, z, rumbo)
    L.caja(0, 0.05, 0, 1.4, 0.1, 1.0, (170, 170, 176), ruido=0.1)
    L.cilindro(-0.55, 0.0, 0, 0.09, 2.5, ACERO, 6)
    L.cilindro(0.55, 0.0, 0, 0.09, 2.5, ACERO, 6)
    L.caja(0, 2.3, 0.05, 1.9, 0.5, 0.07, ROJO, grad=(0.95, 1.0))
    L.caja(0, 2.3, 0.015, 2.0, 0.58, 0.03, (255, 255, 255), grad=(0.95, 1.0))
    L.caja(0, 0.5, 0.0, 0.9, 0.08, 0.3, (150, 104, 66))                                   # banco corto


# -- Entidades -------------------------------------------------------------------------------------------


class TelefericoVista(Entity):
    """El cable, las torres y las dos cabinas. `en_trayecto` lo pone viaje_rapido mientras el jugador va a bordo."""

    def __init__(self, mundo, **opciones):
        super().__init__(**opciones)
        from frontend.piezas import pieza
        self.mundo = mundo
        self.trazado = td.construir_trazado(mundo)
        malla = Malla()
        dibujar_cable(malla, self.trazado, mundo.altura)
        self.postes = []
        for estacion in viaje_rapido.ESTACIONES.values():
            x, z, rumbo = viaje_rapido.posicion_de_estacion(mundo, estacion.id)
            dibujar_embarque(malla, x, mundo.altura(x, z), z, rumbo)
            self.postes.append((estacion, x, z, rumbo))
        self.cable = pieza(parent=self, model=malla.mesh(), name="teleferico_cable")
        self.cable.ignore = True
        self.cabinas = []
        for k in range(2):
            m = Malla()
            dibujar_cabina(m)
            cabina = pieza(parent=self, model=m.mesh(), name=f"teleferico_cabina_{k}")
            cabina.ignore = True
            self.cabinas.append(cabina)
        self.letreros = []
        for estacion, x, z, rumbo in self.postes:
            L = _Local(Malla(), x, mundo.altura(x, z), z, rumbo)
            texto = Text("TELEFÉRICO", parent=self, origin=(0, 0), position=L.p(0, 2.3, 0.1), rotation_y=rumbo + 180,
                         scale=5.0, color=rgb((255, 255, 255)))
            try:
                if texto.width > 1.75:
                    texto.scale = 5.0 * 1.75 / texto.width
            except Exception:
                pass
            texto.ignore = True
            self.letreros.append(texto)
        self.en_trayecto = False
        self._t0 = reloj.monotonic()
        self.colocar_ambiente()

    def posicion_de_cabina(self, u):
        """(x, y, z) del cable y rumbo en la fracción u (la cabina cuelga bajo ese punto)."""
        return self.trazado.posicion(u), self.trazado.rumbo(u)

    def colocar(self, cabina, u):
        (x, y, z), rumbo = self.posicion_de_cabina(u)
        cabina.position = (x, y, z)
        cabina.rotation_y = rumbo

    def colocar_ambiente(self, t=None):
        t = (reloj.monotonic() - self._t0) if t is None else t
        ua, ub = td.fase_ambiente(t)
        self.colocar(self.cabinas[0], ua)
        self.colocar(self.cabinas[1], ub)

    def update(self):
        if not self.en_trayecto:
            self.colocar_ambiente()


class EmbarqueTeleferico:
    """Un poste de embarque como Interaccion de frontend/economia_mundo.py: «E: Subir al teleférico (R$ 2)»."""

    prioridad = PRIORIDAD

    def __init__(self, escena, estacion, x, z, panel, viaje):
        self._escena = escena
        self.estacion = estacion
        self.x, self.z = float(x), float(z)
        self.panel = panel
        self.viaje = viaje
        self.nombre = "teleférico"

    def titulo_panel(self):
        return (self.estacion.nombre, "")

    def aviso(self, jugador, x, z):
        if math.hypot(x - self.x, z - self.z) > RADIO_EMBARQUE:
            return None
        precio = viaje_rapido.TARIFA_TELEFERICO
        return f"E: Subir al teleférico ({'R$ ' + str(precio) if precio else 'gratis'})"

    def usar(self, jugador, economia):
        if math.hypot(jugador.x - self.x, jugador.z - self.z) > RADIO_EMBARQUE:
            return False
        mundo = self._escena._mundo
        perfil = perfil_de(jugador, economia.catalogo)
        filas = vc.filas_de_estacion(mundo, self.estacion.id)
        control = vc.ControlViaje(perfil, filas, lambda fila: self.viaje.pedir(fila.destino, jugador, perfil))
        self.panel.comercio_actual = self
        return bool(economia.abrir_modal(self.panel, control))

    def actualizar(self, dt):
        pass


def instalar(economia, viaje, panel):
    """Pone el cable, las cabinas y los dos postes de embarque. Devuelve (TelefericoVista, [EmbarqueTeleferico])."""
    escena = economia.escena
    vista = TelefericoVista(escena._mundo, parent=escena)
    embarques = [economia.registrar(EmbarqueTeleferico(escena, estacion, x, z, panel, viaje))
                 for estacion, x, z, _rumbo in vista.postes]
    economia.teleferico = vista
    viaje.teleferico = vista
    return vista, embarques
