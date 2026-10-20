# Cálculos puros (sin ursina) de los detalles de los techos de la favela: qué casas llevan antena,
# qué pares de casas tienen un tendedero entre ellas y dónde cuelga cada prenda. Lo dibuja
# frontend/detalles_techos.py; aquí solo hay geometría y azar fijo, así que se prueba sin ventana.
#
# Convenciones: `casas` son CasaDecorativa (cx, cz, ancho, fondo, alto_total). `apoyos` es una lista
# alineada con `casas` de (bajo, alto): el mínimo y el máximo del suelo bajo la huella de cada una.
# La planta baja se apoya en `alto`, así que todo se mide desde ahí. El azar sale de azar_de.

import math
from dataclasses import dataclass

from frontend.azar_fijo import azar_de

PROPORCION_ANTENAS = 0.20       # fracción de casas con antena
SEPARACION_MIN = 1.2            # m mínimos entre las cajas de dos casas con tendedero
SEPARACION_MAX = 4.0            # m máximos
DIFERENCIA_APOYO_MAX = 1.5      # m máximos entre los apoyos (alto) de las dos casas
PROPORCION_TENDEDEROS = 0.30    # fracción de los pares candidatos que se eligen
MAXIMO_TENDEDEROS = 40
SOLAPE_MIN = 1.0                # m mínimos que las dos caras enfrentadas se miran de frente
ALTURA_CUERDA = 2.6             # m sobre el apoyo (alto) del punto MÁS BAJO de la cuerda
SEPARACION_PRENDAS = 0.5        # m entre prendas
ALTO_PRENDA = 0.45              # m (el mismo que usa detalles_techos)
MARGEN_PROHIBIDO = 0.3          # m extra de separación con calles, accesos, escaleras y otras casas
COLORES_PRENDAS = (
    (230, 60, 70), (250, 200, 40), (60, 140, 235), (70, 190, 110),
    (240, 120, 40), (190, 90, 220), (245, 245, 245), (40, 200, 200),
)


@dataclass(frozen=True)
class Tendedero:
    """Cuerda de (ax, az) a (bx, bz), atada a `y` m en los dos extremos y con una comba de `caida` m."""

    ax: float
    az: float
    bx: float
    bz: float
    y: float
    caida: float

    # Largo en planta (m) de la cuerda recta entre sus extremos, sin contar la comba.
    @property
    def largo(self):
        return math.hypot(self.bx - self.ax, self.bz - self.az)

    # Punto de la cuerda en t en [0, 1]: parábola que cuelga `caida` m en el medio.
    def punto(self, t):
        return (self.ax + (self.bx - self.ax) * t,
                self.y - self.caida * 4 * t * (1 - t),
                self.az + (self.bz - self.az) * t)


@dataclass(frozen=True)
class Prenda:
    """Una prenda: centro (x, y, z), giro `rumbo` (rotation_y, su ancho va a lo largo de la cuerda)
    y color."""

    x: float
    y: float
    z: float
    rumbo: float
    color: tuple


# Índices (de `casas`) de las casas con antena: ~20 %, elegidas por su posición.
def indices_con_antena(casas):
    return [i for i, c in enumerate(casas) if azar_de(c.cz * 1.7, c.cx) < PROPORCION_ANTENAS]


# Las casas con antena (mismo criterio que indices_con_antena).
def casas_con_antena(casas):
    return [casas[i] for i in indices_con_antena(casas)]


# Esquina del techo (signo en x) donde va el tanque de agua; la antena y lo demás van en la opuesta.
def esquina_del_tanque(casa):
    return 1 if azar_de(casa.cz, casa.cx) < 0.5 else -1


# (x, z) de la antena sobre el techo: esquina opuesta a la del tanque (-esquina * ancho/4, -fondo/4).
def posicion_antena(casa):
    return (casa.cx - esquina_del_tanque(casa) * casa.ancho / 4, casa.cz - casa.fondo / 4)


