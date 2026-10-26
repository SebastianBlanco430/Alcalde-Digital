# Cálculos del mapa grande a pantalla casi completa (frontend/mapa_grande_vista.py). Python puro: NO importa ursina; se
# prueba con pytest sin ventana.
#
# El mapa se dibuja con mallas ESTÁTICAS sin casas (en un mundo de ~4.600 casas serían ruido): fondo de terreno
# suavizado por altura con sombreado de ladera, calles, plazas de los lugares con su color, y encima el jugador, el
# destino y la ruta del GPS. Aquí está lo que se decide con números: cómo encajar el mundo en el área libre de la
# pantalla (16:9 o 4:3), el color de cada punto del terreno y dónde caben las etiquetas sin pisarse.

import math

# Tecla que abre y cierra el mapa. Ocupadas: «M» (Seguir misión), «Tab» (teléfono), «E» (interactuar), «I» (mochila),
# «G» (saludos online), 1-9 (opciones numeradas), «F3» (telemetría), WASD y flechas. «N» estaba libre.
TECLA_MAPA = "n"

PASO_TERRENO = 16.0                 # m entre muestras de altura del fondo (≈ 2.900 muestras en 976 x 724 m)

# Rampa de color por altura (0 = punto más bajo, 1 = más alto): oscura y apagada para que plazas, ruta y destino resalten.
RAMPA_TERRENO = (
    (0.00, (38, 62, 66)),
    (0.30, (62, 96, 76)),
    (0.60, (104, 118, 84)),
    (1.00, (160, 148, 108)),
)
LUZ_X, LUZ_Z = -0.6, 0.8            # hacia dónde está el sol en el plano del mapa (noroeste: x < 0, z > 0)
FUERZA_SOMBRA = 2.2                 # cuánto pesa la pendiente en el sombreado
SOMBRA_MAX = 0.42
OSCURECER = 0.82                    # el fondo no compite con plazas, etiquetas, ruta ni destino


# -- Encaje del mundo en la pantalla -----------------------------------------------------------------------------------

# Área libre (cx, cy, ancho, alto) para el mapa dentro de una pantalla de `aspecto` x 1 unidades de camera.ui: deja arriba
# un encabezado y abajo la leyenda.
def area_del_mapa(aspecto, margen=0.03, encabezado=0.085, leyenda=0.06):
    ancho = aspecto - 2 * margen - 0.04
    alto = 1.0 - 2 * margen - encabezado - leyenda
    cy = 0.5 - margen - encabezado - alto / 2
    return (0.0, cy, ancho, alto)


# (escala, ox, oy): u = ox + escala * x, v = oy + escala * z llevan el rectángulo (xmin, xmax, zmin, zmax) del mundo,
# sin deformarlo, al centro del área (cx, cy, ancho, alto). Escala uniforme: la mayor que cabe.
def encajar(extension, area):
    xmin, xmax, zmin, zmax = extension
    cx, cy, ancho, alto = area
    escala = min(ancho / (xmax - xmin), alto / (zmax - zmin))
    return (escala, cx - escala * (xmin + xmax) / 2, cy - escala * (zmin + zmax) / 2)


def a_pantalla(encaje, x, z):
    escala, ox, oy = encaje
    return (ox + escala * x, oy + escala * z)


# -- Terreno ------------------------------------------------------------------------------------------------------------

# Rejilla de alturas del terreno: (xs, zs, alturas[j][i]) con muestras cada ~`paso` m que cubren toda la extensión.
def rejilla_alturas(altura, extension, paso=PASO_TERRENO):
    xmin, xmax, zmin, zmax = extension
    nx = max(1, int(math.ceil((xmax - xmin) / paso)))
    nz = max(1, int(math.ceil((zmax - zmin) / paso)))
    xs = [xmin + (xmax - xmin) * i / nx for i in range(nx + 1)]
    zs = [zmin + (zmax - zmin) * j / nz for j in range(nz + 1)]
    return xs, zs, [[altura(x, z) for x in xs] for z in zs]


# Color (r, g, b, a) en 0-1 de la rampa para t en [0, 1] (interpolado entre paradas).
def color_de_rampa(t, rampa=RAMPA_TERRENO):
    t = max(0.0, min(1.0, t))
    for (t0, c0), (t1, c1) in zip(rampa, rampa[1:]):
        if t <= t1:
            f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return tuple((a + (b - a) * f) / 255 for a, b in zip(c0, c1)) + (1.0,)
    return tuple(c / 255 for c in rampa[-1][1]) + (1.0,)


# Un color por vértice de la rejilla: la rampa por altura relativa multiplicada por un sombreado de ladera (las laderas
# que miran al sol se aclaran y las contrarias se oscurecen), así el relieve se lee sin mallas de casas.
def colores_de_rejilla(xs, zs, alturas):
    bajo = min(min(f) for f in alturas)
    alto = max(max(f) for f in alturas)
    rango = (alto - bajo) or 1.0
    nz, nx = len(zs), len(xs)
    colores = []
    for j in range(nz):
        for i in range(nx):
            i0, i1, j0, j1 = max(0, i - 1), min(nx - 1, i + 1), max(0, j - 1), min(nz - 1, j + 1)
            dhdx = (alturas[j][i1] - alturas[j][i0]) / ((xs[i1] - xs[i0]) or 1.0)
            dhdz = (alturas[j1][i] - alturas[j0][i]) / ((zs[j1] - zs[j0]) or 1.0)
            sombra = -(dhdx * LUZ_X + dhdz * LUZ_Z) * FUERZA_SOMBRA
            sombra = max(-SOMBRA_MAX, min(SOMBRA_MAX, sombra))
            r, g, b, a = color_de_rampa((alturas[j][i] - bajo) / rango)
            k = (1.0 + sombra) * OSCURECER
            colores.append((min(1.0, r * k), min(1.0, g * k), min(1.0, b * k), a))
    return colores


