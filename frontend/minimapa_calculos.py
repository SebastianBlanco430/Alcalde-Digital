# Modelo PURO de las capas del minimapa y del mapa grande (Python puro: NO importa ursina; se prueba con pytest sin
# ventana). Las vistas (frontend/hud.py: Minimapa; frontend/mapa_grande_vista.py) solo dibujan lo que este módulo
# decide: qué marcadores y zonas hay, en qué capa están y qué polígonos/triángulos salen de ellos.
#
# API PARA OTRAS PARTES DEL JUEGO (NPC, zonas de vigilancia, parkour...) SIN TOCAR LAS VISTAS: hay un registro global
# (`registro()`) del que leen el minimapa y el mapa grande. Dos formas de alimentarlo, las dos con las mismas clases:
#
#   EMPUJAR (cuando algo cambia):
#       from frontend import minimapa_calculos as mm
#       mm.registro().poner_marcador(mm.MarcadorMinimapa("npc", x, z, id="guardia-1", etiqueta="Guardia"), fuente="npc")
#       mm.registro().poner_zona(mm.ZonaMinimapa.rectangulo("sala-vip", cx, cz, ancho, fondo, tipo="restringida",
#                                etiqueta="Zona restringida"), fuente="vigilancia")
#       mm.registro().quitar("guardia-1", fuente="npc")           # o limpiar_fuente("npc")
#   SONDEAR (cuando se mueve cada frame): la vista pregunta ella sola, unas 15 veces por segundo:
#       mm.registro().registrar_fuente("npc", lambda: ([mm.MarcadorMinimapa(...), ...], []))
#   PARKOUR (alturas): marcadores tipo "altura" con `altura` en metros + mm.registro().fijar_altura_jugador(y) cada vez
#       que cambie; el minimapa escribe «+3 m» / «-2 m» / «Nivel» junto a cada uno (texto, no solo color).
#
# `fuente` es solo una etiqueta para poder reemplazar/limpiar lo propio sin pisar lo de otros.
# Capas: calles, edificios, jugador (las dibujan las vistas) + misiones, objetivos, zonas, npc, alturas (marcadores).
# Cada capa se puede encender o apagar (`fijar_capa`) y las vistas lo respetan.

import math
from dataclasses import dataclass

from frontend import estilo, hud_calculos

# --- Capas ---------------------------------------------------------------------------------------------------------------

CAPAS = ("calles", "edificios", "jugador", "misiones", "objetivos", "zonas", "npc", "alturas")
CAPAS_MARCADORES = ("misiones", "objetivos", "npc", "alturas")
NOMBRES_CAPA = {
    "calles": "Calles", "edificios": "Edificios", "jugador": "Jugadores", "misiones": "Misiones",
    "objetivos": "Objetivos", "zonas": "Zonas", "npc": "Personajes", "alturas": "Alturas",
}

# tipo de marcador -> (capa, forma, color rgb, letra). Forma Y letra además del color (daltonismo): el color nunca es la
# única señal.
TIPOS_MARCADOR = {
    "mision": ("misiones", "diamante", (255, 170, 60), "M"),
    "objetivo": ("objetivos", "cuadro", (120, 230, 150), "O"),
    "npc": ("npc", "triangulo", (230, 130, 255), "P"),
    "altura": ("alturas", "pentagono", (240, 240, 250), "A"),
}
FORMAS_LADOS = {"diamante": (4, 0.0), "cuadro": (4, 45.0), "triangulo": (3, 90.0), "pentagono": (5, 90.0)}

# tipo de zona -> (color rgb del borde y relleno, nombre visible). Relleno translúcido (ver ALFA_RELLENO_ZONA) más borde.
TIPOS_ZONA = {
    "restringida": ((214, 62, 62), "Zona restringida"),
    "vigilancia": ((255, 150, 40), "Zona vigilada"),
    "segura": ((80, 190, 110), "Zona segura"),
}
COLOR_ZONA_DESCONOCIDA = (170, 172, 190)
ALFA_RELLENO_ZONA = 0.28
ALFA_BORDE_ZONA = 0.95

MAX_ETIQUETA = 28
MAX_MARCADORES = 400                # tope duro: una fuente descontrolada no puede congelar el dibujo
MAX_ZONAS = 80
MAX_PUNTOS_ZONA = 64
TOLERANCIA_NIVEL_M = 1.0            # a menos de esto de diferencia se considera «mismo nivel»


