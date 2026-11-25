# Torre de la Rádio Comunitária (docs/RADIO_3D.md): dónde va y de qué piezas está hecha. Lógica PURA (sin ursina), con
# tests en tests/test_a_radio_torre.py. La dibuja frontend/radio_torre_modelo.py y la usa la emisión en 3D
# (frontend/radio3d_escena.py) como centro de la órbita de la cámara.
#
# La torre es un mástil de celosía de tres patas con travesaños y diagonales, una plataforma, un pequeño reflector de
# antena y una luz roja de aviso en la punta que parpadea siempre. Va JUNTO al edificio de la radio (lugar
# «Rádio Comunitária» del mundo), detrás o a un lado de la caseta, nunca delante de la puerta.
#
# BANDERA: ALCALDE_RADIO3D (frontend/radio3d_camara_calculos.py). Con =0 no se construye la torre.

import math

LUGAR_RADIO = "Rádio Comunitária"

# -- Medidas del mástil (m) --
ALTO_TORRE = 15.0
ANCHO_BASE = 1.8               # lado del triángulo de las patas abajo
ANCHO_PUNTA = 0.55             # lado arriba (la torre se estrecha)
GROSOR_PATA = 0.12
GROSOR_BARRA = 0.06
PASO_TRAVESANOS = 1.5          # cada cuántos metros un anillo de travesaños (con su diagonal)
ALTO_PLATAFORMA = 0.75         # fracción del alto con la plataforma de servicio
ALTO_ZAPATA = 0.5              # dado de hormigón bajo cada pata (absorbe el desnivel de la ladera)
RADIO_LUZ = 0.22               # la bombilla roja de la punta
RADIO_HALO = 0.6               # el resplandor alrededor (esfera translúcida)
RADIO_CUERPO = 1.4             # radio de colisión y de reserva de sitio

# -- Colocación --
DISTANCIAS = (2.8, 3.6, 4.6, 5.8)      # m desde la caja del edificio hasta el centro de la torre
DESNIVEL_MAXIMO = 0.6                  # desnivel por metro bajo la torre (más que un prop: lleva zapatas)

# -- Luz de aviso --
PERIODO_LUZ_S = 1.4            # un destello cada tanto (encendida la primera parte del periodo)
FRACCION_ENCENDIDA = 0.45
BRILLO_APAGADA = 0.18          # no se apaga del todo: se sigue viendo de noche


def _normal(lado):
    return {"n": (0.0, 1.0), "s": (0.0, -1.0), "e": (1.0, 0.0), "o": (-1.0, 0.0), "w": (-1.0, 0.0)}.get(lado, (0.0, 1.0))


def candidatos(caja, lado_puerta, distancias=DISTANCIAS):
    """Sitios posibles (x, z), del preferido al último: detrás del edificio (lado opuesto a la puerta), luego en los
    laterales, luego en las esquinas traseras; cada fila, de más cerca a más lejos de la caja. Nunca por delante."""
    x0, x1, z0, z1 = caja
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    medio_x, medio_z = (x1 - x0) / 2, (z1 - z0) / 2
    nx, nz = _normal(lado_puerta)
    # tangente a lo largo de la fachada y medio largo en cada dirección
    tx, tz = -nz, nx
    medio_n = medio_x * abs(nx) + medio_z * abs(nz)
    medio_t = medio_x * abs(tx) + medio_z * abs(tz)
    salida = []
    for d in distancias:
        # detrás: centro y a medio camino de cada esquina
        for f in (0.0, 0.5, -0.5):
            salida.append((cx - nx * (medio_n + d) + tx * f * medio_t, cz - nz * (medio_n + d) + tz * f * medio_t))
        # laterales: hacia la parte trasera
        for signo in (1.0, -1.0):
            for f in (-0.5, 0.0):
                salida.append((cx + signo * tx * (medio_t + d) + nx * f * medio_n,
                               cz + signo * tz * (medio_t + d) + nz * f * medio_n))
        # esquinas traseras
        for signo in (1.0, -1.0):
            salida.append((cx - nx * (medio_n + d * 0.75) + signo * tx * (medio_t + d * 0.75),
                           cz - nz * (medio_n + d * 0.75) + signo * tz * (medio_t + d * 0.75)))
    return [(round(x, 3), round(z, 3)) for x, z in salida]


