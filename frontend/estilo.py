# Estilo visual compartido (paleta y reglas de color) de la interfaz.
# Python puro: no importa ursina, así se prueba con pytest sin abrir ventana.
# Los colores son tuplas RGB de 0 a 255; frontend/componentes.py las convierte
# a `ursina.color`.

# --- Paleta ---
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
COLOR_BOTON_RESALTADO = (95, 118, 185)
COLOR_BOTON_DESHABILITADO = (55, 57, 70)
COLOR_BOTON_TEXTO = (240, 240, 245)

# --- Umbrales de los tercios de un indicador ---
UMBRAL_BAJO = 34     # valor < 34  -> "bajo"
UMBRAL_ALTO = 66     # valor > 66  -> "alto"; entre ambos (inclusive) -> "medio"

# Texto que se muestra en la interfaz para cada indicador del backend.
ETIQUETAS_INDICADORES = {
    "convivencia": "Convivencia",
    "confianza": "Confianza",
    "desinformacion": "Desinformación",
}


# Clasifica un indicador en "bajo" (< 34), "medio" (34 a 66) o "alto" (> 66).
def nivel_indicador(valor):
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


# Color RGB (0-255) del relleno de barra que corresponde a `valor`.
def rgb_por_valor(valor):
    return _RGB_POR_NIVEL[nivel_indicador(valor)]
