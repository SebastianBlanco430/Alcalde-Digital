# Parámetros del rostro, el pelo y los accesorios de los personajes (NO importa ursina ni panda3d).
# Estilo cómic cel-shaded (Borderlands): ojos grandes con esclerótica, iris, pupila y brillo; cejas gruesas
# de tinta; nariz con fosas; boca con comisuras; arrugas de trazo; pelo con volumen y mechones; barba,
# bigote, gafas, gorra y auriculares según el rol. Las bandas de luz (2-3 tonos) las hornea
# frontend/malla_calculos.py en el color de los vértices.
#
# Los .glb (periodista y smoking) traen la cabeza como piel lisa y los muñecos procedurales una esfera:
# frontend/rostro_modelo.py coloca estas piezas en ambos. Todas las medidas son metros RELATIVOS AL HUESO DE
# LA CABEZA, en los ejes del glb crudo de Blender: x a la izquierda del personaje, y hacia atrás (la cara
# mira hacia -y) y z hacia arriba. El hueso está en REPOSO_CABEZA (bind pose, sin escala del wrapper).
# Cada pieza es un dict con
#   nombre:   único dentro del rostro
#   forma:    "esfera" (elipsoide), "caja", "cilindro" (eje z) o "anillo" (toro en el plano xz)
#   pos:      centro (x, y, z)
#   escala:   semiejes (esfera), semi-medidas (caja), radio-radio-semialtura (cilindro) o radio mayor (anillo)
#   rot:      giro HPR de Panda3D en grados, SOLO en las piezas animadas (ver ANIMADAS)
#   giro:     giro en grados alrededor de x, y y z (piezas estáticas; ver malla_calculos)
#   color:    (r, g, b) de 0 a 1
#   contorno: grosor en metros del casco de tinta (la pieza se dibuja con su contorno), opcional
#   bandas:   False para color plano sin bandas de luz, opcional
#   detalle:  (segmentos, anillos) de la malla en vez de los que da malla_calculos.detalle_para, opcional

import math

HUESO_CABEZA = "DEF-spine.006"
REPOSO_CABEZA = (0.0, -0.014, 1.731)       # m: hueso de la cabeza en bind pose

# Volumen de la malla de la cabeza relativo al hueso: z de 1.741 a 1.987 (coronilla), x ±0.108,
# y de -0.19 (cara) a +0.097 (nuca).
VOLUMEN_CABEZA = {"x": (-0.108, 0.108), "y": (-0.19 - REPOSO_CABEZA[1], 0.097 - REPOSO_CABEZA[1]),
                  "z": (1.741 - REPOSO_CABEZA[2], 1.987 - REPOSO_CABEZA[2])}
MARGEN_VOLUMEN = 0.06                      # m: lo que una pieza puede sobresalir del volumen

CONTORNO_ESCALA = 1.07                     # (heredado) el casco negro era un 7 % mayor
CONTORNO_COLOR = (0.07, 0.078, 0.125)      # TINTA (18, 20, 32) / 255, el mismo color de tinta de todo el juego
GROSOR_CONTORNO = 0.0095                   # m: casco de tinta del pelo, la gorra y los accesorios grandes
GROSOR_CONTORNO_FINO = 0.0045              # m: accesorios pequeños

BLANCO_OJO = (0.98, 0.97, 0.93)
NEGRO_PUPILA = (0.04, 0.035, 0.05)
BRILLO_OJO = (1.0, 1.0, 1.0)
INTERIOR_BOCA = (0.30, 0.04, 0.07)         # boca abierta (animación facial)
TINTA = CONTORNO_COLOR

PIEL_PERIODISTA = (0.80, 0.57, 0.37)       # colores de vértice de la cabeza en cada glb
PIEL_CANDIDATO = (0.35, 0.20, 0.06)

FORMAS_PIEZA = ("esfera", "caja", "cilindro", "anillo")

# Piezas con animación facial (rostro_modelo.RostroAnimado las mueve por su nombre): cada una es un nodo propio.
ANIMADAS = frozenset(f"{base}_{lado}" for base in ("esclera", "iris", "pupila", "ceja", "comisura", "parpado")
                     for lado in (-1, 1)) | {"boca", "boca_interior", "labio_inf"}

CENTRO_CRANEO = (0.0, -0.035, 0.150)       # elipsoides de la cabeza del muñeco procedural (ejes del glb)
SEMIEJES_CRANEO = (0.108, 0.125, 0.115)
CENTRO_MANDIBULA = (0.0, -0.085, 0.050)
SEMIEJES_MANDIBULA = (0.082, 0.085, 0.050)
CENTRO_CABEZA = (0.0, -0.046, 0.133)       # centro de la cabeza para pasar del glb al muñeco procedural
ESCALA_PROCEDURAL = 1.25                   # la cabeza del muñeco procedural es algo mayor (cómic)


