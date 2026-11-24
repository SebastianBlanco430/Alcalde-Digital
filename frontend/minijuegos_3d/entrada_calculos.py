# Cálculos PUROS (sin ursina) de la ENTRADA y la SALIDA animadas de los minijuegos 3D (sesión B, Módulo 3; bandera
# ALCALDE_ANIM_SILLA). Los usan sets.py (dónde va la silla), base.py (decisión de camino, punto de partida, costura) y
# se prueban en tests/test_entrada_minijuegos_calculos.py.
#
# Geometría (metros, mundo; rumbo en grados: 0 = mira a +z, 90 = mira a +x, como Personaje.fijar_rumbo):
#   - oficina (EscenaInterior, set «interior» / «cuarto_pc»): escritorio x 0,3..2,1 · z 1,6..2,4 · tablero 0,755;
#     la silla del PC centrada en ASIENTO; sala x ±3 · z ±2,5.
#   - cuarto_mesa (sets._set_cuarto_mesa): mesa x ±0,85 · z 0,1..1,1 · tablero 0,78; sala x ±2,5 · z ±2,3.
# Una silla se describe con un dict con las claves de cinematica_silla_calculos.Silla (posicion, rumbo, altura_asiento,
# altura_respaldo, retiro, lado, suelo_y) y una mesa con las de Mesa (altura, borde, manos): sets.py los convierte en los
# dataclasses del contrato cuando el módulo existe.

import math

# -- Claves de «ya la vio» (guion.md: pc, mesa, corcho; la salida con sufijo _salida) --
CLAVES = {"pc": "pc", "mesa": "mesa", "corcho": "corcho"}
FAMILIAS_SILLA = ("pc", "mesa")

# -- Silla estándar (la de la oficina: asiento 0,48 x 0,48 a 0,45 m, respaldo 0,55 m de alto 0,22 m detrás) --
MEDIO_FONDO_ASIENTO = 0.24          # m del centro del asiento a su canto delantero
ATRAS_RESPALDO = 0.25               # m del centro del asiento a la cara de atrás del respaldo
ALTURA_ASIENTO = 0.485              # cara de arriba del asiento (cubo de 0,07 centrado a 0,45)
ALTURA_RESPALDO = 1.055             # borde de arriba del respaldo (cubo de 0,55 centrado a 0,78)
RETIRO = 0.45                       # m que se desliza hacia atrás al sacarla (guion.md)
HOLGURA_MESA = 0.06                 # m mínimos entre el canto delantero del asiento acomodado y el canto de la mesa
MARGEN_PARED = 0.15                 # m del respaldo retirado (y de la cámara) a la pared

# -- Oficina (copia de los números de frontend/guion_cinematicas.py y EscenaInterior._escritorio) --
OFICINA_LIMITES = (-3.0, 3.0, -2.5, 2.5)            # x0, x1, z0, z1 (caras interiores de las paredes)
OFICINA_MESA = {"x": (0.3, 2.1), "z": (1.6, 2.4), "altura": 0.755}