# Franjas prohibidas para los tendederos, sacadas de un MundoCiudad por duck typing: calles (asfalto
# más aceras), accesos (de la plaza a la entrada de cada edificio) y escaleras. Cada franja es
# (ax, az, bx, bz, ancho). Es el snippet de integración: tendederos(..., prohibidos=franjas_prohibidas(mundo)).
def franjas_prohibidas(mundo, ancho_acera=2.0, ancho_acceso=2.0):
    franjas = []
    for a, b in mundo.segmentos():
        (ax, az), (bx, bz) = mundo.coordenada(a), mundo.coordenada(b)
        franjas.append((ax, az, bx, bz, mundo.ancho_calle + 2 * ancho_acera))
    for e in mundo.edificios():
        px, pz = mundo.coordenada(e.lugar)
        ex, ez = e.punto_entrada()
        franjas.append((px, pz, ex, ez, ancho_acceso))
    for esc in mundo.escaleras():
        franjas.append((esc.ax, esc.az, esc.bx, esc.bz, esc.ancho))
    return franjas


# Tendederos entre pares de casas: cajas enfrentadas con 1,2 a 4 m de callejón, apoyos (alto) que
# difieren menos de 1,5 m y que se miran de frente al menos 1 m. De los candidatos se elige ~30 %
# con azar_de y se conservan como mucho `maximo` (los de menor valor de azar). La cuerda sale de la
# cara de cada casa a la altura del punto más bajo de la comba = ALTURA_CUERDA sobre el apoyo más
# alto, o sobre el suelo más alto bajo la cuerda si se da `suelo`. Se descartan los que cruzan una
# franja de `prohibidos` (calle, acceso o escalera) o atraviesan otra casa.
def tendederos(casas, apoyos, maximo=MAXIMO_TENDEDEROS, prohibidos=(), suelo=None):
    candidatos = []
    for i in range(len(casas)):
        for j in range(i + 1, len(casas)):
            par = _par_enfrentado(casas[i], casas[j])
            if par is None:
                continue
            (ax, az), (bx, bz) = par
            if abs(apoyos[i][1] - apoyos[j][1]) >= DIFERENCIA_APOYO_MAX:
                continue
            azar = azar_de(casas[i].cx * 1.3 + casas[j].cz * 0.37, casas[i].cz * 1.9 + casas[j].cx * 0.53)
            if azar >= PROPORCION_TENDEDEROS:
                continue
            if _cruza_algo(ax, az, bx, bz, prohibidos, casas, (i, j)):
                continue
            referencia = max(apoyos[i][1], apoyos[j][1])
            if suelo is not None:
                n = max(1, math.ceil(math.hypot(bx - ax, bz - az) / 0.25))
                referencia = max(referencia, *(suelo(ax + (bx - ax) * k / n, az + (bz - az) * k / n)
                                               for k in range(n + 1)))
            largo = math.hypot(bx - ax, bz - az)
            caida = 0.25 + 0.04 * largo
            candidatos.append((azar, Tendedero(ax, az, bx, bz, referencia + ALTURA_CUERDA + caida, caida)))
    candidatos.sort(key=lambda c: c[0])
    return [t for _, t in candidatos[:maximo]]


# Prendas cada ~0,5 m sobre la comba, colgadas de la cuerda (su borde superior toca el cable). El
# último punto de cada cuerda queda a medio paso del extremo. El borde inferior queda a
# ALTURA_CUERDA - ALTO_PRENDA = 2,15 m sobre el apoyo, que supera los 2,1 m.
def prendas(tendedero):
    n = max(1, round(tendedero.largo / SEPARACION_PRENDAS))
    rumbo = math.degrees(math.atan2(tendedero.bx - tendedero.ax, tendedero.bz - tendedero.az)) + 90
    resultado = []
    for k in range(n):
        x, y, z = tendedero.punto((k + 0.5) / n)
        indice = int(azar_de(x * 2.1 + k, z * 1.3) * len(COLORES_PRENDAS)) % len(COLORES_PRENDAS)
        resultado.append(Prenda(x, y - ALTO_PRENDA / 2, z, rumbo, COLORES_PRENDAS[indice]))
    return resultado


# Segmentos (pares de vértices) de la cuerda, de 10 tramos, para sumar a la malla de líneas de los cables.
def vertices_cuerda(tendedero, tramos=10):
    puntos = [tendedero.punto(k / tramos) for k in range(tramos + 1)]
    vertices = []
    for a, b in zip(puntos, puntos[1:]):
        vertices += [a, b]
    return vertices


# -- Geometría auxiliar ------------------------------------------------------------------------------


