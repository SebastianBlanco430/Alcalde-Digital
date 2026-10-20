# Fondo de los menús (inicio y selección de rol) y utilidades comunes de menú (T7-T9,
# docs/DISENO.md sección 6). Todo 2D en camera.ui y sin shaders ni texturas:
#   - cielo de tarde con degradado por colores de vértice,
#   - baliza amarilla (rombo) como sol bajo,
#   - 3 capas de siluetas de ladera y casas que derivan despacio (cada capa, una malla),
#   - velo de tinta para que el contenido se lea.
# Capa pura (sin ventana): `generar_silueta`, `degradado_cielo`, `desplazamiento_capa`.
# Utilidades: `anadir_filo` (borde interior claro, porque la tinta casi no se ve sobre el fondo
# oscuro) y `FocoTeclado` (navegación por teclado entre botones, coexiste con el ratón).
import math
import random

from ursina import Entity, Mesh, camera, color, time

from frontend import estilo
from frontend.componentes import a_unidades, modelo_redondeado, rgb

# --- Cielo de tarde: (y relativa 0 = arriba, 1 = horizonte), color RGB ---
PARADAS_CIELO = (
    (0.0, (38, 48, 104)),
    (0.45, (96, 84, 150)),
    (0.78, (232, 140, 120)),
    (1.0, (255, 200, 124)),
)
Y_HORIZONTE = -0.12          # y (camera.ui) donde el cielo llega al horizonte
ANCHO_CIELO = 6.0
PERIODO = 3.0                # ancho (unidades) tras el cual el dibujo de una capa se repite
X_ORIGEN = -1.5              # borde izquierdo de la primera copia de cada capa

# Capas de lejos a cerca: color de la ladera, base y, amplitud, casas, velocidad de deriva (u/s).
CAPAS = (
    {"nombre": "lejana", "color": (104, 106, 168), "base": -0.10, "amplitud": 0.05, "casas": 0,
     "velocidad": 0.010, "z": 0.90},
    {"nombre": "media", "color": (64, 66, 120), "base": -0.22, "amplitud": 0.05, "casas": 9,
     "velocidad": 0.020, "z": 0.80},
    {"nombre": "cercana", "color": (30, 32, 62), "base": -0.36, "amplitud": 0.04, "casas": 7,
     "velocidad": 0.034, "z": 0.70},
)
ALFA_VELO = 55
Y_FONDO = -0.6              # parte baja del dibujo (por debajo de la pantalla)


# Degradado vertical: lista de (y, rgb) de arriba (y = 0.5) a `Y_HORIZONTE`.
def degradado_cielo(arriba=0.6, horizonte=Y_HORIZONTE, paradas=PARADAS_CIELO):
    return [(arriba + (horizonte - arriba) * t, c) for t, c in paradas]