# -- cuarto_mesa (copia de sets._set_cuarto_mesa / _set_base) --
CUARTO_LIMITES = (-2.5, 2.5, -2.3, 2.3)
CUARTO_MESA = {"x": (-0.85, 0.85), "z": (0.1, 1.1), "altura": 0.78}
# Dónde se SIENTA cada minijuego de mesa (decisión de Sam: en la mesa se juega sentado). Comparar: borde cercano, a la
# izquierda (donde estaba de pie, PIE_MESA, pero de frente a la mesa: la cámara alta lo deja fuera de cuadro y no tapa
# los papeles). Señales: al otro lado de la mesa, de cara a la cámara (donde estaba de pie, PIE_SENALES), un poco más al
# centro para que la mano del plumón llegue a más zonas de la captura.
SILLAS_MESA = {
    # Comparar: las palmas cerca del canto, a los lados (no sobre el pie de la hoja ORIGINAL, que empieza en z ~0,24)
    "comparar": {"posicion": (-0.45, -0.25), "rumbo": 0.0, "lado": "i",
                 "manos": {"d": (-0.27, 0.17), "i": (-0.65, 0.17)}},
    # Señales: las manos se apoyan FUERA de la captura (x ±0,35 en la banda del fondo) y de la nota «PISTA» (x >= 0,45):
    # la derecha (lado -x) a la izquierda de la captura y la izquierda entre la captura y la nota.
    # Sesión H: con el atril (ATRIL_SENALES) la derecha termina en el canto de la mesa, delante del pie del atril (el
    # plumón la lleva enseguida); la izquierda apoyada a la izquierda del atril (que no pasa de x 0,15), al alcance
    # también de la influencer
    "senales": {"posicion": (0.0, 1.40), "rumbo": 180.0, "lado": "d",
                "manos": {"d": (-0.20, 1.08), "i": (0.28, 1.08)}},
}
# Minijuegos de mesa que se juegan SENTADOS con la entrada nueva. Señales sentado estuvo apagado hasta la sesión H: con
# la captura plana sobre la mesa a la mano del plumón le faltaban 0,26 m (0,40 m la influencer). Se cambió el SET, no el
# personaje: sentado, la captura va en un ATRIL inclinado hacia el jugador, delante de su hombro derecho y más pequeña
# (ATRIL_SENALES); así llega a todas las zonas con los 4 protagonistas (falta_alcance_senales(..., atril=...)).
MESA_SENTADO = ("comparar", "senales")
# Atril de Señales sentado (mundo del cuarto_mesa). La captura (senales_3d.CAPTURA, en m de hoja) se monta escalada
# `escala` sobre una tabla inclinada `inclinacion` grados sobre la mesa, con la cara hacia el jugador (rumbo 180, +z):
# su canto de abajo (el del jugador) en z = `borde_z`, `base` m sobre el tablero (el reborde que la sostiene), centrada
# en x = `x` (delante del hombro derecho del sentado: x = -HOMBRO_LADO). Búsqueda en sesiones-24nov/detalles-h: con
# 60° y escala 0,65 a los 4 les sobran >= 2 cm; más grande o menos inclinado, la influencer (brazo 0,43 m) no llega.
ATRIL_SENALES = {"x": -0.18, "borde_z": 1.06, "base": 0.02, "inclinacion": 60.0, "escala": 0.65}
# Manos al terminar de sentarse (sobre el tablero, 12 cm dentro del canto cercano, ±0,16 m del centro del asiento)
MANOS_DENTRO = 0.12
MANOS_LADO = 0.16
MANOS_ALTO = 0.025                  # m sobre el tablero (la palma apoyada; nunca por debajo de altura + 2 cm)

# -- Corcho --
CORCHO_PIE_DISTANCIA = 0.42         # m del corcho a los pies al tocar la nota (el brazo de la influencer, ~0,43 m, llega)
CORCHO_PIE_LATERAL = 0.05           # m a la izquierda del borde izquierdo del corcho (no tapa el corcho al llegar)
CORCHO_NOTA_DENTRO = 0.12           # m dentro del borde izquierdo: la nota que toca
CORCHO_NOTA_ALTURA = 1.35           # y de mundo de la nota (a la altura del hombro)
CORCHO_PARTIDA = 2.2                # m delante del corcho donde empieza (bajo el fundido)
MARGEN_PARTIDA = 0.4                # m de las paredes al punto de partida

# -- Costura entrada -> juego --
TOLERANCIA_COSTURA = 1e-6           # m / grados: la última cámara de la entrada ES toma_juego()


def _adelante(rumbo):
    r = math.radians(rumbo)
    return (math.sin(r), math.cos(r))


def _izquierda(rumbo):
    """Izquierda (x, z) de quien mira a `rumbo` (derecha = (cos, -sin), como poses_3d._ejes)."""
    r = math.radians(rumbo)
    return (-math.cos(r), math.sin(r))


def finito(p):
    try:
        return p is not None and all(math.isfinite(float(c)) for c in p)
    except (TypeError, ValueError):
        return False


