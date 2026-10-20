# Muros de contención de la ladera (datos puros, sin ursina). Donde el terreno es demasiado
# empinado para caminarlo (Terreno.caminable) hay un talud que hoy se ve solo como tierra; aquí
# se calcula la lista de losas verticales que el frontend dibuja para "contener" ese talud.
#
# Un muro es una losa a lo largo de la curva de nivel (perpendicular al gradiente del suelo):
#   - centro (cx, cz) y `rumbo` del eje largo, en grados [0, 180) con la convención de Ursina
#     (adelante = (sin ψ, cos ψ)); como la losa es simétrica, ψ y ψ + 180 son el mismo muro;
#   - `largo` m (paso * 1.1 por celda, un poco más que la celda para que no queden rendijas);
#   - `y_base` = esquina más baja de sus celdas - 0.3 (se entierra) y `y_tope` = la más alta + 0.4
#     (parapeto).
# Es solo dato visual: la colisión sigue siendo el talud no caminable de MundoCiudad.es_transitable.

import math
from dataclasses import dataclass

PASO_MURO = 1.0              # m: lado de las celdas que se recorren (= PASO_GRILLA del terreno)
HOLGURA_LARGO = 1.1          # factor adimensional: el largo de una losa es paso * HOLGURA_LARGO (m)
ENTIERRO_BASE = 0.3          # m que la base queda bajo la esquina más baja
PARAPETO = 0.4               # m que el tope sobresale de la esquina más alta
TOLERANCIA_RUMBO = 15.0      # grados: dos celdas vecinas se fusionan si sus rumbos difieren menos
DISTANCIA_LIBRE = 1.0        # m base libres entre un muro y el eje de una escalera, calle o acceso
                             # (la exclusión real suma media losa + 0.05 m: ver muros_de_contencion)
PENDIENTE_MINIMA = 0.4       # m de desnivel entre esquinas por m de paso, para mirar una celda: filtro
                             # conservador, tan(32°) / sqrt(2) = 0.44, así no se pierde ninguna


@dataclass(frozen=True)
class Muro:
    """Losa vertical de contención: ver el encabezado del módulo."""

    cx: float
    cz: float
    rumbo: float
    largo: float
    y_base: float
    y_tope: float


# Distancia del punto (x, z) al segmento a-b.
def _distancia_segmento(x, z, a, b):
    dx, dz = b[0] - a[0], b[1] - a[1]
    largo2 = dx * dx + dz * dz
    t = 0.0 if largo2 < 1e-12 else min(1.0, max(0.0, ((x - a[0]) * dx + (z - a[1]) * dz) / largo2))
    return math.hypot(x - (a[0] + dx * t), z - (a[1] + dz * t))


# Diferencia angular mínima entre dos rumbos de eje (módulo 180), en grados.
def _diferencia_rumbo(a, b):
    d = abs(a - b) % 180
    return min(d, 180 - d)


# Celdas no caminables del terreno: [(i, j, cx, cz, rumbo, tx, tz, y_min, y_max)] con la tangente
# unitaria (a lo largo de la curva de nivel) y la altura mínima y máxima de las 4 esquinas.
def _celdas_empinadas(terreno, paso):
    x0, x1, z0, z1 = terreno.extension
    nx, nz = int(math.floor((x1 - x0) / paso)), int(math.floor((z1 - z0) / paso))
    previa = [terreno.altura(x0 + i * paso, z0) for i in range(nx + 1)]
    celdas = []
    for j in range(nz):
        z = z0 + j * paso
        siguiente = [terreno.altura(x0 + i * paso, z + paso) for i in range(nx + 1)]
        for i in range(nx):
            esquinas = (previa[i], previa[i + 1], siguiente[i], siguiente[i + 1])
            y_min, y_max = min(esquinas), max(esquinas)
            if y_max - y_min < PENDIENTE_MINIMA * paso:
                continue
            cx, cz = x0 + (i + 0.5) * paso, z + paso / 2
            if terreno.caminable(cx, cz):
                continue
            h = paso / 2
            gx = (terreno.altura(cx + h, cz) - terreno.altura(cx - h, cz)) / paso
            gz = (terreno.altura(cx, cz + h) - terreno.altura(cx, cz - h)) / paso
            norma = math.hypot(gx, gz)
            if norma < 1e-9:
                continue
            tx, tz = -gz / norma, gx / norma             # perpendicular al gradiente
            if tz < 0 or (abs(tz) < 1e-9 and tx < 0):
                tx, tz = -tx, -tz                        # sentido canónico: rumbo en [0, 180)
            celdas.append((i, j, cx, cz, math.degrees(math.atan2(tx, tz)) % 180, tx, tz, y_min, y_max))
        previa = siguiente
    return celdas