def _finito(valor):
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def _color_rgb(valor):
    if valor is None:
        return None
    try:
        r, g, b = valor
    except (TypeError, ValueError):
        return None
    if not all(_finito(c) for c in (r, g, b)):
        return None
    return tuple(int(max(0, min(255, round(c)))) for c in (r, g, b))


def _texto(valor, maximo=MAX_ETIQUETA):
    if not isinstance(valor, str):
        return ""
    return "".join(c for c in valor if c.isprintable()).strip()[:maximo]


# --- Marcadores ----------------------------------------------------------------------------------------------------------

# Un punto del mapa (en coordenadas de MUNDO x, z). `altura` (metros, y del mundo) solo para parkour; `color` opcional
# (si no, el del tipo). Inmutable: para moverlo se pone otro con el mismo `id` (poner_marcador reemplaza).
@dataclass(frozen=True)
class MarcadorMinimapa:
    tipo: str
    x: float
    z: float
    altura: object = None
    etiqueta: str = ""
    id: str = ""
    color: object = None

    def __post_init__(self):
        if self.tipo not in TIPOS_MARCADOR:
            raise ValueError(f"tipo de marcador desconocido: {self.tipo!r} (usa {sorted(TIPOS_MARCADOR)})")
        if not (_finito(self.x) and _finito(self.z)):
            raise ValueError("x y z del marcador deben ser números finitos")
        object.__setattr__(self, "x", float(self.x))
        object.__setattr__(self, "z", float(self.z))
        altura = float(self.altura) if _finito(self.altura) else None
        object.__setattr__(self, "altura", altura)
        object.__setattr__(self, "etiqueta", _texto(self.etiqueta))
        object.__setattr__(self, "id", _texto(self.id, 48))
        object.__setattr__(self, "color", _color_rgb(self.color))

    @property
    def capa(self):
        return TIPOS_MARCADOR[self.tipo][0]

    @property
    def forma(self):
        return TIPOS_MARCADOR[self.tipo][1]

    @property
    def letra(self):
        return TIPOS_MARCADOR[self.tipo][3]

    @property
    def color_rgb(self):
        return self.color if self.color is not None else TIPOS_MARCADOR[self.tipo][2]


# --- Zonas ---------------------------------------------------------------------------------------------------------------

# Polígono simple (cóncavo o convexo) en coordenadas de mundo. Constructores: ZonaMinimapa.rectangulo / .circulo.
@dataclass(frozen=True)
class ZonaMinimapa:
    id: str
    puntos: tuple
    tipo: str = "restringida"
    etiqueta: str = ""
    color: object = None

    def __post_init__(self):
        puntos = []
        for p in self.puntos:
            try:
                x, z = p
            except (TypeError, ValueError):
                raise ValueError("cada punto de la zona es (x, z)") from None
            if not (_finito(x) and _finito(z)):
                raise ValueError("los puntos de la zona deben ser números finitos")
            puntos.append((float(x), float(z)))
        if len(puntos) < 3:
            raise ValueError("una zona necesita al menos 3 puntos")
        if len(puntos) > MAX_PUNTOS_ZONA:
            raise ValueError(f"una zona admite como mucho {MAX_PUNTOS_ZONA} puntos")
        object.__setattr__(self, "puntos", tuple(puntos))
        object.__setattr__(self, "id", _texto(self.id, 48))
        object.__setattr__(self, "etiqueta", _texto(self.etiqueta))
        object.__setattr__(self, "color", _color_rgb(self.color))

    @classmethod
    def rectangulo(cls, id, cx, cz, ancho, fondo, **opciones):
        mx, mz = abs(ancho) / 2, abs(fondo) / 2
        return cls(id, ((cx - mx, cz - mz), (cx + mx, cz - mz), (cx + mx, cz + mz), (cx - mx, cz + mz)), **opciones)

    @classmethod
    def circulo(cls, id, cx, cz, radio, lados=20, **opciones):
        lados = max(6, min(MAX_PUNTOS_ZONA, int(lados)))
        return cls(id, tuple((cx + radio * math.cos(2 * math.pi * k / lados),
                              cz + radio * math.sin(2 * math.pi * k / lados)) for k in range(lados)), **opciones)

    @property
    def capa(self):
        return "zonas"

    @property
    def color_rgb(self):
        if self.color is not None:
            return self.color
        return TIPOS_ZONA.get(self.tipo, (COLOR_ZONA_DESCONOCIDA, ""))[0]

    @property
    def nombre(self):
        return self.etiqueta or TIPOS_ZONA.get(self.tipo, (None, "Zona"))[1]

    def contiene(self, x, z):
        return punto_en_poligono(x, z, self.puntos)

    def centro(self):
        return (sum(p[0] for p in self.puntos) / len(self.puntos), sum(p[1] for p in self.puntos) / len(self.puntos))