# -- Distancias en planta --

def distancia_a_rect(posicion, rumbo, rect):
    """Metros desde `posicion` (x, z) hasta el borde del rectángulo `rect` ({"x": (x0, x1), "z": (z0, z1)}) avanzando a lo
    largo de `rumbo`. None si el rayo no lo toca (o si la posición ya está dentro)."""
    ax, az = _adelante(rumbo)
    (x0, x1), (z0, z1) = rect["x"], rect["z"]
    px, pz = posicion
    if x0 <= px <= x1 and z0 <= pz <= z1:
        return None
    tmin, tmax = 0.0, math.inf
    for p, d, lo, hi in ((px, ax, x0, x1), (pz, az, z0, z1)):
        if abs(d) < 1e-9:
            if not lo <= p <= hi:
                return None
            continue
        t1, t2 = (lo - p) / d, (hi - p) / d
        tmin, tmax = max(tmin, min(t1, t2)), min(tmax, max(t1, t2))
    if tmin > tmax:
        return None
    return tmin


def dentro(punto, limites, margen=0.0):
    x0, x1, z0, z1 = limites
    return x0 + margen <= punto[0] <= x1 - margen and z0 + margen <= punto[1] <= z1 - margen


def acotar(punto, limites, margen=0.0):
    x0, x1, z0, z1 = limites
    return (min(max(punto[0], x0 + margen), x1 - margen), min(max(punto[1], z0 + margen), z1 - margen))


# -- Sillas y mesas --

def silla(posicion, rumbo, lado="i", retiro=RETIRO):
    return {"posicion": (float(posicion[0]), float(posicion[1])), "rumbo": float(rumbo), "altura_asiento": ALTURA_ASIENTO,
            "altura_respaldo": ALTURA_RESPALDO, "retiro": float(retiro), "lado": lado, "suelo_y": 0.0}


def retiro_que_cabe(posicion, rumbo, limites, retiro=RETIRO, margen=MARGEN_PARED):
    """El retiro, recortado para que la cara de atrás del respaldo de la silla retirada no pase de la pared (guion.md:
    «si retiro no cabe, se recorta»)."""
    ax, az = _adelante(rumbo)
    r = float(retiro)
    while r > 0:
        atras = r + ATRAS_RESPALDO
        if dentro((posicion[0] - ax * atras, posicion[1] - az * atras), limites, margen):
            return r
        r = round(r - 0.01, 4)
    return 0.0


def mesa(altura, borde, manos=None):
    return {"altura": float(altura), "borde": float(borde), "manos": manos}


def manos_sobre_tablero(posicion, rumbo, borde, altura, dentro_m=MANOS_DENTRO, lado_m=MANOS_LADO, alto=MANOS_ALTO):
    """{"i": (x, y, z), "d": (x, y, z)} con las palmas `dentro_m` m dentro del canto cercano y ±`lado_m` m del eje."""
    ax, az = _adelante(rumbo)
    ix, iz = _izquierda(rumbo)
    d = borde + dentro_m
    cx, cz = posicion[0] + ax * d, posicion[1] + az * d
    y = altura + alto
    return {"i": (cx + ix * lado_m, y, cz + iz * lado_m), "d": (cx - ix * lado_m, y, cz - iz * lado_m)}


def silla_pc(asiento, adelante_sentado):
    """Silla de la oficina con el asiento ACOMODADO donde hoy se sienta el personaje del 3D (ASIENTO + ADELANTE_SENTADO
    hacia el escritorio). `asiento` = (x, z, rumbo) de set.asiento."""
    x, z, rumbo = asiento
    ax, az = _adelante(rumbo)
    pos = (x + ax * adelante_sentado, z + az * adelante_sentado)
    return silla(pos, rumbo, "i", retiro_que_cabe(pos, rumbo, OFICINA_LIMITES))


def mesa_pc(silla_desc, manos):
    """Mesa del escritorio de la oficina para `silla_desc`; `manos` = {"i": teclado, "d": ratón} (los de imitar_pc)."""
    borde = distancia_a_rect(silla_desc["posicion"], silla_desc["rumbo"], OFICINA_MESA)
    return mesa(OFICINA_MESA["altura"], borde if borde is not None else 0.35, manos)