def tono(color, factor):
    # Oscurece (factor < 1) o aclara (> 1) un color sin salirse de 0..1.
    return tuple(max(0.0, min(1.0, canal * factor)) for canal in color)


def mezclar(a, b, t):
    # Mezcla lineal de dos colores (t = 0 da a, t = 1 da b).
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def _pieza(nombre, forma, pos, escala, color, **extra):
    datos = {"nombre": nombre, "forma": forma, "pos": pos, "escala": escala, "color": color}
    datos.update(extra)
    return datos


def _arco(prefijo, centro, radio_y, radio_z, desde, hasta, n, grosor, color, **extra):
    # Un arco de cajas en el plano yz (la diadema de unos auriculares): ángulos medidos desde +z hacia -y.
    # Cada caja se gira alrededor de x para quedar tangente al arco.
    piezas = []
    for i in range(n):
        a = math.radians(desde + (hasta - desde) * (i + 0.5) / n)
        largo = abs(math.radians(hasta - desde)) / n * (radio_y + radio_z) / 2 * 0.62
        tangente = math.degrees(math.atan2(-radio_z * math.sin(a), -radio_y * math.cos(a)))
        piezas.append(_pieza(f"{prefijo}_{i}", "caja",
                             (centro[0], centro[1] - radio_y * math.sin(a), centro[2] + radio_z * math.cos(a)),
                             (grosor, largo, grosor), color, giro=(tangente, 0.0, 0.0), **extra))
    return piezas


# -- Rasgos de la cara --

