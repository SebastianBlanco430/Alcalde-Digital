# Cálculos PUROS de los puestos de comercio (sin ursina, con tests): dónde cabe cada puesto sobre el mundo real.
# El ancla del catálogo (backend/datos/comercios_semilla.py) dice dónde quiere estar el comercio; aquí se mira la
# huella del puesto (un rectángulo de ~2,6 x 2,4 m con el dependiente de pie en su origen) y, si pisa un edificio,
# el asfalto de una calle, unas escaleras o un obstáculo, se prueba girarlo y, si hace falta, correrlo unos
# metros. El decorado no tiene colisión: esto solo evita que se vea metido en una casa o en medio de la calle.

import math

ANCHO_PUESTO = 2.6               # m a lo largo del mostrador
ATRAS_PUESTO = 0.95              # m de la espalda del dependiente al fondo del puesto
ADELANTE_PUESTO = 1.4            # m del dependiente al borde de la acera (por donde llega el cliente)
PASO_MUESTRA = 0.65              # m entre puntos de la huella
RADIO_BUSQUEDA = 3.0             # m máximos que se corre un puesto respecto a su ancla
PASO_BUSQUEDA = 0.5
MARGEN_EDIFICIO = 0.3
MARGEN_ASFALTO = 0.15
MARGEN_ESCALERA = 0.6
GIROS = (0.0, 90.0, -90.0, 180.0)   # el primero (el rumbo del ancla) gana los empates


def _normalizar(grados):
    return ((grados + 180.0) % 360.0) - 180.0


def _distancia_segmento(x, z, a, b):
    dx, dz = b[0] - a[0], b[1] - a[1]
    largo2 = dx * dx + dz * dz
    t = 0.0 if largo2 < 1e-12 else min(1.0, max(0.0, ((x - a[0]) * dx + (z - a[1]) * dz) / largo2))
    return math.hypot(x - (a[0] + dx * t), z - (a[1] + dz * t))


# Punto del mundo para (a lo largo, hacia delante) locales del puesto con ese rumbo (grados).
def punto_local(x, z, rumbo, da, df):
    s, c = math.sin(math.radians(rumbo)), math.cos(math.radians(rumbo))
    return (x + c * da + s * df, z - s * da + c * df)


# Puntos que cubren la huella del puesto (esquinas y rejilla): (x, z).
def muestras_huella(x, z, rumbo, ancho=ANCHO_PUESTO, atras=ATRAS_PUESTO, adelante=ADELANTE_PUESTO, paso=PASO_MUESTRA):
    columnas = max(2, int(math.ceil(ancho / paso)) + 1)
    filas = max(2, int(math.ceil((atras + adelante) / paso)) + 1)
    puntos = []
    for i in range(columnas):
        da = -ancho / 2 + ancho * i / (columnas - 1)
        for j in range(filas):
            df = -atras + (atras + adelante) * j / (filas - 1)
            puntos.append(punto_local(x, z, rumbo, da, df))
    return puntos