# Si las cajas de a y b están enfrentadas con el callejón pedido, ((ax, az), (bx, bz)) son los
# extremos de la cuerda en las caras que se miran, a mitad del tramo que comparten; si no, None.
def _par_enfrentado(a, b):
    huecos = (abs(a.cx - b.cx) - (a.ancho + b.ancho) / 2, abs(a.cz - b.cz) - (a.fondo + b.fondo) / 2)
    solapes = (min(a.cz + a.fondo / 2, b.cz + b.fondo / 2) - max(a.cz - a.fondo / 2, b.cz - b.fondo / 2),
               min(a.cx + a.ancho / 2, b.cx + b.ancho / 2) - max(a.cx - a.ancho / 2, b.cx - b.ancho / 2))
    if SEPARACION_MIN <= huecos[0] <= SEPARACION_MAX and solapes[0] >= SOLAPE_MIN:
        z = (min(a.cz + a.fondo / 2, b.cz + b.fondo / 2) + max(a.cz - a.fondo / 2, b.cz - b.fondo / 2)) / 2
        signo = 1 if b.cx > a.cx else -1
        return (a.cx + signo * a.ancho / 2, z), (b.cx - signo * b.ancho / 2, z)
    if SEPARACION_MIN <= huecos[1] <= SEPARACION_MAX and solapes[1] >= SOLAPE_MIN:
        x = (min(a.cx + a.ancho / 2, b.cx + b.ancho / 2) + max(a.cx - a.ancho / 2, b.cx - b.ancho / 2)) / 2
        signo = 1 if b.cz > a.cz else -1
        return (x, a.cz + signo * a.fondo / 2), (x, b.cz - signo * b.fondo / 2)
    return None


# ¿La cuerda a-b cruza una franja prohibida o la caja de una casa que no sea de sus extremos?
def _cruza_algo(ax, az, bx, bz, prohibidos, casas, propias):
    for fx, fz, gx, gz, ancho in prohibidos:
        if _distancia_segmentos((ax, az), (bx, bz), (fx, fz), (gx, gz)) < ancho / 2 + MARGEN_PROHIBIDO:
            return True
    for k, c in enumerate(casas):
        if k in propias:
            continue
        caja = (c.cx - c.ancho / 2, c.cx + c.ancho / 2, c.cz - c.fondo / 2, c.cz + c.fondo / 2)
        if _segmento_toca_caja((ax, az), (bx, bz), caja):
            return True
    return False


# ¿El segmento a-b toca la caja (xmin, xmax, zmin, zmax)? Recorte de Liang-Barsky.
def _segmento_toca_caja(a, b, caja):
    xmin, xmax, zmin, zmax = caja
    t0, t1 = 0.0, 1.0
    dx, dz = b[0] - a[0], b[1] - a[1]
    for p, q in ((-dx, a[0] - xmin), (dx, xmax - a[0]), (-dz, a[1] - zmin), (dz, zmax - a[1])):
        if p == 0:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True


# Distancia mínima entre dos segmentos del plano (0 si se cortan).
def _distancia_segmentos(a, b, c, d):
    if _se_cortan(a, b, c, d):
        return 0.0
    return min(_distancia_punto_segmento(a, c, d), _distancia_punto_segmento(b, c, d),
               _distancia_punto_segmento(c, a, b), _distancia_punto_segmento(d, a, b))


# ¿Los segmentos a-b y c-d se cruzan de verdad (en un punto interior)? Con el signo del giro
# (producto cruzado 2D): cada segmento debe dejar los extremos del otro a lados opuestos. Si solo se
# tocan o son colineales devuelve False; _distancia_segmentos lo cubre con la distancia punto-segmento.
def _se_cortan(a, b, c, d):
    def giro(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return giro(a, b, c) * giro(a, b, d) < 0 and giro(c, d, a) * giro(c, d, b) < 0


# Distancia (m) del punto p al segmento a-b: se proyecta p sobre la recta y se recorta t a [0, 1]
# para quedarse con el extremo más cercano; si a == b (largo 0) es la distancia al punto.
def _distancia_punto_segmento(p, a, b):
    dx, dz = b[0] - a[0], b[1] - a[1]
    largo2 = dx * dx + dz * dz
    t = 0.0 if largo2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / largo2))
    return math.hypot(p[0] - (a[0] + dx * t), p[1] - (a[1] + dz * t))