def rasgos(piel, iris, ceja, labio, nariz_f=0.9, oreja_f=0.92, brillo=True, arrugas=False,
           cejas=(0.0235, 0.0058, 0.0058), inclinacion_cejas=7.0, parpado_tinta=True, mejillas=True,
           ojeras=False, procedural=False):
    # Rasgos comunes, ajustados al tono de piel. Cara en y ≈ -0.157 (x = 0) a -0.12 (x = ±0.045).
    piezas = []
    sombra = tono(piel, 0.66)
    rubor = mezclar(piel, (min(1.0, piel[0] * 1.05 + 0.04), piel[1] * 0.70, piel[2] * 0.72), 0.55)
    if sum(piel) / 3 < 0.40:      # piel oscura: en vez de rubor, un pómulo con luz (el rubor se pierde)
        rubor = tono(piel, 1.55)
    for lado in (-1, 1):
        x = 0.046 * lado
        piezas.append(_pieza(f"esclera_{lado}", "esfera", (x, -0.1505, 0.133), (0.0212, 0.0105, 0.0225), BLANCO_OJO))
        piezas.append(_pieza(f"iris_{lado}", "esfera", (x, -0.1575, 0.1325), (0.0128, 0.0055, 0.0138), iris))
        piezas.append(_pieza(f"pupila_{lado}", "esfera", (x, -0.1618, 0.1325), (0.0062, 0.0045, 0.0068), NEGRO_PUPILA))
        if brillo:   # brillo del ojo: un punto blanco arriba, hacia el interior (no sigue a la pupila: parece cristal)
            piezas.append(_pieza(f"brillo_{lado}", "esfera", (x - 0.0045 * lado, -0.1655, 0.1395),
                                 (0.0034, 0.003, 0.0036), BRILLO_OJO, bandas=False))
        piezas.append(_pieza(f"ceja_{lado}", "esfera", (x, -0.1465, 0.1735), cejas, ceja,
                             rot=(0, 0, inclinacion_cejas * lado)))
        piezas.append(_pieza(f"oreja_{lado}", "esfera", (0.108 * lado, -0.025, 0.105),
                             (0.0135, 0.0245, 0.035), tono(piel, oreja_f)))
        piezas.append(_pieza(f"oreja_int_{lado}", "esfera", (0.1155 * lado, -0.024, 0.105),
                             (0.0042, 0.012, 0.02), tono(piel, 0.7), bandas=False))
        # boca: tramo central recto y dos comisuras levantadas (sonrisa)
        piezas.append(_pieza(f"comisura_{lado}", "esfera", (0.0305 * lado, -0.1585, 0.0455),
                             (0.0145, 0.0048, 0.0048), labio, rot=(0, 0, -25 * lado)))
        # párpado: cúpula de piel sobre el ojo; rostro_modelo la encoge hacia arriba (abierto) o la estira (cerrado)
        piezas.append(_pieza(f"parpado_{lado}", "esfera", (x, -0.1485, 0.133), (0.0225, 0.0205, 0.0225), piel))
        if parpado_tinta:   # línea de tinta del párpado superior: da la mirada de cómic
            piezas.append(_pieza(f"linea_ojo_{lado}", "caja", (x, -0.1535, 0.1530), (0.0245, 0.0042, 0.0034), TINTA,
                                 giro=(0, 7.0 * lado, 0), bandas=False))
        if ojeras:
            piezas.append(_pieza(f"ojera_{lado}", "caja", (x, -0.1525, 0.1075), (0.0165, 0.0028, 0.0021), sombra,
                                 giro=(0, 6.0 * lado, 0), bandas=False))
        if mejillas:
            piezas.append(_pieza(f"mejilla_{lado}", "esfera", (0.0615 * lado, -0.1265 if procedural else -0.1305, 0.0715),
                                 (0.0195, 0.0045, 0.0135), rubor))
        # arruga de la sonrisa (del ala de la nariz a la comisura): trazo de tinta suave
        piezas.append(_pieza(f"arruga_nasal_{lado}", "caja", (0.0345 * lado, -0.1655, 0.0625),
                             (0.0024, 0.0022, 0.0098), sombra, giro=(0, 20.0 * lado, 0), bandas=False))
        piezas.append(_pieza(f"fosa_{lado}", "esfera", (0.0085 * lado, (-0.1635 if procedural else -0.1855), 0.0815),
                             (0.0048, 0.0042, 0.0036), tono(piel, 0.42), bandas=False))
        if arrugas:    # patas de gallo y líneas de expresión: carácter
            for k in (0, 1):
                piezas.append(_pieza(f"pata_gallo_{lado}_{k}", "caja",
                                     (0.0715 * lado, -0.1385 + 0.0, 0.1325 + 0.007 * (k - 0.5)),
                                     (0.0105, 0.0022, 0.0018), sombra,
                                     giro=(0, (-24.0 + 48.0 * k) * lado, 0), bandas=False))
    piezas.append(_pieza("boca_interior", "esfera", (0.0, -0.170, 0.0405), (0.022, 0.0055, 0.01), INTERIOR_BOCA))
    piezas.append(_pieza("labio_inf", "esfera", (0.0, -0.170, 0.0405), (0.0185, 0.0048, 0.0042), labio))
    piezas.append(_pieza("boca", "esfera", (0.0, -0.170, 0.0405), (0.0245, 0.0052, 0.0052), labio))
    nariz_y = -0.153 if procedural else -0.1745
    nariz_e = (0.0150, 0.0155, 0.0180) if procedural else (0.0175, 0.02, 0.0205)
    piezas.append(_pieza("nariz", "esfera", (0.0, nariz_y, 0.092), nariz_e, tono(piel, nariz_f)))
    piezas.append(_pieza("nariz_puente", "esfera", (0.0, nariz_y + 0.009, 0.1155), (0.0085, 0.011, 0.0225),
                         tono(piel, 0.97)))
    if arrugas:
        piezas.append(_pieza("frente_arruga", "caja", (0.0, -0.1405, 0.196), (0.018, 0.0022, 0.0018),
                             sombra, bandas=False))
    return piezas


# -- Pelo --

def _lado(prefijo, lado, *args, **kw):
    return _pieza(f"{prefijo}_{lado}", *args, **kw)


