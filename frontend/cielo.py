# Cielo de la ciudad (Ursina) sin shaders nuevos ni texturas: un domo con COLORES DE VÉRTICE
# (horizonte cálido de tarde que sube a un azul más profundo), un resplandor suave hacia el sol y
# nubes de baja poligonización (esferas aplastadas de 42 vértices, blancas arriba y azuladas abajo).
#
# Reemplaza a ursina.Sky: Ciudad3D lo guarda en `self.cielo` (y lo excluye de silenciar() porque
# necesita update()). Igual que Sky, se dibuja en el bin 'background' con unlit_shader y su escala
# se ajusta al plano lejano de la cámara. Las nubes son un hijo que gira muy despacio.
#
# La parte pura (colores y geometría, sin ursina) se prueba en tests/frontend_3d/test_cielo.py.
# COLOR_HORIZONTE es también el color de la niebla (frontend/niebla.py): lo lejano se funde con el cielo.

import math
import sys

from ursina import Entity, Mesh, camera, time
from ursina.shaders import unlit_shader

from frontend import ciclo_dia_calculos as ciclo
from frontend.azar_fijo import azar_de

# Atardecer cálido tipo Río (ver MODELOS_3D.md, sección «Cielo»): horizonte dorado-anaranjado que sube a rosa,
# violeta y azul profundo. Para volver al cielo de antes, los valores de la mañana son:
#   COLOR_HORIZONTE (238, 224, 204); paradas (206, 220, 232), (146, 190, 232), (100, 156, 224), (74, 128, 210).
COLOR_HORIZONTE = (252, 208, 160)        # RGB 0-255: dorado cálido; también el de la niebla
# (elevación = seno del ángulo sobre el horizonte, color): el degradado se interpola entre paradas.
PARADAS_CIELO = (
    (0.00, COLOR_HORIZONTE),
    (0.08, (250, 176, 140)),             # salmón
    (0.22, (232, 140, 160)),             # rosa
    (0.45, (168, 122, 196)),             # violeta
    (0.75, (104, 112, 212)),             # azul violáceo
    (1.00, (70, 100, 206)),              # azul profundo del cenit
)
COLOR_RESPLANDOR = (255, 232, 176)
DIRECCION_SOL = (1.0, -1.1, 0.8)          # hacia donde apunta la luz; el resplandor sale del lado opuesto (la de siempre: ~43° de altura;
                                          # más baja aparece acné de sombra en los techos con el shadow_bias actual)
FUERZA_RESPLANDOR = 0.75
POTENCIA_RESPLANDOR = 5                   # menor = el resplandor se abre más por el cielo
ELEVACIONES_ANILLOS = (-1.0, -0.65, -0.35, 0.0, 0.025, 0.06, 0.11, 0.18, 0.28, 0.42, 0.6, 0.8, 1.0)   # senos
SEGMENTOS = 28
RADIO_NUBES = 0.955                       # dentro del domo (radio 1), para ganarle en profundidad
CANTIDAD_NUBES = 15
VELOCIDAD_NUBES = 0.35                    # grados por segundo
COLOR_NUBE_ARRIBA = (255, 224, 196)       # el sol de tarde las enciende por encima
COLOR_NUBE_ABAJO = (214, 132, 156)        # y por debajo se ven rosadas
RADIO_SOL = 0.035                         # radio del disco del sol (el domo mide 1)
COLOR_SOL = (255, 240, 190)
# Mar al fondo (en el lado del sol): franja baja pegada al horizonte, azul lejos del sol y dorada bajo él.
COLOR_MAR = (92, 124, 178)
COLOR_REFLEJO_MAR = (255, 204, 138)
SEMIARCO_MAR = math.radians(95)           # medio ancho angular del mar alrededor del azimut del sol
ALTURA_MAR = 0.012                        # seno de la altura del borde superior del mar


