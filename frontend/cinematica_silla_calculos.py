# Cálculos de las animaciones de silla, corcho y pantalla (Python puro: NO importa ursina ni panda). Los usa
# frontend/cinematica_silla.py; contrato en sesiones-24nov/animaciones/contrato-silla.md y guion en guion.md.
#
# Idea: cada secuencia es un GUION puro, una función del tiempo t -> Estado (dónde está el personaje, su rumbo, cuánto
# baja la pelvis, dónde van las manos y los pies, dónde está la silla, la toma de cámara y el velo). La vista solo
# aplica Estado(t) cada frame; saltar = aplicar Estado(duracion). Así todo lo físico (silla acotada, manos sobre el
# tablero, cámara lejos de la cabeza, toma final exacta) se comprueba en tests sin ventana.
#
# Coordenadas de MUNDO (metros). Rumbo en grados como Personaje.fijar_rumbo: 0 = mira a +z, 90 = mira a +x.
#   adelante(r) = (sin r, cos r)   derecha(r) = (cos r, -sin r)     (en el plano x/z; igual que poses_3d._ejes)

import math
import os
from dataclasses import dataclass, field

from frontend.minijuegos_3d import camaras_calculos as ccal

# -- Bandera --------------------------------------------------------------------------------------------------------

VARIABLE = "ALCALDE_ANIM_SILLA"
ANIM_SILLA = True                    # valor por defecto (encendida)
_APAGADO = ("0", "false", "no", "off")
_ENCENDIDO = ("1", "true", "si", "sí", "on")


def activa(entorno=None):
    """¿Está encendida ALCALDE_ANIM_SILLA? Mismos valores que frontend/minijuegos_3d/banderas.py (0/false/no/off apaga).
    Se lee en cada llamada."""
    valor = (entorno if entorno is not None else os.environ).get(VARIABLE, "").strip().lower()
    if valor in _APAGADO:
        return False
    if valor in _ENCENDIDO:
        return True
    return bool(ANIM_SILLA)


# -- Descripciones (contrato §2) ------------------------------------------------------------------------------------

@dataclass
class Silla:
    posicion: tuple = (0.0, 0.0)     # (x, z) centro del asiento con la silla YA ACOMODADA
    rumbo: float = 0.0               # hacia donde mira el sentado (hacia la mesa)
    altura_asiento: float = 0.45
    altura_respaldo: float = 0.95
    retiro: float = 0.45             # m que se desliza hacia atrás al sacarla
    lado: str = "i"                  # por dónde llega/se mete el personaje: "i" | "d"
    suelo_y: float = 0.0


@dataclass
class Mesa:
    altura: float = 0.75             # y de la cara de arriba del tablero
    borde: float = 0.35              # m desde Silla.posicion al canto cercano, a lo largo del rumbo
    manos: dict = None               # {"i": (x, y, z), "d": (x, y, z)}; None = sobre el tablero (ver manos_mesa)


@dataclass
class Corcho:
    centro: tuple = (0.0, 1.5, 0.0)
    normal: tuple = (0.0, 0.0, -1.0)  # del corcho hacia la sala
    ancho: float = 2.0
    alto: float = 1.2
    pie: tuple = None                # (x, z) donde se detiene; None = 0,62 m delante, a la izquierda del centro
    nota: tuple = None               # (x, y, z) que toca; None = el centro


@dataclass
class Cuerpo:
    """Medidas del personaje que cambian la coreografía (la vista las mide del esqueleto cuando ya se dibujó)."""
    alcance: float = 0.56            # m del hombro a la muñeca (brazo + antebrazo al 97 %; medido en ventana)
    alto_hombro: float = 1.44        # y del hombro sobre el suelo, de pie (medido: rig común 1,444)
    alto_cabeza: float = 1.62        # y del centro de la cabeza, de pie
    radio_cabeza: float = 0.41       # m que la cámara respeta al centro de la cabeza a mitad de curva (>= 0,35)


# brasilena.glb (influencer): brazo ~0,43 m y más baja. Valores de partida hasta medir el esqueleto.
CUERPO_POR_ROL = {"influencer": Cuerpo(alcance=0.42, alto_hombro=1.39, alto_cabeza=1.57, radio_cabeza=0.62)}   # afro


def cuerpo_de_rol(rol):
    c = CUERPO_POR_ROL.get(rol)
    return Cuerpo(c.alcance, c.alto_hombro, c.alto_cabeza, c.radio_cabeza) if c else Cuerpo()


# -- Duraciones (guion.md) ------------------------------------------------------------------------------------------

DURACIONES = {
    "sentarse_en": (("llegar", 0.55), ("sacar", 0.45), ("sentarse", 0.75), ("acomodar", 0.45), ("manos", 0.40)),
    "levantarse_de": (("retirar", 0.35), ("levantarse", 0.50), ("empujar", 0.45), ("apartarse", 0.30)),
    "acercarse_a_corcho": (("caminar", 1.30), ("mirar", 0.40), ("mano", 0.50)),
    "dejar_corcho": (("bajar_mano", 0.30), ("apartarse", 0.60)),
    # los 5 tramos de la silla comprimidos a 2,15 s (x0,827), y la cámara entra en la pantalla
    "entrar_a_pantalla": (("llegar", 0.455), ("sacar", 0.372), ("sentarse", 0.620), ("acomodar", 0.372),
                          ("manos", 0.331), ("entrar", 0.65), ("glitch", 0.20)),
    "salir_de_pantalla": (("salir", 0.80),),
}
DURACIONES_RAPIDA = {
    "sentarse_en": (("llegar", 0.25), ("sacar", 0.25), ("sentarse", 0.40), ("acomodar", 0.25), ("manos", 0.20)),
    "levantarse_de": (("retirar", 0.20), ("levantarse", 0.30), ("empujar", 0.25), ("apartarse", 0.15)),
    "acercarse_a_corcho": (("caminar", 0.65), ("mirar", 0.20), ("mano", 0.35)),
    "dejar_corcho": (("bajar_mano", 0.20), ("apartarse", 0.30)),
    "entrar_a_pantalla": (("llegar", 0.185), ("sacar", 0.185), ("sentarse", 0.296), ("acomodar", 0.185),
                          ("manos", 0.149), ("entrar", 0.35), ("glitch", 0.15)),
    "salir_de_pantalla": (("salir", 0.50),),
}
MAXIMO_COMPLETA = 3.0
MAXIMO_RAPIDA = 1.5
VELO_REDUCIDO = (0.25, 0.15)         # reducir movimiento: velo negro que sube / que se quita (s)
VELOCIDAD_EXTRA = 2.2                # m/s de la caminata extra cuando el personaje empieza lejos
GLITCH_DESVANECER = 0.25             # s que tarda el velo del glitch en irse solo tras el cambio de escena


def tramos(secuencia, rapida=False):
    """[(nombre, inicio, fin)] de la secuencia (sin caminata extra)."""
    tabla = (DURACIONES_RAPIDA if rapida else DURACIONES)[secuencia]
    out, t = [], 0.0
    for nombre, d in tabla:
        out.append((nombre, t, t + d))
        t += d
    return out


def duracion_total(secuencia, rapida=False):
    return sum(d for _, d in (DURACIONES_RAPIDA if rapida else DURACIONES)[secuencia])


# -- Regla de la versión rápida (por clave y por proceso) -----------------------------------------------------------

_vistas = set()


def decidir_rapida(clave, rapida=None):
    """None = automático (completa la primera vez que se ve `clave`, rápida después). La marca como vista (saltar también
    cuenta: se marca al empezar)."""
    vista = clave in _vistas
    _vistas.add(clave)
    if rapida is not None:
        return bool(rapida)
    return vista


def ya_vista(clave):
    return clave in _vistas


def reiniciar_vistas():
    """Para los tests (y por si una escena quiere volver a la completa)."""
    _vistas.clear()


def clave_salida(clave):
    return clave if clave.endswith("_salida") else clave + "_salida"


# -- Matemática básica ------------------------------------------------------------------------------------------------

def suave(k):
    k = min(1.0, max(0.0, k))
    return k * k * (3 - 2 * k)


