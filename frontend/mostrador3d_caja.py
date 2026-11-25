# Caja registradora del MOSTRADOR 3D (Ursina, en el mundo; frontend/mostrador3d_escena.py la monta en el mostrador).
#   - Cajón abierto hacia el jugador con 12 compartimentos: los 7 billetes (R$ 2 a 200) y las 5 monedas (R$ 0,05 a 1),
#     cada uno con su valor escrito encima. Clic en un compartimento = pones esa pieza en la bandeja del cambio.
#   - Bandeja del cambio (sobre el mostrador, hacia el cliente): lo que vas a devolver, pieza a pieza; clic en una pieza
#     de la bandeja la devuelve a la caja.
#   - Pago del cliente: los billetes y monedas con que paga, sobre el mostrador.
# Billetes y monedas son mallas de frontend/mostrador3d_productos.py (colores genéricos, solo la denominación). La caja
# no decide nada: llama a al_agregar(valor) / al_quitar(indice) y la escena se lo pasa al TurnoMostrador.

from ursina import Entity, Text, color
from ursina.shaders import lit_with_shadows_shader, unlit_shader

from backend.logica import mostrador3d_dinero as dinero
from frontend import mostrador3d_productos as mp
from frontend.componentes import destruir_arbol, rgb
from frontend.props_mundo import Malla, caja

# Cajón: 4 columnas x 3 filas (de atrás hacia el jugador): billetes grandes, billetes chicos + R$ 1, monedas.
ORDEN_CAJON = ((20000, 10000, 5000, 2000), (1000, 500, 200, 100), (50, 25, 10, 5))
# compartimento (m)
LADO_X, LADO_Z = 0.19, 0.12
# las monedas se ven más grandes que en la vida real (se juega con ellas)
ESCALA_MONEDA = 3.0
GRIS_CAJA, NEGRO_CAJA = (70, 74, 84), (40, 42, 48)
PANTALLA = (120, 200, 140)
TINTA = (24, 24, 30)
RESALTE = (255, 230, 120)


def _texto(padre, cadena, escala, pos, tono=TINTA):
    return Text(parent=padre, text=cadena, scale=escala, origin=(0, 0), position=pos, rotation_x=90, color=rgb(tono))


def entidad_dinero(padre, valor, **opciones):
    """Billete o moneda (Entity con su malla) con su valor escrito encima."""
    if dinero.es_billete(valor):
        e = Entity(parent=padre, model=mp.malla_billete(valor).mesh(), shader=lit_with_shadows_shader, **opciones)
        _texto(e, dinero.nombre_denominacion(valor), 1.5, (0.02, 0.004, 0))
        return e
    e = Entity(parent=padre, model=mp.malla_moneda(valor).mesh(), shader=lit_with_shadows_shader, **opciones)
    e.scale = ESCALA_MONEDA
    _texto(e, dinero.nombre_denominacion(valor).replace("R$ ", ""), 0.32, (0, 0.0035, 0))
    return e