def _mezclar(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


# Paleta del atardecer de siempre, con las constantes de arriba (las del ciclo de día están en frontend/ciclo_dia_calculos.py,
# con las mismas claves). Las funciones de geometría la usan cuando no se les pasa otra: sin ciclo el cielo es el de antes.
def _paleta_tarde():
    return {"horizonte": COLOR_HORIZONTE, "paradas": PARADAS_CIELO, "resplandor": COLOR_RESPLANDOR,
            "fuerza_resplandor": FUERZA_RESPLANDOR, "sol": COLOR_SOL, "mar": COLOR_MAR, "reflejo_mar": COLOR_REFLEJO_MAR,
            "cerros": None, "nube_arriba": COLOR_NUBE_ARRIBA, "nube_abajo": COLOR_NUBE_ABAJO}


# Color del degradado a esa elevación (seno del ángulo, 0 = horizonte; por debajo se queda en él).
def color_degradado(elevacion, paradas=None):
    paradas = PARADAS_CIELO if paradas is None else paradas
    e = min(1.0, max(0.0, elevacion))
    for (e0, c0), (e1, c1) in zip(paradas, paradas[1:]):
        if e <= e1:
            return _mezclar(c0, c1, (e - e0) / (e1 - e0))
    return paradas[-1][1]


# Dirección unitaria HACIA el sol (opuesta a la de la luz).
def direccion_hacia_el_sol(direccion_luz=DIRECCION_SOL):
    x, y, z = direccion_luz
    largo = math.sqrt(x * x + y * y + z * z)
    return (-x / largo, -y / largo, -z / largo)


# Color del cielo en la dirección unitaria `d`: degradado más un resplandor cálido hacia el sol.
def color_en_direccion(d, sol, paleta=None):
    paleta = paleta or _paleta_tarde()
    base = color_degradado(d[1], paleta["paradas"])
    cos = max(0.0, d[0] * sol[0] + d[1] * sol[1] + d[2] * sol[2])
    return _mezclar(base, paleta["resplandor"], paleta["fuerza_resplandor"] * cos ** POTENCIA_RESPLANDOR)


# Siluetas de cerros lejanos: dos filas de picos bajos (la lejana más clara y velada) pegadas al
# horizonte, para que el fondo no sea una pared lisa. (vértices, triángulos, colores) como el domo.
CAPAS_CERROS = (          # (radio, altura base, amplitud, color, desfase de azar)
    (0.985, 0.020, 0.050, (196, 128, 160), 1.0),     # lejanos: rosados y velados
    (0.975, 0.010, 0.032, (132, 92, 140), 2.0),      # cercanos: violetas
)
COLUMNAS_CERROS = 72
# Picos a la manera del Pan de Azúcar: (desfase angular respecto del sol en grados, semiancho en grados,
# altura como seno), en la capa lejana. Dan al horizonte una silueta reconocible junto al mar.
PICOS = ((38.0, 6.0, 0.115), (-52.0, 9.0, 0.085), (150.0, 12.0, 0.07))


def geometria_cerros(paleta=None):
    paleta = paleta or _paleta_tarde()
    horizonte = paleta["horizonte"]
    vertices, triangulos, colores = [], [], []
    sol = direccion_hacia_el_sol()
    azimut_sol = math.atan2(sol[2], sol[0])
    for capa, (radio, base, amplitud, tono, fase) in enumerate(CAPAS_CERROS):
        if paleta["cerros"] is not None:
            tono = paleta["cerros"][capa]
        inicio = len(vertices)
        for k in range(COLUMNAS_CERROS):
            azimut = 2 * math.pi * k / COLUMNAS_CERROS
            # Dos ondas lentas y un diente por columna: cerros redondeados con picos irregulares.
            altura = base + amplitud * (0.45 + 0.3 * math.sin(azimut * 3 + fase) + 0.2 * math.sin(azimut * 7 + 2 * fase)
                                        + 0.35 * azar_de(k, fase))
            if capa == 0:
                for grados, ancho, alto in PICOS:
                    d = (azimut - azimut_sol - math.radians(grados) + math.pi) % (2 * math.pi) - math.pi
                    altura += alto * math.exp(-(d / math.radians(ancho)) ** 2)
            for seno, tono_vertice in ((-0.06, horizonte), (max(0.004, altura), tono)):
                coseno = math.sqrt(1 - seno * seno)
                vertices.append((radio * coseno * math.cos(azimut), radio * seno, radio * coseno * math.sin(azimut)))
                colores.append((tono_vertice[0] / 255, tono_vertice[1] / 255, tono_vertice[2] / 255, 1.0))
        for k in range(COLUMNAS_CERROS):
            a = inicio + 2 * k
            b = inicio + 2 * ((k + 1) % COLUMNAS_CERROS)
            triangulos += [(a, b, b + 1), (a, b + 1, a + 1)]
    return vertices, triangulos, colores


# El mar: una franja baja en el sector del sol, pegada al horizonte y por detrás de los cerros (radio 0.99).
# Azul lejos del sol y dorada bajo él. (vértices, triángulos, colores) como el domo.
COLUMNAS_MAR = 48


def geometria_mar(paleta=None):
    paleta = paleta or _paleta_tarde()
    sol = direccion_hacia_el_sol()
    azimut_sol = math.atan2(sol[2], sol[0])
    vertices, triangulos, colores = [], [], []
    for k in range(COLUMNAS_MAR + 1):
        d = -SEMIARCO_MAR + 2 * SEMIARCO_MAR * k / COLUMNAS_MAR
        azimut = azimut_sol + d
        reflejo = max(0.0, math.cos(d * (math.pi / 2) / SEMIARCO_MAR)) ** 3        # 1 bajo el sol, 0 en los extremos
        borde = max(0.0, 1 - abs(d) / SEMIARCO_MAR) ** 0.5                         # se funde al horizonte en los extremos
        for seno, arriba in ((-0.06, 0.0), (ALTURA_MAR * borde, 1.0)):
            coseno = math.sqrt(1 - seno * seno)
            vertices.append((0.99 * coseno * math.cos(azimut), 0.99 * seno, 0.99 * coseno * math.sin(azimut)))
            tono = _mezclar(paleta["mar"], paleta["reflejo_mar"], reflejo * (0.55 + 0.45 * arriba))
            tono = _mezclar(tono, paleta["horizonte"], (1 - borde) * 0.8)
            colores.append((tono[0] / 255, tono[1] / 255, tono[2] / 255, 1.0))
    for k in range(COLUMNAS_MAR):
        a, b = 2 * k, 2 * (k + 1)
        triangulos += [(a, b, b + 1), (a, b + 1, a + 1)]
    return vertices, triangulos, colores


# Disco del sol: una esfera pequeña (icosfera) en la dirección del sol, dentro del domo y delante del mar.
def geometria_sol(paleta=None):
    tono = (paleta or _paleta_tarde())["sol"]
    sol = direccion_hacia_el_sol()
    base_v, base_t = icosfera()
    centro = tuple(0.96 * c for c in sol)
    vertices = [tuple(centro[i] + RADIO_SOL * v[i] for i in range(3)) for v in base_v]
    colores = [(tono[0] / 255, tono[1] / 255, tono[2] / 255, 1.0)] * len(vertices)
    return vertices, list(base_t), colores


# Domo de radio 1: (vértices, triángulos, colores 0-1 RGBA). Los anillos van de bajo el horizonte
# al cenit; su elevación se concentra cerca del horizonte, donde cambia más el color.
def geometria_domo(direccion_luz=DIRECCION_SOL, paleta=None):
    paleta = paleta or _paleta_tarde()
    sol = direccion_hacia_el_sol(direccion_luz)
    vertices, colores = [], []
    for seno in ELEVACIONES_ANILLOS:
        coseno = math.sqrt(max(0.0, 1 - seno * seno))
        for k in range(SEGMENTOS):
            azimut = 2 * math.pi * k / SEGMENTOS
            d = (coseno * math.cos(azimut), seno, coseno * math.sin(azimut))
            vertices.append(d)
            r, g, b = color_en_direccion(d, sol, paleta)
            colores.append((r / 255, g / 255, b / 255, 1.0))
    triangulos = []
    for fila in range(len(ELEVACIONES_ANILLOS) - 1):
        for k in range(SEGMENTOS):
            a = fila * SEGMENTOS + k
            b = fila * SEGMENTOS + (k + 1) % SEGMENTOS
            triangulos += [(a, b, b + SEGMENTOS), (a, b + SEGMENTOS, a + SEGMENTOS)]
    return vertices, triangulos, colores


# Esfera de 42 vértices y 80 triángulos (icosaedro subdividido una vez), de radio 1.
def icosfera():
    t = (1 + math.sqrt(5)) / 2
    base = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
            (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    caras = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2),
             (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5),
             (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]

    def unitario(v):
        n = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
        return (v[0] / n, v[1] / n, v[2] / n)

    vertices = [unitario(v) for v in base]
    indices = {}

    def medio(i, j):
        clave = (min(i, j), max(i, j))
        if clave not in indices:
            a, b = vertices[i], vertices[j]
            vertices.append(unitario(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)))
            indices[clave] = len(vertices) - 1
        return indices[clave]

    triangulos = []
    for a, b, c in caras:
        ab, bc, ca = medio(a, b), medio(b, c), medio(c, a)
        triangulos += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
    return vertices, triangulos