def sale(k):
    """ease-out cuadrático."""
    k = min(1.0, max(0.0, k))
    return 1 - (1 - k) * (1 - k)


def acercamiento(k):
    """Avance de la cámara en las entradas: ease-in-out que se queda atrás (abierta) mientras el personaje llega y se
    sienta, y se acerca al final (suave^1,5: sale y llega con velocidad 0)."""
    return suave(k) ** 1.5


def alejamiento(k):
    """Avance de la cámara en la salida de la silla: arranca con velocidad 0 pero se aparta pronto (el personaje se
    levanta hacia la cámara de juego, que está junto a su cabeza)."""
    return 1 - (1 - suave(k)) ** 2


def entra_suave(k):
    """ease-in suave (la bajada al asiento: arranca despacio y no «cae»: termina con velocidad moderada)."""
    k = min(1.0, max(0.0, k))
    return 0.5 * k * k + 0.5 * suave(k)


def lerp(a, b, k):
    return a + (b - a) * k


def lerp2(a, b, k):
    return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)


def lerp3(a, b, k):
    return tuple(a[i] + (b[i] - a[i]) * k for i in range(3))


def _sub(a, b):
    return tuple(a[i] - b[i] for i in range(len(a)))


def _add(a, b):
    return tuple(a[i] + b[i] for i in range(len(a)))


def _mul(a, k):
    return tuple(c * k for c in a)


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(len(a)))


def _len(a):
    return math.sqrt(_dot(a, a))


def _unit(a, defecto=None):
    n = _len(a)
    if n < 1e-9:
        return defecto if defecto is not None else a
    return _mul(a, 1.0 / n)


def angulo_corto(a, b):
    """b - a llevado a (-180, 180]."""
    d = (b - a) % 360.0
    return d - 360.0 if d > 180.0 else d


def lerp_angulo(a, b, k):
    return a + angulo_corto(a, b) * k


def adelante(rumbo):
    r = math.radians(rumbo)
    return (math.sin(r), math.cos(r))


def derecha(rumbo):
    r = math.radians(rumbo)
    return (math.cos(r), -math.sin(r))


def rumbo_de(dx, dz, defecto=0.0):
    if abs(dx) + abs(dz) < 1e-9:
        return defecto
    return math.degrees(math.atan2(dx, dz))


def finito(v):
    try:
        return all(math.isfinite(float(c)) for c in v)
    except (TypeError, ValueError):
        return False


def bezier2(p0, p1, p2, k):
    a = (1 - k) * (1 - k)
    b = 2 * k * (1 - k)
    c = k * k
    return tuple(a * p0[i] + b * p1[i] + c * p2[i] for i in range(len(p0)))


def bezier3(p0, p1, p2, p3, k):
    u = 1 - k
    return tuple(u * u * u * p0[i] + 3 * u * u * k * p1[i] + 3 * u * k * k * p2[i] + k * k * k * p3[i]
                 for i in range(len(p0)))


# -- Geometría de la silla ------------------------------------------------------------------------------------------

PROF_ASIENTO = 0.42
ANCHO_ASIENTO = 0.44
RESPALDO_ATRAS = 0.20                # el respaldo está 0,20 m detrás del centro del asiento
HOMBRO_LATERAL = 0.18                # m del centro del cuerpo al hombro
LATERAL_JUNTO = 0.42                 # m del eje de la silla al centro del cuerpo de pie a su lado (no la atraviesa)
PASO_SACAR = 0.22                    # m que el personaje retrocede al sacar la silla (acompaña con medio paso)
FRENTE_SENTARSE = 0.32               # m delante del centro del asiento donde está la pelvis de pie antes de bajar
AVANCE_PIES = 0.48                   # m delante del centro del asiento donde quedan los pies sentado
BAJADA_MAXIMA = 0.70
PELVIS_DE_PIE = 0.97                 # y nominal de la pelvis de pie
PELVIS_SOBRE_ASIENTO = 0.07          # la pelvis queda 7 cm sobre la cara del asiento
SUBIDA_MANOS = 0.04                  # arco de las manos a la mesa
SOBRE_TABLERO = 0.02                 # las manos nunca bajan de mesa.altura + 2 cm sobre el tablero


def signo_lado(lado):
    return -1.0 if lado == "i" else 1.0


def mano_respaldo_lado(silla):
    """La mano que sube al respaldo: la del lado contrario a `silla.lado` (la que queda junto a la silla)."""
    return "d" if silla.lado == "i" else "i"


def en_silla(silla, avance, lateral):
    """Punto (x, z) a `avance` m delante y `lateral` m a la derecha de silla.posicion (ejes de la silla)."""
    a, d = adelante(silla.rumbo), derecha(silla.rumbo)
    x, z = silla.posicion
    return (x + a[0] * avance + d[0] * lateral, z + a[1] * avance + d[1] * lateral)


def bajada_sentado(silla):
    """m que baja la pelvis para quedar sentado (0,97 -> altura del asiento + 0,07), acotado."""
    return min(BAJADA_MAXIMA, max(0.0, PELVIS_DE_PIE - silla.altura_asiento - PELVIS_SOBRE_ASIENTO))


def retiro_efectivo(silla, limites=None):
    """`silla.retiro` acotado a >= 0 y recortado para que el respaldo no salga de `limites` (xmin, xmax, zmin, zmax)."""
    r = max(0.0, float(silla.retiro))
    if limites is None:
        return r
    xmin, xmax, zmin, zmax = limites[:4]
    for _ in range(60):
        x, z = en_silla(silla, -r - RESPALDO_ATRAS - 0.03, 0.0)
        if xmin <= x <= xmax and zmin <= z <= zmax:
            break
        r = max(0.0, r - 0.02)
    return r


def silla_en(silla, d):
    """Centro (x, z) de la silla desplazada `d` m hacia atrás (0 = acomodada)."""
    return en_silla(silla, -d, 0.0)


def acotar_desplazamiento(d, retiro):
    return min(max(0.0, d), max(0.0, retiro))


def frente_asiento(silla, d):
    """Distancia (m, a lo largo del rumbo desde silla.posicion) del frente del asiento con la silla desplazada `d`."""
    return PROF_ASIENTO / 2 - d


def respaldo_mano(silla, d, cuerpo=None):
    """Punto (x, y, z) donde se apoya la mano en el respaldo (esquina del lado `silla.lado`, arriba)."""
    s = signo_lado(silla.lado)
    x, z = en_silla(silla, -d - RESPALDO_ATRAS, s * 0.15)
    return (x, silla.suelo_y + silla.altura_respaldo + 0.01, z)


def atras_respaldo(silla, cuerpo):
    """m que el cuerpo se queda detrás de la línea del respaldo para agarrarlo con el brazo a ~90 % de su alcance (si no
    llega, se acerca: nunca se estira de goma)."""
    dy = (silla.suelo_y + cuerpo.alto_hombro) - (silla.suelo_y + silla.altura_respaldo)
    lateral = LATERAL_JUNTO - HOMBRO_LATERAL - 0.15
    resto = (0.9 * cuerpo.alcance) ** 2 - dy * dy - lateral * lateral
    f = math.sqrt(resto) if resto > 0 else 0.0
    return min(0.22, max(0.0, f))


def junto_respaldo(silla, d, cuerpo):
    """(x, z) del cuerpo de pie junto a la silla (lado `silla.lado`) con la mano en el respaldo (silla desplazada d)."""
    s = signo_lado(silla.lado)
    return en_silla(silla, -d - RESPALDO_ATRAS - atras_respaldo(silla, cuerpo), s * LATERAL_JUNTO)


def _tras_sacar(silla, p_grab0, retiro):
    """Donde queda el cuerpo tras sacar la silla: medio paso atrás (PASO_SACAR, nunca más que el retiro)."""
    a = adelante(silla.rumbo)
    paso = min(PASO_SACAR, retiro)
    return (p_grab0[0] - a[0] * paso, p_grab0[1] - a[1] * paso)