def silla_mesa(minijuego_id):
    """Silla del cuarto_mesa para Comparar / Señales (None para otro id)."""
    datos = SILLAS_MESA.get(minijuego_id)
    if datos is None:
        return None
    return silla(datos["posicion"], datos["rumbo"], datos["lado"],
                 retiro_que_cabe(datos["posicion"], datos["rumbo"], CUARTO_LIMITES))


def mesa_cuarto(silla_desc, minijuego_id=None):
    borde = distancia_a_rect(silla_desc["posicion"], silla_desc["rumbo"], CUARTO_MESA)
    borde = borde if borde is not None else 0.35
    propias = (SILLAS_MESA.get(minijuego_id) or {}).get("manos")
    if propias:
        y = CUARTO_MESA["altura"] + MANOS_ALTO
        manos = {lado: (float(x), y, float(z)) for lado, (x, z) in propias.items()}
    else:
        manos = manos_sobre_tablero(silla_desc["posicion"], silla_desc["rumbo"], borde, CUARTO_MESA["altura"])
    return mesa(CUARTO_MESA["altura"], borde, manos)


def asiento_no_toca_mesa(silla_desc, mesa_desc, holgura=HOLGURA_MESA):
    """¿El canto delantero del asiento acomodado queda a `holgura` m o más del canto de la mesa?"""
    return mesa_desc["borde"] - MEDIO_FONDO_ASIENTO >= holgura - 1e-9


def respaldo_retirado(silla_desc):
    """(x, z) de la cara de atrás del respaldo con la silla retirada del todo."""
    ax, az = _adelante(silla_desc["rumbo"])
    atras = silla_desc["retiro"] + ATRAS_RESPALDO
    x, z = silla_desc["posicion"]
    return (x - ax * atras, z - az * atras)


def partida_silla(silla_desc, limites, atras=1.2, lado_m=0.55, margen=MARGEN_PARTIDA):
    """Copia de cinematica_silla.punto_de_partida (1,2 m detrás y 0,55 m al lado `lado`, mirando hacia el respaldo),
    acotada para quedar DENTRO de la sala (en Señales la silla está a 0,9 m de la pared de atrás). (x, z, rumbo)."""
    ax, az = _adelante(silla_desc["rumbo"])
    ix, iz = _izquierda(silla_desc["rumbo"])
    s = 1.0 if silla_desc["lado"] == "i" else -1.0
    x, z = silla_desc["posicion"]
    p = (x - ax * atras + ix * lado_m * s, z - az * atras + iz * lado_m * s)
    p = acotar(p, limites, margen)
    rumbo = math.degrees(math.atan2(x - p[0], z - p[1]))
    return (p[0], p[1], rumbo)


# -- Corcho --

def corcho_pie_y_nota(centro, normal, derecha, ancho):
    """Pie (x, z) y nota (x, y, z) para acercarse_a_corcho. `centro`, `normal` (hacia la sala) y `derecha` (+x local del
    ancla, a la derecha de quien mira el corcho) en mundo. El pie queda junto al borde izquierdo (no tapa el corcho) y la
    mano toca una nota 12 cm dentro de ese borde, a la altura del hombro."""
    n = _unit2((normal[0], normal[2]))
    r = _unit2((derecha[0], derecha[2]))
    borde = -ancho / 2
    pie = (centro[0] + r[0] * (borde - CORCHO_PIE_LATERAL) + n[0] * CORCHO_PIE_DISTANCIA,
           centro[2] + r[1] * (borde - CORCHO_PIE_LATERAL) + n[1] * CORCHO_PIE_DISTANCIA)
    nota = (centro[0] + r[0] * (borde + CORCHO_NOTA_DENTRO), CORCHO_NOTA_ALTURA,
            centro[2] + r[1] * (borde + CORCHO_NOTA_DENTRO))
    return pie, nota