# --- Geometría de polígonos ----------------------------------------------------------------------------------------------

# Área con signo (positiva = antihorario con z hacia arriba).
def area_firmada(puntos):
    total = 0.0
    for (x0, z0), (x1, z1) in zip(puntos, puntos[1:] + puntos[:1]):
        total += x0 * z1 - x1 * z0
    return total / 2


# Trazado de rayo: ¿(x, z) está dentro del polígono? Los puntos del borde cuentan como dentro.
def punto_en_poligono(x, z, puntos):
    n = len(puntos)
    dentro = False
    for i in range(n):
        x0, z0 = puntos[i]
        x1, z1 = puntos[(i + 1) % n]
        if _sobre_segmento(x, z, x0, z0, x1, z1):
            return True
        if (z0 > z) != (z1 > z):
            if x < (x1 - x0) * (z - z0) / (z1 - z0) + x0:
                dentro = not dentro
    return dentro


def _sobre_segmento(x, z, x0, z0, x1, z1, eps=1e-9):
    cruz = (x - x0) * (z1 - z0) - (z - z0) * (x1 - x0)
    if abs(cruz) > eps * max(1.0, abs(x1 - x0) + abs(z1 - z0)):
        return False
    return min(x0, x1) - eps <= x <= max(x0, x1) + eps and min(z0, z1) - eps <= z <= max(z0, z1) + eps


def _cruz(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _en_triangulo(p, a, b, c):
    d1, d2, d3 = _cruz(a, b, p), _cruz(b, c, p), _cruz(c, a, p)
    return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))


# Triangulación por recorte de orejas de un polígono simple (cóncavo incluido): [(i, j, k)] de índices a `puntos`, todos
# con el mismo sentido. Un polígono degenerado (área 0) devuelve [].
def triangular(puntos):
    n = len(puntos)
    if n < 3 or abs(area_firmada(list(puntos))) < 1e-12:
        return []
    indices = list(range(n))
    if area_firmada(list(puntos)) < 0:
        indices.reverse()                      # se trabaja siempre en antihorario
    triangulos = []
    guarda = 0
    while len(indices) > 3 and guarda < 4 * n * n:
        guarda += 1
        recortada = False
        for pos in range(len(indices)):
            i0, i1, i2 = indices[pos - 1], indices[pos], indices[(pos + 1) % len(indices)]
            a, b, c = puntos[i0], puntos[i1], puntos[i2]
            if _cruz(a, b, c) <= 1e-12:
                continue                       # vértice cóncavo o colineal: no es oreja
            if any(_en_triangulo(puntos[j], a, b, c) and puntos[j] not in (a, b, c)
                   for j in indices if j not in (i0, i1, i2)):
                continue
            triangulos.append((i0, i1, i2))
            del indices[pos]
            recortada = True
            break
        if not recortada:                      # polígono casi degenerado: se cierra en abanico para no colgarse
            triangulos += [(indices[0], indices[k], indices[k + 1]) for k in range(1, len(indices) - 1)]
            return triangulos
    if len(indices) == 3:
        triangulos.append(tuple(indices))
    return triangulos


# --- Niveles de altura (parkour) -----------------------------------------------------------------------------------------

# «arriba» / «abajo» / «igual» del marcador respecto a la altura de referencia (el jugador).
def nivel_relativo(altura, referencia, tolerancia=TOLERANCIA_NIVEL_M):
    if altura is None or referencia is None:
        return "desconocido"
    diferencia = altura - referencia
    if abs(diferencia) < tolerancia:
        return "igual"
    return "arriba" if diferencia > 0 else "abajo"


# Texto corto y SIN caracteres raros para el rótulo: «+3 m», «-2 m», «Nivel» (o la altura absoluta sin referencia).
def texto_altura(altura, referencia):
    if altura is None:
        return ""
    if referencia is None:
        return f"{altura:.0f} m"
    nivel = nivel_relativo(altura, referencia)
    if nivel == "igual":
        return "Nivel"
    return f"{altura - referencia:+.0f} m"