def punto_de_partida(silla):
    """(x, z, rumbo) donde poner al personaje antes de sentarse_en: 1,2 m detrás y 0,55 m al lado `silla.lado` del
    asiento, mirando hacia el respaldo."""
    s = signo_lado(silla.lado)
    x, z = en_silla(silla, -1.2, s * 0.55)
    rx, rz = en_silla(silla, -RESPALDO_ATRAS, 0.0)
    return (x, z, rumbo_de(rx - x, rz - z, silla.rumbo))


def manos_mesa(silla, mesa):
    """{"i": p, "d": p} donde terminan las manos: mesa.manos o, por defecto, sobre el tablero (0,10 m pasado el canto
    cercano, ±0,16 m a los lados), con y >= mesa.altura + 2 cm."""
    if mesa.manos:
        out = {}
        for lado in ("i", "d"):
            p = mesa.manos.get(lado)
            if p is not None:
                out[lado] = (float(p[0]), max(float(p[1]), mesa.altura + SOBRE_TABLERO), float(p[2]))
        return out
    out = {}
    for lado in ("i", "d"):
        x, z = en_silla(silla, mesa.borde + 0.10, signo_lado(lado) * 0.16)
        out[lado] = (x, mesa.altura + 0.03, z)
    return out


def manos_asiento(silla, d):
    """Manos agarrando el borde del asiento a los lados (silla desplazada d)."""
    out = {}
    for lado in ("i", "d"):
        x, z = en_silla(silla, -d + 0.02, signo_lado(lado) * (ANCHO_ASIENTO / 2 + 0.01))
        out[lado] = (x, silla.suelo_y + silla.altura_asiento + 0.03, z)
    return out


def sobre_canto(silla, mesa, lado):
    """Punto de paso de la mano por encima del canto de la mesa (no lo atraviesa)."""
    x, z = en_silla(silla, mesa.borde - 0.02, signo_lado(lado) * 0.18)
    return (x, mesa.altura + 0.07, z)


def avance_sobre_mesa(silla, mesa, p):
    """¿Cuánto (m) está `p` por delante del canto de la mesa (a lo largo del rumbo)? > 0 = sobre el tablero."""
    a = adelante(silla.rumbo)
    x, z = silla.posicion
    return (p[0] - x) * a[0] + (p[2] - z) * a[1] - mesa.borde


def acotar_mano_mesa(silla, mesa, p):
    """Sobre el tablero, la mano nunca baja de mesa.altura + 2 cm."""
    if mesa is None or p is None:
        return p
    if avance_sobre_mesa(silla, mesa, p) > -0.01 and p[1] < mesa.altura + SOBRE_TABLERO:
        return (p[0], mesa.altura + SOBRE_TABLERO, p[2])
    return p


def mano_colgando(x, z, rumbo, lado, cuerpo, suelo_y=0.0):
    """Muñeca de un brazo en reposo junto al costado (aprox. de pc.mano_colgando con medidas nominales)."""
    a, d = adelante(rumbo), derecha(rumbo)
    s = signo_lado(lado)
    hx = x + d[0] * (HOMBRO_LATERAL + 0.05) * s - a[0] * 0.03
    hz = z + d[1] * (HOMBRO_LATERAL + 0.05) * s - a[1] * 0.03
    return (hx, suelo_y + cuerpo.alto_hombro - 0.8 * cuerpo.alcance, hz)


# -- Estado --------------------------------------------------------------------------------------------------------

@dataclass
class Estado:
    x: float
    z: float
    rumbo: float
    bajada: float = 0.0              # m que baja la pelvis (0 = de pie)
    velocidad: float = 0.0           # m/s del desplazamiento (ciclo de marcha); 0 sentado
    pies: tuple = None               # (x, z) del centro de los pies (IK de piernas) mientras bajada > 0
    manos: dict = field(default_factory=dict)   # lado -> (x, y, z) o None (libre, animación)
    silla: tuple = None              # (x, z) del centro de la silla (None = no hay silla)
    camara: dict = None              # toma
    velo: float = 0.0                # glitch 0..1 (pantalla)
    mirar: float = 0.0               # grados que levanta la vista (corcho)
    tramo: str = ""

    @property
    def sentado(self):
        return self.bajada > 0.01


# -- Cámara ----------------------------------------------------------------------------------------------------------

DISTANCIA_CABEZA = 0.35
MARGEN_CABEZA = 0.06


def toma(position, target, fov):
    return {"position": tuple(float(c) for c in position), "target": tuple(float(c) for c in target), "fov": float(fov)}


def copiar_toma(t):
    return {"position": tuple(t["position"]), "target": tuple(t["target"]), "fov": t["fov"]}


def eje_toma(t):
    return _unit(_sub(t["target"], t["position"]), (0.0, 0.0, 1.0))


def recortar(p, limites, margen=0.15):
    """Recorta (x, ?, z) [e y si limites trae ymin, ymax] a la caja de la sala con `margen`."""
    if limites is None:
        return tuple(p)
    x, y, z = p
    xmin, xmax, zmin, zmax = limites[:4]
    if xmax - xmin > 2 * margen:
        x = min(max(x, xmin + margen), xmax - margen)
    if zmax - zmin > 2 * margen:
        z = min(max(z, zmin + margen), zmax - margen)
    if len(limites) >= 6:
        ymin, ymax = limites[4], limites[5]
        y = min(max(y, ymin + margen), ymax - margen)
    return (x, y, z)


def toma_establecimiento(toma_final, retroceso=1.6, subida=0.35, fov_extra=10.0, lateral=0.0, limites=None):
    """Toma de partida por defecto: `toma_final` retrocedida a lo largo de su eje de mirada, más alta, con más fov y
    (opcional) desplazada `lateral` m a la derecha de quien mira; recortada a `limites`."""
    e = eje_toma(toma_final)
    der = _unit((e[2], 0.0, -e[0]), (1.0, 0.0, 0.0))
    p = _add(_add(_sub(toma_final["position"], _mul(e, retroceso)), (0.0, subida, 0.0)), _mul(der, lateral))
    return toma(recortar(p, limites), toma_final["target"], toma_final["fov"] + fov_extra)


FOV_PANTALLA = 40.0
FOV_PANTALLA_MAXIMO = 75.0


def _distancia_llena(pantalla, aspecto, fov, llenado):
    fov_v = ccal.fov_vertical(fov, aspecto)
    d_alto = (pantalla["alto"] / 2) / math.tan(math.radians(fov_v) / 2)
    d_ancho = (pantalla["ancho"] / 2) / math.tan(math.radians(fov) / 2)
    return max(0.03, min(d_alto, d_ancho) * llenado)


def toma_pantalla_llena(pantalla, aspecto=16 / 9, fov=FOV_PANTALLA, llenado=0.97, cabeza=None):
    """Toma de frente a la pantalla, tan cerca que la pantalla llena (cubre) la ventana, con fov 40. Si a esa distancia la
    cámara quedaría a menos de DISTANCIA_CABEZA (+ margen) de `cabeza` (monitor pequeño: con fov 40 habría que ponerse
    donde está la cabeza del sentado), se acerca a la pantalla y abre el fov lo justo (hasta FOV_PANTALLA_MAXIMO)."""
    n = _unit(tuple(pantalla["normal"]), (0.0, 0.0, -1.0))
    c = tuple(pantalla["centro"])
    d = _distancia_llena(pantalla, aspecto, fov, llenado)
    if cabeza is not None:
        objetivo = DISTANCIA_CABEZA + MARGEN_CABEZA + 0.05
        while _len(_sub(_add(c, _mul(n, d)), cabeza)) < objetivo and fov < FOV_PANTALLA_MAXIMO:
            fov = min(FOV_PANTALLA_MAXIMO, fov + 1.0)
            d = _distancia_llena(pantalla, aspecto, fov, llenado)
    return toma(_add(c, _mul(n, d)), c, fov)


def toma_hombro_pantalla(pantalla, aspecto=16 / 9, rol=None):
    return toma(**ccal.toma_sobre_hombro(pantalla, aspecto, rol=rol))


RADIO_CUERPO = 0.90                  # m del eje del cuerpo (de pie o sentado) que la cámara respeta a mitad de curva
ZONA_EXTREMOS = 0.35                 # fracción de k en la que la exigencia pasa de la de los extremos a la plena


