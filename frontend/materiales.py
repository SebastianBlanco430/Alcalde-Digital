# Paleta y estética compartidas del mundo digital (rejilla, wireframe, neón, avatar).
# Python puro: solo constantes RGB (0-255) y funciones de color, SIN ursina y SIN escenas,
# para que las escenas que lo usan (mundo digital, sectores corruptos del parkour) lo
# importen sin acoplarse entre sí. Convención de color igual a frontend/estilo.py: tuplas RGB;
# la conversión a Color de Ursina la hace quien dibuja (componentes.rgb).

from frontend import estilo

# -- Fondo y rejilla --
DIGITAL_FONDO = (6, 8, 20)             # vacío casi negro con tinte azul
DIGITAL_REJILLA = (24, 62, 96)         # líneas de la rejilla del suelo
DIGITAL_REJILLA_EJE = (40, 110, 150)   # líneas mayores cada N celdas
DIGITAL_NIEBLA = (10, 16, 36)

# -- Wireframe y neón --
NEON_CIAN = (70, 230, 255)             # estructuras y avatar (reutiliza el cian de ACENTO_SECUNDARIO)
NEON_MAGENTA = (255, 70, 200)          # elementos interactivos / evidencia
NEON_AMARILLO = estilo.COLOR_ACENTO    # objetivo (mismo amarillo del destino de las misiones)
NEON_VERDE = (90, 255, 150)            # correcto / desbloqueado
NEON_ROJO = (255, 70, 90)              # peligro / sector corrupto / contradicción

WIREFRAME = NEON_CIAN
WIREFRAME_TENUE = (36, 110, 130)

# -- Avatar --
AVATAR_NUCLEO = (210, 250, 255)
AVATAR_CONTORNO = NEON_CIAN

# -- Glitch (efecto de entrada y salida) --
GLITCH_A = NEON_MAGENTA
GLITCH_B = NEON_CIAN

# -- Sector corrupto (parkour): misma estética que el digital con tinte de alerta --
CORRUPTO_FONDO = (18, 6, 14)
CORRUPTO_REJILLA = (96, 24, 52)
CORRUPTO_PLATAFORMA = (150, 40, 90)

_TEMAS = {
    "digital": {"fondo": DIGITAL_FONDO, "rejilla": DIGITAL_REJILLA, "acento": NEON_CIAN},
    "corrupto": {"fondo": CORRUPTO_FONDO, "rejilla": CORRUPTO_REJILLA, "acento": NEON_ROJO},
}


# Colores base de un tema ("digital" o "corrupto"): dict con fondo, rejilla y acento.
# ValueError si el tema no existe. Retorna copia.
def tema(nombre):
    if nombre not in _TEMAS:
        raise ValueError(f"Tema inexistente: {nombre!r}; se esperaba uno de {tuple(_TEMAS)}.")
    return dict(_TEMAS[nombre])


# Color con alfa (0-255) para mallas translúcidas; el resultado es (r, g, b, a).
def con_alfa(rgb, alfa):
    if not 0 <= alfa <= 255:
        raise ValueError(f"alfa fuera de rango: {alfa!r}")
    return (rgb[0], rgb[1], rgb[2], int(alfa))


# Mezcla lineal entre dos colores RGB; t en [0, 1] (se recorta). Útil para pulsos de neón.
def mezclar(rgb_a, rgb_b, t):
    t = max(0.0, min(1.0, t))
    return tuple(round(a + (b - a) * t) for a, b in zip(rgb_a, rgb_b))


# Neón atenuado hacia el fondo del tema; intensidad en [0, 1].
def neon_atenuado(rgb, intensidad, fondo=DIGITAL_FONDO):
    return mezclar(fondo, rgb, intensidad)
