# Parámetros del rostro y el pelo de los personajes con modelo .glb (NO importa ursina ni panda3d).
# Los .glb (periodista y smoking) traen la cabeza como piel lisa: frontend/rostro_modelo.py añade
# ojos, cejas, nariz, boca, orejas y pelo como formas simples de color plano colgadas del hueso de
# la cabeza, para que acompañen las animaciones.
#
# Todas las medidas son metros RELATIVOS AL HUESO DE LA CABEZA, en los ejes del glb crudo de
# Blender: x a la derecha del personaje, y hacia atrás (la cara mira hacia -y) y z hacia arriba.
# El hueso está en REPOSO_CABEZA (bind pose, sin escala del wrapper). Cada pieza es un dict con
#   forma:    "esfera" (elipsoide) o "caja"
#   pos:      centro (x, y, z)
#   escala:   semiejes (esfera) o semi-medidas (caja) en x, y, z
#   rot:      giro (h, p, r) en grados, opcional
#   color:    (r, g, b) de 0 a 1, plano
#   contorno: True si lleva casco negro un poco mayor (el contorno del modelo), opcional

HUESO_CABEZA = "DEF-spine.006"
REPOSO_CABEZA = (0.0, -0.014, 1.731)       # m: hueso de la cabeza en bind pose

# Volumen de la malla de la cabeza relativo al hueso: z de 1.741 a 1.987 (coronilla), x ±0.108,
# y de -0.19 (cara) a +0.097 (nuca).
VOLUMEN_CABEZA = {"x": (-0.108, 0.108), "y": (-0.19 - REPOSO_CABEZA[1], 0.097 - REPOSO_CABEZA[1]),
                  "z": (1.741 - REPOSO_CABEZA[2], 1.987 - REPOSO_CABEZA[2])}
MARGEN_VOLUMEN = 0.06                      # m: lo que una pieza puede sobresalir del volumen

CONTORNO_ESCALA = 1.07                     # el casco negro es un 7 % mayor
CONTORNO_COLOR = (0.0, 0.0, 0.0)

BLANCO_OJO = (0.96, 0.95, 0.92)
NEGRO_PUPILA = (0.05, 0.04, 0.04)
INTERIOR_BOCA = (0.22, 0.04, 0.05)         # boca abierta (animación facial)


PIEL_PERIODISTA = (0.80, 0.57, 0.37)       # colores de vértice de la cabeza en cada glb
PIEL_CANDIDATO = (0.35, 0.20, 0.06)


def tono(color, factor):
    # Oscurece (factor < 1) o aclara (> 1) un color sin salirse de 0..1.
    return tuple(max(0.0, min(1.0, canal * factor)) for canal in color)