# Agrupa celdas vecinas en cadenas rectas: desde una semilla se avanza por su tangente, tomando
# la celda libre más próxima hacia delante (a 0.5-1.6 pasos) que quede a <= 0.6 pasos de la recta
# de la semilla y con rumbo parecido (+-TOLERANCIA_RUMBO). Devuelve listas de celdas.
def _fusionar(celdas, paso):
    libres = {(c[0], c[1]): c for c in celdas}
    cadenas = []
    for clave in sorted(libres):
        if clave not in libres:
            continue
        semilla = libres.pop(clave)
        _, _, sx, sz, rumbo, tx, tz = semilla[:7]
        cadena = [semilla]
        for sentido in (1, -1):
            actual = 0.0                                  # posición a lo largo de la recta
            while True:
                mejor = None
                avance = sentido * (actual + paso) / paso       # celdas hasta el siguiente punto previsto
                for dj in range(-1, 2):
                    for di in range(-1, 2):
                        c = libres.get((semilla[0] + int(round(avance * tx)) + di,
                                        semilla[1] + int(round(avance * tz)) + dj))
                        if c is None or _diferencia_rumbo(c[4], rumbo) > TOLERANCIA_RUMBO:
                            continue
                        rx, rz = c[2] - sx, c[3] - sz
                        a_lo_largo = (rx * tx + rz * tz) * sentido
                        lateral = abs(-rx * tz + rz * tx)
                        if 0.5 * paso <= a_lo_largo - actual <= 1.6 * paso and lateral <= 0.6 * paso:
                            if mejor is None or a_lo_largo < mejor[0]:
                                mejor = (a_lo_largo, c)
                if mejor is None:
                    break
                actual = mejor[0]
                cadena.append(libres.pop((mejor[1][0], mejor[1][1])))
        cadenas.append(cadena)
    return cadenas


def muros_de_contencion(terreno, escaleras, cajas_ocupadas, paso=PASO_MURO, lineas_libres=()):
    """Muros que contienen los taludes no caminables del `terreno`.

    Recorre las celdas de lado `paso` de su grilla; una celda no caminable genera un muro salvo si
    está sobre una escalera, dentro de una caja ocupada `(xmin, xmax, zmin, zmax)` (edificios y
    casas) o demasiado cerca del eje de una escalera o de alguna de las `lineas_libres` [(a, b)]
    (ejes de calle, caminos plaza -> puerta): la distancia de exclusión es DISTANCIA_LIBRE + media
    losa (paso * HOLGURA_LARGO / 2) + 0.05 m, o sea ~1.6 m con el paso por defecto. Las celdas vecinas
    de rumbo parecido se funden en una sola losa más larga.
    """
    media = paso * HOLGURA_LARGO / 2
    ejes = [((e.ax, e.az), (e.bx, e.bz)) for e in escaleras]
    ejes += [(tuple(a), tuple(b)) for a, b in lineas_libres]
    permitidas = []
    for celda in _celdas_empinadas(terreno, paso):
        cx, cz = celda[2], celda[3]
        if any(e.contiene(cx, cz) for e in escaleras):
            continue
        if any(_distancia_segmento(cx, cz, a, b) < DISTANCIA_LIBRE + media + 0.05 for a, b in ejes):
            continue
        if any(xmin - paso / 2 <= cx <= xmax + paso / 2 and zmin - paso / 2 <= cz <= zmax + paso / 2
               for xmin, xmax, zmin, zmax in cajas_ocupadas):
            continue
        permitidas.append(celda)
    muros = []
    for cadena in _fusionar(permitidas, paso):
        _, _, sx, sz, rumbo, tx, tz = cadena[0][:7]
        posiciones = [(c[2] - sx) * tx + (c[3] - sz) * tz for c in cadena]
        medio = (min(posiciones) + max(posiciones)) / 2
        muros.append(Muro(round(sx + tx * medio, 3), round(sz + tz * medio, 3), round(rumbo, 2),
                          round(max(posiciones) - min(posiciones) + paso * HOLGURA_LARGO, 3),
                          round(min(c[7] for c in cadena) - ENTIERRO_BASE, 3),
                          round(max(c[8] for c in cadena) + PARAPETO, 3)))
    return muros