# Nubes: (vértices, triángulos, colores). Cada nube son varias esferas aplastadas en fila sobre el
# domo; los colores van de blanco (arriba) a azul grisáceo (abajo) y se tiñen de horizonte las bajas.
def geometria_nubes(cantidad=CANTIDAD_NUBES, paleta=None):
    paleta = paleta or _paleta_tarde()
    base_v, base_t = icosfera()
    vertices, triangulos, colores = [], [], []
    for n in range(cantidad):
        azimut = 2 * math.pi * (n + 0.8 * azar_de(n, 3.1)) / cantidad
        elevacion = math.radians(9 + 38 * azar_de(n, 7.7) ** 1.4)
        tamano = 0.05 + 0.05 * azar_de(n, 1.3)
        blobs = 3 + int(azar_de(n, 5.9) * 3)
        centro = (math.cos(elevacion) * math.cos(azimut), math.sin(elevacion), math.cos(elevacion) * math.sin(azimut))
        tangente = (-math.sin(azimut), 0.0, math.cos(azimut))
        subida = (-math.sin(elevacion) * math.cos(azimut), math.cos(elevacion), -math.sin(elevacion) * math.sin(azimut))
        tinte = max(0.0, 1 - math.degrees(elevacion) / 24) * 0.45          # las bajas se tiñen de horizonte
        for j in range(blobs):
            fila = j - (blobs - 1) / 2
            radio = tamano * (1.0 - 0.28 * abs(fila) / max(1.0, blobs / 2)) * (0.85 + 0.3 * azar_de(n, j + 9.1))
            desplazamiento = fila * tamano * 1.15
            altura = (azar_de(n + 4.4, j) - 0.4) * tamano * 0.35
            pos = tuple(RADIO_NUBES * centro[i] + tangente[i] * desplazamiento + subida[i] * altura for i in range(3))
            largo = math.sqrt(sum(c * c for c in pos))
            pos = tuple(c / largo * RADIO_NUBES for c in pos)               # pegada a la esfera de las nubes
            radial = tuple(c / RADIO_NUBES for c in pos)
            inicio = len(vertices)
            for x, y, z in base_v:
                # x a lo largo de la fila, y hacia arriba (aplastada), z hacia el domo (muy fina)
                v = tuple(pos[i] + tangente[i] * x * radio * 1.35 + subida[i] * y * radio * 0.46
                          + radial[i] * z * radio * 0.35 for i in range(3))
                vertices.append(v)
                t = (y + 1) / 2
                arriba = _mezclar(paleta["nube_abajo"], paleta["nube_arriba"], min(1.0, t * 1.25))
                r, g, b = _mezclar(arriba, paleta["horizonte"], tinte)
                colores.append((r / 255, g / 255, b / 255, 1.0))
            triangulos += [(inicio + a, inicio + b, inicio + c) for a, b, c in base_t]
    return vertices, triangulos, colores