def peinado(nombre, pelo, brillo=None):
    # Piezas de pelo (con contorno de tinta) del peinado `nombre`: corto, atras, pompadour, largo, afro, mono, calvo.
    c = GROSOR_CONTORNO
    base = [_pieza("pelo_casquete", "esfera", (0.0, 0.004, 0.152), (0.119, 0.127, 0.110), pelo, contorno=c)]
    claro = brillo or tono(pelo, 1.55)
    if nombre == "corto":       # castaño con flequillo levantado y mechones
        base = [_pieza("pelo_casquete", "esfera", (0.0, 0.0, 0.158), (0.120, 0.128, 0.112), pelo, contorno=c)]
        base += [
            _pieza("pelo_flequillo", "esfera", (0.0, -0.075, 0.225), (0.100, 0.064, 0.043), pelo,
                   giro=(12, 0, 0), contorno=c),
            _pieza("pelo_tupe", "esfera", (-0.02, -0.075, 0.250), (0.060, 0.050, 0.032), pelo,
                   giro=(0, 15, 0), contorno=c),
            _pieza("pelo_mechon_1", "esfera", (0.055, -0.112, 0.222), (0.022, 0.026, 0.028), pelo,
                   giro=(0, -25, 20), contorno=GROSOR_CONTORNO_FINO),
            _pieza("pelo_mechon_2", "esfera", (-0.052, -0.118, 0.214), (0.020, 0.024, 0.026), pelo,
                   giro=(0, 25, -20), contorno=GROSOR_CONTORNO_FINO),
            _pieza("pelo_brillo", "esfera", (-0.034, -0.095, 0.2755), (0.032, 0.022, 0.0075), claro, bandas=False),
        ]
        base += [_pieza(f"pelo_patilla_{lado}", "caja", (0.1075 * lado, -0.076, 0.168), (0.0075, 0.016, 0.026), pelo)
                 for lado in (-1, 1)]
        return base
    if nombre == "atras":       # peinado hacia atrás, pulido, con brillo
        base = [_pieza("pelo_casquete", "esfera", (0.0, 0.004, 0.152), (0.118, 0.126, 0.108), pelo, contorno=c)]
        base += [
            _pieza("pelo_peinado", "esfera", (0.0, -0.045, 0.232), (0.100, 0.090, 0.036), pelo,
                   giro=(-8, 0, 0), contorno=c),
            _pieza("pelo_ola", "esfera", (0.0, -0.082, 0.245), (0.082, 0.038, 0.026), pelo, giro=(10, 0, 0),
                   contorno=GROSOR_CONTORNO_FINO),
            _pieza("pelo_brillo_1", "esfera", (0.025, -0.071, 0.272), (0.045, 0.023, 0.0055), claro, bandas=False),
            _pieza("pelo_brillo_2", "esfera", (-0.04, -0.01, 0.2625), (0.038, 0.020, 0.005), claro, bandas=False),
        ]
        return base
    if nombre == "pompadour":   # copete grande hacia adelante y arriba (influencer)
        return [
            _pieza("pelo_casquete", "esfera", (0.0, 0.004, 0.152), (0.119, 0.127, 0.110), pelo, contorno=c),
            _pieza("pelo_copete", "esfera", (0.0, -0.075, 0.238), (0.090, 0.082, 0.046), pelo, giro=(-14, 0, 0),
                   contorno=c),
            _pieza("pelo_copete_2", "esfera", (0.018, -0.112, 0.256), (0.058, 0.048, 0.032), pelo, giro=(-22, 0, 8),
                   contorno=c),
            _pieza("pelo_brillo", "esfera", (0.02, -0.123, 0.2825), (0.034, 0.022, 0.0065), claro, bandas=False,
                   giro=(-22, 0, 8)),
        ] + [_pieza(f"pelo_patilla_{lado}", "caja", (0.1075 * lado, -0.07, 0.165), (0.0075, 0.016, 0.026), pelo)
             for lado in (-1, 1)]
    if nombre == "largo":
        return base + [
            _pieza("pelo_flequillo", "esfera", (0.0, -0.085, 0.222), (0.100, 0.060, 0.040), pelo, giro=(14, 0, 0),
                   contorno=c),
            _pieza("pelo_melena", "esfera", (0.0, 0.045, 0.085), (0.118, 0.078, 0.140), pelo, contorno=c),
        ] + [_pieza(f"pelo_lado_{lado}", "esfera", (0.1 * lado, 0.0, 0.10), (0.022, 0.060, 0.115), pelo,
                    contorno=GROSOR_CONTORNO_FINO) for lado in (-1, 1)]
    if nombre == "afro":
        return [_pieza("pelo_casquete", "esfera", (0.0, 0.012, 0.172), (0.146, 0.148, 0.140), pelo, contorno=c),
                _pieza("pelo_brillo", "esfera", (-0.04, -0.09, 0.285), (0.045, 0.03, 0.01), claro, bandas=False,
                       giro=(-30, 10, 0))]
    if nombre == "mono":
        return base + [
            _pieza("pelo_flequillo", "esfera", (0.0, -0.08, 0.222), (0.098, 0.058, 0.038), pelo, giro=(12, 0, 0),
                   contorno=c),
            _pieza("pelo_mono", "esfera", (0.0, 0.07, 0.262), (0.045, 0.045, 0.045), pelo, contorno=c),
        ]
    if nombre == "calvo":       # solo la corona de pelo de los lados
        return [_pieza(f"pelo_lado_{lado}", "esfera", (0.098 * lado, 0.02, 0.122), (0.017, 0.06, 0.04), pelo,
                       contorno=GROSOR_CONTORNO_FINO) for lado in (-1, 1)] + [
            _pieza("pelo_nuca", "esfera", (0.0, 0.07, 0.10), (0.08, 0.026, 0.035), pelo, contorno=GROSOR_CONTORNO_FINO)]
    raise ValueError(f"peinado desconocido: {nombre}")


