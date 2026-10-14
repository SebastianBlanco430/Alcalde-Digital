# Ciudad Nova en 3D real (Ursina): construye el mundo visible a partir de un MundoCiudad
# (backend): suelo de pasto, calles con líneas y aceras con bordillo, plazas, un edificio por
# lugar con ventanas, letrero y PUERTA con bisagra, árboles, farolas y bancos, cielo, luz
# direccional con sombras y una luz ambiental.
#
# Rendimiento (medido en la Fase 0, ver mundo3d-progreso.md): la geometría estática se
# combina con Entity.combine() por tipo de material (suelo, calles, plazas, edificios,
# ventanas, vegetación, mobiliario, luces): ~13 veces más rápido que ~300 entidades
# sueltas. Solo quedan sueltos lo que se mueve o se anima (puertas) y los letreros (Text).
#
# Terreno: el suelo es una malla (o el plano de siempre si el terreno es plano) y calles, aceras,
# líneas, plazas, edificios y props se posan sobre la altura analítica del backend
# (MundoCiudad.altura_en). Las calles se parten en tramos de ~2 m inclinados para seguir la rampa.
#
# Assets: cada edificio, árbol, farola, banco y puerta pasa por catalogo_assets.crear_entidad: sin
# modelo (.glb) se dibuja con primitivas, como siempre; con modelo se coloca como Entity suelta
# (no se combina: perdería la textura) en el grupo `modelos`. El modelo es solo visual: huella,
# puerta y colisiones salen del backend.
#
# Colisión: solo los EDIFICIOS tienen collider 'box', y cuelgan de `raiz_colisiones`, que es
# lo único contra lo que hace raycast la cámara. El movimiento del jugador NO usa estos
# colliders: lo resuelve MundoCiudad (backend) con círculos y cajas.
#
# Puertas: `puertas[lugar]` es un PuertaEdificio. Su raíz está en la puerta del modelo y
# gira con el rumbo de entrada (su +z local apunta hacia DENTRO del edificio, -z hacia la
# calle); la bisagra está a la derecha y la hoja se abre hacia afuera con rotation_y = -100.

import math

from ursina import Entity, Sky, Text, color, scene
from ursina.lights import AmbientLight, DirectionalLight
from ursina.shaders import lit_with_shadows_shader

from ursina import Mesh, Vec3

from frontend import catalogo_assets, geometria_mundo
from frontend.componentes import rgb
from frontend.piezas import encender_luz, pieza, silenciar

SOMBRAS = True                       # decidido en la Fase 0: cuestan ~0.1 ms con combine()
RESOLUCION_SOMBRAS = (4096, 4096)

COLOR_PASTO = (84, 142, 74)
COLOR_ASFALTO = (66, 68, 78)
COLOR_LINEA = (235, 220, 150)
COLOR_ACERA = (178, 178, 186)
COLOR_PLAZA = (206, 196, 176)
COLOR_ANILLO_PLAZA = (172, 172, 180)
COLOR_EMBLEMA = (150, 140, 124)
COLOR_VENTANA = (150, 205, 235)
COLOR_MADERA = (122, 82, 52)
COLOR_MARCO_PUERTA = (28, 28, 36)
COLOR_LETRERO = (30, 32, 46)
PALETA_EDIFICIOS = (
    (226, 226, 232), (232, 196, 170), (176, 196, 232), (196, 232, 196),
    (232, 196, 214), (240, 224, 164), (206, 190, 232),
)

# Alturas (y) de las capas planas del piso (cada una por encima de la anterior).
Y_ASFALTO = 0.05          # cubo de 0.10: tapa en y = 0.10
Y_LINEA = 0.106
Y_ACERA = 0.10            # cubo de 0.20: tapa en y = 0.20
Y_ANILLO = 0.12
Y_PLAZA = 0.14
Y_EMBLEMA = 0.16

ANCHO_PUERTA, ALTO_PUERTA = 1.6, 2.4
ANGULO_PUERTA_ABIERTA = -100
SEPARACION_LINEAS = 4.0
SEPARACION_VENTANAS = 3.2