COLORES_NIVEL = {"arriba": (120, 220, 255), "abajo": (255, 170, 90), "igual": (240, 240, 250),
                 "desconocido": (240, 240, 250)}


# --- Registro ------------------------------------------------------------------------------------------------------------

class RegistroMinimapa:

    def __init__(self):
        self._marcadores = {}       # (fuente, id) -> MarcadorMinimapa
        self._zonas = {}            # (fuente, id) -> ZonaMinimapa
        self._proveedores = {}      # fuente -> callable() -> (marcadores, zonas)
        self._visibles = {capa: True for capa in CAPAS}
        self._altura_jugador = None
        self._siguiente = 0
        self.version = 0            # sube en cada cambio real: las vistas rehacen sus mallas solo si cambió

    # -- Empujar --

    def poner_marcador(self, marcador, fuente="externo"):
        if not isinstance(marcador, MarcadorMinimapa):
            raise TypeError("se esperaba un MarcadorMinimapa")
        clave = (fuente, marcador.id or self._id_nuevo("m"))
        if clave not in self._marcadores and len(self._marcadores) >= MAX_MARCADORES:
            raise ValueError(f"demasiados marcadores (máximo {MAX_MARCADORES})")
        if self._marcadores.get(clave) != marcador:
            self._marcadores[clave] = marcador
            self.version += 1
        return clave[1]

    def poner_zona(self, zona, fuente="externo"):
        if not isinstance(zona, ZonaMinimapa):
            raise TypeError("se esperaba una ZonaMinimapa")
        clave = (fuente, zona.id or self._id_nuevo("z"))
        if clave not in self._zonas and len(self._zonas) >= MAX_ZONAS:
            raise ValueError(f"demasiadas zonas (máximo {MAX_ZONAS})")
        if self._zonas.get(clave) != zona:
            self._zonas[clave] = zona
            self.version += 1
        return clave[1]

    def quitar(self, id, fuente="externo"):
        cambio = self._marcadores.pop((fuente, id), None) is not None
        cambio = (self._zonas.pop((fuente, id), None) is not None) or cambio
        if cambio:
            self.version += 1
        return cambio

    # Reemplaza TODO lo de `fuente` por estos marcadores y zonas (idempotente: si es igual no cambia la versión).
    def reemplazar_fuente(self, fuente, marcadores=(), zonas=()):
        nuevos_m = {}
        for m in list(marcadores)[:MAX_MARCADORES]:
            if not isinstance(m, MarcadorMinimapa):
                raise TypeError("se esperaba un MarcadorMinimapa")
            nuevos_m[(fuente, m.id or f"auto-{len(nuevos_m)}")] = m
        nuevas_z = {}
        for z in list(zonas)[:MAX_ZONAS]:
            if not isinstance(z, ZonaMinimapa):
                raise TypeError("se esperaba una ZonaMinimapa")
            nuevas_z[(fuente, z.id or f"auto-{len(nuevas_z)}")] = z
        previos_m = {k: v for k, v in self._marcadores.items() if k[0] == fuente}
        previas_z = {k: v for k, v in self._zonas.items() if k[0] == fuente}
        if previos_m == nuevos_m and previas_z == nuevas_z:
            return False
        self._marcadores = {k: v for k, v in self._marcadores.items() if k[0] != fuente}
        self._zonas = {k: v for k, v in self._zonas.items() if k[0] != fuente}
        self._marcadores.update(nuevos_m)
        self._zonas.update(nuevas_z)
        self.version += 1
        return True

    def limpiar_fuente(self, fuente):
        self._proveedores.pop(fuente, None)
        return self.reemplazar_fuente(fuente)

    # -- Sondear --

    # `proveedor()` devuelve (marcadores, zonas); se le pregunta en cada sondear() y su resultado reemplaza a la fuente.
    def registrar_fuente(self, fuente, proveedor):
        if not callable(proveedor):
            raise TypeError("el proveedor debe ser invocable")
        self._proveedores[fuente] = proveedor

    # Pregunta a todos los proveedores. Un proveedor que falla se ignora (no tumba el dibujo). True si algo cambió.
    def sondear(self):
        cambio = False
        for fuente, proveedor in list(self._proveedores.items()):
            try:
                marcadores, zonas = proveedor()
                cambio = self.reemplazar_fuente(fuente, marcadores or (), zonas or ()) or cambio
            except Exception as error:        # una fuente rota no debe impedir dibujar las demás
                print(f"[minimapa] la fuente {fuente!r} falló: {error}")
        return cambio

    # -- Capas --

    def fijar_capa(self, capa, visible):
        if capa not in self._visibles:
            raise ValueError(f"capa desconocida: {capa!r}")
        visible = bool(visible)
        if self._visibles[capa] != visible:
            self._visibles[capa] = visible
            self.version += 1

    def capa_visible(self, capa):
        return self._visibles.get(capa, False)

    def capas_visibles(self):
        return tuple(c for c in CAPAS if self._visibles[c])

    # -- Altura del jugador (parkour) --

    def fijar_altura_jugador(self, altura):
        valor = float(altura) if _finito(altura) else None
        self._altura_jugador = valor          # NO sube la versión: cambia a cada salto y solo afecta a los rótulos

    @property
    def altura_jugador(self):
        return self._altura_jugador

    # -- Consulta --

    # Marcadores de las capas visibles (o de `capas` si se indica), en orden estable de inserción.
    def marcadores(self, capas=None):
        permitidas = set(capas) if capas is not None else {c for c in CAPAS if self._visibles[c]}
        return [m for m in self._marcadores.values() if m.capa in permitidas and self._visibles[m.capa]]

    def zonas(self):
        if not self._visibles["zonas"]:
            return []
        return list(self._zonas.values())

    # Zonas (visibles o no: es lógica, no dibujo) que contienen el punto; `tipo` filtra.
    def zonas_que_contienen(self, x, z, tipo=None):
        return [zona for zona in self._zonas.values() if (tipo is None or zona.tipo == tipo) and zona.contiene(x, z)]

    def esta_vacio(self):
        return not self._marcadores and not self._zonas and not self._proveedores

    def _id_nuevo(self, prefijo):
        self._siguiente += 1
        return f"{prefijo}-auto-{self._siguiente}"

    def vaciar(self):
        self._marcadores.clear()
        self._zonas.clear()
        self._proveedores.clear()
        self._visibles = {capa: True for capa in CAPAS}
        self._altura_jugador = None
        self.version += 1


