# Cálculos PUROS de los puestos de comercio (sin ursina, con tests): dónde cabe cada puesto sobre el mundo real.
# El ancla del catálogo (backend/datos/comercios_semilla.py) dice dónde quiere estar el comercio; aquí se mira la
# huella del puesto (un rectángulo de ~2,6 x 2,4 m con el dependiente de pie en su origen) y, si pisa un edificio,
# el asfalto de una calle, unas escaleras o un obstáculo, se prueba girarlo y, si hace falta, correrlo unos
# metros. Esto evita que se vea metido en una casa o en medio de la calle; la colisión del puesto ya colocado la da
# obstaculos_puesto() (mostrador y pared del fondo; el frente, donde se habla con el dependiente, queda libre).

import math

from backend.logica import feria
from backend.logica.mundo_ciudad import Obstaculo

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


# Colisión de un puesto colocado: una fila de círculos en el mostrador (delante del dependiente) y otra en la pared del
# fondo. El cliente se queda delante del mostrador, a ~1,6 m del dependiente: dentro del radio de la E (2,4 m).
FILAS_COLISION_PUESTO = ((0.85, 0.36), (-0.95, 0.30))     # (hacia delante, radio) de cada fila
COLUMNAS_COLISION_PUESTO = (-1.0, 0.0, 1.0)              # m a lo largo del mostrador


def obstaculos_puesto(x, z, rumbo):
    obstaculos = []
    for df, radio in FILAS_COLISION_PUESTO:
        for da in COLUMNAS_COLISION_PUESTO:
            px, pz = punto_local(x, z, rumbo, da, df)
            obstaculos.append(Obstaculo("puesto", round(px, 3), round(pz, 3), radio=radio))
    return obstaculos


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
# Los puestos nuevos se apartan de ellos para no taparlos. La colocación sale de backend/logica/feria.py (la misma que
# dibuja favela_detalles.mercadito y la que choca en favela_calculos.obstaculos_de_zonas).
def huellas_mercadito(zona, mitad_ancho=1.3, mitad_fondo=1.1):
    largo_x = zona.ancho >= zona.fondo
    hx, hz = (mitad_ancho, mitad_fondo) if largo_x else (mitad_fondo, mitad_ancho)
    return [(cx - hx, cx + hx, cz - hz, cz + hz) for cx, cz, _rumbo in feria.puestos_decorativos(zona)]


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


# (x, z, rumbo, violaciones) del puesto: el ancla tal cual si es FIJA (ALCALDE_PUESTOS_FIJOS: revisada a mano; aquí solo
# se cuenta lo que pisa, los tests exigen 0) o el mejor sitio de elegir_puesto si no lo es (como antes).
def colocar_puesto(ocupacion, x, z, rumbo, fijo=False):
    if fijo:
        return (x, z, rumbo, ocupacion.violaciones(muestras_huella(x, z, rumbo)))
    return elegir_puesto(ocupacion, x, z, rumbo)


# -- Revisión de un puesto colocado (tests y avisos) -----------------------------------------------------------------
# Lo que Ocupacion no mira: puertas (de los lugares y de las casas decorativas), bancos, farolas, árboles y demás props,
# puntos de misión. Puro: los props llegan como (tipo, x, z, radio).
DISTANCIA_PUERTA = 2.0           # m mínimos de una puerta (lugar o casa) a la huella del puesto
DISTANCIA_PROP = 1.0             # m mínimos de un banco/farola/árbol a la huella (o su radio, si es mayor)
DISTANCIA_MISION = 4.0           # m mínimos del dependiente a un punto de misión (sus E no se pisan)
PASILLO_PUERTA = 2.5             # m libres entre las dos huellas de una pareja, frente a la puerta


# Distancia de (px, pz) al rectángulo de la huella del puesto (0 si cae dentro).
def distancia_a_huella(px, pz, x, z, rumbo, ancho=ANCHO_PUESTO, atras=ATRAS_PUESTO, adelante=ADELANTE_PUESTO):
    s, c = math.sin(math.radians(rumbo)), math.cos(math.radians(rumbo))
    dx, dz = px - x, pz - z
    da = c * dx - s * dz                       # a lo largo del mostrador (inversa de punto_local)
    df = s * dx + c * dz                       # hacia delante
    ea = max(0.0, abs(da) - ancho / 2)
    ef = max(0.0, -atras - df, df - adelante)
    return math.hypot(ea, ef)


# Puerta (x, z) de una casa decorativa: centro de su frente (+z del modelo girado `rumbo`), corrida su puerta_x.
def puerta_de_casa(casa):
    from backend.datos.modelos_edificios import modelo_de
    r = math.radians(casa.rumbo)
    fx, fz = math.sin(r), math.cos(r)
    medio_fondo = (casa.fondo if casa.rumbo % 180 == 0 else casa.ancho) / 2
    try:
        corrida = modelo_de(casa.modelo).puerta_x * casa.escala
    except Exception:                          # noqa: BLE001  modelo desconocido: el centro del frente
        corrida = 0.0
    return (casa.cx + fx * medio_fondo + math.cos(r) * corrida, casa.cz + fz * medio_fondo - math.sin(r) * corrida)