# Terreno (malla del suelo).
RESOLUCION_TERRENO = 2.0     # m por celda de la malla
MARGEN_TERRENO = 40.0        # m de ladera más allá de los límites caminables
PASO_CALLE = 2.0             # m de cada tramo inclinado de calle
HUNDIMIENTO = 0.12           # m que baja la malla bajo lo construido (los pisos finos no quedan tapados)
FALDON_EDIFICIO = 1.5        # m que el zócalo baja bajo la plataforma para tapar el talud
COLOR_TIERRA = (142, 106, 72)
COLOR_ROCA = (126, 122, 116)
COLOR_PASTO_SECO = (128, 150, 82)


# Una puerta con bisagra: la hoja gira sobre `bisagra`. abrir(t) con t en [0, 1].
class PuertaEdificio(Entity):

    # `base_y`: altura del suelo en la puerta. `ocultar` = el modelo del edificio trae su propia
    # puerta: no se dibuja la procedural (la bisagra y el letrero siguen existiendo).
    def __init__(self, edificio, base_y=0.0, ocultar=False, **opciones):
        px, pz = edificio.puerta()
        super().__init__(position=(px, base_y, pz), rotation_y=edificio.rumbo_puerta(), **opciones)
        self.edificio = edificio
        self.bisagra = Entity(parent=self, position=(ANCHO_PUERTA / 2, 0, -0.07))
        self.marco = self.hoja = None
        if ocultar:
            return
        self.marco = pieza(parent=self, model="cube", color=rgb(COLOR_MARCO_PUERTA),
                           position=(0, ALTO_PUERTA / 2 + 0.05, 0), scale=(ANCHO_PUERTA + 0.3, ALTO_PUERTA + 0.1, 0.12))
        # Hoja con modelo propio (catálogo "puerta": origen en la base, al centro de la hoja) o procedural.
        self.hoja = catalogo_assets.crear_entidad(
            "puerta", parent=self.bisagra, position=(-ANCHO_PUERTA / 2, 0, 0))

    # 0 = cerrada, 1 = abierta del todo.
    def abrir(self, t):
        self.bisagra.rotation_y = ANGULO_PUERTA_ABIERTA * min(1.0, max(0.0, t))

    @property
    def apertura(self):
        return self.bisagra.rotation_y / ANGULO_PUERTA_ABIERTA


# Constructores procedurales del catálogo (lo que se dibuja mientras no hay modelo). Reciben
# `parent` y `position` (x, y, z con y = suelo) y devuelven la primera pieza creada.

def _puerta_procedural(clave, parent=None, position=(0, 0, 0), **_):
    x, y, z = position
    hoja = pieza(parent=parent, model="cube", color=rgb(COLOR_MADERA),
                 position=(x, y + ALTO_PUERTA / 2, z), scale=(ANCHO_PUERTA, ALTO_PUERTA, 0.1))
    pieza(parent=parent, model="sphere", color=color.rgb32(220, 200, 120),
          position=(x - ANCHO_PUERTA / 2 + 0.2, y + ALTO_PUERTA / 2, z - 0.09), scale=0.12)
    return hoja


def _arbol_procedural(clave, parent=None, position=(0, 0, 0), variante=0, **_):
    x, y, z = position
    verde = ((58, 130, 62), (74, 148, 70), (46, 112, 70))[variante % 3]
    tronco = pieza(parent=parent, model="cube", color=rgb((98, 68, 44)), position=(x, y + 0.9, z),
                   scale=(0.32, 1.8, 0.32))
    pieza(parent=parent, model="sphere", color=rgb(verde), position=(x, y + 2.9, z), scale=(2.7, 2.4, 2.7))
    pieza(parent=parent, model="sphere", color=rgb(tuple(min(255, c + 14) for c in verde)),
          position=(x + 0.2, y + 3.9, z - 0.1), scale=1.7)
    return tronco


def _farola_procedural(clave, parent=None, position=(0, 0, 0), luces=None, **_):
    x, y, z = position
    poste = pieza(parent=parent, model="cube", color=rgb((70, 72, 82)), position=(x, y + 2.1, z),
                  scale=(0.14, 4.2, 0.14))
    pieza(parent=luces if luces is not None else parent, model="sphere", color=rgb((255, 238, 170)),
          position=(x, y + 4.35, z), scale=0.5, shader=None)
    return poste