def elegir_sitio(caja, lado_puerta, cabe, desnivel=None):
    """El primer candidato donde `cabe(x, z, RADIO_CUERPO)` y el desnivel (si se da) no pasa de DESNIVEL_MAXIMO, o
    None si ninguno sirve."""
    for x, z in candidatos(caja, lado_puerta):
        if not cabe(x, z, RADIO_CUERPO):
            continue
        if desnivel is not None and desnivel(x, z) > DESNIVEL_MAXIMO:
            continue
        return (x, z)
    return None


def lado_a(y):
    """Lado del triángulo de patas a la altura `y` (se estrecha de la base a la punta)."""
    f = min(1.0, max(0.0, y / ALTO_TORRE))
    return ANCHO_BASE + (ANCHO_PUNTA - ANCHO_BASE) * f


def patas(y):
    """Las tres patas (x, z) relativas al centro a la altura `y` (triángulo equilátero, una pata hacia +z)."""
    r = lado_a(y) / math.sqrt(3)
    return [(r * math.sin(math.radians(a)), r * math.cos(math.radians(a))) for a in (0.0, 120.0, 240.0)]


def barra(p, q):
    """(centro, largo, giro_y, inclinación_x) de una barra recta de p a q (x, y, z), para un cubo estirado en z."""
    dx, dy, dz = (q[i] - p[i] for i in range(3))
    horizontal = math.hypot(dx, dz)
    largo = math.sqrt(dx * dx + dy * dy + dz * dz)
    centro = tuple((p[i] + q[i]) / 2 for i in range(3))
    return centro, largo, math.degrees(math.atan2(dx, dz)), -math.degrees(math.atan2(dy, horizontal))


def piezas_celosia():
    """Las barras de la celosía: [(p, q, grosor)] relativas a la base (y = 0 en el suelo del centro): las tres patas,
    un anillo de travesaños cada PASO_TRAVESANOS y una diagonal por cara entre anillos."""
    piezas = []
    pies, puntas = patas(0.0), patas(ALTO_TORRE)
    for (ax, az), (bx, bz) in zip(pies, puntas):
        piezas.append(((ax, 0.0, az), (bx, ALTO_TORRE, bz), GROSOR_PATA))
    alturas = [k * PASO_TRAVESANOS for k in range(1, int(ALTO_TORRE / PASO_TRAVESANOS) + 1)]
    previas = None
    for i, y in enumerate(alturas):
        anillo = [(x, y, z) for x, z in patas(y)]
        for k in range(3):
            piezas.append((anillo[k], anillo[(k + 1) % 3], GROSOR_BARRA))
        if previas is not None:
            for k in range(3):
                # diagonales alternadas (zigzag) para que se lea como celosía
                a, b = (previas[k], anillo[(k + 1) % 3]) if i % 2 else (anillo[k], previas[(k + 1) % 3])
                piezas.append((a, b, GROSOR_BARRA))
        previas = anillo
    return piezas


def punta():
    """(x, y, z) de la luz de aviso, relativa a la base."""
    return (0.0, ALTO_TORRE + 0.45, 0.0)


def brillo_luz(t, reducir=False):
    """Brillo 0..1 de la luz roja en el instante `t`: destello y apagado parcial; con «reducir movimiento», un pulso
    suave sin cortes."""
    if PERIODO_LUZ_S <= 0:
        return 1.0
    fase = (t % PERIODO_LUZ_S) / PERIODO_LUZ_S
    if reducir:
        return BRILLO_APAGADA + (1.0 - BRILLO_APAGADA) * (0.5 - 0.5 * math.cos(2 * math.pi * fase))
    return 1.0 if fase < FRACCION_ENCENDIDA else BRILLO_APAGADA
