# Matemática PURA (sin Ursina/Panda3D) del aspecto cyber/neón del parkour: estilos por tipo de plataforma (color + patrón,
# para no depender solo del color), geometría de las cajas con franja de borde, domo de cielo, torres de servidores,
# rejillas en profundidad, anillos/tubos de efectos y el FOV extra. La vista (parkour_vista/decoracion/efectos) solo
# convierte estas listas en mallas. Todo color es RGB 0-255; toda malla es (vertices, colores, triangulos).
#
# ALCALDE_PARKOUR_VISUAL=0 (o no/false/off) devuelve el aspecto anterior.

import math
import os
import random

ENTORNO_VISUAL = "ALCALDE_PARKOUR_VISUAL"
BORDE = 0.24                  # m de la franja brillante de aterrizaje en el borde de cada plataforma
FRANJA_LATERAL = 0.10         # m de la franja de neón en el canto superior de las paredes


def visual_activo(entorno=None):
    entorno = os.environ if entorno is None else entorno
    return str(entorno.get(ENTORNO_VISUAL, "1")).strip().lower() not in ("0", "no", "false", "off")


# -- Estilos por tipo --
# panel = relleno oscuro; tenue = segunda tonalidad del relleno; acento = color del patrón; borde = franja de aterrizaje.
# Tipos distinguibles por patrón (liso con baldosas / franjas / ajedrez fino / puntos / cuadros concéntricos / ajedrez
# grande) y por luminancia/tono, no solo rojo-verde.
ESTILOS = {
    "fija": {"panel": (12, 34, 66), "tenue": (18, 50, 92), "acento": (70, 230, 255), "borde": (110, 240, 255),
             "patron": "baldosas", "nombre": "Fija"},
    "movil": {"panel": (40, 30, 4), "tenue": (40, 30, 4), "acento": (255, 190, 30), "borde": (255, 215, 70),
              "patron": "franjas", "nombre": "Móvil"},
    "desaparece": {"panel": (34, 12, 66), "tenue": (34, 12, 66), "acento": (190, 130, 255), "borde": (225, 190, 255),
                   "patron": "ajedrez", "nombre": "Se desvanece"},
    "interruptor": {"panel": (58, 8, 48), "tenue": (58, 8, 48), "acento": (255, 70, 200), "borde": (255, 130, 220),
                    "patron": "puntos", "nombre": "Aparece con interruptor"},
    "checkpoint": {"panel": (4, 40, 26), "tenue": (4, 40, 26), "acento": (50, 190, 110), "borde": (170, 255, 205),
                   "patron": "concentrico", "nombre": "Checkpoint"},
    "meta": {"panel": (70, 54, 6), "tenue": (255, 248, 225), "acento": (255, 214, 60), "borde": (255, 240, 150),
             "patron": "bandera", "nombre": "Meta"},
}
CLAVES = tuple(ESTILOS)

TEMAS_VISUALES = {
    # cielo: (cenit, horizonte, abismo); luz = color de las ventanas de las torres; rejilla = líneas del vacío
    "digital": {"cenit": (4, 8, 28), "horizonte": (20, 90, 140), "abismo": (2, 3, 12), "luz": (70, 230, 255),
                "luz2": (255, 70, 200), "rejilla": (40, 130, 190)},
    "corrupto": {"cenit": (14, 2, 18), "horizonte": (150, 24, 70), "abismo": (8, 1, 10), "luz": (255, 80, 100),
                 "luz2": (255, 190, 60), "rejilla": (170, 36, 84)},
}


def tema_visual(nombre):
    return dict(TEMAS_VISUALES.get(nombre, TEMAS_VISUALES["digital"]))


# Clave de estilo de una plataforma (prioridad: meta > interruptor > checkpoint > tipo).
def clave_estilo(tipo, requiere=None, es_meta=False, checkpoint=False):
    if es_meta:
        return "meta"
    if requiere:
        return "interruptor"
    if checkpoint:
        return "checkpoint"
    return tipo if tipo in ("movil", "desaparece") else "fija"