_registro = RegistroMinimapa()


# Registro global del que leen el minimapa y el mapa grande.
def registro():
    return _registro


# --- Planes de dibujo (qué mallas salen de los datos) -------------------------------------------------------------------

# Vértices (u, v) de un polígono regular de `lados` lados, radio `radio` y giro en grados (antihorario).
def poligono_regular(u, v, radio, lados, giro_grados=0.0):
    giro = math.radians(giro_grados)
    return [(u + radio * math.cos(giro + 2 * math.pi * k / lados), v + radio * math.sin(giro + 2 * math.pi * k / lados))
            for k in range(lados)]


# Malla de los marcadores: (vertices, triangulos, colores) con un contorno oscuro (tinta) detrás de cada forma para que se
# lea sobre cualquier fondo. `proyectar(x, z) -> (u, v)`; `radio` en unidades del espacio de (u, v) del que dibuja.
# vertices = [(u, v, 0)], colores = [(r, g, b, a)] en 0-1, triangulos = [(a, b, c)].
def plan_marcadores(marcadores, proyectar, radio):
    vertices, triangulos, colores = [], [], []
    tinta = tuple(c / 255 for c in estilo.TINTA) + (1.0,)
    for m in marcadores:
        u, v = proyectar(m.x, m.z)
        lados, giro = FORMAS_LADOS[m.forma]
        for r, tono, z in ((radio * 1.3, tinta, 0), (radio, tuple(c / 255 for c in m.color_rgb) + (1.0,), -0.0002)):
            base = len(vertices)           # el relleno un pelo más cerca (z menor) que el contorno: sin empate de profundidad
            vertices.append((u, v, z))
            colores.append(tono)
            for pu, pv in poligono_regular(u, v, r, lados, giro):
                vertices.append((pu, pv, z))
                colores.append(tono)
            triangulos += [(base, base + 1 + k, base + 1 + (k + 1) % lados) for k in range(lados)]
    return vertices, triangulos, colores