def punto_en_segmento(p, a, b):
    ab = _sub(b, a)
    n = _dot(ab, ab)
    if n < 1e-12:
        return tuple(a)
    u = min(1.0, max(0.0, _dot(_sub(p, a), ab) / n))
    return _add(a, _mul(ab, u))


class CurvaCamara:
    """De `desde` a `hasta`: posición por Bézier CÚBICA, `target` y `fov` lineales sobre la misma k; toma(1) == `hasta`
    exacto. Obstáculos (funciones de k): `cabeza(k)` -> punto (la cámara no entra a menos de DISTANCIA_CABEZA) y
    `cuerpo(k)` -> segmento (a, b) del eje del cuerpo (a menos de RADIO_CUERPO a mitad de curva: el torso no llena la
    pantalla). Cerca de los extremos la exigencia baja a la distancia que ya tengan las tomas dadas (la toma de juego sobre el
    hombro está a ~0,4 m de la cabeza). Los dos puntos de control se empujan hasta cumplir. `llegada="eje"`: llega por
    detrás a lo largo del eje de mirada de `hasta` (un acercamiento, «dolly-in»)."""

    def __init__(self, desde, hasta, cabeza=None, limites=None, cuerpo=None, llegada=None, radio_cabeza=None):
        self.desde = copiar_toma(desde)
        self.hasta = copiar_toma(hasta)
        p0, p3 = self.desde["position"], self.hasta["position"]
        largo = _len(_sub(p3, p0))
        self.c1 = lerp3(p0, p3, 1 / 3)
        if llegada == "eje" and largo > 1e-6:
            self.c2 = _sub(p3, _mul(eje_toma(self.hasta), largo / 3))
        else:
            self.c2 = lerp3(p0, p3, 2 / 3)
        if limites:
            self.c1, self.c2 = recortar(self.c1, limites, 0.15), recortar(self.c2, limites, 0.15)
        self._obs = []
        if cabeza is not None:
            radio = max(DISTANCIA_CABEZA + MARGEN_CABEZA, radio_cabeza or 0.0)
            self._obs.append((lambda k: (cabeza(k), cabeza(k)), radio, DISTANCIA_CABEZA))
        if cuerpo is not None:
            self._obs.append((cuerpo, RADIO_CUERPO, 0.0))
        self._extremos = []
        for fn, radio, minimo in self._obs:
            d0 = self._dist(p0, fn(0.0))
            d1 = self._dist(p3, fn(1.0))
            self._extremos.append((min(radio, max(minimo, d0 - 0.01)), min(radio, max(minimo, d1 - 0.01))))
        if self._obs:
            self._esquivar(limites)

    @staticmethod
    def _dist(p, seg):
        if seg is None or seg[0] is None:
            return float("inf")
        return _len(_sub(p, punto_en_segmento(p, seg[0], seg[1])))

    def requerido(self, i, k):
        radio = self._obs[i][1]
        r0, r1 = self._extremos[i]
        a = lerp(r0, radio, suave(k / ZONA_EXTREMOS))
        b = lerp(r1, radio, suave((1 - k) / ZONA_EXTREMOS))
        return min(a, b)

    def posicion(self, k):
        return bezier3(self.desde["position"], self.c1, self.c2, self.hasta["position"], k)

    def peor(self, muestras=80):
        """(déficit, k, índice del obstáculo, punto, punto del obstáculo) del peor incumplimiento (déficit <= 0: cumple)."""
        peor = (-float("inf"), None, None, None, None)
        for j in range(1, muestras):
            k = j / muestras
            p = self.posicion(k)
            for i, (fn, _, _) in enumerate(self._obs):
                seg = fn(k)
                if seg is None or seg[0] is None:
                    continue
                q = punto_en_segmento(p, seg[0], seg[1])
                deficit = self.requerido(i, k) - _len(_sub(p, q))
                if deficit > peor[0]:
                    peor = (deficit, k, i, p, q)
        return peor

    def _esquivar(self, limites):
        for _ in range(120):
            deficit, k, i, p, q = self.peor()
            if k is None or deficit <= 0.0:
                return
            dir_ = _sub(p, q)
            if _len(dir_) < 1e-6:
                dir_ = (0.0, 1.0, 0.0)
            dir_ = _unit(_add(_unit(dir_), (0.0, 0.3, 0.0)))     # preferir pasar por encima
            w1 = 3 * k * (1 - k) ** 2
            w2 = 3 * k * k * (1 - k)
            n = w1 * w1 + w2 * w2
            if n < 1e-9:
                return
            paso = deficit + 0.01
            self.c1 = _add(self.c1, _mul(dir_, paso * w1 / n))
            self.c2 = _add(self.c2, _mul(dir_, paso * w2 / n))
            if limites:
                self.c1, self.c2 = recortar(self.c1, limites, 0.15), recortar(self.c2, limites, 0.15)

    def toma(self, k):
        if k >= 1.0:
            return copiar_toma(self.hasta)
        k = max(0.0, k)
        return {"position": self.posicion(k),
                "target": lerp3(self.desde["target"], self.hasta["target"], k),
                "fov": lerp(self.desde["fov"], self.hasta["fov"], k)}


# -- Guion ---------------------------------------------------------------------------------------------------------

class Tramo:
    def __init__(self, nombre, t0, t1, pose):
        self.nombre, self.t0, self.t1, self.pose = nombre, t0, t1, pose   # pose(u) -> dict parcial de Estado

    def u(self, t):
        if self.t1 - self.t0 <= 1e-9:
            return 1.0
        return min(1.0, max(0.0, (t - self.t0) / (self.t1 - self.t0)))


class Guion:
    """Función pura t -> Estado. `camara(t)` es una función aparte (curva continua sobre todo el total)."""

    def __init__(self, secuencia, tramos_, camara, duracion, silla_activa=True, final_exacto=None):
        self.secuencia = secuencia
        self.tramos = tramos_
        self._camara = camara
        self.duracion = duracion
        self.silla_activa = silla_activa
        self._final = final_exacto     # Estado final exacto (posición/rumbo/silla/manos/cámara)

    def tramo_en(self, t):
        for tr in self.tramos:
            if t < tr.t1:
                return tr
        return self.tramos[-1]

    def _pose(self, t):
        tr = self.tramo_en(t)
        return tr.nombre, tr.pose(tr.u(t))

    def posicion(self, t):
        _, p = self._pose(min(max(t, 0.0), self.duracion))
        return p["pos"]

    def velocidad(self, t):
        h = 1 / 120
        if t <= 0 or t >= self.duracion:
            return 0.0
        _, p = self._pose(t)
        if p.get("bajada", 0.0) > 0.01:
            return 0.0
        a = self.posicion(max(0.0, t - h))
        b = self.posicion(min(self.duracion, t + h))
        return math.hypot(b[0] - a[0], b[1] - a[1]) / (2 * h)

    def estado(self, t):
        if t >= self.duracion and self._final is not None:
            return self.final()
        t = min(max(t, 0.0), self.duracion)
        nombre, p = self._pose(t)
        x, z = p["pos"]
        return Estado(x=x, z=z, rumbo=p["rumbo"], bajada=p.get("bajada", 0.0), velocidad=self.velocidad(t),
                      pies=p.get("pies"), manos=dict(p.get("manos", {})), silla=p.get("silla"),
                      camara=self._camara(t), velo=p.get("velo", 0.0), mirar=p.get("mirar", 0.0), tramo=nombre)

    def final(self):
        e = self._final
        return Estado(x=e.x, z=e.z, rumbo=e.rumbo, bajada=e.bajada, velocidad=0.0, pies=e.pies, manos=dict(e.manos),
                      silla=e.silla, camara=copiar_toma(e.camara), velo=e.velo, mirar=e.mirar, tramo="fin")

    def cabeza(self, t, cuerpo):
        """Centro (x, y, z) aproximado de la cabeza en t."""
        nombre, p = self._pose(min(max(t, 0.0), self.duracion))
        x, z = p["pos"]
        a = adelante(p["rumbo"])
        suelo = p.get("suelo", 0.0)
        return (x + a[0] * 0.04, suelo + cuerpo.alto_cabeza - p.get("bajada", 0.0), z + a[1] * 0.04)

    def eje_cuerpo(self, t, cuerpo):
        """Segmento vertical (pies a hombros) del cuerpo en t: lo que la cámara no debe rozar a mitad de curva."""
        _, p = self._pose(min(max(t, 0.0), self.duracion))
        x, z = p["pos"]
        suelo = p.get("suelo", 0.0)
        alto = suelo + cuerpo.alto_cabeza - p.get("bajada", 0.0) - 0.15
        return ((x, suelo + 0.25, z), (x, max(suelo + 0.3, alto), z))