# -- Accesorios --

def gafas(color_montura, grosor=0.0045):
    # Gafas redondas de montura gruesa de tinta: dos aros, puente y patillas hacia las orejas.
    c = GROSOR_CONTORNO_FINO
    piezas = [_pieza("gafas_puente", "caja", (0.0, -0.1725, 0.139), (0.012, 0.0042, 0.0042), color_montura)]
    for lado in (-1, 1):
        piezas.append(_pieza(f"gafas_aro_{lado}", "anillo", (0.046 * lado, -0.1725, 0.133), (0.0335, 0.0045, 0.0315),
                             color_montura, bandas=False))
        piezas.append(_pieza(f"gafas_patilla_{lado}", "caja", (0.0905 * lado, -0.1275, 0.1385),
                             (0.0036, 0.0475, 0.0036), color_montura, bandas=False))
    return piezas


def gafas_de_sol_en_la_frente(color_lente, color_montura):
    # Gafas de sol subidas a la frente (influencer): dos lentes oscuras inclinadas con montura de color.
    piezas = [_pieza("gafas_puente", "caja", (0.0, -0.1385, 0.2215), (0.013, 0.0045, 0.0055), color_montura)]
    for lado in (-1, 1):
        piezas.append(_pieza(f"gafas_marco_{lado}", "esfera", (0.0455 * lado, -0.1375, 0.2245),
                             (0.0395, 0.0085, 0.0275), color_montura, giro=(0, 8.0 * lado, 0), bandas=False))
        piezas.append(_pieza(f"gafas_lente_{lado}", "esfera", (0.0455 * lado, -0.1455, 0.2245),
                             (0.0345, 0.0065, 0.0225), color_lente, giro=(0, 8.0 * lado, 0), bandas=False))
        piezas.append(_pieza(f"gafas_reflejo_{lado}", "caja", (0.0455 * lado + 0.011 * lado, -0.1555, 0.2315),
                             (0.0046, 0.0016, 0.0085), (0.85, 0.95, 1.0), giro=(0, 25.0 * lado, 0), bandas=False))
        piezas.append(_pieza(f"gafas_patilla_{lado}", "caja", (0.0985 * lado, -0.085, 0.2185),
                             (0.0036, 0.052, 0.0036), color_montura, bandas=False))
    return piezas


def auriculares(color, color_almohadilla):
    # Auriculares sobre las orejas con diadema en arco por encima de la cabeza (influencer).
    c = GROSOR_CONTORNO_FINO
    piezas = []
    for lado in (-1, 1):
        piezas.append(_pieza(f"auricular_{lado}", "cilindro", (0.1265 * lado, -0.02, 0.105), (0.040, 0.040, 0.0125),
                             color, giro=(0, 90, 0), contorno=c))
        piezas.append(_pieza(f"auricular_almohadilla_{lado}", "cilindro", (0.1135 * lado, -0.02, 0.105),
                             (0.034, 0.034, 0.0055), color_almohadilla, giro=(0, 90, 0), bandas=False))
    piezas += _arco("diadema", (0.0, 0.0, 0.105), 0.130, 0.205, -88, 88, 11, 0.0095, color, bandas=False)
    return piezas


def gorra(color, color_visera, tinta=TINTA):
    # Gorra con cúpula, visera y botón (ciudadano).
    c = GROSOR_CONTORNO
    return [
        _pieza("gorra_cupula", "esfera", (0.0, -0.02, 0.180), (0.1265, 0.150, 0.100), color, contorno=c),
        _pieza("gorra_banda", "esfera", (0.0, -0.02, 0.1665), (0.1290, 0.1515, 0.0345), color_visera, contorno=c),
        _pieza("gorra_visera", "esfera", (0.0, -0.150, 0.1855), (0.078, 0.078, 0.0095), color_visera,
               giro=(-10, 0, 0), contorno=c),
        _pieza("gorra_boton", "esfera", (0.0, -0.02, 0.274), (0.0105, 0.0105, 0.0085), color_visera,
               contorno=GROSOR_CONTORNO_FINO),
    ]