# Relleno y borde de las zonas, agrupados por color (cada grupo = una malla con un solo color de entidad, que admite
# transparencia): {rgb: {"relleno": (vertices, triangulos), "borde": [cuadrilaterosuv]}}. `grosor` en unidades de (u, v).
def plan_zonas(zonas, proyectar, grosor):
    grupos = {}
    for zona in zonas:
        puntos = [proyectar(x, z) for x, z in zona.puntos]
        grupo = grupos.setdefault(zona.color_rgb, {"relleno": ([], []), "borde": []})
        vertices, triangulos = grupo["relleno"]
        base = len(vertices)
        vertices += [(u, v, 0) for u, v in puntos]
        triangulos += [(base + a, base + b, base + c) for a, b, c in triangular(puntos)]
        for p0, p1 in zip(puntos, puntos[1:] + puntos[:1]):
            grupo["borde"].append(_rectangulo_segmento(p0, p1, grosor))
    return grupos


def _rectangulo_segmento(p0, p1, ancho):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    largo = math.hypot(dx, dy)
    if largo == 0:
        return (p0, p0, p0, p0)
    nx, ny = -dy / largo * ancho / 2, dx / largo * ancho / 2
    return ((p0[0] - nx, p0[1] - ny), (p1[0] - nx, p1[1] - ny), (p1[0] + nx, p1[1] + ny), (p0[0] + nx, p0[1] + ny))


# Los `maximo` marcadores de alturas más cercanos a (x, z) con su texto relativo: [(marcador, texto, nivel)].
def rotulos_de_altura(marcadores, x, z, referencia, maximo=6, radio_m=None):
    candidatos = []
    for m in marcadores:
        if m.tipo != "altura" or m.altura is None:
            continue
        d = math.hypot(m.x - x, m.z - z)
        if radio_m is not None and d > radio_m:
            continue
        candidatos.append((d, m))
    candidatos.sort(key=lambda t: t[0])
    return [(m, texto_altura(m.altura, referencia), nivel_relativo(m.altura, referencia))
            for _, m in candidatos[:maximo]]


# --- Controles del minimapa ----------------------------------------------------------------------------------------------

# Siguiente escalón de una escalera de valores ordenados (se queda en el extremo).
def siguiente_escalon(escalones, actual, direccion):
    escalones = list(escalones)
    indice = min(range(len(escalones)), key=lambda i: abs(escalones[i] - actual))
    indice = max(0, min(len(escalones) - 1, indice + (1 if direccion > 0 else -1)))
    return escalones[indice]


# Yaw que usa el mapa según el modo de giro: «camara» gira con la cámara; «norte» deja siempre el norte arriba.
def yaw_efectivo(modo, yaw_camara):
    return 0.0 if modo == "norte" else float(yaw_camara)


# Capas de base que dibuja el minimapa según el detalle (1 = calles y lugares; 2 = + casas y escaleras; 3 = + rótulos).
def detalle(nivel):
    nivel = max(1, min(3, int(nivel)))
    return {"casas": nivel >= 2, "rotulos": nivel >= 3}


# --- Geometría local con zoom (mundo grande) -----------------------------------------------------------------------------

# GeometriaMinimapaLocal + zoom. Las capas estáticas se construyen SIEMPRE con la escala base (`absoluto`) y la vista las
# escala con `capa_mundo.scale = zoom`; `punto()` y todo lo que dibuja en pantalla usan la escala efectiva (base * zoom).
# Subclase aparte para no tocar frontend/hud_calculos.py: con zoom 1 se comporta exactamente como la clase base.
class GeometriaLocalAjustable(hud_calculos.GeometriaMinimapaLocal):

    def __init__(self, mapa, tamano, yaw_grados, zoom=1.0, **opciones):
        super().__init__(mapa, tamano, yaw_grados, **opciones)
        self.escala_base = self.escala
        self.radio_base = self.radio_ventana
        self.zoom = 1.0
        self.fijar_zoom(zoom)

    def fijar_zoom(self, zoom):
        zoom = float(zoom) if _finito(zoom) and zoom > 0 else 1.0
        self.zoom = max(0.25, min(8.0, zoom))
        self.escala = self.escala_base * self.zoom
        self.radio_ventana = self.radio_base / self.zoom

    # Coordenadas de la capa estática (escala base, sin girar ni centrar).
    def absoluto(self, x, z):
        return (self.escala_base * x, self.escala_base * z)
