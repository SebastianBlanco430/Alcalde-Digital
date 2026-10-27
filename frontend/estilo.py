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
COLOR_BOTON_RESALTADO = (80, 102, 168)   # texto claro encima: contraste >4,5 (antes 95,118,185 = 3,9)
COLOR_BOTON_DESHABILITADO = (55, 57, 70)
COLOR_BOTON_TEXTO = (240, 240, 245)
COLOR_ACENTO = (255, 220, 60)           # amarillo del destino; reservado para el botón primario
COLOR_ACENTO_TEXTO = (24, 26, 38)      # texto oscuro sobre el acento

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


# ===========================================================================
# Roles de color (T1, docs/DISENO.md sección 2). Solo se AÑADEN constantes:
# los valores de arriba no cambian. Los valores del cian y del amarillo viven
# aquí (fuente única); los módulos que hoy los duplican se alinean después.
# ===========================================================================

# --- Tinta y papel (estilo «cómic cívico») ---
TINTA = (18, 20, 32)              # contornos, sombras duras, texto sobre amarillo
PAPEL = (250, 244, 228)           # iconos, teclas, retratos
COLOR_SUPERFICIE_ALTA = (58, 62, 88)   # hover de tarjeta, chip

# --- Acentos ---
ACENTO_PRIMARIO = COLOR_ACENTO    # amarillo: destino y acción principal
ACENTO_SECUNDARIO = (70, 220, 255)     # cian: ruta e información
COLOR_RUTA = ACENTO_SECUNDARIO    # cian de la ruta (minimapa y mundo)
COLOR_DESTINO = ACENTO_PRIMARIO   # amarillo del destino (igual que la baliza)

# --- Estados ---
ESTADO_EXITO = COLOR_BARRA_ALTO   # (80, 190, 110)
ESTADO_AVISO = (215, 180, 60)
ESTADO_ERROR = (214, 62, 62)
ESTADO_INFO = ACENTO_SECUNDARIO

# --- Botones: secundario y bordes ---
GROSOR_BORDE_PX = 3               # borde de tinta (2 en HUD denso)
GROSOR_BORDE_DENSO_PX = 2
DESPLAZAMIENTO_SOMBRA_PX = (4, -5)  # sombra plana: (+x, -y) respecto al panel
ALFA_SOMBRA = 160                 # sobre 255
RADIO_CHIP_PX = 6
RADIO_TARJETA_PX = 10
RADIO_PANEL_PX = 14

# --- Lugares: identidad, nunca estado ---
COLORES_LUGAR = {
    "Praça da Sé": (240, 200, 90),
    "Prefeitura": (70, 110, 190),
    "Universidade": (140, 110, 200),
    "Parque": (80, 170, 100),
    "Morro da Esperança": (230, 120, 150),
    "Rodoviária": (235, 140, 60),
    "Hospital": (60, 180, 170),
    "Mercado": (200, 96, 58),
    "Escola de Samba": (220, 60, 160),
    "Rádio": (110, 190, 60),
    "Estação do Teleférico": (120, 130, 160),
    # Mapa grande
    "Posto de Saúde Vila Nova": (46, 160, 130),
    "Ponto de Mototáxi da Entrada": (240, 150, 40),
    "Padaria Pão Quente": (220, 150, 60),
    "Supermercado Dois Irmãos": (200, 70, 60),
    "Oficina do Seu Zé": (230, 170, 40),
    "Bar do Cabo": (190, 90, 50),
    "Igreja Nossa Senhora da Esperança": (120, 150, 200),
    "Escola Municipal Paulo Freire": (60, 130, 220),
    "Salão da Dona Lu": (210, 80, 140),
    "Campo de Várzea": (90, 170, 70),
    "Feira da Ladeira": (230, 120, 90),
    "Mirante do Alto": (150, 120, 190),
    "Estação Alto do Morro": (110, 130, 170),
}

# --- Roles de personaje propuestos (decisión del dueño, T15; aún NO usados) ---
COLORES_ROL_PROPUESTOS = {
    "ciudadano": (66, 133, 244),
    "periodista": (46, 184, 116),
    "influencer": (232, 84, 150),
    "candidato": (240, 226, 190),
}


# Contraste WCAG entre dos colores RGB 0-255 (1 a 21).
def contraste(rgb_a, rgb_b):
    def luminancia(c):
        lineal = [(v / 255 / 12.92) if v / 255 <= 0.03928 else (((v / 255) + 0.055) / 1.055) ** 2.4 for v in c]
        return 0.2126 * lineal[0] + 0.7152 * lineal[1] + 0.0722 * lineal[2]
    claro, oscuro = sorted((luminancia(rgb_a), luminancia(rgb_b)), reverse=True)
    return (claro + 0.05) / (oscuro + 0.05)