def lapiz():
    # Lápiz amarillo detrás de la oreja (periodista).
    c = GROSOR_CONTORNO_FINO
    return [
        _pieza("lapiz_cuerpo", "cilindro", (0.099, -0.03, 0.1625), (0.0052, 0.0052, 0.0365), (1.0, 0.78, 0.12),
               giro=(78, 0, 0), contorno=c),
        _pieza("lapiz_punta", "cilindro", (0.099, -0.0655, 0.1685), (0.0034, 0.0034, 0.008), (0.95, 0.80, 0.60),
               giro=(78, 0, 0), bandas=False),
        _pieza("lapiz_goma", "cilindro", (0.099, 0.0067, 0.1546), (0.0054, 0.0054, 0.0042), (0.95, 0.35, 0.40),
               giro=(78, 0, 0), bandas=False),
    ]


def bigote(color, ancho=0.0135):
    return [_pieza(f"bigote_{lado}", "esfera", (0.0105 * lado, -0.1745, 0.0545), (ancho, 0.005, 0.0055), color,
                   giro=(0, -14.0 * lado, 0), contorno=0.0022) for lado in (-1, 1)]


def barba(tipo, color, piel):
    # Barba: "incipiente" (sombra en la mandíbula), "chivo" (mechón bajo la boca) o "completa" (marco de la cara).
    if tipo == "incipiente":
        sombra = mezclar(piel, color, 0.26)
        return [_pieza("barba_menton", "esfera", (0.0, -0.1235, 0.013), (0.050, 0.054, 0.022), sombra)]
    if tipo == "chivo":
        return [_pieza("barba_chivo", "esfera", (0.0, -0.155, 0.017), (0.022, 0.026, 0.0275), color,
                       contorno=GROSOR_CONTORNO_FINO)]
    if tipo == "completa":
        return [_pieza("barba_menton", "esfera", (0.0, -0.12, 0.012), (0.066, 0.066, 0.040), color,
                       contorno=GROSOR_CONTORNO_FINO),
                _pieza("barba_lado_-1", "esfera", (-0.080, -0.08, 0.055), (0.026, 0.065, 0.055), color),
                _pieza("barba_lado_1", "esfera", (0.080, -0.08, 0.055), (0.026, 0.065, 0.055), color)]
    raise ValueError(f"barba desconocida: {tipo}")


# -- Rostros por rol --

_PELO_PERIODISTA = (0.30, 0.18, 0.10)
_PELO_CANDIDATO = (0.09, 0.08, 0.10)
_SIEN_CANDIDATO = (0.46, 0.48, 0.55)       # sienes canosas: se notan contra el pelo negro sin parecer un adorno
_ROJO_GORRA = (0.90, 0.33, 0.24)
_AZUL_OSCURO = (0.07, 0.09, 0.16)

# Descriptor de cada rol: cómo se arma el rostro (cada clave la usa `piezas_rostro`).
DESCRIPTOR_POR_ROL = {
    "periodista": dict(piel=PIEL_PERIODISTA, iris=(0.10, 0.36, 0.30), ceja=(0.20, 0.11, 0.06), labio=(0.62, 0.24, 0.20),
                       nariz_f=0.93, oreja_f=0.92, peinado="corto", pelo=_PELO_PERIODISTA, gafas=TINTA,
                       barba="incipiente", barba_color=(0.22, 0.14, 0.09), lapiz=True, ojeras=True,
                       cejas=(0.026, 0.0065, 0.0062), inclinacion_cejas=9.0),
    "candidato": dict(piel=PIEL_CANDIDATO, iris=(0.10, 0.06, 0.03), ceja=(0.05, 0.045, 0.05), labio=(0.30, 0.10, 0.10),
                      nariz_f=0.88, oreja_f=0.9, peinado="atras", pelo=_PELO_CANDIDATO, bigote=(0.06, 0.055, 0.06),
                      chivo=False, arrugas=True, canas=True, cejas=(0.028, 0.007, 0.0066), inclinacion_cejas=10.0),
    "ciudadano": dict(piel=(0.93, 0.78, 0.64), iris=(0.20, 0.30, 0.50), ceja=(0.24, 0.15, 0.10), labio=(0.68, 0.28, 0.26),
                      nariz_f=0.94, peinado="corto", pelo=(0.40, 0.25, 0.14), gorra=(_ROJO_GORRA, (0.75, 0.22, 0.17)),
                      cejas=(0.025, 0.0062, 0.006), inclinacion_cejas=6.0),
    "influencer": dict(piel=(0.95, 0.80, 0.68), iris=(0.55, 0.28, 0.10), ceja=(0.45, 0.25, 0.12), labio=(0.86, 0.30, 0.40),
                       nariz_f=0.95, peinado="pompadour", pelo=(0.92, 0.55, 0.18), gafas_sol=((0.07, 0.07, 0.10), (1.0, 0.92, 0.35)),
                       auriculares=((0.10, 0.80, 0.92), (0.16, 0.18, 0.26)), cejas=(0.0235, 0.0052, 0.0058),
                       inclinacion_cejas=4.0),
}