def _mezclar(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


# Altura de la ladera en x: suma de senos con ciclos enteros por PERIODO (la capa casa al repetirse).
def altura_ladera(x, base, amplitud, fase):
    u = 2 * math.pi * x / PERIODO
    return base + amplitud * (0.62 * math.sin(2 * u + fase) + 0.38 * math.sin(5 * u + 1.7 * fase))


# Silueta de una capa en datos puros: (vertices [(x, y)], triangulos [(a, b, c)], colores [rgb]).
# Ladera en tiras + casas (caja y tejado a dos aguas, algo más oscuro) sobre la ladera.
# Con la misma `semilla` sale siempre lo mismo.
def generar_silueta(semilla, color_base, base, amplitud, casas, ventanas=False, paso=0.05):
    azar = random.Random(semilla)
    fase = azar.uniform(0, 2 * math.pi)
    vertices, triangulos, colores = [], [], []

    def cuadro(p0, p1, p2, p3, c):
        i = len(vertices)
        vertices.extend([p0, p1, p2, p3])
        colores.extend([c] * 4)
        triangulos.extend([(i, i + 1, i + 2), (i, i + 2, i + 3)])

    def triangulo(p0, p1, p2, c):
        i = len(vertices)
        vertices.extend([p0, p1, p2])
        colores.extend([c] * 3)
        triangulos.append((i, i + 1, i + 2))

    n = int(round(PERIODO / paso))
    for k in range(n):
        x0, x1 = k * paso, (k + 1) * paso
        y0 = altura_ladera(x0, base, amplitud, fase)
        y1 = altura_ladera(x1, base, amplitud, fase)
        cuadro((x0, Y_FONDO), (x1, Y_FONDO), (x1, y1), (x0, y0), color_base)

    oscuro = _mezclar(color_base, estilo.TINTA, 0.35)
    claro = _mezclar(color_base, (255, 255, 255), 0.10)
    cerca = ventanas
    for i in range(casas):
        centro = (i + azar.uniform(0.15, 0.85)) * PERIODO / max(casas, 1)
        ancho = azar.uniform(0.10, 0.17) if cerca else azar.uniform(0.07, 0.12)
        alto = azar.uniform(0.07, 0.12) if cerca else azar.uniform(0.045, 0.08)
        suelo = min(altura_ladera(centro - ancho / 2, base, amplitud, fase),
                    altura_ladera(centro + ancho / 2, base, amplitud, fase)) - 0.01
        izq, der = centro - ancho / 2, centro + ancho / 2
        tono = claro if azar.random() < 0.4 else color_base
        cuadro((izq, suelo), (der, suelo), (der, suelo + alto), (izq, suelo + alto), tono)
        triangulo((izq - 0.012, suelo + alto), (der + 0.012, suelo + alto),
                  (centro, suelo + alto + ancho * 0.30), oscuro)
        if ventanas:
            lado = ancho * 0.16
            for v in range(azar.choice((1, 2))):
                vx = izq + ancho * (0.22 + 0.42 * v)
                vy = suelo + alto * 0.35
                cuadro((vx, vy), (vx + lado, vy), (vx + lado, vy + lado * 1.2), (vx, vy + lado * 1.2),
                       estilo.COLOR_ACENTO)
    return vertices, triangulos, colores


# Desplazamiento x (negativo, hacia la izquierda) de una capa a los `t` segundos.
def desplazamiento_capa(t, velocidad, periodo=PERIODO):
    return -((t * velocidad) % periodo)


def _malla(vertices, triangulos, colores):
    from ursina import Vec3
    return Mesh(
        vertices=[Vec3(x, y, 0) for x, y in vertices], triangles=triangulos,
        colors=[color.rgb32(*c) for c in colores], static=True,
    )



# Rombo unitario (baliza del juego). Un Mesh solo puede colgar de una entidad: una malla por uso.
def malla_rombo():
    from ursina import Vec3
    return Mesh(vertices=[Vec3(0, -0.5, 0), Vec3(0.5, 0, 0), Vec3(0, 0.5, 0), Vec3(-0.5, 0, 0)],
                triangles=[(0, 1, 2), (0, 2, 3)], static=True)


# Fondo animado del menú. `velo` = alfa (0-255) del velo de tinta; `deriva` = si las capas se mueven.
class FondoMenu(Entity):

    def __init__(self, velo=ALFA_VELO, deriva=True, **opciones):
        opciones.setdefault("parent", camera.ui)
        super().__init__(**opciones)
        self.deriva = deriva
        self.t = 0.0
        # Cielo: franjas horizontales con color por vértice (degradado sin textura).
        niveles = degradado_cielo()
        vertices, tri, colores = [], [], []
        for i, (y, c) in enumerate(niveles):
            vertices += [(-ANCHO_CIELO / 2, y), (ANCHO_CIELO / 2, y)]
            colores += [c, c]
            if i:
                b = 2 * i
                tri += [(b - 2, b + 1, b - 1), (b - 2, b, b + 1)]
        # Bajo el horizonte, relleno con el color del horizonte.
        b = len(vertices)
        vertices += [(-ANCHO_CIELO / 2, Y_FONDO), (ANCHO_CIELO / 2, Y_FONDO)]
        colores += [niveles[-1][1]] * 2
        tri += [(b - 2, b + 1, b - 1), (b - 2, b, b + 1)]
        self.cielo = Entity(parent=self, model=_malla(vertices, tri, colores), z=1.0, shader=None)

        # Baliza amarilla como sol bajo (rombo con borde de tinta), sobre el horizonte.
        self.sol = Entity(parent=self, position=(0.64, 0.05, 0.95))
        Entity(parent=self.sol, model=malla_rombo(), scale=(0.16, 0.22), color=rgb(estilo.TINTA), z=0.001)
        Entity(parent=self.sol, model=malla_rombo(), scale=(0.12, 0.17), color=rgb(estilo.ACENTO_PRIMARIO))

        # Capas de siluetas: tres copias contiguas por capa para que la deriva no deje huecos.
        self.capas = []
        for indice, capa in enumerate(CAPAS):
            datos = generar_silueta(
                31 + indice * 17, capa["color"], capa["base"], capa["amplitud"], capa["casas"],
                ventanas=capa["nombre"] == "cercana")
            raiz = Entity(parent=self, position=(X_ORIGEN, 0, capa["z"]))
            for k in range(3):
                Entity(parent=raiz, model=_malla(*datos), x=k * PERIODO, shader=None)
            self.capas.append((raiz, capa["velocidad"]))

        self.velo = Entity(parent=self, model="quad", scale=(ANCHO_CIELO, 2), z=0.5,
                           color=color.rgba32(*estilo.TINTA, velo))
        self.actualizar_capas()

    def actualizar_capas(self):
        for raiz, velocidad in self.capas:
            raiz.x = X_ORIGEN + desplazamiento_capa(self.t, velocidad)

    def update(self):
        if self.deriva:
            self.t += time.dt
            self.actualizar_capas()


# Borde interior claro de un panel_tinta: la tinta casi no se ve sobre fondos oscuros, así el
# panel conserva su silueta. Va entre el borde de tinta y la cara. Devuelve la entidad.
def anadir_filo(panel, ancho, alto, radio_px, tono=estilo.COLOR_SUPERFICIE_ALTA, grosor_px=2):
    g = a_unidades(grosor_px)
    filo = Entity(parent=panel, model=modelo_redondeado(ancho + 2 * g, alto + 2 * g, radio_px + grosor_px),
                  scale=(ancho + 2 * g, alto + 2 * g), color=rgb(tono), z=0.0035)
    panel.filo = filo
    return filo


def _bajo_el_raton(control):
    consulta = getattr(control, "bajo_el_raton", None)
    return consulta() if callable(consulta) else bool(getattr(control, "hovered", False))


# Navegación por teclado entre controles (flechas/Tab mueven el foco, Enter/Espacio activan).
# `obtener` devuelve la lista actual de controles; cada uno ofrece fijar_foco(bool),
# esta_habilitado() y manejar_clic(); `hovered` o bajo_el_raton() es opcional. El anillo de foco solo se ve tras
# usar el teclado; si el ratón pasa por un control, el foco se va con él (ratón y teclado coexisten).
class FocoTeclado(Entity):

    ATRAS = ("up arrow", "left arrow", "shift tab")
    ADELANTE = ("down arrow", "right arrow", "tab")
    ACTIVAR = ("enter", "space")

    def __init__(self, obtener, **opciones):
        super().__init__(**opciones)
        self._obtener = obtener
        self.indice = 0
        self.visible = False
        self._hover_previo = None

    def controles(self):
        return [c for c in self._obtener() if c.esta_habilitado()]

    def enfocado(self):
        lista = self.controles()
        if not lista:
            return None
        self.indice = max(0, min(self.indice, len(lista) - 1))
        return lista[self.indice]

    def _aplicar(self):
        lista = self.controles()
        actual = self.enfocado()
        for c in self._obtener():
            c.fijar_foco(self.visible and c is actual and c in lista)

    # Restablece el foco al primer control (al entrar en una pantalla o cambiar de paso).
    def reiniciar(self):
        self.indice = 0
        self.visible = False
        self._aplicar()

    def mover(self, paso):
        lista = self.controles()
        if not lista:
            return
        self.visible = True
        self.indice = (self.indice + paso) % len(lista)
        self._aplicar()

    def activar(self):
        actual = self.enfocado()
        if actual is not None:
            actual.manejar_clic()

    def input(self, key):
        if key in self.ATRAS:
            self.mover(-1)
        elif key in self.ADELANTE:
            self.mover(1)
        elif key in self.ACTIVAR:
            self.activar()

    def update(self):
        lista = self.controles()
        bajo_el_raton = next((c for c in lista if _bajo_el_raton(c)), None)
        if bajo_el_raton is not self._hover_previo:
            self._hover_previo = bajo_el_raton
            if bajo_el_raton is not None:
                self.indice = lista.index(bajo_el_raton)
                self.visible = False
        self._aplicar()