class Caja:

    # padre: raíz del set. posicion: centro del cajón sobre el mostrador. al_agregar(valor), al_quitar(indice).
    def __init__(self, padre, posicion, al_agregar, al_quitar, bandeja=(0.3, 0.96, 0.2), pago=(0.0, 0.96, 0.3)):
        self.raiz = Entity(parent=padre, position=posicion)
        self.al_agregar, self.al_quitar = al_agregar, al_quitar
        self._bandeja_pos, self._pago_pos = bandeja, pago
        self._en_bandeja = []
        self._en_pago = []
        self.activa = False
        self.compartimentos = {}
        self._construir(padre)

    def _construir(self, padre):
        filas, columnas = len(ORDEN_CAJON), len(ORDEN_CAJON[0])
        ancho, fondo = columnas * LADO_X + 0.03, filas * LADO_Z + 0.03
        m = Malla()
        m.agregar(caja(), (0, 0.015, 0), (ancho, 0.03, fondo), 0, NEGRO_CAJA, (1, 1))
        for k in range(columnas + 1):
            m.agregar(caja(), (-ancho / 2 + 0.015 + k * LADO_X, 0.035, 0), (0.008, 0.03, fondo), 0, GRIS_CAJA, (1, 1))
        for k in range(filas + 1):
            m.agregar(caja(), (0, 0.035, -fondo / 2 + 0.015 + k * LADO_Z), (ancho, 0.03, 0.008), 0, GRIS_CAJA, (1, 1))
        # la máquina, a la derecha del cajón, con su pantallita verde mirando al jugador
        mx = ancho / 2 + 0.17
        m.agregar(caja(), (mx, 0.12, 0.02), (0.3, 0.24, 0.36), 0, GRIS_CAJA, (0.8, 1.05))
        m.agregar(caja(), (mx, 0.3, 0.1), (0.24, 0.12, 0.06), 0, NEGRO_CAJA, (1, 1))
        m.agregar(caja(), (mx, 0.3, 0.068), (0.2, 0.07, 0.006), 0, PANTALLA, (1, 1.1))
        for i in range(3):
            for j in range(3):
                m.agregar(caja(), (mx - 0.07 + j * 0.07, 0.245, -0.1 + i * 0.055), (0.055, 0.012, 0.042), 0,
                          (200, 200, 206), (1, 1))
        Entity(parent=self.raiz, model=m.mesh(), shader=lit_with_shadows_shader)
        self.pantalla = Text(parent=self.raiz, text="", scale=0.75, origin=(0, 0), color=rgb(TINTA),
                             position=(mx, 0.3, 0.064))
        for i, fila in enumerate(ORDEN_CAJON):
            for j, valor in enumerate(fila):
                x = -ancho / 2 + 0.015 + (j + 0.5) * LADO_X
                z = fondo / 2 - 0.015 - (i + 0.5) * LADO_Z
                self.compartimentos[valor] = self._compartimento(valor, x, z)

    def _compartimento(self, valor, x, z):
        zona = Entity(parent=self.raiz, model="cube", position=(x, 0.03, z), scale=(LADO_X - 0.01, 0.05, LADO_Z - 0.01),
                      color=color.rgba32(255, 255, 255, 0), collider="box", shader=unlit_shader)
        # tres piezas apiladas, un poco desordenadas
        for k in range(3):
            entidad_dinero(self.raiz, valor, position=(x + 0.004 * k, 0.032 + 0.004 * k, z - 0.003 * k),
                           rotation_y=4 * k - 4)
        zona.on_click = lambda v=valor: self.activa and self.al_agregar(v)
        zona.on_mouse_enter = lambda z=zona: setattr(z, "color", color.rgba32(*RESALTE, 70) if self.activa else z.color)
        zona.on_mouse_exit = lambda z=zona: setattr(z, "color", color.rgba32(255, 255, 255, 0))
        return zona

    # -- Bandeja del cambio y pago del cliente --

    def poner_bandeja(self, valores):
        """Pinta la bandeja con `valores` (lista del TurnoMostrador): billetes en abanico, monedas en fila."""
        for e in self._en_bandeja:
            destruir_arbol(e)
        self._en_bandeja = []
        bx, by, bz = self._bandeja_pos
        billetes = [(i, v) for i, v in enumerate(valores) if dinero.es_billete(v)]
        monedas = [(i, v) for i, v in enumerate(valores) if not dinero.es_billete(v)]
        for k, (i, v) in enumerate(billetes):
            self._en_bandeja.append(self._pieza_bandeja(i, v, (bx + 0.012 * k, by + 0.003 * k, bz + 0.01 * k), 8 * k))
        for k, (i, v) in enumerate(monedas):
            fila, col = divmod(k, 6)
            self._en_bandeja.append(self._pieza_bandeja(i, v, (bx - 0.12 + 0.05 * col, by + 0.002, bz - 0.09 - 0.05 * fila),
                                                        0))

    def _pieza_bandeja(self, indice, valor, pos, giro):
        e = entidad_dinero(self.raiz.parent, valor, position=pos, rotation_y=giro)
        e.collider = "box"
        e.on_click = lambda i=indice: self.activa and self.al_quitar(i)
        return e

    def poner_pago(self, valores):
        """Lo que paga el cliente, sobre el mostrador delante de él."""
        for e in self._en_pago:
            destruir_arbol(e)
        self._en_pago = []
        px, py, pz = self._pago_pos
        for k, v in enumerate(valores):
            if dinero.es_billete(v):
                pos = (px + 0.02 * k, py + 0.003 * k, pz + 0.012 * k)
            else:
                pos = (px - 0.16 + 0.05 * k, py + 0.002, pz - 0.08)
            self._en_pago.append(entidad_dinero(self.raiz.parent, v, position=pos, rotation_y=180 + 6 * k))

    def mostrar_total(self, centavos):
        self.pantalla.text = "" if centavos is None else dinero.formatear(centavos)

    def destruir(self):
        for e in self._en_bandeja + self._en_pago:
            destruir_arbol(e)
        destruir_arbol(self.raiz)
