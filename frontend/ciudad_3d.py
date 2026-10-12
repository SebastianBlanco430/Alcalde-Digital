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

from frontend import geometria_mundo
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


# Una puerta con bisagra: la hoja gira sobre `bisagra`. abrir(t) con t en [0, 1].
class PuertaEdificio(Entity):

    def __init__(self, edificio, **opciones):
        px, pz = edificio.puerta()
        super().__init__(position=(px, 0, pz), rotation_y=edificio.rumbo_puerta(), **opciones)
        self.edificio = edificio
        self.marco = pieza(parent=self, model="cube", color=rgb(COLOR_MARCO_PUERTA),
                           position=(0, ALTO_PUERTA / 2 + 0.05, 0), scale=(ANCHO_PUERTA + 0.3, ALTO_PUERTA + 0.1, 0.12))
        self.bisagra = Entity(parent=self, position=(ANCHO_PUERTA / 2, 0, -0.07))
        self.hoja = pieza(parent=self.bisagra, model="cube", color=rgb(COLOR_MADERA),
                          position=(-ANCHO_PUERTA / 2, ALTO_PUERTA / 2, 0),
                          scale=(ANCHO_PUERTA, ALTO_PUERTA, 0.1))
        pieza(parent=self.bisagra, model="sphere", color=color.rgb32(220, 200, 120),
              position=(-ANCHO_PUERTA + 0.2, ALTO_PUERTA / 2, -0.09), scale=0.12)

    # 0 = cerrada, 1 = abierta del todo.
    def abrir(self, t):
        self.bisagra.rotation_y = ANGULO_PUERTA_ABIERTA * min(1.0, max(0.0, t))

    @property
    def apertura(self):
        return self.bisagra.rotation_y / ANGULO_PUERTA_ABIERTA


