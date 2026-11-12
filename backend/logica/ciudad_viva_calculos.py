# Ciudad viva: cómo LUCE la ciudad según el Ambiente (punto 5 del plan final, cambios FÍSICOS). Módulo PURO (sin ursina ni
# panda3d, sin importar frontend/): convierte un `Ambiente` (backend/logica/ambiente_ciudad.py) en parámetros de luz, cielo y
# niebla, y en «cantidades» (0..1) de basura, grafitis, flores, guirnaldas, faroles apagados y plazas con gente. Además
# trae lo geométrico que no necesita motor: sitios fijos con azar propio, rejilla espacial y reparto estable de ranuras.
# El frontend (frontend/ciudad_viva.py) solo dibuja lo que este módulo decide.
#
# GRADUALIDAD: nada aquí salta. El Ambiente ya llega suavizado (AmbienteSuave, τ = 30 s) y todas las curvas son continuas;
# la aparición/desaparición de objetos usa un umbral FIJO por sitio (`u`, sale de frontend/azar_fijo.azar_de) contra la
# cantidad, con histéresis, y un fundido de escala (`fundir`) de ~1,5 s. El mismo Ambiente da siempre la misma ciudad.
#
# ESCALA DE REFERENCIA: el arranque de partida es 50/50/50 (salud 0,5, nivel «sano»). Con salud 0,5 la luz, el cielo y la niebla
# son EXACTAMENTE los de antes de este módulo (factores = 1) y casi no hay basura ni adornos; hacia arriba la ciudad se vuelve
# cálida y se adorna; hacia abajo, fría, gris, sucia y con faroles apagados.

import math
from types import SimpleNamespace
from typing import NamedTuple

from backend.logica import ambiente_ciudad as ac
from backend.logica.azar_fijo import azar_de

# -- Luz, cielo y niebla ----------------------------------------------------------------------------------------------

SALUD_REFERENCIA = 0.5          # con esta salud todo queda como antes (factores = 1)
GANANCIA_TINTE = 1.6            # amplía la desviación del tinte de ambiente_ciudad.luz_ambiente (que es sutil)
GANANCIA_BRILLO_BAJA = 1.5      # y la del brillo cuando la ciudad se apaga
BRILLO_MAXIMO = 1.06            # tope de brillo de la luz con la ciudad sana: más y las plazas se vuelven blancas

# (salud, valor) del tinte multiplicativo del cielo (RGB): gris frío y apagado abajo, dorado un poco más cálido arriba.
TINTE_CIELO = ((0.0, (0.64, 0.74, 0.88)), (0.5, (1.0, 1.0, 1.0)), (1.0, (1.0, 0.975, 0.92)))
# (salud, factor) sobre la distancia de la niebla (más corta = cerrada) y sobre su fuerza (alfa).
FACTOR_FIN_NIEBLA = ((0.0, 0.55), (0.5, 1.0), (1.0, 1.15))
FACTOR_FUERZA_NIEBLA = ((0.0, 1.30), (0.5, 1.0), (1.0, 0.85))
FUERZA_NIEBLA_MAXIMA = 0.92