def _rasgos(piel, iris, ceja, labio, nariz_f, oreja_f):
    # Rasgos comunes, ajustados al tono de piel. Cara en y ≈ -0.157 (x = 0) a -0.12 (x = ±0.045).
    piezas = []
    for lado in (-1, 1):
        x = 0.045 * lado
        piezas.append({"nombre": f"esclera_{lado}", "forma": "esfera", "pos": (x, -0.147, 0.133),
                       "escala": (0.0185, 0.014, 0.0165), "color": BLANCO_OJO})
        piezas.append({"nombre": f"iris_{lado}", "forma": "esfera", "pos": (x, -0.1565, 0.133),
                       "escala": (0.0108, 0.0075, 0.0108), "color": iris})
        piezas.append({"nombre": f"pupila_{lado}", "forma": "esfera", "pos": (x, -0.1615, 0.133),
                       "escala": (0.0052, 0.0045, 0.0052), "color": NEGRO_PUPILA})
        piezas.append({"nombre": f"ceja_{lado}", "forma": "caja", "pos": (x, -0.1445, 0.162),
                       "escala": (0.022, 0.0055, 0.0042), "rot": (0, 0, 7 * lado), "color": ceja})
        piezas.append({"nombre": f"oreja_{lado}", "forma": "esfera", "pos": (0.108 * lado, -0.025, 0.105),
                       "escala": (0.013, 0.024, 0.034), "color": tono(piel, oreja_f)})
        # boca: tramo central recto y dos comisuras levantadas (leve sonrisa)
        piezas.append({"nombre": f"comisura_{lado}", "forma": "caja", "pos": (0.0305 * lado, -0.1585, 0.0455),
                       "escala": (0.0125, 0.0042, 0.0042), "rot": (0, 0, -25 * lado), "color": labio})
        # párpado: cúpula de piel sobre el ojo; rostro_modelo la encoge hacia arriba (abierto) o la estira (cerrado)
        piezas.append({"nombre": f"parpado_{lado}", "forma": "esfera", "pos": (x, -0.1485, 0.133),
                       "escala": (0.0215, 0.0205, 0.0185), "color": piel})
    piezas.append({"nombre": "boca_interior", "forma": "esfera", "pos": (0.0, -0.170, 0.0405),
                   "escala": (0.022, 0.0055, 0.01), "color": INTERIOR_BOCA})
    piezas.append({"nombre": "labio_inf", "forma": "caja", "pos": (0.0, -0.170, 0.0405),
                   "escala": (0.019, 0.0045, 0.0038), "color": labio})
    piezas.append({"nombre": "boca", "forma": "caja", "pos": (0.0, -0.170, 0.0405),
                   "escala": (0.021, 0.0045, 0.0042), "color": labio})
    piezas.append({"nombre": "nariz", "forma": "esfera", "pos": (0.0, -0.1745, 0.092),
                   "escala": (0.016, 0.02, 0.019), "color": tono(piel, nariz_f)})
    return piezas


# Periodista: pelo corto castaño con volumen estilo cómic (casquete + flequillo levantado).
_PELO_PERIODISTA = (0.30, 0.18, 0.10)
_PELO_CANDIDATO = (0.09, 0.08, 0.08)
_SIEN_CANDIDATO = (0.34, 0.34, 0.33)       # sienes entrecanas

_PELO_P = [
    {"nombre": "pelo_casquete", "forma": "esfera", "pos": (0.0, 0.0, 0.158),
     "escala": (0.120, 0.128, 0.112), "color": _PELO_PERIODISTA, "contorno": True},
    {"nombre": "pelo_flequillo", "forma": "esfera", "pos": (0.0, -0.075, 0.225),
     "escala": (0.098, 0.062, 0.043), "rot": (0, 12, 0), "color": _PELO_PERIODISTA, "contorno": True},
    {"nombre": "pelo_tupe", "forma": "esfera", "pos": (-0.02, -0.07, 0.247),
     "escala": (0.058, 0.048, 0.03), "rot": (0, 0, -15), "color": _PELO_PERIODISTA, "contorno": True},
]

# Candidato: pelo corto oscuro peinado hacia atrás aspecto presidencial.
_PELO_C = [
    {"nombre": "pelo_casquete", "forma": "esfera", "pos": (0.0, 0.004, 0.152),
     "escala": (0.118, 0.126, 0.108), "color": _PELO_CANDIDATO, "contorno": True},
    {"nombre": "pelo_peinado", "forma": "esfera", "pos": (0.0, -0.045, 0.232),
     "escala": (0.098, 0.088, 0.034), "rot": (0, -8, 0), "color": _PELO_CANDIDATO, "contorno": True},
] + [
    {"nombre": f"pelo_sien_{lado}", "forma": "esfera", "pos": (0.108 * lado, -0.07, 0.168),
     "escala": (0.010, 0.022, 0.02), "color": _SIEN_CANDIDATO}
    for lado in (-1, 1)
]

ROSTRO_POR_ROL = {
    "periodista": _rasgos(PIEL_PERIODISTA, (0.22, 0.13, 0.07), (0.24, 0.14, 0.08), (0.45, 0.17, 0.13),
                          0.93, 0.92) + _PELO_P,
    "candidato": _rasgos(PIEL_CANDIDATO, (0.10, 0.06, 0.03), (0.07, 0.06, 0.06), (0.14, 0.07, 0.05),
                         0.88, 0.9) + _PELO_C,
}