def _obstaculos(g, cuerpo, t_de_k, con_cuerpo=True):
    obs = {"cabeza": lambda k: g.cabeza(t_de_k(k), cuerpo), "radio_cabeza": cuerpo.radio_cabeza}
    if con_cuerpo:
        obs["cuerpo"] = lambda k: g.eje_cuerpo(t_de_k(k), cuerpo)
    return obs


def _inversa(f, k):
    """x en [0, 1] con f(x) = k (f creciente)."""
    lo, hi = 0.0, 1.0
    for _ in range(30):
        mid = (lo + hi) / 2
        if f(mid) < k:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _tramos_con_extra(secuencia, rapida, extra):
    """Tramos de la tabla con `extra` s sumados al primero (caminata por lejanía)."""
    out = []
    t = 0.0
    for i, (nombre, d) in enumerate((DURACIONES_RAPIDA if rapida else DURACIONES)[secuencia]):
        d = d + (extra if i == 0 else 0.0)
        out.append((nombre, t, t + d))
        t += d
    return out, t


def _camino_rumbo(p0, p1, u, rumbo_final, giro_desde=0.6, rumbo_inicial=None):
    """Rumbo al caminar de p0 a p1: el de la marcha y, desde `giro_desde`, girando hasta `rumbo_final`."""
    marcha = rumbo_de(p1[0] - p0[0], p1[1] - p0[1], rumbo_final)
    if rumbo_inicial is not None and u < 0.25:
        marcha = lerp_angulo(rumbo_inicial, marcha, suave(u / 0.25))
    if u <= giro_desde:
        return marcha
    return lerp_angulo(marcha, rumbo_final, suave((u - giro_desde) / (1 - giro_desde)))


def _rodear(silla, d, desde, hasta, u):
    """Camino de `desde` (junto a la silla) a `hasta` (frente al asiento) por fuera del volumen de la silla: cúbica con
    los dos puntos de control en la esquina delantera del lado `silla.lado`."""
    s = signo_lado(silla.lado)
    esquina = en_silla(silla, -d + FRENTE_SENTARSE, s * LATERAL_JUNTO)
    return bezier3(desde, esquina, esquina, hasta, u)


# -- Construcción de los guiones ----------------------------------------------------------------------------------

def _velo_glitch(u):
    return min(1.0, max(0.0, u))


def guion_sentarse(silla, mesa=None, *, desde=None, toma_final, toma_inicial=None, rapida=False, cuerpo=None,
                   limites=None, secuencia="sentarse_en", pantalla=None, aspecto=16 / 9, rol=None, toma_llena=None):
    """Guion de sentarse_en (y de entrar_a_pantalla con `secuencia="entrar_a_pantalla"` y `pantalla`).
    desde = (x, z, rumbo) del personaje al empezar (None = punto_de_partida)."""
    mesa = mesa or Mesa()
    cuerpo = cuerpo or Cuerpo()
    desde = tuple(desde) if desde is not None else punto_de_partida(silla)
    retiro = retiro_efectivo(silla, limites)
    bajada = bajada_sentado(silla)
    suelo = silla.suelo_y
    rumbo = silla.rumbo
    p_grab0 = junto_respaldo(silla, 0.0, cuerpo)
    p_grab1 = _tras_sacar(silla, p_grab0, retiro)
    p_frente = en_silla(silla, -retiro + FRENTE_SENTARSE, 0.0)
    p_sentado_r = silla_en(silla, retiro)
    pies_fijos = en_silla(silla, -retiro + AVANCE_PIES, 0.0)
    mano_r = mano_respaldo_lado(silla)
    finales = manos_mesa(silla, mesa)

    nominal = math.hypot(*_sub(p_grab0, punto_de_partida(silla)[:2]))
    real = math.hypot(*_sub(p_grab0, desde[:2]))
    extra = max(0.0, real - nominal - 0.3) / VELOCIDAD_EXTRA
    lista, total = _tramos_con_extra(secuencia, rapida, extra)
    tiempos = {n: (a, b) for n, a, b in lista}

    def silla_pos(d):
        return silla_en(silla, acotar_desplazamiento(d, retiro))

    def llegar(u):
        k = suave(u)
        pos = lerp2(desde[:2], p_grab0, k)
        manos = {}
        if u > 0.7:                       # al final la mano sube al respaldo
            w = suave((u - 0.7) / 0.3)
            reposo = mano_colgando(pos[0], pos[1], rumbo, mano_r, cuerpo, suelo)
            manos[mano_r] = lerp3(reposo, respaldo_mano(silla, 0.0), w)
        return {"pos": pos, "rumbo": _camino_rumbo(desde[:2], p_grab0, u, rumbo, 0.55, desde[2]), "manos": manos,
                "silla": silla_pos(0.0), "suelo": suelo}

    def sacar(u):
        k = sale(u)
        d = retiro * k
        return {"pos": lerp2(p_grab0, p_grab1, k), "rumbo": rumbo, "manos": {mano_r: respaldo_mano(silla, d)},
                "silla": silla_pos(d), "suelo": suelo}

    def sentarse(u):
        # 0-0,5: rodea la esquina hasta quedar de pie frente al asiento; 0,5-1: baja la pelvis y se echa atrás
        if u < 0.5:
            v = suave(u / 0.5)
            pos = _rodear(silla, retiro, p_grab1, p_frente, v)
            manos = {}
            if u < 0.12:
                manos[mano_r] = lerp3(respaldo_mano(silla, retiro),
                                      mano_colgando(pos[0], pos[1], rumbo, mano_r, cuerpo, suelo), suave(u / 0.12))
            return {"pos": pos, "rumbo": rumbo, "manos": manos, "silla": silla_pos(retiro), "suelo": suelo}
        v = (u - 0.5) / 0.5
        b = bajada * entra_suave(v)
        pos = lerp2(p_frente, p_sentado_r, suave(v))
        # los pies se plantan delante al empezar a bajar (rápido) y ya no se mueven
        bajo_pelvis = en_silla(silla, -retiro + FRENTE_SENTARSE + 0.06, 0.0)
        pies = lerp2(bajo_pelvis, pies_fijos, suave(min(1.0, v / 0.3)))
        manos = {}
        if v > 0.6:                       # las manos buscan el borde del asiento al final de la bajada
            w = suave((v - 0.6) / 0.4)
            asiento = manos_asiento(silla, retiro)
            for lado in ("i", "d"):
                manos[lado] = lerp3(mano_colgando(pos[0], pos[1], rumbo, lado, cuerpo, suelo - b), asiento[lado], w)
        return {"pos": pos, "rumbo": rumbo, "bajada": b, "pies": pies, "manos": manos, "silla": silla_pos(retiro),
                "suelo": suelo}

    def acomodar(u):
        d = retiro * (1 - suave(u))
        pos = silla_pos(d)
        pies = en_silla(silla, -d + AVANCE_PIES, 0.0)
        return {"pos": pos, "rumbo": rumbo, "bajada": bajada, "pies": pies, "manos": manos_asiento(silla, d),
                "silla": pos, "suelo": suelo}

    asiento0 = manos_asiento(silla, 0.0)

    def manos_(u):
        k = sale(u)
        manos = {}
        for lado in ("i", "d"):
            paso = sobre_canto(silla, mesa, lado)
            fin = finales.get(lado, asiento0[lado])
            if k < 0.5:
                p = lerp3(asiento0[lado], paso, suave(k / 0.5))
            else:
                w = (k - 0.5) / 0.5
                p = lerp3(paso, fin, w)
                p = (p[0], p[1] + SUBIDA_MANOS * 4 * w * (1 - w) * 0.5, p[2])
            manos[lado] = acotar_mano_mesa(silla, mesa, p)
        return {"pos": tuple(silla.posicion), "rumbo": rumbo, "bajada": bajada,
                "pies": en_silla(silla, AVANCE_PIES, 0.0), "manos": manos, "silla": tuple(silla.posicion),
                "suelo": suelo}

    def sentado_quieto(u):
        return manos_(1.0)

    poses = {"llegar": llegar, "sacar": sacar, "sentarse": sentarse, "acomodar": acomodar, "manos": manos_,
             "entrar": sentado_quieto, "glitch": sentado_quieto}
    lista_tramos = [Tramo(n, a, b, poses[n]) for n, a, b in lista]

    final_pose = manos_(1.0)
    manos_finales = {lado: finales.get(lado) for lado in ("i", "d")}
    final = Estado(x=float(silla.posicion[0]), z=float(silla.posicion[1]), rumbo=rumbo, bajada=bajada,
                   pies=final_pose["pies"], manos=manos_finales, silla=tuple(silla.posicion))

    provisional = Guion(secuencia, lista_tramos, lambda t: None, total)

    if secuencia == "entrar_a_pantalla":
        hombro = toma_hombro_pantalla(pantalla, aspecto, rol)
        llena = copiar_toma(toma_llena) if toma_llena is not None else             toma_pantalla_llena(pantalla, aspecto, cabeza=provisional.cabeza(total, cuerpo))
        t_fin_cam = tiempos["glitch"][0]
        t_hombro = tiempos["entrar"][0]
        inicio = _toma_de_inicio(toma_inicial, hombro, limites, silla, desde, retiro)
        curva_a = CurvaCamara(inicio, hombro, limites=limites, llegada="eje",
                              **_obstaculos(provisional, cuerpo, lambda k: _inversa(_tiempo_continuo, k) * t_hombro))
        curva_b = CurvaCamara(hombro, llena, **_obstaculos(
            provisional, cuerpo, lambda k: t_hombro + _inversa(_entrada_pantalla, k) * (t_fin_cam - t_hombro), False))
        ka = t_hombro / t_fin_cam

        def camara(t):
            if t >= t_fin_cam:
                return copiar_toma(llena)
            k = t / t_fin_cam
            if k < ka:
                return curva_a.toma(_tiempo_continuo(k / ka))
            return curva_b.toma(_entrada_pantalla((k - ka) / (1 - ka)))

        def glitch(u):
            p = sentado_quieto(1.0)
            p["velo"] = _velo_glitch(u)
            return p
        lista_tramos[-1] = Tramo("glitch", tiempos["glitch"][0], tiempos["glitch"][1], glitch)
        final.camara = copiar_toma(llena)
        final.velo = 1.0
    else:
        inicio = _toma_de_inicio(toma_inicial, toma_final, limites, silla, desde, retiro)
        curva = CurvaCamara(inicio, toma_final, limites=limites, llegada="eje",
                            **_obstaculos(provisional, cuerpo, lambda k: _inversa(acercamiento, k) * total))

        def camara(t):
            if t >= total:
                return copiar_toma(toma_final)
            return curva.toma(acercamiento(t / total))
        final.camara = copiar_toma(toma_final)

    g = Guion(secuencia, lista_tramos, camara, total, final_exacto=final)
    g.retiro = retiro
    g.cuerpo = cuerpo
    g.extra = extra
    g.silla_desc = silla
    g.mesa_desc = mesa
    return g