def _banco_procedural(clave, parent=None, position=(0, 0, 0), ancho=1.8, fondo=0.7, **_):
    x, y, z = position
    madera = rgb((140, 96, 60))
    asiento = pieza(parent=parent, model="cube", color=madera, position=(x, y + 0.46, z), scale=(ancho, 0.1, fondo))
    pieza(parent=parent, model="cube", color=madera, position=(x, y + 0.82, z + fondo / 2 - 0.04),
          scale=(ancho, 0.5, 0.08))
    for dx in (-ancho / 2 + 0.15, ancho / 2 - 0.15):
        pieza(parent=parent, model="cube", color=rgb((60, 62, 72)), position=(x + dx, y + 0.22, z),
              scale=(0.1, 0.44, fondo - 0.1))
    return asiento


# Cuerpo del edificio (cubo, zócalo y techo). `position` = centro de la base; `faldon` baja el zócalo.
def _edificio_procedural(clave, parent=None, position=(0, 0, 0), huella=(1, 1, 1), tono=(226, 226, 232),
                         faldon=0.0, **_):
    x, y, z = position
    ancho, fondo, alto = huella
    oscuro = tuple(int(c * 0.62) for c in tono)
    cuerpo = pieza(parent=parent, model="cube", color=rgb(tono), position=(x, y + alto / 2, z),
                   scale=(ancho, alto, fondo))
    pieza(parent=parent, model="cube", color=rgb((120, 120, 130)), position=(x, y + 0.35 - faldon / 2, z),
          scale=(ancho + 0.3, 0.7 + faldon, fondo + 0.3))                              # zócalo
    pieza(parent=parent, model="cube", color=rgb(oscuro), position=(x, y + alto + 0.18, z),
          scale=(ancho + 0.7, 0.36, fondo + 0.7))                                      # techo
    return cuerpo


# Color provisorio del terreno según pendiente (fracción) y altura (m): pasto, tierra, roca.
def _color_terreno(pendiente, altura):
    seco = min(1.0, max(0.0, (altura - 3.0) / 8.0)) * 0.5
    base = _mezclar(COLOR_PASTO, COLOR_PASTO_SECO, seco)
    t_tierra = min(1.0, max(0.0, (pendiente - 0.15) / 0.2))
    t_roca = min(1.0, max(0.0, (pendiente - 0.45) / 0.3))
    return _mezclar(_mezclar(base, COLOR_TIERRA, t_tierra), COLOR_ROCA, t_roca)