def partida_corcho(pie, normal, limites, distancia=CORCHO_PARTIDA - CORCHO_PIE_DISTANCIA, margen=MARGEN_PARTIDA):
    """(x, z, rumbo) a `distancia` m del pie hacia la sala (2,2 m del corcho), dentro de la sala, mirando al pie."""
    n = _unit2((normal[0], normal[2]))
    p = acotar((pie[0] + n[0] * distancia, pie[1] + n[1] * distancia), limites, margen)
    return (p[0], p[1], math.degrees(math.atan2(pie[0] - p[0], pie[1] - p[1])))


def _unit2(v):
    n = math.hypot(v[0], v[1]) or 1.0
    return (v[0] / n, v[1] / n)


# -- Costura y decisión de camino --

def costura(camara, toma):
    """(metros, grados de fov) entre la cámara `camara` y la toma `toma` (dicts {"position", "target", "fov"})."""
    return (math.dist(tuple(camara["position"]), tuple(toma["position"])) + math.dist(tuple(camara["target"]),
                                                                                       tuple(toma["target"])),
            abs(float(camara["fov"]) - float(toma["fov"])))


def sin_costura(camara, toma, tolerancia=TOLERANCIA_COSTURA):
    m, g = costura(camara, toma)
    return m <= tolerancia and g <= tolerancia


def camino_entrada(bandera, modulo, familia, descriptores):
    """'nueva' (cinemática de cinematica_silla dentro del 3D) o 'hoy'. Nueva solo con la bandera encendida, el módulo
    importado, una familia conocida y sus descriptores (silla+mesa en pc/mesa, corcho en corcho)."""
    if not (bandera and modulo) or familia not in CLAVES:
        return "hoy"
    return "nueva" if descriptores else "hoy"


def previa_tras_entrada(familia, animada):
    """¿La previa «Antes de empezar» va DESPUÉS de la entrada animada? (sesión E, pendiente de B). Solo corcho y mesa con
    la entrada nueva: el fundido va directo a la animación 3D y la previa sale cuando termina. El PC ya la enseña en el
    monitor mientras se sienta; con la bandera en 0, la de hoy (previa 2D antes del 3D)."""
    return bool(animada) and familia in ("corcho", "mesa")


# -- Alcance de la mano del plumón en Señales SENTADO (sesión E: por qué Señales sigue de pie) --
ALTO_CADERA_DE_PIE = 0.93           # m: el hombro sentado = asiento + (hombro de pie - cadera de pie)
HOMBRO_LADO = 0.18                  # m del centro del pecho al hombro
MANO_SOBRE_PUNTA = 0.11             # como Senales3D._mano_para: la mano 11 cm encima de la punta...
MANO_HACIA_EL_CUERPO = 0.08         # ...y 8 cm hacia el cuerpo


def atril_normal(atril=None):
    """Normal (mundo) de la cara del atril: hacia arriba y hacia el jugador (+z)."""
    t = math.radians((atril or ATRIL_SENALES)["inclinacion"])
    return (0.0, math.cos(t), math.sin(t))


def atril_arriba(atril=None):
    """Dirección (mundo) «hacia arriba» de la hoja en el atril: sube y se aleja del jugador (-z)."""
    t = math.radians((atril or ATRIL_SENALES)["inclinacion"])
    return (0.0, math.sin(t), -math.cos(t))


def atril_centro(captura, atril=None):
    """Centro (mundo) de la captura montada en el atril."""
    return atril_punto(0.0, 0.0, captura, atril)


def atril_punto(u, v, captura, atril=None):
    """Punto (u, v) de la captura (m de hoja; u = x de la hoja, v = y de la hoja, centro = 0) -> mundo, en el atril. La
    hoja mira al jugador: su +x va hacia -x de mundo (se lee desde detrás del jugador) y su +y sube por la tabla."""
    a = atril or ATRIL_SENALES
    t = math.radians(a["inclinacion"])
    k = a["escala"]
    d = k * (v + captura["alto"] / 2)                   # m por la tabla desde el canto de abajo
    return (a["x"] - k * u, CUARTO_MESA["altura"] + a["base"] + d * math.sin(t), a["borde_z"] - d * math.cos(t))