def puertas_del_mundo(mundo):
    """[(x, z)] de las puertas de los lugares y de las casas decorativas."""
    puertas = [tuple(e.puerta()) for e in mundo.edificios()]
    puertas += [puerta_de_casa(o) for o in mundo.obstaculos() if o.tipo == "casa" and getattr(o, "modelo", "")]
    return puertas


def props_del_mundo(mundo, props=()):
    """[(tipo, x, z, radio)] de bancos, farolas, árboles... del modelo y de los props del frontend (props_mundo.Prop)."""
    salida = [(o.tipo, o.cx, o.cz, o.radio or max(o.ancho or 0, o.fondo or 0) / 2) for o in mundo.obstaculos()
              if o.tipo in ("banco", "farola", "arbol", "bananero", "palmera")]
    if props:
        from frontend.props_mundo import RADIO_PROP          # sin ursina al importar
        salida += [(p.tipo, p.x, p.z, RADIO_PROP.get(p.tipo, 0.5)) for p in props if p.tipo != "fuente"]
    return salida


# [motivo] de lo que falla en el puesto (x, z, rumbo): vacío si está bien. `ocupacion`: Ocupacion del mundo (+ feria);
# `puertas`, `props`, `puntos_mision`: listas de arriba. `puerta_propia`: la puerta de su lugar (se mira aparte, con el
# pasillo de la pareja).
def problemas_puesto(ocupacion, x, z, rumbo, puertas=(), props=(), puntos_mision=(), puerta_propia=None):
    problemas = list(ocupacion.motivos(muestras_huella(x, z, rumbo)))
    for px, pz in puertas:
        if puerta_propia is not None and math.hypot(px - puerta_propia[0], pz - puerta_propia[1]) < 1e-6:
            continue
        if distancia_a_huella(px, pz, x, z, rumbo) < DISTANCIA_PUERTA:
            problemas.append(f"puerta en ({px:.1f}, {pz:.1f})")
    for tipo, px, pz, radio in props:
        if distancia_a_huella(px, pz, x, z, rumbo) < max(DISTANCIA_PROP, radio):
            problemas.append(f"{tipo} en ({px:.1f}, {pz:.1f})")
    for px, pz in puntos_mision:
        if math.hypot(px - x, pz - z) < DISTANCIA_MISION:
            problemas.append(f"misión en ({px:.1f}, {pz:.1f})")
    return problemas


# Ancho libre entre las huellas de dos puestos con el mismo rumbo (a lo largo del mostrador).
def pasillo_entre(a, b):
    (xa, za, ra), (xb, zb, _rb) = a, b
    c, s = math.cos(math.radians(ra)), math.sin(math.radians(ra))
    da = abs(c * (xb - xa) - s * (zb - za))
    return da - ANCHO_PUESTO


# -- Terminal de una misión digital junto a una puerta con puestos fijos ----------------------------------------------
# frontend/registro_mundo_digital.sitio_junto_al_destino pone el computador del caso 1,5 m fuera de la puerta del destino
# y 1,4 m a un lado. Con ALCALDE_PUESTOS_FIJOS la pareja del Mercado ocupa justo ese sitio: se busca el primer lateral
# (el de siempre, el otro lado y luego cada vez más lejos) donde el escritorio, la silla y el sitio desde el que se llega
# (huella local: ±0,7 m a lo ancho, de -0,45 a +1,4 m hacia delante) quedan a >= 0,4 m de todo puesto y son transitables.
MITAD_TERMINAL, ATRAS_TERMINAL, ADELANTE_TERMINAL, MARGEN_TERMINAL = 0.7, 0.45, 1.4, 0.4


def lateral_terminal(mundo, lugar, fuera, lateral, puestos, paso=0.25, maximo=8.0):
    """Lateral (m) para el terminal frente a la puerta de `lugar`: `lateral` si cabe, o el primero que cabe.
    `puestos`: [(x, z, rumbo)] colocados. None si ninguno cabe."""
    from backend.logica.comercios import resolver_ancla
    candidatos = [lateral, -lateral]
    k = abs(lateral) + paso
    while k <= maximo + 1e-9:
        candidatos += [math.copysign(k, lateral), -math.copysign(k, lateral)]
        k += paso
    transitable = getattr(mundo, "es_transitable", None)
    for lat in candidatos:
        x, z, rumbo = resolver_ancla(mundo, {"lugar": lugar, "fuera": fuera, "lateral": lat})
        puntos = muestras_huella(x, z, rumbo, ancho=2 * MITAD_TERMINAL, atras=ATRAS_TERMINAL,
                                 adelante=ADELANTE_TERMINAL, paso=0.35)
        if transitable is not None and not all(transitable(px, pz) for px, pz in puntos):
            continue
        if all(distancia_a_huella(px, pz, sx, sz, sr) >= MARGEN_TERMINAL for px, pz in puntos for sx, sz, sr in puestos):
            return lat
    return None