# Domo, mar, cerros y sol en UNA malla: (vértices, triángulos, colores) con los colores de `paleta` (None = la tarde).
def geometria_cielo(paleta=None):
    vertices, triangulos, colores = geometria_domo(paleta=paleta)
    for extra in (geometria_mar(paleta), geometria_cerros(paleta), geometria_sol(paleta)):
        cv, ct, cc = extra
        ct = [(a + len(vertices), b + len(vertices), c + len(vertices)) for a, b, c in ct]
        vertices, triangulos, colores = vertices + cv, triangulos + ct, colores + cc
    return vertices, triangulos, colores


# Reescribe la columna de color de la malla de `entidad` con `plano` (lista plana RGBA 0..1, un color por vértice y en el
# mismo orden). Solo esa columna (la de Ursina es un arreglo float32 aparte): sin Mesh.generate(), que rehace la malla entera.
def escribir_colores(entidad, plano):
    from array import array
    for camino in entidad.model.find_all_matches("**/+GeomNode"):
        nodo = camino.node()
        for i in range(nodo.get_num_geoms()):
            datos = nodo.modify_geom(i).modify_vertex_data()
            if datos.get_num_rows() * 4 != len(plano):
                raise ValueError("la malla del cielo no tiene un color por vértice")
            formato = datos.get_format()
            for k in range(formato.get_num_arrays()):
                if formato.get_array(k).has_column("color"):
                    datos.modify_array(k).modify_handle().set_data(array("f", plano).tobytes())
                    return
    raise ValueError("la malla del cielo no tiene columna de color")