def falta_alcance_senales(alcance, alto_hombro, captura, silla_id="senales", atril=None, puntos=None):
    """Cuánto le falta (m, 0 = llega) a la mano derecha, sentada en la silla de Señales, para llevar la punta del plumón
    a las 4 esquinas y al centro de `captura` ({"centro": (x, y) del tablero, "ancho", "alto"}; y = hacia el fondo, +z
    de mundo, como el ancla «mesa» del cuarto_mesa; «_i» = x menor). Sin inclinar el torso (Senales3D no lo inclina).
    Con `atril` (p. ej. ATRIL_SENALES) la captura va montada en el atril (atril_punto) y la mano se separa por su normal;
    `puntos` = {nombre: (u, v)} extra en m de hoja (p. ej. el punto más lejano de cada zona)."""
    if atril is not None:
        return _falta_en_atril(alcance, alto_hombro, captura, silla_id, atril, puntos)
    datos = SILLAS_MESA[silla_id]
    sx, sz = datos["posicion"]
    ax, az = _adelante(datos["rumbo"])
    dx_, dz_ = az, -ax                                     # derecha del sentado (rumbo 0 = +z -> derecha +x)
    hombro = (sx + dx_ * HOMBRO_LADO, ALTURA_ASIENTO + alto_hombro - ALTO_CADERA_DE_PIE, sz + dz_ * HOMBRO_LADO)
    mesa_z = sum(CUARTO_MESA["z"]) / 2
    cx, cy = captura["centro"]
    w, h = captura["ancho"] / 2, captura["alto"] / 2
    puntos = {"centro": (cx, cy), "lejos_i": (cx - w, cy - h), "lejos_d": (cx + w, cy - h),
              "cerca_i": (cx - w, cy + h), "cerca_d": (cx + w, cy + h)}
    faltas = {}
    for nombre, (px, py) in puntos.items():
        punta = (px, CUARTO_MESA["altura"], mesa_z + py)
        mano = (punta[0] - ax * MANO_HACIA_EL_CUERPO, punta[1] + MANO_SOBRE_PUNTA, punta[2] - az * MANO_HACIA_EL_CUERPO)
        faltas[nombre] = round(max(0.0, math.dist(hombro, mano) - alcance), 3)
    return faltas


def _hombro_derecho_sentado(alto_hombro, silla_id):
    datos = SILLAS_MESA[silla_id]
    sx, sz = datos["posicion"]
    ax, az = _adelante(datos["rumbo"])
    return (sx + az * HOMBRO_LADO, ALTURA_ASIENTO + alto_hombro - ALTO_CADERA_DE_PIE, sz - ax * HOMBRO_LADO), (ax, az)


def _falta_en_atril(alcance, alto_hombro, captura, silla_id, atril, puntos):
    hombro, (ax, az) = _hombro_derecho_sentado(alto_hombro, silla_id)
    n = atril_normal(atril)
    w, h = captura["ancho"] / 2, captura["alto"] / 2
    # «_i» = x de MUNDO menor, como en la captura plana (la hoja del atril tiene su +x hacia -x de mundo)
    todos = {"centro": (0.0, 0.0), "lejos_i": (w, h), "lejos_d": (-w, h), "cerca_i": (w, -h), "cerca_d": (-w, -h)}
    todos.update(puntos or {})
    faltas = {}
    for nombre, (u, v) in todos.items():
        p = atril_punto(u, v, captura, atril)
        mano = (p[0] + n[0] * MANO_SOBRE_PUNTA - ax * MANO_HACIA_EL_CUERPO, p[1] + n[1] * MANO_SOBRE_PUNTA,
                p[2] + n[2] * MANO_SOBRE_PUNTA - az * MANO_HACIA_EL_CUERPO)
        faltas[nombre] = round(max(0.0, math.dist(hombro, mano) - alcance), 3)
    return faltas