def _mezclar(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


catalogo_assets.registrar_procedural("puerta", _puerta_procedural)
catalogo_assets.registrar_procedural("arbol", _arbol_procedural)
catalogo_assets.registrar_procedural("farola", _farola_procedural)
catalogo_assets.registrar_procedural("banco", _banco_procedural)
catalogo_assets.registrar_procedural("edificio", _edificio_procedural)


class Ciudad3D(Entity):

    def __init__(self, mundo, sombras=SOMBRAS, **opciones):
        opciones.setdefault("parent", scene)
        super().__init__(**opciones)
        self._mundo = mundo
        self.puertas = {}              # lugar -> PuertaEdificio
        self.letreros = {}             # lugar -> Text
        self.raiz_colisiones = Entity(parent=self)
        self._terreno = mundo.terreno
        self.modelos = Entity(parent=self)       # modelos importados: sueltos, sin combinar
        self._grupos = {nombre: Entity(parent=self, shader=lit_with_shadows_shader) for nombre in (
            "suelo", "calles", "plazas", "edificios", "vegetacion", "mobiliario")}
        # Lo que debe verse brillante, sin sombreado (ventanas y focos de las farolas).
        self._grupos["ventanas"] = Entity(parent=self, shader=None)
        self._grupos["luces"] = Entity(parent=self, shader=None)

        # El cielo cuelga de la ciudad (no se ve en los menús 2D) y sigue a la cámara en su update().
        self.cielo = Sky(parent=self)
        self.luz = DirectionalLight(parent=self, shadows=False, shadow_map_resolution=RESOLUCION_SOMBRAS)
        self.luz.look_at((1, -1.6, 0.8))
        self.ambiente = AmbientLight(parent=self, color=color.rgba32(112, 112, 122, 255))

        self._construir_suelo()
        self._construir_calles()
        self._construir_plazas()
        self._construir_edificios()
        self._construir_obstaculos()
        for grupo in self._grupos.values():
            if grupo.children:                   # un grupo vacío (todo con modelo propio) no se combina
                grupo.combine()
        for hijo in self.children:
            if hijo is not self.cielo:
                silenciar(hijo)            # lo estático no necesita update() (ver piezas.silenciar)
        if sombras:
            self.luz.shadows = True
            # El volumen de sombra abarca los edificios (no el suelo gigante: restaría precisión).
            self.luz.update_bounds(self._grupos["edificios"] if self._grupos["edificios"].model
                                   else self.modelos)
        self.encender_luces(False)           # EscenaMundo la enciende en al_entrar

    # La ciudad enciende su luz al entrar a la escena y la apaga al salir (ver piezas.encender_luz).
    def encender_luces(self, encendidas):
        encender_luz(self.luz, encendidas)
        encender_luz(self.ambiente, encendidas)

    def cerrar_puertas(self):
        for puerta in self.puertas.values():
            puerta.abrir(0)

    # -- Suelo, calles y plazas --

    # Altura del suelo en (x, z) (0 si el terreno es plano).
    def _y(self, x, z):
        return self._mundo.altura_en(x, z)

    def _construir_suelo(self):
        xmin, xmax, zmin, zmax = self._mundo.limites()
        if self._terreno.es_plano:
            pieza(parent=self._grupos["suelo"], model="plane", color=rgb(COLOR_PASTO),
                  position=((xmin + xmax) / 2, 0, (zmin + zmax) / 2),
                  scale=(xmax - xmin + 80, 1, zmax - zmin + 80))
            return
        # Malla del terreno: una sola Entity (no entra al combine), color y normal por vértice.
        paso = RESOLUCION_TERRENO
        x0, z0 = xmin - MARGEN_TERRENO, zmin - MARGEN_TERRENO
        nx = math.ceil((xmax + MARGEN_TERRENO - x0) / paso) + 1
        nz = math.ceil((zmax + MARGEN_TERRENO - z0) / paso) + 1
        alturas = [[self._y(x0 + i * paso, z0 + j * paso) for j in range(nz)] for i in range(nx)]
        vertices, colores, normales = [], [], []
        for i in range(nx):
            i0, i1 = max(i - 1, 0), min(i + 1, nx - 1)
            for j in range(nz):
                j0, j1 = max(j - 1, 0), min(j + 1, nz - 1)
                x, z, h = x0 + i * paso, z0 + j * paso, alturas[i][j]
                dhdx = (alturas[i1][j] - alturas[i0][j]) / ((i1 - i0) * paso)
                dhdz = (alturas[i][j1] - alturas[i][j0]) / ((j1 - j0) * paso)
                d = self._terreno.distancia_a_lo_construido(x, z)
                hundido = HUNDIMIENTO * max(0.0, 1.0 - d / 3.0)
                vertices.append(Vec3(x, h - hundido, z))
                largo = math.sqrt(dhdx * dhdx + 1 + dhdz * dhdz)
                normales.append(Vec3(-dhdx / largo, 1 / largo, -dhdz / largo))
                colores.append(rgb(_color_terreno(math.hypot(dhdx, dhdz), h)))
        triangulos = []
        for i in range(nx - 1):
            for j in range(nz - 1):
                a, b = i * nz + j, i * nz + j + 1
                c, d = (i + 1) * nz + j, (i + 1) * nz + j + 1
                triangulos += [(a, b, d), (a, d, c)]
        malla = Mesh(vertices=vertices, triangles=triangulos, colors=colores, normals=normales, static=True)
        pieza(parent=self, model=malla, double_sided=True)

    # Cada calle se parte en tramos de PASO_CALLE m (uno solo con terreno plano); cada tramo es un
    # cubo inclinado según la altura en sus extremos. Las aceras van por tramos entre las plazas.
    def _construir_calles(self):
        mundo = self._mundo
        calles = self._grupos["calles"]
        semiancho = mundo.ancho_calle / 2
        plano = self._terreno.es_plano
        for a, b in mundo.segmentos():
            (ax, az), (bx, bz) = mundo.coordenada(a), mundo.coordenada(b)
            largo = math.hypot(bx - ax, bz - az)
            ux, uz = (bx - ax) / largo, (bz - az) / largo
            rumbo = geometria_mundo.rumbo_de(bx - ax, bz - az)
            for s0, s1 in self._tramos(0.0, largo, plano):
                self._tramo(calles, COLOR_ASFALTO, (ax, az), (ux, uz), s0, s1, rumbo, 0.0, mundo.ancho_calle,
                            Y_ASFALTO, 0.10)
            # Aceras: a cada lado, entre las plazas (el aro de la plaza las recibe).
            inicio, fin = mundo.radio_plaza + 0.9, largo - mundo.radio_plaza - 0.9
            if fin > inicio:
                for s0, s1 in self._tramos(inicio, fin, plano):
                    for lado in (-1, 1):
                        self._tramo(calles, COLOR_ACERA, (ax, az), (ux, uz), s0, s1, rumbo,
                                    lado * (semiancho + 1.0), 2.0, Y_ACERA, 0.20)
            # Línea central discontinua.
            s = mundo.radio_plaza + 2.0
            while s + 1.0 <= largo - mundo.radio_plaza - 2.0:
                self._tramo(calles, COLOR_LINEA, (ax, az), (ux, uz), s, s + 2.0, rumbo, 0.0, 0.22,
                            Y_LINEA, 0.02)
                s += SEPARACION_LINEAS

    # [(s0, s1)] partiendo [desde, hasta] en tramos de ~PASO_CALLE (uno solo si `entero`).
    @staticmethod
    def _tramos(desde, hasta, entero):
        n = 1 if entero else max(1, math.ceil((hasta - desde) / PASO_CALLE))
        return [(desde + (hasta - desde) * k / n, desde + (hasta - desde) * (k + 1) / n) for k in range(n)]

    # Un cubo plano a lo largo del eje de una calle entre s0 y s1 (metros desde su inicio), desplazado
    # `lateral` m, de `ancho` x `grosor`, con su cara inferior a `y_capa` sobre el suelo.
    def _tramo(self, grupo, tono, origen, eje, s0, s1, rumbo, lateral, ancho, y_capa, grosor):
        (ax, az), (ux, uz) = origen, eje
        x0, z0 = ax + ux * s0 - uz * lateral, az + uz * s0 + ux * lateral
        x1, z1 = ax + ux * s1 - uz * lateral, az + uz * s1 + ux * lateral
        y0, y1 = self._y(x0, z0), self._y(x1, z1)
        paso = s1 - s0
        largo = math.hypot(paso, y1 - y0) * (1.0 if self._terreno.es_plano else 1.04)   # sin rendijas
        pieza(parent=grupo, model="cube", color=rgb(tono),
              position=((x0 + x1) / 2, (y0 + y1) / 2 + y_capa, (z0 + z1) / 2),
              scale=(ancho, grosor, largo),
              rotation=(-math.degrees(math.atan2(y1 - y0, paso)), rumbo, 0))

    def _construir_plazas(self):
        plazas = self._grupos["plazas"]
        radio = self._mundo.radio_plaza
        for lugar in self._mundo.lugares():
            cx, cz = self._mundo.coordenada(lugar)
            base = self._mundo.elevacion_lugar(lugar)
            for y, r, tono in ((Y_ANILLO, radio + 0.9, COLOR_ANILLO_PLAZA), (Y_PLAZA, radio, COLOR_PLAZA),
                               (Y_EMBLEMA, 1.6, COLOR_EMBLEMA)):
                pieza(parent=plazas, model="circle", rotation_x=90, position=(cx, base + y, cz),
                      scale=2 * r, color=rgb(tono))

    # -- Edificios --

    def _construir_edificios(self):
        for i, edificio in enumerate(self._mundo.edificios()):
            tono = PALETA_EDIFICIOS[i % len(PALETA_EDIFICIOS)]
            base = self._mundo.elevacion_lugar(edificio.lugar)
            clave = catalogo_assets.clave_edificio(edificio.lugar)
            asset = catalogo_assets.asset_de(clave)
            con_modelo = catalogo_assets.usa_modelo(clave)
            # El modelo es solo visual: la huella (ancho, fondo, alto) y la puerta vienen del backend.
            catalogo_assets.crear_entidad(
                clave, parent=self.modelos if con_modelo else self._grupos["edificios"],
                position=(edificio.cx, base, edificio.cz), huella=(edificio.ancho, edificio.fondo, edificio.alto),
                tono=tono, faldon=0.0 if self._terreno.es_plano else FALDON_EDIFICIO)
            if not con_modelo:
                self._ventanas(edificio, base)
            self.puertas[edificio.lugar] = PuertaEdificio(
                edificio, base_y=self._y(*edificio.puerta()), ocultar=con_modelo and asset.ocultar_puerta,
                parent=self)
            self._letrero(edificio)
            # Collider solo para el raycast de la cámara.
            Entity(parent=self.raiz_colisiones, model="cube", collider="box", visible=False,
                   position=(edificio.cx, base + edificio.alto / 2, edificio.cz),
                   scale=(edificio.ancho, edificio.alto, edificio.fondo))

    # Ventanas en las cuatro caras (en la de la puerta, solo a los lados de ella).
    def _ventanas(self, e, base=0.0):
        g = self._grupos["ventanas"]
        filas = (2.6,) if e.alto < 7 else (2.6, 5.4)
        if e.alto >= 9:
            filas = (2.6, 5.4, 8.0)[: int((e.alto - 1) // 2.7)]
        caras = {"n": (0, 1, e.ancho), "s": (0, -1, e.ancho), "e": (1, 0, e.fondo), "o": (-1, 0, e.fondo)}
        for lado, (nx, nz, largo) in caras.items():
            cantidad = max(1, int((largo - 1.5) // SEPARACION_VENTANAS))
            for k in range(cantidad):
                desfase = (k - (cantidad - 1) / 2) * SEPARACION_VENTANAS
                if lado == e.lado_puerta and abs(desfase) < 2.4:
                    continue
                for y in filas:
                    if lado == e.lado_puerta and y < 3.0 and abs(desfase) < 3.4:
                        continue
                    # a lo largo de la cara: eje x para n/s, eje z para e/o
                    x = e.cx + nx * (e.ancho / 2 + 0.03) + (desfase if nx == 0 else 0)
                    z = e.cz + nz * (e.fondo / 2 + 0.03) + (desfase if nz == 0 else 0)
                    escala = (1.5, 1.3, 0.06) if nx == 0 else (0.06, 1.3, 1.5)
                    pieza(parent=g, model="cube", color=rgb(COLOR_VENTANA), position=(x, base + y + 0.6, z),
                          scale=escala, shader=None)

    # Cartel sobre la puerta: tablero oscuro y texto con el nombre del edificio.
    def _letrero(self, e):
        puerta = self.puertas[e.lugar]
        ancho = min(max(len(e.titulo) * 0.42, 3.0), e.ancho - 0.5)
        pieza(parent=puerta, model="cube", color=rgb(COLOR_LETRERO),
              position=(0, ALTO_PUERTA + 0.75, -0.12), scale=(ancho, 0.8, 0.14))
        texto = Text(e.titulo, parent=puerta, origin=(0, 0), position=(0, ALTO_PUERTA + 0.75, -0.22),
                     scale=11, color=color.rgb32(240, 240, 245))
        self.letreros[e.lugar] = texto

    # -- Árboles, farolas y bancos (salen de los obstáculos del modelo) --

    def _construir_obstaculos(self):
        for o in self._mundo.obstaculos():
            if o.tipo == "arbol":
                self._arbol(o)
            elif o.tipo == "farola":
                self._farola(o)
            elif o.tipo == "banco":
                self._banco(o)

    def _arbol(self, o):
        variante = (int(abs(o.cx * 7 + o.cz * 13)) % 3)
        self._prop("arbol", o, variante=variante)

    def _farola(self, o):
        self._prop("farola", o, luces=self._grupos["luces"])

    def _banco(self, o):
        self._prop("banco", o, ancho=o.ancho, fondo=o.fondo)

    # Un prop del catálogo sobre el terreno: con modelo, suelto en `modelos`; sin él, en el grupo
    # combinado que le toca.
    def _prop(self, clave, o, **opciones):
        grupo = {"arbol": "vegetacion", "farola": "mobiliario", "banco": "mobiliario"}[clave]
        con_modelo = catalogo_assets.usa_modelo(clave)
        catalogo_assets.crear_entidad(
            clave, parent=self.modelos if con_modelo else self._grupos[grupo],
            position=(o.cx, self._y(o.cx, o.cz), o.cz), **opciones)