class CieloDegradado(Entity):

    def __init__(self, **opciones):
        vertices, triangulos, colores = geometria_cielo()
        opciones.setdefault("scale", 400)
        super().__init__(model=Mesh(vertices=vertices, triangles=triangulos, colors=colores),
                         shader=unlit_shader, unlit=True, double_sided=True, name="cielo", **opciones)
        self.setBin("background", 0)
        vn, tn, cn = geometria_nubes()
        self.nubes = Entity(parent=self, model=Mesh(vertices=vn, triangles=tn, colors=cn),
                            shader=unlit_shader, unlit=True, double_sided=True, name="nubes")
        self.nubes.setBin("background", 1)
        # Ciclo de mañana, tarde y noche (frontend/ciclo_dia_calculos.py): los colores de cada paleta se calculan UNA vez y
        # luego solo se mezclan. `horizonte` (RGB 0-255) es el color del horizonte vigente: la niebla lo usa (ciudad_viva).
        self.horizonte = COLOR_HORIZONTE
        self._paletas = None
        self._diferencias = {}           # (a, b) -> (dif. del cielo, dif. de las nubes), listas planas; una vez por par
        self._clave_ciclo = ("tarde", "tarde", 0.0)
        self._t_ciclo = 0.0
        if ciclo.activo():
            try:
                self._paletas = {"tarde": (_paleta_tarde(), ciclo.plano(colores), ciclo.plano(cn))}
                for nombre, paleta in ciclo.PALETAS.items():
                    self._paletas[nombre] = (paleta, ciclo.plano(geometria_cielo(paleta)[2]),
                                             ciclo.plano(geometria_nubes(paleta=paleta)[2]))
            except Exception as error:      # noqa: BLE001 — sin ciclo el cielo queda como siempre
                self._paletas = None
                print(f"[cielo] ciclo de día desactivado ({type(error).__name__}: {error})", file=sys.stderr)

    # Como Sky: del tamaño del plano lejano y sin giro propio; solo las nubes derivan despacio.
    def update(self):
        self.scale = camera.clip_plane_far * 0.8
        self.nubes.rotation_y += VELOCIDAD_NUBES * time.dt
        if self._paletas is not None:
            self._t_ciclo -= time.dt
            if self._t_ciclo <= 0:
                self._t_ciclo = ciclo.PERIODO_CICLO
                self.aplicar_hora(self._hora())

    @staticmethod
    def _hora():
        forzada = ciclo.hora_forzada()
        if forzada is not None:
            return forzada
        from frontend import ambiente_vivo
        return ambiente_vivo.hora()

    # Pone el cielo de esa hora (None = el atardecer de siempre). Solo escribe colores si cambió el escalón de mezcla.
    def aplicar_hora(self, hora):
        if self._paletas is None:
            return
        clave = ciclo.mezcla_de_hora(hora)
        if clave == self._clave_ciclo:
            return
        a, b, t = clave
        (paleta_a, cielo_a, nubes_a), (paleta_b, cielo_b, nubes_b) = self._paletas[a], self._paletas[b]
        try:
            if t > 0.0 and (a, b) not in self._diferencias:
                self._diferencias[(a, b)] = (ciclo.diferencia(cielo_a, cielo_b), ciclo.diferencia(nubes_a, nubes_b))
            dif_cielo, dif_nubes = self._diferencias.get((a, b), (None, None))
            escribir_colores(self, ciclo.mezclar_plano(cielo_a, dif_cielo, t))
            escribir_colores(self.nubes, ciclo.mezclar_plano(nubes_a, dif_nubes, t))
        except Exception as error:          # noqa: BLE001 — si la malla no se deja, el cielo se queda como estaba
            self._paletas = None
            print(f"[cielo] ciclo de día desactivado ({type(error).__name__}: {error})", file=sys.stderr)
            return
        self._clave_ciclo = clave
        self.horizonte = ciclo.mezclar_rgb(paleta_a["horizonte"], paleta_b["horizonte"], t)