def _tiempo_continuo(k):
    """Primer tramo de la cámara de la pantalla: arranca suave y llega con velocidad (sin pausa sobre el hombro)."""
    k = min(1.0, max(0.0, k))
    return k * k * (2 - k)


def _entrada_pantalla(k):
    """Segundo tramo: sale con la velocidad con la que llegó y frena al llenar la pantalla."""
    k = min(1.0, max(0.0, k))
    return sale(k)


def _t_de_k_suave(k, total):
    """Inversa aproximada de suave(t/total) para muestrear la cabeza en el tiempo que corresponde a k."""
    lo, hi = 0.0, 1.0
    for _ in range(30):
        mid = (lo + hi) / 2
        if suave(mid) < k:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2 * total


def _toma_de_inicio(toma_inicial, toma_final, limites, silla=None, desde=None, retiro=0.45):
    if isinstance(toma_inicial, dict):
        return copiar_toma(toma_inicial)
    if silla is not None:
        return toma_establecimiento_silla(silla, desde, retiro, limites)
    return toma_establecimiento(toma_final, limites=limites)


DISTANCIA_ABIERTA = 3.0              # m de la toma abierta (establecimiento de la silla / salida) a lo que encuadra
FOV_ABIERTA = 60.0


def _toma_abierta_en(silla, centro_xz, limites):
    """Toma abierta de tres cuartos por detrás de la silla, del lado CONTRARIO a `silla.lado` (el personaje llega y se va
    por `silla.lado`: se le ve entero al otro lado de la silla), mirando a `centro_xz` a 0,85 m del suelo."""
    a, d = adelante(silla.rumbo), derecha(silla.rumbo)
    s = -signo_lado(silla.lado)
    eje = _unit((-a[0] * 0.8 + d[0] * s * 0.5, 0.45, -a[1] * 0.8 + d[1] * s * 0.5))
    c = (centro_xz[0], silla.suelo_y + 0.85, centro_xz[1])
    p = recortar(_add(c, _mul(eje, DISTANCIA_ABIERTA)), limites)
    return toma(p, c, FOV_ABIERTA)


def toma_establecimiento_silla(silla, desde=None, retiro=0.45, limites=None):
    """Toma de partida por defecto de sentarse_en / entrar_a_pantalla: abierta, encuadra la silla (retirada) y el punto
    de partida del personaje. (El guion pedía la toma final retrocedida 1,6 m por su eje; en ventana eso deja al personaje
    fuera de cuadro y la cámara le pasa rozando la espalda: ver informe-silla-nucleo.md.)"""
    desde = desde if desde is not None else punto_de_partida(silla)
    c = lerp2(silla_en(silla, retiro * 0.5), desde[:2], 0.5)
    return _toma_abierta_en(silla, c, limites)


def toma_abierta_silla(silla, destino, limites=None):
    """Toma abierta por defecto de levantarse_de: encuadra la silla y el punto donde queda el personaje."""
    return _toma_abierta_en(silla, lerp2(tuple(silla.posicion), destino, 0.5), limites)