def _recortar(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def interpolar(puntos, x):
    """Interpolación lineal por tramos de ((x0, y0), (x1, y1), ...) (y puede ser un número o una tupla); fuera, se queda en el extremo."""
    if x <= puntos[0][0]:
        return puntos[0][1]
    for (x0, y0), (x1, y1) in zip(puntos, puntos[1:]):
        if x <= x1:
            t = (x - x0) / (x1 - x0)
            if isinstance(y0, tuple):
                return tuple(a + (b - a) * t for a, b in zip(y0, y1))
            return y0 + (y1 - y0) * t
    return puntos[-1][1]


def suave(x, a, b):
    """Suavizado (smoothstep) de x entre a y b: 0 con x <= a, 1 con x >= b; vale también con a > b (curva decreciente)."""
    if a == b:
        return 1.0 if x >= b else 0.0
    t = _recortar((x - a) / (b - a))
    return t * t * (3.0 - 2.0 * t)


def _byte(v):
    return int(round(_recortar(v, 0.0, 255.0)))


def factores_de_luz(amb):
    """(tinte (r, g, b), brillo): factores sobre la luz del sol y del ambiente RELATIVOS al arranque (salud 0,5 -> 1, 1, 1)."""
    ref = ac.luz_ambiente(SimpleNamespace(salud=SALUD_REFERENCIA))
    luz = ac.luz_ambiente(amb)
    tinte = tuple(1.0 + GANANCIA_TINTE * (luz["tinte"][i] / ref["tinte"][i] - 1.0) for i in range(3))
    brillo = luz["brillo"] / ref["brillo"]
    brillo = 1.0 + (GANANCIA_BRILLO_BAJA if brillo < 1.0 else 1.0) * (brillo - 1.0)
    return tinte, min(BRILLO_MAXIMO, brillo)


def atmosfera(amb, sol=(255, 232, 192), ambiente=(134, 124, 150), horizonte=(252, 208, 160), fin=260.0, fuerza=0.65):
    """Parámetros de luz, cielo y niebla para ese Ambiente, a partir de los valores BASE de la ciudad (los de siempre):
      sol, ambiente   color RGB 0-255 de la DirectionalLight y de la AmbientLight (la DIRECCIÓN del sol no se toca)
      cielo           factor RGB (0..1) que multiplica el color de la malla del cielo
      niebla_color    RGB 0-255 = horizonte x cielo: el horizonte del cielo y la niebla siguen siendo el mismo color (sin costura)
      niebla_fin      m a los que la niebla llega a su máximo;  niebla_fuerza = alfa del color de niebla (0..1)
    Con salud 0,5 devuelve exactamente los valores base."""
    s = _recortar(amb.salud)
    tinte, brillo = factores_de_luz(amb)
    cielo = tuple(round(c, 4) for c in interpolar(TINTE_CIELO, s))
    return {
        "sol": tuple(_byte(sol[i] * tinte[i] * brillo) for i in range(3)),
        "ambiente": tuple(_byte(ambiente[i] * tinte[i] * brillo) for i in range(3)),
        "cielo": cielo,
        "niebla_color": tuple(_byte(horizonte[i] * cielo[i]) for i in range(3)),
        "niebla_fin": round(fin * interpolar(FACTOR_FIN_NIEBLA, s), 2),
        "niebla_fuerza": round(min(FUERZA_NIEBLA_MAXIMA, fuerza * interpolar(FACTOR_FUERZA_NIEBLA, s)), 4),
    }


def cambio_apreciable(a, b, tol_color=1.0, tol_fin=1.0, tol_fuerza=0.01):
    """¿Difieren dos resultados de `atmosfera` lo bastante para volver a aplicarlos? (evita recorrer entidades por nada)."""
    if a is None or b is None:
        return True
    for clave in ("sol", "ambiente", "niebla_color"):
        if any(abs(x - y) >= tol_color for x, y in zip(a[clave], b[clave])):
            return True
    if any(abs(x - y) >= 0.004 for x, y in zip(a["cielo"], b["cielo"])):
        return True
    return abs(a["niebla_fin"] - b["niebla_fin"]) >= tol_fin or abs(a["niebla_fuerza"] - b["niebla_fuerza"]) >= tol_fuerza


# -- Cantidades (0..1) ------------------------------------------------------------------------------------------------

CAPAS = ("basura", "grafitis", "carteles", "flores", "marchitas", "guirnaldas", "apagados", "bancos", "corros")


def cantidades(amb):
    """Fracción (0..1) de los sitios de cada capa que deben estar «encendidos» con ese Ambiente. Continuo en el Ambiente.
      basura       bolsas, papeles y cajas en aceras y plazas                      (limpieza baja)
      grafitis     pintadas en las paredes de las calles                          (limpieza baja)
      carteles     carteles torcidos de «sin conexión»                            (salud baja)
      flores       macetas con flores vivas en plazas y esquinas                  (salud alta)
      marchitas    las mismas macetas, secas                                       (salud baja)
      guirnaldas   guirnaldas con banderines y bombillas cálidas entre farolas    (salud alta)
      apagados     farolas apagadas                                                (salud baja)
      bancos       bancos de plaza ocupados                                        (actividad de plazas)
      corros       grupos de gente charlando en las plazas                         (actividad de plazas alta)"""
    s = _recortar(amb.salud)
    limpieza = ac.limpieza(amb)
    actividad = ac.actividad_plazas(amb)
    return {
        "basura": suave(limpieza, 0.62, 0.12),
        "grafitis": suave(limpieza, 0.45, 0.05),
        "carteles": suave(s, 0.35, 0.05),
        "flores": suave(s, 0.55, 0.90),
        "marchitas": suave(s, 0.42, 0.12),
        "guirnaldas": suave(s, 0.62, 0.90),
        "apagados": 0.85 * suave(s, 0.40, 0.10),
        "bancos": suave(actividad, 0.20, 0.80),
        "corros": suave(actividad, 0.55, 0.90),
    }


# -- Umbral fijo, histéresis y fundido --------------------------------------------------------------------------------

MARGEN_HISTERESIS = 0.03        # fracción de cantidad que hay que pasar para cambiar de estado un sitio
SEGUNDOS_FUNDIDO = 1.5          # de 0 a 1 de escala (y de vuelta)


def azar_sitio(x, z, sal):
    """Número fijo en [0, 1) del sitio (x, z) para la capa de semilla `sal` (el mismo siempre; no usa random ni hash())."""
    return azar_de(x * 0.731 + sal * 17.13, z * 1.317 - sal * 5.71)


def encendido(u, cantidad, estaba, margen=MARGEN_HISTERESIS):
    """¿Debe estar encendido un sitio de umbral `u` con esa `cantidad`? Histéresis: encendido sigue hasta que u >= cantidad +
    margen; apagado vuelve a encenderse solo cuando u < cantidad - margen. Con cantidad 0 nunca; con 1 siempre."""
    if cantidad <= 0.0:
        return False
    if cantidad >= 1.0:
        return True
    return u < cantidad + margen if estaba else u < cantidad - margen


def fundir(actual, objetivo, dt, segundos=SEGUNDOS_FUNDIDO):
    """Acerca `actual` a `objetivo` (0..1) a razón de 1/segundos por segundo, sin pasarse."""
    paso = max(0.0, dt) / segundos
    if actual < objetivo:
        return min(objetivo, actual + paso)
    return max(objetivo, actual - paso)


def escala_fundida(f):
    """Escala visual (0..1) de un fundido f en 0..1: sale suave (smoothstep), no lineal."""
    return f * f * (3.0 - 2.0 * f)


# -- Sitios -----------------------------------------------------------------------------------------------------------


class Sitio(NamedTuple):
    x: float
    z: float
    giro: float        # grados (rotation_y de Ursina) hacia donde «mira» el objeto
    u: float           # umbral fijo 0..1 de este sitio
    v: int             # variante estable (elige el modelo)


def sitios_de_borde(segmentos, ancho_calle, radio_plaza, paso=6.0, acera=2.0, sal=1.0):
    """Puntos sobre las aceras (ambos lados) de cada calle `segmentos` = [((ax, az), (bx, bz))], cada ~`paso` m con un
    desplazamiento fijo, sin entrar en el disco de las plazas de los extremos. Devuelve [Sitio] con giro = rumbo de la calle."""
    sitios = []
    semiancho = ancho_calle / 2.0
    for (ax, az), (bx, bz) in segmentos:
        largo = math.hypot(bx - ax, bz - az)
        if largo < 1e-9:
            continue
        ux, uz = (bx - ax) / largo, (bz - az) / largo
        nx, nz = -uz, ux
        giro = math.degrees(math.atan2(ux, uz))
        s = radio_plaza + 1.5
        k = 0
        while s < largo - radio_plaza - 1.5:
            for lado in (-1, 1):
                k += 1
                ds = s + (azar_de(k * 0.37 + ax, lado + az) - 0.5) * paso * 0.7
                d = lado * (semiancho + acera * (0.25 + 0.5 * azar_de(ds + bx, lado * 2.3 + bz)))
                x, z = ax + ux * ds + nx * d, az + uz * ds + nz * d
                v = int(azar_de(x, z) * 1000)
                sitios.append(Sitio(round(x, 3), round(z, 3), round((giro + 360 * azar_de(z, x * 0.5)) % 360, 1),
                                    azar_sitio(x, z, sal), v))
            s += paso
    return sitios


def sitios_de_plaza(centro, radio_plaza, cantidad=10, sal=1.0, escalon=0.0):
    """`cantidad` puntos en un anillo dentro de la plaza (entre 55 % y 92 % del radio), repartidos con azar fijo."""
    cx, cz = centro
    arranque = 360.0 * azar_de(cx + 1.7, cz - 2.9)
    sitios = []
    for k in range(cantidad):
        a = math.radians(arranque + k * 360.0 / cantidad + 11.0 * (azar_de(cx + k, cz) - 0.5))
        r = radio_plaza * (0.55 + 0.37 * azar_de(cx - k, cz + k * 0.7 + escalon))
        x, z = cx + r * math.cos(a), cz + r * math.sin(a)
        sitios.append(Sitio(round(x, 3), round(z, 3), round(math.degrees(a) % 360, 1), azar_sitio(x, z, sal), int(azar_de(x, z) * 1000)))
    return sitios


class Pared(NamedTuple):
    x: float
    z: float
    nx: float          # normal que sale de la pared (eje x o z, ±1)
    nz: float
    y0: float          # suelo bajo la pared
    u: float
    v: int


def paredes_de_calle(casas, segmentos, ancho_calle, suelo, distancia_max=9.0, sal=3.0, piso=None):
    """Una pared candidata por casa que mira a una calle: la cara de la caja alineada que más apunta al punto más cercano de
    la calle, a menos de `distancia_max` m del borde de la acera. `casas` = [(cx, cz, ancho, fondo)]; `suelo(x, z)` = altura.
    `piso(cx, cz, ancho, fondo)` (opcional) da la altura del piso de la casa (sobre pilotes o zócalo); sin él, el suelo bajo la pared.
    Devuelve [Pared] con un desplazamiento lateral fijo (no siempre en el centro de la cara)."""
    paredes = []
    semiancho = ancho_calle / 2.0 + 2.0
    for cx, cz, ancho, fondo in casas:
        mejor = None
        for (ax, az), (bx, bz) in segmentos:
            dx, dz = bx - ax, bz - az
            l2 = dx * dx + dz * dz
            t = 0.0 if l2 < 1e-12 else _recortar(((cx - ax) * dx + (cz - az) * dz) / l2)
            px, pz = ax + dx * t, az + dz * t
            d = math.hypot(cx - px, cz - pz)
            if mejor is None or d < mejor[0]:
                mejor = (d, px, pz)
        if mejor is None:
            continue
        d, px, pz = mejor
        if d - max(ancho, fondo) / 2.0 - semiancho > distancia_max or d < 1e-9:
            continue
        vx, vz = (px - cx) / d, (pz - cz) / d              # de la casa hacia la calle
        # La cara más enfrentada: compara cuánto apunta cada cara hacia la calle, normalizando por la mitad de su lado.
        if abs(vx) * fondo >= abs(vz) * ancho:
            nx, nz = (1.0 if vx > 0 else -1.0), 0.0
        else:
            nx, nz = 0.0, (1.0 if vz > 0 else -1.0)
        lateral = (azar_de(cx, cz + 5.1) - 0.5) * 0.6 * (fondo if nx else ancho)
        x = cx + nx * ancho / 2.0 + (lateral if nz else 0.0)
        z = cz + nz * fondo / 2.0 + (lateral if nx else 0.0)
        y0 = suelo(x, z) if piso is None else piso(cx, cz, ancho, fondo)
        paredes.append(Pared(round(x, 3), round(z, 3), nx, nz, round(y0, 3), azar_sitio(cx, cz, sal), int(azar_de(cz, cx) * 1000)))
    return paredes


def pares_de_farolas(farolas, distancia_min=6.0, distancia_max=24.0, maximo_por_farola=2):
    """Pares (a, b) de farolas vecinas (índices en `farolas` = [(x, z)]) a una distancia entre los límites, cada farola en a lo
    sumo `maximo_por_farola` pares y sin repetir. Sirve para colgar guirnaldas entre ellas."""
    rejilla = Rejilla(celda=distancia_max)
    for i, (x, z) in enumerate(farolas):
        rejilla.agregar(x, z, i)
    usados = [0] * len(farolas)
    pares = []
    for i, (x, z) in enumerate(farolas):
        cercanas = sorted((math.hypot(farolas[j][0] - x, farolas[j][1] - z), j) for j in rejilla.cerca(x, z, distancia_max) if j > i)
        for d, j in cercanas:
            if usados[i] >= maximo_por_farola:
                break
            if d < distancia_min or d > distancia_max or usados[j] >= maximo_por_farola:
                continue
            pares.append((i, j))
            usados[i] += 1
            usados[j] += 1
    return pares


# -- Rejilla espacial y reparto estable de ranuras ---------------------------------------------------------------------


class Rejilla:
    """Rejilla de celdas cuadradas de `celda` m: `cerca(x, z, r)` da los objetos de las celdas que toca el círculo."""

    def __init__(self, celda=24.0):
        self.celda = float(celda)
        self._celdas = {}
        self.cantidad = 0

    def _clave(self, x, z):
        return (int(math.floor(x / self.celda)), int(math.floor(z / self.celda)))

    def agregar(self, x, z, objeto):
        self._celdas.setdefault(self._clave(x, z), []).append(objeto)
        self.cantidad += 1

    def cerca(self, x, z, radio):
        c0 = self._clave(x - radio, z - radio)
        c1 = self._clave(x + radio, z + radio)
        for i in range(c0[0], c1[0] + 1):
            for j in range(c0[1], c1[1] + 1):
                yield from self._celdas.get((i, j), ())


def elegir_sitios(candidatos, x, z, radio, cantidad, estado_previo, maximo):
    """De `candidatos` = [(indice, sx, sz, u)] elige los índices que deben estar visibles: a menos de `radio` m de (x, z)
    (histéresis de 15 % para los que ya lo estaban, en `estado_previo` = conjunto de índices), con `encendido(u, cantidad)`,
    los `maximo` más cercanos. Devuelve la lista ordenada por distancia."""
    r2, r2_sale = radio * radio, (radio * 1.15) ** 2
    pasan = []
    for i, sx, sz, u in candidatos:
        estaba = i in estado_previo
        d2 = (sx - x) ** 2 + (sz - z) ** 2
        if d2 > (r2_sale if estaba else r2):
            continue
        if encendido(u, cantidad, estaba):
            pasan.append((d2, i))
    pasan.sort()
    return [i for _, i in pasan[:maximo]]


class Ranuras:
    """Reparto ESTABLE de una piscina fija de `n` ranuras entre sitios: un sitio que ya tiene ranura la conserva mientras se
    quiera; los nuevos toman ranuras libres; una ranura cuyo sitio ya no se quiere se funde (estado f -> 0) y solo se libera
    al llegar a 0 (así nada desaparece de golpe). Puro: no sabe de entidades, solo de índices de ranura."""

    def __init__(self, n):
        self.n = n
        self.sitio = [None] * n          # índice de sitio en la ranura (o None)
        self.f = [0.0] * n               # fundido 0..1
        self.quiere = [False] * n

    def actualizar(self, deseados):
        """Fija qué sitios se quieren ahora (iterable de índices, por prioridad). Devuelve las ranuras que cambiaron de sitio
        (nuevas) como [(ranura, sitio)]."""
        deseados = list(deseados)
        quedan = set(deseados)
        por_sitio = {s: k for k, s in enumerate(self.sitio) if s is not None}
        for k, s in enumerate(self.sitio):
            self.quiere[k] = s is not None and s in quedan
        nuevas = []
        libres = [k for k, s in enumerate(self.sitio) if s is None]
        for s in deseados:
            if s in por_sitio:
                continue
            if not libres:
                break
            k = libres.pop(0)
            self.sitio[k] = s
            self.f[k] = 0.0
            self.quiere[k] = True
            por_sitio[s] = k
            nuevas.append((k, s))
        return nuevas

    def avanzar(self, dt, segundos=SEGUNDOS_FUNDIDO):
        """Un paso de fundido. Devuelve [(ranura, liberada)] de las ranuras cuyo fundido cambió; `liberada` es True si
        terminó de apagarse y quedó libre."""
        cambios = []
        for k in range(self.n):
            if self.sitio[k] is None:
                continue
            objetivo = 1.0 if self.quiere[k] else 0.0
            nuevo = fundir(self.f[k], objetivo, dt, segundos)
            if nuevo <= 0.0 and not self.quiere[k]:
                self.f[k] = 0.0
                self.sitio[k] = None
                cambios.append((k, True))
            elif nuevo != self.f[k]:
                self.f[k] = nuevo
                cambios.append((k, False))
        return cambios

    def animando(self):
        return any(s is not None and self.f[k] != (1.0 if self.quiere[k] else 0.0) for k, s in enumerate(self.sitio))

    def ocupadas(self):
        return sum(1 for s in self.sitio if s is not None)