# Triángulos (a, b, c) de la rejilla de nx x nz vértices (índice = j * nx + i).
def triangulos_de_rejilla(nx, nz):
    triangulos = []
    for j in range(nz - 1):
        for i in range(nx - 1):
            a = j * nx + i
            triangulos += [(a, a + 1, a + nx + 1), (a, a + nx + 1, a + nx)]
    return triangulos


# -- Lugares y etiquetas -------------------------------------------------------------------------------------------------

# Color de identidad del lugar (como Minimapa.color_de_lugar): nombre exacto, o la clave con la que empieza, o gris.
def color_de_lugar(lugar, colores, gris=(150, 152, 164)):
    if lugar in colores:
        return colores[lugar]
    for clave, tono in colores.items():
        if lugar.startswith(clave):
            return tono
    return gris


def _se_pisan(a, b):
    return abs(a[0] - b[0]) < (a[2] + b[2]) / 2 and abs(a[1] - b[1]) < (a[3] + b[3]) / 2


# Coloca etiquetas junto a sus marcas sin que se pisen entre sí, ni con otras marcas, ni salgan del área.
#   marcas: [(u, v, radio)]   etiquetas: [(ancho, alto)] (mismo orden)   area: (cx, cy, ancho, alto)
# Devuelve [(u, v, anillo)]: el CENTRO de cada etiqueta y el anillo en que cayó (0 = pegada a su marca; mayor = apartada,
# el que dibuja le pone una línea guía hasta la marca). Voraz por orden: para cada una prueba posiciones alrededor de su
# marca, de cerca a lejos (anillos) y en 12 direcciones (derecha primero), y se queda con la primera libre; si ninguna
# lo está, la que menos pisa.
ANILLOS_ETIQUETA = 4
DIRECCIONES_ETIQUETA = 12


def colocar_etiquetas(marcas, etiquetas, area, hueco=0.004):
    cx, cy, ancho, alto = area
    limites = (cx - ancho / 2, cx + ancho / 2, cy - alto / 2, cy + alto / 2)
    cajas_marcas = [(u, v, 2 * r, 2 * r) for u, v, r in marcas]
    puestas = []
    resultado = []
    for indice, ((u, v, r), (w, h)) in enumerate(zip(marcas, etiquetas)):
        mejor, mejor_costo = None, None
        for anillo in range(ANILLOS_ETIQUETA):
            d = r + hueco + anillo * h * 1.3
            for k in range(DIRECCIONES_ETIQUETA):
                angulo = 2 * math.pi * k / DIRECCIONES_ETIQUETA
                dx, dy = math.cos(angulo), math.sin(angulo)
                # el centro se aleja lo justo para que el borde de la etiqueta quede a distancia d de la marca
                pu = u + dx * (d + abs(dx) * w / 2)
                pv = v + dy * (d + abs(dy) * h / 2)
                caja = (pu, pv, w, h)
                costo = 0
                if pu - w / 2 < limites[0] or pu + w / 2 > limites[1] or pv - h / 2 < limites[2] or pv + h / 2 > limites[3]:
                    costo += 1000
                costo += 100 * sum(1 for otra in puestas if _se_pisan(caja, otra))
                costo += 100 * sum(1 for n, m in enumerate(cajas_marcas) if n != indice and _se_pisan(caja, m))
                costo += anillo * 2 + k * 0.1
                if mejor_costo is None or costo < mejor_costo:
                    mejor, mejor_costo = (pu, pv, anillo), costo
            if mejor_costo < 100:          # ya hay un hueco libre en este anillo: no se busca más lejos
                break
        puestas.append((mejor[0], mejor[1], w, h))
        resultado.append(mejor)
    return resultado


# Nombre corto de un lugar para su etiqueta en el mapa: la glosa en español si el nombre visible la trae («Cerro»), y si
# no el propio nombre recortado por palabras a `maximo` letras sin dejar «de/da/do» colgando.
def nombre_corto_mapa(visible, maximo=18):
    if visible.endswith(")") and "(" in visible:
        glosa = visible[visible.rindex("(") + 1:-1].strip()
        if glosa:
            return glosa
    palabras = visible.split()
    while len(" ".join(palabras)) > maximo and len(palabras) > 1:
        palabras.pop()
    while len(palabras) > 1 and palabras[-1].lower() in ("de", "da", "do", "dos", "das", "del", "la", "el"):
        palabras.pop()
    return " ".join(palabras)


# -- Ruta -----------------------------------------------------------------------------------------------------------------

# Puntos (x, z) de la ruta del GPS para dibujar: el jugador y cada lugar que falta. [] sin ruta.
def puntos_de_ruta(mundo, x, z, ruta):
    if not ruta:
        return []
    return [(x, z)] + [mundo.coordenada(lugar) for lugar in ruta]


# Distancia en metros redondeada a decenas (para el texto del encabezado: no parpadea con cada paso).
def metros_redondeados(metros):
    return int(round(metros / 10.0)) * 10