def mezclar(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def escalar(c, k):
    return tuple(max(0.0, min(255.0, v * k)) for v in c)


# -- Patrones de la cara superior --

# Celdas (x0, z0, x1, z1, tono) del relleno interior de una plataforma de ancho x fondo (centrada en el origen). `tono`
# es "panel", "tenue" o "acento". Las celdas no se solapan y cubren exactamente el interior (todo menos el borde).
def celdas_patron(patron, ancho, fondo, borde=BORDE):
    b = min(borde, ancho / 4, fondo / 4)
    ix0, ix1, iz0, iz1 = -ancho / 2 + b, ancho / 2 - b, -fondo / 2 + b, fondo / 2 - b
    w, h = ix1 - ix0, iz1 - iz0
    if patron == "concentrico":
        celdas, k, s = [], 0, 0.0
        paso = max(0.18, min(w, h) / 7)
        while ix0 + s < ix1 - s - 1e-6 and iz0 + s < iz1 - s - 1e-6:
            tono = "acento" if k % 2 == 1 else "panel"
            x0, x1, z0, z1 = ix0 + s, ix1 - s, iz0 + s, iz1 - s
            nx0, nx1, nz0, nz1 = x0 + paso, x1 - paso, z0 + paso, z1 - paso
            if nx0 >= nx1 - 1e-6 or nz0 >= nz1 - 1e-6:
                celdas.append((x0, z0, x1, z1, tono))         # centro: rectángulo macizo
                break
            celdas += [(x0, z0, x1, z0 + paso, tono), (x0, z1 - paso, x1, z1, tono),
                       (x0, z0 + paso, x0 + paso, z1 - paso, tono), (x1 - paso, z0 + paso, x1, z1 - paso, tono)]
            s += paso
            k += 1
        return celdas
    if patron == "franjas":
        n = max(2, round(h / 0.55))
        if n % 2 == 0:
            n += 1                                              # nº impar: empiezan y acaban en acento
        dz = h / n
        return [(ix0, iz0 + i * dz, ix1, iz0 + (i + 1) * dz, "acento" if i % 2 == 0 else "panel") for i in range(n)]
    tam = {"baldosas": 1.0, "ajedrez": 0.5, "puntos": 0.42, "bandera": 0.55}.get(patron, 1.0)
    nx, nz = max(1, round(w / tam)), max(1, round(h / tam))
    dx, dz = w / nx, h / nz
    celdas = []
    for i in range(nx):
        for j in range(nz):
            if patron == "baldosas":
                tono = "tenue" if (i + j) % 2 else "panel"
            elif patron == "ajedrez":
                tono = "acento" if (i + j) % 2 == 0 else "panel"
            elif patron == "puntos":
                tono = "acento" if (i % 2 == 0 and j % 2 == 0) else "panel"
            else:                                                # bandera a cuadros
                tono = "acento" if (i + j) % 2 == 0 else "tenue"
            celdas.append((ix0 + i * dx, iz0 + j * dz, ix0 + (i + 1) * dx, iz0 + (j + 1) * dz, tono))
    return celdas


def _quad(v, c, t, pts, cols):
    base = len(v)
    v += [tuple(p) for p in pts]
    c += [tuple(x) for x in cols]
    t += [(base, base + 1, base + 2), (base, base + 2, base + 3)]


# Caja neón centrada en (0, 0) del plano, con la cara superior en y = 0 y el fondo en y = -grosor.
# Cara superior: franja de borde brillante + relleno con patrón. Paredes: franja de neón arriba y degradado a oscuro.
def caja_neon(ancho, fondo, grosor, clave, borde=BORDE):
    e = ESTILOS[clave]
    v, c, t = [], [], []
    b = min(borde, ancho / 4, fondo / 4)
    hx, hz = ancho / 2, fondo / 2
    brillo = e["borde"]

    def arriba(x0, z0, x1, z1, col):
        _quad(v, c, t, [(x0, 0, z0), (x1, 0, z0), (x1, 0, z1), (x0, 0, z1)], [col] * 4)

    arriba(-hx, -hz, hx, -hz + b, brillo)
    arriba(-hx, hz - b, hx, hz, brillo)
    arriba(-hx, -hz + b, -hx + b, hz - b, brillo)
    arriba(hx - b, -hz + b, hx, hz - b, brillo)
    for x0, z0, x1, z1, tono in celdas_patron(e["patron"], ancho, fondo, borde):
        arriba(x0, z0, x1, z1, e[tono])
    fr = FRANJA_LATERAL
    cuerpo_arriba, cuerpo_abajo = escalar(e["panel"], 0.9), escalar(e["panel"], 0.12)
    cuerpo_arriba = mezclar(cuerpo_arriba, e["acento"], 0.18)
    for (ax, az), (bx, bz) in (((-hx, -hz), (hx, -hz)), ((hx, -hz), (hx, hz)), ((hx, hz), (-hx, hz)), ((-hx, hz), (-hx, -hz))):
        _quad(v, c, t, [(ax, 0, az), (bx, 0, bz), (bx, -fr, bz), (ax, -fr, az)], [e["acento"]] * 4)
        _quad(v, c, t, [(ax, -fr, az), (bx, -fr, bz), (bx, -grosor, bz), (ax, -grosor, az)],
              [cuerpo_arriba, cuerpo_arriba, cuerpo_abajo, cuerpo_abajo])
    return v, c, t


def desplazar(vertices, dx, dy, dz):
    return [(x + dx, y + dy, z + dz) for x, y, z in vertices]


# Une varias mallas (v, c, t) en una (reindexa los triángulos).
def unir_mallas(mallas):
    v, c, t = [], [], []
    for mv, mc, mt in mallas:
        base = len(v)
        v += mv
        c += mc
        t += [(a + base, b + base, d + base) for a, b, d in mt]
    return v, c, t


# -- Cielo --

# Color del domo a `elev` grados sobre el horizonte (-90 abismo ... +90 cenit).
def color_cielo(elev, tema):
    if elev >= 0:
        k = min(1.0, elev / 70.0) ** 0.6
        return mezclar(tema["horizonte"], tema["cenit"], k)
    k = min(1.0, -elev / 35.0) ** 0.7
    return mezclar(escalar(tema["horizonte"], 0.55), tema["abismo"], k)


# Esfera de `radio` con colores por elevación: (vertices, colores, triangulos).
def domo(radio, tema, anillos=14, segmentos=24):
    v, c, t = [], [], []
    for i in range(anillos + 1):
        elev = -90 + 180 * i / anillos
        er = math.radians(elev)
        for j in range(segmentos):
            az = 2 * math.pi * j / segmentos
            v.append((radio * math.cos(er) * math.sin(az), radio * math.sin(er), radio * math.cos(er) * math.cos(az)))
            c.append(color_cielo(elev, tema))
    for i in range(anillos):
        for j in range(segmentos):
            a = i * segmentos + j
            b = i * segmentos + (j + 1) % segmentos
            t += [(a, b, a + segmentos), (b, b + segmentos, a + segmentos)]
    return v, c, t


# -- Torres de servidores --

# Coloca hasta `n` torres (x, z, ancho, fondo, y_techo) alrededor de los puntos (x, z) de las plataformas: ninguna a menos
# de `libre` m de una plataforma, entre sí separadas por `separacion`. Determinista por `semilla`.
def colocar_torres(puntos, n, semilla, y_base, y_alto, libre=30.0, alcance=(42.0, 135.0), separacion=18.0):
    rng = random.Random(semilla)
    torres, intentos = [], 0
    if not puntos:
        return torres
    while len(torres) < n and intentos < n * 40:
        intentos += 1
        px, pz = rng.choice(puntos)
        d, a = rng.uniform(*alcance), rng.uniform(0, 2 * math.pi)
        x, z = px + d * math.cos(a), pz + d * math.sin(a)
        if any(math.hypot(x - qx, z - qz) < libre for qx, qz in puntos):
            continue
        if any(math.hypot(x - o[0], z - o[1]) < separacion for o in torres):
            continue
        ancho, fondo = rng.uniform(4.0, 9.0), rng.uniform(4.0, 9.0)
        techo = rng.uniform(y_base + 0.2 * (y_alto - y_base) + 20, y_alto)
        torres.append((x, z, ancho, fondo, techo))
    return torres


# Malla de una torre desde y_fondo hasta y_techo con filas de ventanas luminosas. `niebla` 0..1 la atenúa hacia `cielo`.
def malla_torre(x, z, ancho, fondo, y_fondo, y_techo, tema, semilla, niebla=0.0, cielo=(8, 8, 20)):
    rng = random.Random(semilla)
    v, c, t = [], [], []
    hx, hz = ancho / 2, fondo / 2

    def tono(col, k=1.0):
        return mezclar(escalar(col, k), cielo, niebla)

    cuerpo_alto, cuerpo_bajo = tono(tema["cenit"], 1.9), tono(tema["abismo"], 0.7)
    esquinas = [(-hx, -hz), (hx, -hz), (hx, hz), (-hx, hz)]
    for k in range(4):
        (ax, az), (bx, bz) = esquinas[k], esquinas[(k + 1) % 4]
        _quad(v, c, t, [(x + ax, y_fondo, z + az), (x + bx, y_fondo, z + bz), (x + bx, y_techo, z + bz),
                        (x + ax, y_techo, z + az)], [cuerpo_bajo, cuerpo_bajo, cuerpo_alto, cuerpo_alto])
        piso = y_fondo + 3.0
        while piso < y_techo - 1.0:
            if rng.random() < 0.34:
                luz = tema["luz"] if rng.random() < 0.8 else tema["luz2"]
                f0, f1 = rng.uniform(0.08, 0.3), rng.uniform(0.7, 0.92)
                pa = (ax + (bx - ax) * f0, az + (bz - az) * f0)
                pb = (ax + (bx - ax) * f1, az + (bz - az) * f1)
                col = tono(luz, 0.75)
                _quad(v, c, t, [(x + pa[0], piso, z + pa[1]), (x + pb[0], piso, z + pb[1]),
                                (x + pb[0], piso + 0.4, z + pb[1]), (x + pa[0], piso + 0.4, z + pa[1])], [col] * 4)
            piso += 2.8
    # baliza del techo
    col = tono(tema["luz2"], 1.0)
    _quad(v, c, t, [(x - 0.6, y_techo + 0.02, z - 0.6), (x + 0.6, y_techo + 0.02, z - 0.6),
                    (x + 0.6, y_techo + 0.02, z + 0.6), (x - 0.6, y_techo + 0.02, z + 0.6)], [col] * 4)
    return v, c, t


# -- Rejilla del vacío en profundidad --

# Líneas (pares de vértices) y colores de una rejilla centrada en (cx, cz) de semiancho/semifondo dados, troceada en
# tramos de ~`tramo` m cuyo brillo cae con la distancia al centro (no hace falta niebla) y con una línea mayor cada
# `mayor` líneas. Devuelve (vertices, colores).
def rejilla_en_profundidad(cx, cz, sx, sz, y, paso, color, mayor=4, tramo=10.0):
    v, c = [], []
    radio = math.hypot(sx, sz)

    def brillo(x, z):
        return max(0.0, 1.0 - math.hypot(x - cx, z - cz) / radio) ** 1.4

    def linea(p0, p1, es_mayor):
        n = max(1, math.ceil(math.dist(p0, p1) / tramo))
        for i in range(n):
            a = (p0[0] + (p1[0] - p0[0]) * i / n, p0[1] + (p1[1] - p0[1]) * i / n)
            b = (p0[0] + (p1[0] - p0[0]) * (i + 1) / n, p0[1] + (p1[1] - p0[1]) * (i + 1) / n)
            base = 1.0 if es_mayor else 0.55
            for q in (a, b):
                v.append((q[0], y, q[1]))
                c.append(escalar(color, base * brillo(*q) * 1.2))

    x0, x1, z0, z1 = cx - sx, cx + sx, cz - sz, cz + sz
    k = 0
    x = math.floor(x0 / paso) * paso
    while x <= x1:
        linea((x, z0), (x, z1), round(x / paso) % mayor == 0)
        x += paso
        k += 1
    z = math.floor(z0 / paso) * paso
    while z <= z1:
        linea((x0, z), (x1, z), round(z / paso) % mayor == 0)
        z += paso
    return v, c


# Desplazamiento de la rejilla que se desliza `velocidad` m/s sin salirse nunca más de un `paso`.
def deriva(t, velocidad, paso):
    return (t * velocidad) % paso


# -- Bits de datos flotantes --

# `n` puntos (x, y, z, color) en una caja [x0,x1]x[y0,y1]x[z0,z1]; el patrón se repite cada (y1-y0) para que subir y
# envolver sea continuo (ver `subida_bits`). Determinista por semilla.
def bits_de_datos(n, caja, semilla, paleta):
    rng = random.Random(semilla)
    (x0, x1), (y0, y1), (z0, z1) = caja
    return [(rng.uniform(x0, x1), rng.uniform(y0, y1), rng.uniform(z0, z1), rng.choice(paleta)) for _ in range(n)]


def subida_bits(t, velocidad, alto):
    return (t * velocidad) % alto


# -- Anillos y tubos de efectos --

# Anillo plano (y = 0) de radio exterior 1 e interior `interior`; `arcos` > 0 deja huecos (arcos giratorios).
def malla_anillo(interior=0.82, segmentos=40, arcos=0):
    v, c, t = [], [], []
    for j in range(segmentos):
        if arcos and (j * arcos * 2 // segmentos) % 2 == 1:
            continue
        a0, a1 = 2 * math.pi * j / segmentos, 2 * math.pi * (j + 1) / segmentos
        base = len(v)
        for r, a in ((1.0, a0), (1.0, a1), (interior, a1), (interior, a0)):
            v.append((r * math.sin(a), 0.0, r * math.cos(a)))
            c.append((255, 255, 255))
        t += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
    return v, c, t


# Tubo vertical abierto de radio 1 y alto 1 con alfa que baja de `alfa_abajo` a 0 hacia arriba (colores RGBA 0-255).
def malla_tubo(segmentos=12, alfa_abajo=255):
    v, c, t = [], [], []
    for j in range(segmentos):
        a0, a1 = 2 * math.pi * j / segmentos, 2 * math.pi * (j + 1) / segmentos
        base = len(v)
        v += [(math.sin(a0), 0.0, math.cos(a0)), (math.sin(a1), 0.0, math.cos(a1)),
              (math.sin(a1), 1.0, math.cos(a1)), (math.sin(a0), 1.0, math.cos(a0))]
        c += [(255, 255, 255, alfa_abajo)] * 2 + [(255, 255, 255, 0)] * 2
        t += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
    return v, c, t


def suave(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


# Estado de un anillo expansivo: (radio, alfa 0..1) a los `edad` s de una vida `duracion` (sale rápido y se desvanece).
def estado_anillo(edad, duracion, radio0, radio1, alfa0=1.0):
    k = max(0.0, min(1.0, edad / duracion)) if duracion > 0 else 1.0
    salida = 1 - (1 - k) ** 3
    return radio0 + (radio1 - radio0) * salida, alfa0 * (1 - k) ** 1.5


# Partículas de polvo de datos: (vx, vy, vz) de la i-ésima de `n` en abanico, determinista.
def velocidad_polvo(i, n, rapidez, semilla=0):
    rng = random.Random(semilla * 7919 + i)
    a = 2 * math.pi * (i + rng.uniform(-0.3, 0.3)) / max(1, n)
    r = rapidez * rng.uniform(0.5, 1.0)
    return r * math.sin(a), rapidez * rng.uniform(0.5, 1.1), r * math.cos(a)


# Un paso de física de una partícula: ((x, y, z), (vx, vy, vz)) con gravedad `g` y rozamiento horizontal.
def paso_particula(pos, vel, dt, g=9.0, roce=2.5):
    k = max(0.0, 1 - roce * dt)
    vx, vy, vz = vel[0] * k, vel[1] - g * dt, vel[2] * k
    return (pos[0] + vx * dt, pos[1] + vy * dt, pos[2] + vz * dt), (vx, vy, vz)


# Pulso periódico 0..1 (interruptor sin activar, baliza de la meta).
def pulso(t, hz=1.0, fase=0.0):
    return 0.5 + 0.5 * math.sin(2 * math.pi * hz * t + fase)


# -- Cámara --

FOV_EXTRA_CAIDA = 7.0         # grados máximos que se suman al caer rápido
VY_CAIDA_INICIO, VY_CAIDA_PLENO = -7.0, -17.0
FOV_EXTRA_SALTO = 2.5         # grados al ir hacia arriba rápido


# FOV extra objetivo (grados) según la velocidad vertical: crece al caer, un poco al subir; 0 en el suelo.
def fov_extra_objetivo(vy, en_aire):
    if not en_aire:
        return 0.0
    if vy < VY_CAIDA_INICIO:
        return FOV_EXTRA_CAIDA * suave((vy - VY_CAIDA_INICIO) / (VY_CAIDA_PLENO - VY_CAIDA_INICIO))
    if vy > 3.0:
        return FOV_EXTRA_SALTO * suave((vy - 3.0) / 5.0)
    return 0.0


# Acerca `actual` a `objetivo` con una exponencial (sube en ~0.2 s, baja en ~0.35 s); sin saltos con dt grandes.
def suavizar_fov(actual, objetivo, dt):
    rapidez = 9.0 if objetivo > actual else 5.5
    return actual + (objetivo - actual) * (1 - math.exp(-rapidez * max(0.0, dt)))


# -- HUD --

# Avance 0..1 hacia la meta: proyección de (x, z) sobre el segmento inicio -> meta (no retrocede por rodeos laterales).
def progreso_hacia_meta(x, z, inicio, meta):
    dx, dz = meta[0] - inicio[0], meta[1] - inicio[1]
    largo2 = dx * dx + dz * dz
    if largo2 < 1e-9:
        return 0.0
    return max(0.0, min(1.0, ((x - inicio[0]) * dx + (z - inicio[1]) * dz) / largo2))


# Alfa del destello de pantalla a los `edad` s (dura `duracion`): sube casi al instante y baja suave. 0 cuando acaba.
def alfa_destello(edad, duracion, alfa_max):
    if edad >= duracion or duracion <= 0:
        return 0.0
    k = edad / duracion
    return alfa_max * (k / 0.12 if k < 0.12 else (1 - k) / 0.88) ** 1.3 if k < 1 else 0.0


# Escala del texto de aviso a los `edad` s: nace un 35 % más grande y se asienta en 0.18 s.
def escala_aviso(edad):
    return 1.0 + 0.35 * max(0.0, 1 - edad / 0.18) ** 2