def guion_levantarse(silla, mesa=None, *, desde_camara, toma_final=None, hacia=None, rapida=False, cuerpo=None,
                     limites=None):
    """Guion de levantarse_de: retirar, levantarse, empujar, apartarse."""
    mesa = mesa or Mesa()
    cuerpo = cuerpo or Cuerpo()
    retiro = retiro_efectivo(silla, limites)
    bajada = bajada_sentado(silla)
    suelo = silla.suelo_y
    rumbo = silla.rumbo
    s = signo_lado(silla.lado)
    p_frente = en_silla(silla, -retiro + FRENTE_SENTARSE, 0.0)
    p_grab0 = junto_respaldo(silla, 0.0, cuerpo)
    p_grab1 = _tras_sacar(silla, p_grab0, retiro)
    destino = tuple(hacia) if hacia is not None else en_silla(silla, -0.65, s * 0.62)
    rumbo_fin = rumbo if hacia is None else rumbo_de(destino[0] - p_grab0[0], destino[1] - p_grab0[1], rumbo)
    mano_r = mano_respaldo_lado(silla)
    inicio_manos = manos_mesa(silla, mesa)
    lista, total = _tramos_con_extra("levantarse_de", rapida, 0.0)
    extra_camino = max(0.0, math.hypot(destino[0] - p_grab0[0], destino[1] - p_grab0[1]) - 1.0) / VELOCIDAD_EXTRA
    if extra_camino > 0:
        n, a, b = lista[-1]
        lista[-1] = (n, a, b + extra_camino)
        total += extra_camino

    def silla_pos(d):
        return silla_en(silla, acotar_desplazamiento(d, retiro))

    def retirar(u):
        k = suave(u)
        d = retiro * k
        asiento = manos_asiento(silla, d)
        manos = {}
        for lado in ("i", "d"):
            if u < 0.4:                  # de la mesa al borde del asiento (por encima del canto)
                w = suave(u / 0.4)
                paso = sobre_canto(silla, mesa, lado)
                ini = inicio_manos.get(lado, asiento[lado])
                p = lerp3(ini, paso, min(1.0, w * 2)) if w < 0.5 else lerp3(paso, asiento[lado], (w - 0.5) * 2)
                manos[lado] = acotar_mano_mesa(silla, mesa, p)
            else:
                manos[lado] = asiento[lado]
        return {"pos": silla_pos(d), "rumbo": rumbo, "bajada": bajada, "pies": en_silla(silla, -d + AVANCE_PIES, 0.0),
                "manos": manos, "silla": silla_pos(d), "suelo": suelo}

    pies_fijos = en_silla(silla, -retiro + AVANCE_PIES, 0.0)
    bajo_pelvis = en_silla(silla, -retiro + FRENTE_SENTARSE + 0.06, 0.0)

    def levantarse(u):
        if u < 0.55:                     # se impulsa hacia delante y sube
            v = u / 0.55
            b = bajada * (1 - suave(v))
            pos = lerp2(silla_pos(retiro), p_frente, suave(v))
            pies = lerp2(pies_fijos, bajo_pelvis, suave(max(0.0, (v - 0.7) / 0.3)))
            manos = {}
            if v < 0.5:
                manos = {lado: p for lado, p in manos_asiento(silla, retiro).items()}
            return {"pos": pos, "rumbo": rumbo, "bajada": b, "pies": pies if b > 0.01 else None, "manos": manos,
                    "silla": silla_pos(retiro), "suelo": suelo}
        v = suave((u - 0.55) / 0.45)
        pos = _rodear(silla, retiro, p_grab1, p_frente, 1 - v)
        manos = {}
        if v > 0.75:
            w = suave((v - 0.75) / 0.25)
            manos[mano_r] = lerp3(mano_colgando(pos[0], pos[1], rumbo, mano_r, cuerpo, suelo),
                                  respaldo_mano(silla, retiro), w)
        return {"pos": pos, "rumbo": rumbo, "manos": manos, "silla": silla_pos(retiro), "suelo": suelo}

    def empujar(u):
        k = suave(u)
        d = retiro * (1 - k)
        return {"pos": lerp2(p_grab1, p_grab0, k), "rumbo": rumbo, "manos": {mano_r: respaldo_mano(silla, d)},
                "silla": silla_pos(d), "suelo": suelo}

    def apartarse(u):
        k = suave(u)
        pos = lerp2(p_grab0, destino, k)
        manos = {}
        if u < 0.35:
            manos[mano_r] = lerp3(respaldo_mano(silla, 0.0), mano_colgando(pos[0], pos[1], rumbo, mano_r, cuerpo, suelo),
                                  suave(u / 0.35))
        return {"pos": pos, "rumbo": lerp_angulo(rumbo, rumbo_fin, k), "manos": manos, "silla": silla_pos(0.0),
                "suelo": suelo}

    poses = {"retirar": retirar, "levantarse": levantarse, "empujar": empujar, "apartarse": apartarse}
    lista_tramos = [Tramo(n, a, b, poses[n]) for n, a, b in lista]
    provisional = Guion("levantarse_de", lista_tramos, lambda t: None, total)
    if toma_final is None:
        toma_final = toma_abierta_silla(silla, destino, limites)
    curva = CurvaCamara(desde_camara, toma_final, limites=limites,
                        **_obstaculos(provisional, cuerpo, lambda k: _inversa(alejamiento, k) * total))

    def camara(t):
        if t >= total:
            return copiar_toma(toma_final)
        return curva.toma(alejamiento(t / total))

    final = Estado(x=float(destino[0]), z=float(destino[1]), rumbo=rumbo_fin, manos={"i": None, "d": None},
                   silla=tuple(silla.posicion), camara=copiar_toma(toma_final))
    g = Guion("levantarse_de", lista_tramos, camara, total, final_exacto=final)
    g.retiro, g.cuerpo, g.extra, g.silla_desc, g.mesa_desc = retiro, cuerpo, 0.0, silla, mesa
    g.toma_final = toma_final
    return g


def toma_abierta(desde, cabeza_fin=None, limites=None, retroceso=0.8, subida=0.25, fov_extra=6.0):
    """Toma que retrocede desde `desde` (la cámara de juego) a una más abierta; si queda cerca de la cabeza final, sube y
    retrocede más."""
    t = toma_establecimiento(desde, retroceso, subida, fov_extra, limites=limites)
    if cabeza_fin is not None:
        c = cabeza_fin()
        for _ in range(20):
            if _len(_sub(t["position"], c)) >= DISTANCIA_CABEZA + MARGEN_CABEZA:
                break
            retroceso += 0.15
            subida += 0.05
            t = toma_establecimiento(desde, retroceso, subida, fov_extra, limites=limites)
    return t


# -- Corcho ----------------------------------------------------------------------------------------------------------

def _corcho_ejes(corcho):
    n = _unit((float(corcho.normal[0]), 0.0, float(corcho.normal[2])), (0.0, 0.0, -1.0))
    rumbo_c = rumbo_de(-n[0], -n[2])          # mirando al corcho
    return n, rumbo_c


def pie_corcho(corcho):
    if corcho.pie is not None:
        return (float(corcho.pie[0]), float(corcho.pie[1]))
    n, rumbo_c = _corcho_ejes(corcho)
    d = derecha(rumbo_c)
    return (corcho.centro[0] + n[0] * 0.62 - d[0] * 0.18, corcho.centro[2] + n[2] * 0.62 - d[1] * 0.18)


def nota_corcho(corcho):
    p = corcho.nota if corcho.nota is not None else corcho.centro
    n = _unit(tuple(float(c) for c in corcho.normal), (0.0, 0.0, -1.0))
    return tuple(float(p[i]) + n[i] * 0.03 for i in range(3))    # 3 cm delante del plano: lo toca sin atravesarlo


def no_atravesar(p, punto_plano, normal, margen=0.02):
    n = _unit(tuple(normal), (0.0, 0.0, 1.0))
    d = _dot(_sub(p, punto_plano), n)
    if d >= margen:
        return tuple(p)
    return _add(p, _mul(n, margen - d))


def punto_de_partida_corcho(corcho):
    """(x, z, rumbo) 2,2 m delante del corcho, mirándolo."""
    n, rumbo_c = _corcho_ejes(corcho)
    d = derecha(rumbo_c)
    return (corcho.centro[0] + n[0] * 2.2 - d[0] * 0.18, corcho.centro[2] + n[2] * 2.2 - d[1] * 0.18, rumbo_c)