# Huellas de los puestos con toldo del mercadito decorativo (frontend/favela_detalles.mercadito): cajas (x0, x1, z0, z1).
# Los puestos nuevos se apartan de ellos para no taparlos.
def huellas_mercadito(zona, mitad_ancho=1.3, mitad_fondo=1.1):
    largo_x = zona.ancho >= zona.fondo
    largo, ancho = (zona.ancho, zona.fondo) if largo_x else (zona.fondo, zona.ancho)
    cuantos = max(2, int(largo // 3.2))
    cajas = []
    for fila in (-1, 1):
        for k in range(cuantos):
            a = -largo / 2 + (k + 0.5) * largo / cuantos
            b = fila * (ancho / 2 - 1.3)
            cx, cz = (zona.cx + a, zona.cz + b) if largo_x else (zona.cx + b, zona.cz + a)
            hx, hz = (mitad_ancho, mitad_fondo) if largo_x else (mitad_fondo, mitad_ancho)
            cajas.append((cx - hx, cx + hx, cz - hz, cz + hz))
    return cajas


class Ocupacion:
    """Lo que un puesto no debe pisar: edificios, asfalto, escaleras, lo no transitable y las `cajas`/`circulos` extra."""

    def __init__(self, mundo, cajas=(), circulos=()):
        self.mundo = mundo
        self.edificios = [e.caja() for e in mundo.edificios()]
        self.plaza = getattr(mundo, "radio_plaza", 0.0)
        self.plazas = [mundo.coordenada(lugar) for lugar in mundo.lugares()]
        self.semiancho = getattr(mundo, "ancho_calle", 0.0) / 2
        self.calles = []
        for a, b in mundo.segmentos():
            pa, pb = mundo.coordenada(a), mundo.coordenada(b)
            if math.dist(pa, pb) > 1e-9:
                self.calles.append((pa, pb))
        self.escaleras = [((e.ax, e.az), (e.bx, e.bz), e.ancho / 2) for e in mundo.escaleras()]
        self.cajas = list(cajas)
        self.circulos = list(circulos)

    def agregar_circulo(self, x, z, radio):
        self.circulos.append((x, z, radio))

    # Motivo por el que el punto (x, z) no sirve para un puesto, o None si está libre.
    def motivo(self, x, z):
        if not self.mundo.es_transitable(x, z):
            return "no transitable"
        for x0, x1, z0, z1 in self.edificios:
            if x0 - MARGEN_EDIFICIO <= x <= x1 + MARGEN_EDIFICIO and z0 - MARGEN_EDIFICIO <= z <= z1 + MARGEN_EDIFICIO:
                return "edificio"
        if not any(math.hypot(x - px, z - pz) < self.plaza for px, pz in self.plazas):
            for a, b in self.calles:
                if _distancia_segmento(x, z, a, b) < self.semiancho + MARGEN_ASFALTO:
                    return "calle"
        for a, b, mitad in self.escaleras:
            if _distancia_segmento(x, z, a, b) < mitad + MARGEN_ESCALERA:
                return "escalera"
        for x0, x1, z0, z1 in self.cajas:
            if x0 <= x <= x1 and z0 <= z <= z1:
                return "otro puesto"
        for cx, cz, r in self.circulos:
            if math.hypot(x - cx, z - cz) < r:
                return "otro puesto"
        return None

    # Cuántos puntos de la huella no están libres.
    def violaciones(self, puntos):
        return sum(1 for x, z in puntos if self.motivo(x, z) is not None)

    # Motivos (únicos, en orden) por los que falla la huella: para los tests y los avisos.
    def motivos(self, puntos):
        vistos = []
        for x, z in puntos:
            m = self.motivo(x, z)
            if m is not None and m not in vistos:
                vistos.append(m)
        return vistos


# (x, z, rumbo, violaciones) del mejor sitio para el puesto de ancla (x, z, rumbo): primero el ancla con sus cuatro
# giros y, si todos fallan, anillos cada vez más lejos (hasta `radio`). Devuelve el primero sin violaciones; si no
# hay ninguno, el de menos (el más cercano al ancla en los empates). Determinista.
def elegir_puesto(ocupacion, x, z, rumbo, radio=RADIO_BUSQUEDA, paso=PASO_BUSQUEDA):
    mejor = None
    pasos = int(radio / paso)
    desfases = [(0.0, 0.0)]
    for anillo in range(1, pasos + 1):
        r = anillo * paso
        n = max(8, int(2 * math.pi * r / paso))
        desfases += [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)) for k in range(n)]
    for dx, dz in desfases:
        px, pz = x + dx, z + dz
        if ocupacion.motivo(px, pz) is not None:
            continue                                    # el dependiente tiene que estar en suelo libre
        for orden, giro in enumerate(GIROS):
            r_giro = _normalizar(rumbo + giro)
            v = ocupacion.violaciones(muestras_huella(px, pz, r_giro))
            clave = (v, math.hypot(dx, dz), orden)
            if mejor is None or clave < mejor[0]:
                mejor = (clave, (px, pz, r_giro))
            if v == 0 and mejor[0][0] == 0:
                break
        if mejor is not None and mejor[0][0] == 0:
            break
    if mejor is None:
        return (x, z, rumbo, ocupacion.violaciones(muestras_huella(x, z, rumbo)))
    px, pz, r = mejor[1]
    return (px, pz, r, mejor[0][0])