def piezas_craneo(piel):
    # Cabeza del muñeco procedural: cráneo y mandíbula (dos elipsoides) con contorno de tinta, y un cuello corto.
    return [
        _pieza("craneo", "esfera", CENTRO_CRANEO, SEMIEJES_CRANEO, piel, contorno=GROSOR_CONTORNO, detalle=(16, 10)),
        _pieza("mandibula", "esfera", CENTRO_MANDIBULA, SEMIEJES_MANDIBULA, piel, contorno=GROSOR_CONTORNO,
               detalle=(14, 8)),
        _pieza("cuello", "cilindro", (0.0, -0.02, -0.005), (0.04, 0.04, 0.035), tono(piel, 0.88)),
    ]


def piezas_rostro(d, procedural=False):
    # Todas las piezas del rostro descrito por `d`. Con `procedural` ajusta lo que depende de la forma de la cabeza.
    piel = d["piel"]
    piezas = piezas_craneo(piel) if procedural else []
    piezas += rasgos(piel, d["iris"], d["ceja"], d["labio"], d.get("nariz_f", 0.9), d.get("oreja_f", 0.92),
                    arrugas=d.get("arrugas", False), cejas=d.get("cejas", (0.0235, 0.0058, 0.0058)),
                    inclinacion_cejas=d.get("inclinacion_cejas", 7.0), ojeras=d.get("ojeras", False),
                    procedural=procedural)
    if d.get("peinado"):
        pelo = peinado(d["peinado"], d["pelo"]) if not d.get("gorra") else peinado("calvo", d["pelo"])
        piezas += pelo
    if d.get("canas"):      # mechas canosas sobre las sienes, pegadas al pelo
        piezas += [_pieza(f"pelo_cana_{lado}_{k}", "esfera", (0.1078 * lado, -0.06 - 0.03 * k, 0.188 - 0.004 * k),
                          (0.0038, 0.02, 0.0075), _SIEN_CANDIDATO, bandas=False) for lado in (-1, 1)
                   for k in (0, 1)]
    if d.get("gorra"):
        piezas += gorra(*d["gorra"])
        piezas += [_pieza("pelo_flequillo", "esfera", (0.0, -0.1, 0.2), (0.07, 0.03, 0.02), d["pelo"])]
    if d.get("gafas"):
        piezas += gafas(d["gafas"])
    if d.get("gafas_sol"):
        piezas += gafas_de_sol_en_la_frente(*d["gafas_sol"])
    if d.get("auriculares"):
        piezas += auriculares(*d["auriculares"])
    if d.get("lapiz"):
        piezas += lapiz()
    if d.get("bigote"):
        piezas += bigote(d["bigote"])
    if d.get("barba"):
        piezas += barba(d["barba"], d.get("barba_color", d["pelo"]), piel)
    return piezas


ROSTRO_POR_ROL = {rol: piezas_rostro(DESCRIPTOR_POR_ROL[rol]) for rol in ("periodista", "candidato")}
# Roles sin modelo .glb: se arman sobre la cabeza del muñeco procedural (personaje.py).
ROSTRO_PROCEDURAL_POR_ROL = {rol: piezas_rostro(DESCRIPTOR_POR_ROL[rol], procedural=True)
                             for rol in ("ciudadano", "influencer")}


def descriptor_peaton(rasgos_peaton, piel, pelo):
    # Descriptor de un peatón a partir de sus rasgos (peatones_calculos.rasgos_peaton) y su piel y pelo.
    d = dict(piel=tuple(c / 255 for c in piel), iris=rasgos_peaton["iris"], ceja=tono(tuple(c / 255 for c in pelo), 0.75),
             labio=mezclar(tuple(c / 255 for c in piel), (0.45, 0.12, 0.12), 0.55), peinado=rasgos_peaton["peinado"],
             pelo=tuple(c / 255 for c in pelo), nariz_f=0.92, cejas=rasgos_peaton["cejas"],
             inclinacion_cejas=rasgos_peaton["inclinacion"])
    if rasgos_peaton.get("gorra"):
        d["gorra"] = (tuple(c / 255 for c in rasgos_peaton["gorra"]), tono(tuple(c / 255 for c in rasgos_peaton["gorra"]), 0.8))
    if rasgos_peaton.get("gafas"):
        d["gafas"] = TINTA
    if rasgos_peaton.get("bigote"):
        d["bigote"] = tono(tuple(c / 255 for c in pelo), 0.7)
    if rasgos_peaton.get("barba"):
        d["barba"] = rasgos_peaton["barba"]
        d["barba_color"] = tono(tuple(c / 255 for c in pelo), 0.8)
    d["arrugas"] = bool(rasgos_peaton.get("arrugas"))
    return d