class Ciudad3D(Entity):

    def __init__(self, mundo, sombras=SOMBRAS, **opciones):
        opciones.setdefault("parent", scene)
        super().__init__(**opciones)
        self._mundo = mundo
        self.puertas = {}              # lugar -> PuertaEdificio
        self.letreros = {}             # lugar -> Text
        self.raiz_colisiones = Entity(parent=self)
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
            grupo.combine()
        for hijo in self.children:
            if hijo is not self.cielo:
                silenciar(hijo)            # lo estático no necesita update() (ver piezas.silenciar)
        if sombras:
            self.luz.shadows = True
            # El volumen de sombra abarca los edificios (no el suelo gigante: restaría precisión).
            self.luz.update_bounds(self._grupos["edificios"])
        self.encender_luces(False)           # EscenaMundo la enciende en al_entrar

    # La ciudad enciende su luz al entrar a la escena y la apaga al salir (ver piezas.encender_luz).
    def encender_luces(self, encendidas):
        encender_luz(self.luz, encendidas)
        encender_luz(self.ambiente, encendidas)

    def cerrar_puertas(self):
        for puerta in self.puertas.values():
            puerta.abrir(0)

    # -- Suelo, calles y plazas --

    def _construir_suelo(self):
        xmin, xmax, zmin, zmax = self._mundo.limites()
        pieza(parent=self._grupos["suelo"], model="plane", color=rgb(COLOR_PASTO),
              position=((xmin + xmax) / 2, 0, (zmin + zmax) / 2),
              scale=(xmax - xmin + 80, 1, zmax - zmin + 80))

    def _construir_calles(self):
        mundo = self._mundo
        calles = self._grupos["calles"]
        semiancho = mundo.ancho_calle / 2
        for a, b in mundo.segmentos():
            (ax, az), (bx, bz) = mundo.coordenada(a), mundo.coordenada(b)
            largo = math.hypot(bx - ax, bz - az)
            ux, uz = (bx - ax) / largo, (bz - az) / largo
            rumbo = geometria_mundo.rumbo_de(bx - ax, bz - az)
            pieza(parent=calles, model="cube", color=rgb(COLOR_ASFALTO),
                  position=((ax + bx) / 2, Y_ASFALTO, (az + bz) / 2),
                  scale=(mundo.ancho_calle, 0.10, largo), rotation_y=rumbo)
            # Aceras: a cada lado, entre las plazas (el aro de la plaza las recibe).
            tramo = largo - 2 * (mundo.radio_plaza + 0.9)
            if tramo > 0:
                mx, mz = (ax + bx) / 2, (az + bz) / 2
                for lado in (-1, 1):
                    d = semiancho + 1.0
                    pieza(parent=calles, model="cube", color=rgb(COLOR_ACERA),
                          position=(mx - uz * lado * d, Y_ACERA, mz + ux * lado * d),
                          scale=(2.0, 0.20, tramo), rotation_y=rumbo)
            # Línea central discontinua.
            s = mundo.radio_plaza + 2.0
            while s + 1.0 <= largo - mundo.radio_plaza - 2.0:
                pieza(parent=calles, model="cube", color=rgb(COLOR_LINEA),
                      position=(ax + ux * (s + 1.0), Y_LINEA, az + uz * (s + 1.0)),
                      scale=(0.22, 0.02, 2.0), rotation_y=rumbo)
                s += SEPARACION_LINEAS

    def _construir_plazas(self):
        plazas = self._grupos["plazas"]
        radio = self._mundo.radio_plaza
        for lugar in self._mundo.lugares():
            cx, cz = self._mundo.coordenada(lugar)
            for y, r, tono in ((Y_ANILLO, radio + 0.9, COLOR_ANILLO_PLAZA), (Y_PLAZA, radio, COLOR_PLAZA),
                               (Y_EMBLEMA, 1.6, COLOR_EMBLEMA)):
                pieza(parent=plazas, model="circle", rotation_x=90, position=(cx, y, cz),
                      scale=2 * r, color=rgb(tono))

    # -- Edificios --

    def _construir_edificios(self):
        for i, edificio in enumerate(self._mundo.edificios()):
            tono = PALETA_EDIFICIOS[i % len(PALETA_EDIFICIOS)]
            self._cuerpo_del_edificio(edificio, tono)
            self._ventanas(edificio)
            self.puertas[edificio.lugar] = PuertaEdificio(edificio, parent=self)
            self._letrero(edificio)
            # Collider solo para el raycast de la cámara.
            Entity(parent=self.raiz_colisiones, model="cube", collider="box", visible=False,
                   position=(edificio.cx, edificio.alto / 2, edificio.cz),
                   scale=(edificio.ancho, edificio.alto, edificio.fondo))

    def _cuerpo_del_edificio(self, e, tono):
        g = self._grupos["edificios"]
        oscuro = tuple(int(c * 0.62) for c in tono)
        pieza(parent=g, model="cube", color=rgb(tono), position=(e.cx, e.alto / 2, e.cz),
              scale=(e.ancho, e.alto, e.fondo))
        pieza(parent=g, model="cube", color=rgb((120, 120, 130)), position=(e.cx, 0.35, e.cz),
              scale=(e.ancho + 0.3, 0.7, e.fondo + 0.3))                              # zócalo
        pieza(parent=g, model="cube", color=rgb(oscuro), position=(e.cx, e.alto + 0.18, e.cz),
              scale=(e.ancho + 0.7, 0.36, e.fondo + 0.7))                             # techo

    # Ventanas en las cuatro caras (en la de la puerta, solo a los lados de ella).
    def _ventanas(self, e):
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
                    pieza(parent=g, model="cube", color=rgb(COLOR_VENTANA), position=(x, y + 0.6, z),
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
        g = self._grupos["vegetacion"]
        variante = (int(abs(o.cx * 7 + o.cz * 13)) % 3)
        verde = ((58, 130, 62), (74, 148, 70), (46, 112, 70))[variante]
        pieza(parent=g, model="cube", color=rgb((98, 68, 44)), position=(o.cx, 0.9, o.cz),
              scale=(0.32, 1.8, 0.32))
        pieza(parent=g, model="sphere", color=rgb(verde), position=(o.cx, 2.9, o.cz), scale=(2.7, 2.4, 2.7))
        pieza(parent=g, model="sphere", color=rgb(tuple(min(255, c + 14) for c in verde)),
              position=(o.cx + 0.2, 3.9, o.cz - 0.1), scale=1.7)

    def _farola(self, o):
        pieza(parent=self._grupos["mobiliario"], model="cube", color=rgb((70, 72, 82)),
              position=(o.cx, 2.1, o.cz), scale=(0.14, 4.2, 0.14))
        pieza(parent=self._grupos["luces"], model="sphere", color=rgb((255, 238, 170)),
              position=(o.cx, 4.35, o.cz), scale=0.5, shader=None)

    def _banco(self, o):
        g = self._grupos["mobiliario"]
        madera = rgb((140, 96, 60))
        pieza(parent=g, model="cube", color=madera, position=(o.cx, 0.46, o.cz), scale=(o.ancho, 0.1, o.fondo))
        pieza(parent=g, model="cube", color=madera, position=(o.cx, 0.82, o.cz + o.fondo / 2 - 0.04),
              scale=(o.ancho, 0.5, 0.08))
        for dx in (-o.ancho / 2 + 0.15, o.ancho / 2 - 0.15):
            pieza(parent=g, model="cube", color=rgb((60, 62, 72)), position=(o.cx + dx, 0.22, o.cz),
                  scale=(0.1, 0.44, o.fondo - 0.1))
