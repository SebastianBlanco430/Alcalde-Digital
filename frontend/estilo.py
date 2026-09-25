"""
Estilo visual compartido (paleta y reglas de color) de la interfaz.

Python PURO: no importa ursina ni pygame, así se prueba con pytest sin abrir
ventana (tests/test_estilo.py). Los colores son tuplas RGB de 0 a 255 y son
IDÉNTICOS a los de la versión pygame original (retirada en el Módulo 5, donde
se verificó la paridad). La conversión a `ursina.color` (`color.rgb32(*rgb)`) la hace
`frontend/componentes.py`.
"""

# --- Paleta ------------------------------------------------------------------
COLOR_FONDO = (24, 26, 38)
COLOR_PANEL = (36, 39, 56)
COLOR_TARJETA = (46, 50, 71)
COLOR_TEXTO = (235, 235, 240)
COLOR_TEXTO_TENUE = (170, 172, 190)
COLOR_BARRA_FONDO = (60, 63, 84)

COLOR_BARRA_BAJO = (200, 70, 70)      # valor < 34: en zona de riesgo
COLOR_BARRA_MEDIO = (215, 180, 60)    # 34 <= valor <= 66: zona intermedia
COLOR_BARRA_ALTO = (80, 190, 110)     # valor > 66: zona saludable

COLOR_BOTON = (70, 90, 150)
COLOR_BOTON_HOVER = (95, 118, 185)
COLOR_BOTON_DESHABILITADO = (55, 57, 70)
COLOR_BOTON_TEXTO = (240, 240, 245)

# --- Umbrales de los tercios de un indicador ------------------------------------
UMBRAL_BAJO = 34     # valor < 34  -> "bajo"
UMBRAL_ALTO = 66     # valor > 66  -> "alto"; entre ambos (inclusive) -> "medio"

# Texto que se muestra en la interfaz para cada indicador del backend.
ETIQUETAS_INDICADORES = {
    "convivencia": "Convivencia",
    "confianza": "Confianza",
    "desinformacion": "Desinformación",
}


def nivel_indicador(valor):
    """Clasifica un indicador en tercios: "bajo" (< 34), "medio" (34 a 66) o "alto" (> 66).

    Misma regla que `_color_por_valor` de la versión pygame: rojo/amarillo/verde
    para que el jugador identifique de un vistazo qué indicador está en problemas.
    """
    if valor < UMBRAL_BAJO:
        return "bajo"
    if valor <= UMBRAL_ALTO:
        return "medio"
    return "alto"


_RGB_POR_NIVEL = {
    "bajo": COLOR_BARRA_BAJO,
    "medio": COLOR_BARRA_MEDIO,
    "alto": COLOR_BARRA_ALTO,
}


def rgb_por_valor(valor):
    """Tupla RGB (0-255) del relleno de barra que corresponde a `valor`."""
    return _RGB_POR_NIVEL[nivel_indicador(valor)]