def piezas_peaton(rasgos_peaton, piel, pelo):
    # Piezas del rostro de un peatón (procedural, sin animación).
    return piezas_rostro(descriptor_peaton(rasgos_peaton, piel, pelo), procedural=True)


# -- Modelos de brasilena.glb (influencer) y ciudadano.glb (ciudadano) --
# Las caras de estos dos .glb también llegan lisas (el pelo afro de la brasileña sí viene en el modelo; el
# ciudadano trae la cabeza calva). El ciudadano comparte malla y armadura de la cabeza con el periodista
# (mismo hueso y mismas medidas); la brasileña tiene otra armadura (hueso "Head", cabeza algo menor y más
# atrás), así que sus piezas se ajustan con (factor, dy, dz) respecto a las medidas del periodista.
HUESO_CABEZA_POR_ROL = {"influencer": "Head"}                      # los demás roles: HUESO_CABEZA
REPOSO_CABEZA_POR_ROL = {"influencer": (0.0, -0.054, 1.73)}        # los demás roles: REPOSO_CABEZA
AJUSTE_ROSTRO_POR_ROL = {"influencer": (0.93, 0.065, -0.045)}      # (factor, dy, dz) en metros
CENTRO_AJUSTE = (0.0, -0.15, 0.10)                                 # punto fijo del cambio de tamaño

PIEL_CIUDADANO_MODELO = (0.42, 0.29, 0.20)
PIEL_INFLUENCER_MODELO = (0.31, 0.20, 0.14)

DESCRIPTOR_MODELO_POR_ROL = {
    "ciudadano": dict(piel=PIEL_CIUDADANO_MODELO, iris=(0.20, 0.12, 0.07), ceja=(0.10, 0.07, 0.05), labio=(0.45, 0.20, 0.17),
                      nariz_f=0.93, peinado="corto", pelo=(0.10, 0.07, 0.05), cejas=(0.025, 0.0062, 0.006),
                      inclinacion_cejas=6.0),
    "influencer": dict(piel=PIEL_INFLUENCER_MODELO, iris=(0.22, 0.12, 0.06), ceja=(0.06, 0.04, 0.03), labio=(0.60, 0.20, 0.24),
                       nariz_f=0.95, cejas=(0.0235, 0.0052, 0.0058), inclinacion_cejas=4.0),
}


def hueso_cabeza(rol=None):
    # Nombre del hueso de la cabeza del .glb del rol.
    return HUESO_CABEZA_POR_ROL.get(rol, HUESO_CABEZA)


def reposo_cabeza(rol=None):
    # Posición del hueso de la cabeza en bind pose del .glb del rol.
    return REPOSO_CABEZA_POR_ROL.get(rol, REPOSO_CABEZA)


def ajustar_piezas(piezas, factor, dy, dz):
    # Copia de las piezas con posición y tamaño cambiados (factor alrededor de CENTRO_AJUSTE) y luego movidas (dy, dz).
    # Los grosores de contorno no se tocan; los giros tampoco.
    cx, cy, cz = CENTRO_AJUSTE
    ajustadas = []
    for datos in piezas:
        x, y, z = datos["pos"]
        nueva = dict(datos)
        nueva["pos"] = (cx + (x - cx) * factor, cy + (y - cy) * factor + dy, cz + (z - cz) * factor + dz)
        nueva["escala"] = tuple(e * factor for e in datos["escala"])
        ajustadas.append(nueva)
    return ajustadas


ROSTRO_MODELO_POR_ROL = {}       # rostros de los .glb nuevos; ROSTRO_POR_ROL (periodista, candidato) no cambia
for _rol, _d in DESCRIPTOR_MODELO_POR_ROL.items():
    _piezas = piezas_rostro(_d)
    if _rol in AJUSTE_ROSTRO_POR_ROL:
        _piezas = ajustar_piezas(_piezas, *AJUSTE_ROSTRO_POR_ROL[_rol])
    ROSTRO_MODELO_POR_ROL[_rol] = _piezas


def rostro_del_modelo(rol):
    # Piezas del rostro para el .glb del rol (None si ese rol no recibe cara por código).
    return ROSTRO_POR_ROL.get(rol) or ROSTRO_MODELO_POR_ROL.get(rol)