def guion_corcho(corcho, *, desde, toma_final, toma_inicial=None, rapida=False, cuerpo=None, limites=None, suelo_y=0.0):
    cuerpo = cuerpo or Cuerpo()
    n, rumbo_c = _corcho_ejes(corcho)
    pie = pie_corcho(corcho)
    nota = nota_corcho(corcho)
    nominal = 2.2 - 0.62
    real = math.hypot(pie[0] - desde[0], pie[1] - desde[1])
    extra = max(0.0, real - nominal - 0.3) / VELOCIDAD_EXTRA
    lista, total = _tramos_con_extra("acercarse_a_corcho", rapida, extra)

    def caminar(u):
        pos = lerp2(desde[:2], pie, suave(u))
        return {"pos": pos, "rumbo": _camino_rumbo(desde[:2], pie, u, rumbo_c, 0.8, desde[2]), "manos": {},
                "suelo": suelo_y}

    def mirar(u):
        r0 = _camino_rumbo(desde[:2], pie, 1.0, rumbo_c, 0.8, desde[2]) if real > 1e-3 else desde[2]
        return {"pos": pie, "rumbo": lerp_angulo(r0, rumbo_c, suave(u)), "mirar": 6.0 * suave(u), "manos": {},
                "suelo": suelo_y}

    def mano(u):
        reposo = mano_colgando(pie[0], pie[1], rumbo_c, "d", cuerpo, suelo_y)
        k = suave(u)
        p = lerp3(reposo, nota, k)
        p = (p[0], p[1] + 0.05 * 4 * k * (1 - k), p[2])
        p = no_atravesar(p, corcho.centro, n, 0.02)
        return {"pos": pie, "rumbo": rumbo_c, "mirar": 6.0, "manos": {"d": p}, "suelo": suelo_y}

    poses = {"caminar": caminar, "mirar": mirar, "mano": mano}
    lista_tramos = [Tramo(nm, a, b, poses[nm]) for nm, a, b in lista]
    provisional = Guion("acercarse_a_corcho", lista_tramos, lambda t: None, total)
    if toma_inicial is None or toma_inicial == "establecimiento":
        inicio = toma_establecimiento_corcho(toma_final, pie, limites)
    else:
        inicio = copiar_toma(toma_inicial)
    curva = CurvaCamara(inicio, toma_final, limites=limites, llegada="eje",
                        **_obstaculos(provisional, cuerpo, lambda k: _inversa(acercamiento, k) * total))

    def camara(t):
        if t >= total:
            return copiar_toma(toma_final)
        return curva.toma(acercamiento(t / total))

    final = Estado(x=pie[0], z=pie[1], rumbo=rumbo_c, manos={"d": nota, "i": None}, mirar=6.0,
                   camara=copiar_toma(toma_final))
    g = Guion("acercarse_a_corcho", lista_tramos, camara, total, final_exacto=final)
    g.cuerpo, g.extra = cuerpo, extra
    return g


def toma_establecimiento_corcho(toma_final, pie, limites=None):
    """toma_final retrocedida 1,4 m y 0,25 m al costado contrario al personaje, +8° de fov."""
    e = eje_toma(toma_final)
    der = _unit((e[2], 0.0, -e[0]), (1.0, 0.0, 0.0))
    rel = (pie[0] - toma_final["position"][0], 0.0, pie[1] - toma_final["position"][2])
    lado = -1.0 if _dot(rel, der) > 0 else 1.0
    return toma_establecimiento(toma_final, 1.4, 0.0, 8.0, lateral=0.25 * lado, limites=limites)


def guion_dejar_corcho(corcho, *, desde, desde_camara, toma_final=None, hacia=None, rapida=False, cuerpo=None,
                       limites=None, suelo_y=0.0):
    cuerpo = cuerpo or Cuerpo()
    n, rumbo_c = _corcho_ejes(corcho)
    inicio = (float(desde[0]), float(desde[1]))
    rumbo0 = float(desde[2])
    nota = nota_corcho(corcho)
    destino = tuple(hacia) if hacia is not None else (inicio[0] + n[0] * 0.9, inicio[1] + n[2] * 0.9)
    lejos = math.hypot(destino[0] - inicio[0], destino[1] - inicio[1])
    rumbo_fin = rumbo0 if hacia is None or lejos < 1.0 else rumbo_de(destino[0] - inicio[0], destino[1] - inicio[1])
    lista, total = _tramos_con_extra("dejar_corcho", rapida, 0.0)
    extra = max(0.0, lejos - 1.0) / VELOCIDAD_EXTRA
    if extra > 0:
        nm, a, b = lista[-1]
        lista[-1] = (nm, a, b + extra)
        total += extra

    def bajar(u):
        reposo = mano_colgando(inicio[0], inicio[1], rumbo0, "d", cuerpo, suelo_y)
        p = no_atravesar(lerp3(nota, reposo, suave(u)), corcho.centro, n, 0.02)
        return {"pos": inicio, "rumbo": rumbo0, "manos": {"d": p} if u < 1.0 else {}, "mirar": 6.0 * (1 - suave(u)),
                "suelo": suelo_y}

    def apartarse(u):
        k = suave(u)
        return {"pos": lerp2(inicio, destino, k), "rumbo": lerp_angulo(rumbo0, rumbo_fin, k), "manos": {},
                "suelo": suelo_y}

    poses = {"bajar_mano": bajar, "apartarse": apartarse}
    lista_tramos = [Tramo(nm, a, b, poses[nm]) for nm, a, b in lista]
    provisional = Guion("dejar_corcho", lista_tramos, lambda t: None, total)
    if toma_final is None:
        toma_final = toma_abierta(desde_camara, lambda: provisional.cabeza(total, cuerpo), limites, 0.8, 0.1, 4.0)
    curva = CurvaCamara(desde_camara, toma_final, limites=limites,
                        **_obstaculos(provisional, cuerpo, lambda k: _t_de_k_suave(k, total)))

    def camara(t):
        if t >= total:
            return copiar_toma(toma_final)
        return curva.toma(suave(t / total))

    final = Estado(x=destino[0], z=destino[1], rumbo=rumbo_fin, manos={"d": None, "i": None},
                   camara=copiar_toma(toma_final))
    g = Guion("dejar_corcho", lista_tramos, camara, total, final_exacto=final)
    g.cuerpo, g.extra = cuerpo, extra
    g.toma_final = toma_final
    return g


def estado_sentado(silla, mesa=None):
    """Estado sentado y acomodado (sin cámara): el final de sentarse_en."""
    mesa = mesa or Mesa()
    finales = manos_mesa(silla, mesa)
    return Estado(x=float(silla.posicion[0]), z=float(silla.posicion[1]), rumbo=silla.rumbo, bajada=bajada_sentado(silla),
                  pies=en_silla(silla, AVANCE_PIES, 0.0), manos={lado: finales.get(lado) for lado in ("i", "d")},
                  silla=tuple(silla.posicion))


def guion_salir_pantalla(silla, mesa, pantalla, *, toma_final, rapida=False, cuerpo=None, aspecto=16 / 9,
                         toma_llena=None, limites=None):
    """La cámara sale de la pantalla (glitch inverso) a toma_final; el personaje sentado con las manos en la mesa."""
    mesa = mesa or Mesa()
    cuerpo = cuerpo or Cuerpo()
    quieto = estado_sentado(silla, mesa)
    a = adelante(silla.rumbo)
    cabeza = (quieto.x + a[0] * 0.04, silla.suelo_y + cuerpo.alto_cabeza - quieto.bajada, quieto.z + a[1] * 0.04)
    llena = copiar_toma(toma_llena) if toma_llena is not None else toma_pantalla_llena(pantalla, aspecto, cabeza=cabeza)
    lista, total = _tramos_con_extra("salir_de_pantalla", rapida, 0.0)

    def salir(u):
        return {"pos": (quieto.x, quieto.z), "rumbo": quieto.rumbo, "bajada": quieto.bajada, "pies": quieto.pies,
                "manos": dict(quieto.manos), "silla": quieto.silla, "velo": max(0.0, 1.0 - u / 0.3),
                "suelo": silla.suelo_y}

    lista_tramos = [Tramo(nm, a, b, salir) for nm, a, b in lista]
    provisional = Guion("salir_de_pantalla", lista_tramos, lambda t: None, total)
    curva = CurvaCamara(llena, toma_final, limites=limites,
                        **_obstaculos(provisional, cuerpo, lambda k: _t_de_k_suave(k, total), False))

    def camara(t):
        if t >= total:
            return copiar_toma(toma_final)
        return curva.toma(suave(t / total))

    final = Estado(x=quieto.x, z=quieto.z, rumbo=quieto.rumbo, bajada=quieto.bajada, pies=quieto.pies,
                   manos=dict(quieto.manos), silla=quieto.silla, camara=copiar_toma(toma_final))
    g = Guion("salir_de_pantalla", lista_tramos, camara, total, final_exacto=final)
    g.cuerpo, g.extra, g.silla_desc, g.mesa_desc = cuerpo, 0.0, silla, mesa
    g.toma_llena = llena
    return g
