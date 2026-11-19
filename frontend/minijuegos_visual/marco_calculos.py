# Cálculos PUROS (sin ursina) del «marco» común de los minijuegos de verificar: mesa de papel, cabecera con el rumor en una
# tira de papel, panel de resultado con sello y textos del resultado. Lo dibuja frontend/minijuegos_visual/marco_mesa.py.
#
# Bandera: ALCALDE_MARCO_VISUAL=0 apaga todo el marco (vuelve el fondo azul, la cabecera y el banner de siempre).

import re

from frontend import banderas_visuales as bv
from frontend import estilo

MARCO_VISUAL = True
VARIABLE = "ALCALDE_MARCO_VISUAL"

# --- Colores ---
MESA = (104, 80, 58)                  # mesa de redacción; PAPEL encima: contraste 6,8
MESA_VETA = (70, 50, 34)              # vetas finas (alfa bajo)
MESA_LUZ = (150, 120, 90)
PAPEL = estilo.PAPEL
TINTA = estilo.TINTA
ROJO_PESTANA = (120, 40, 40)          # pestaña «RUMOR»
SELLO_BIEN = (30, 110, 60)
SELLO_MAL = (170, 40, 40)
TEXTO_SUAVE = (90, 70, 50)            # etiquetas sobre papel (regular)
TEXTO_SOBRE_MESA = PAPEL              # ayuda de teclas y títulos sobre la mesa

# --- Escala tipográfica (px de referencia; nunca por debajo de lo que había) ---
PX_TITULO = 32
PX_RUMOR = 19
PX_CUERPO = 20
PX_ETIQUETA = 17
PX_AYUDA = 16
PX_TITULO_RESULTADO = 30
PX_DETALLE_RESULTADO = 19
PX_PISTA = 17

# --- Receta de borde y sombra (una sola) ---
BORDE_PX = estilo.GROSOR_BORDE_PX
SOMBRA_PX = estilo.DESPLAZAMIENTO_SOMBRA_PX
RADIO_PAPEL_PX = 6

ROTACION_TIRA = -0.6                   # grados; 0 con «reducir movimiento»


def activo():
    return bv.activa(MARCO_VISUAL, VARIABLE)


def rotacion_tira(reducir):
    return 0.0 if reducir else ROTACION_TIRA


def texto_lugar(destino_glosado):
    """Nombre del lugar SIN la glosa entre paréntesis («Escola de Samba (Escuela de samba)» -> «Escola de Samba»)."""
    limpio = re.sub(r"\s*\([^)]*\)", "", str(destino_glosado or ""))
    return " ".join(limpio.split())


def frase_pista(destino_glosado, pista):
    """«Fuiste a X y viste: …»: el lugar se dice una sola vez."""
    lugar = texto_lugar(destino_glosado)
    pista = " ".join(str(pista or "").split())
    if not lugar:
        return "Viste: " + pista if pista else ""
    return f"Fuiste a {lugar} y viste: {pista}"


def veredicto(es_verdadera):
    return "El rumor era cierto." if es_verdadera else "El rumor era falso."


def titulo_resultado(bien, por_poco=False):
    if bien:
        return "Verificaste bien"
    return "Se te escapó algo"


def palabra_sello(bien):
    return "BIEN" if bien else "OJO"


def color_sello(bien):
    return SELLO_BIEN if bien else SELLO_MAL


def chip_propina(propina):
    """Texto de la moneda de propina, o None si no hay (sin cifras de indicadores: es dinero del jugador)."""
    try:
        propina = int(propina)
    except (TypeError, ValueError):
        return None
    return f"Propina R$ {propina}" if propina > 0 else None


def chip_por_poco(por_poco):
    return "Por poco" if por_poco else None


def vetas(n=46, semilla=7):
    """Vetas de la mesa: lista de (x, y, largo, alfa) en fracciones 0..1 del ancho/alto; determinista, alfa 10-15 %."""
    import random
    azar = random.Random(semilla)
    salida = []
    for _ in range(n):
        salida.append((azar.random(), azar.random(), 0.08 + azar.random() * 0.30, round(255 * (0.10 + azar.random() * 0.05))))
    return salida



# Acento de color de cada portada (relleno del papel de la ilustración); identidad del minijuego, nunca estado.
ACENTOS_PORTADA = {
    "rastrear": (196, 150, 100),
    "comparar": (240, 170, 90),
    "cronologia": (240, 208, 96),
    "chat": (120, 190, 225),
    "senales": (130, 190, 165),
    "contrarreloj": (200, 222, 170),
}
ACENTO_PORTADA_GENERICO = (214, 196, 160)
ROTACION_PORTADA = -1.5          # grados del papel de la ilustración (0 con «reducir movimiento»)
ETIQUETA_REDES = "APUNTA ESTO PARA TUS REDES"
ETIQUETA_ANTES = "ANTES DE EMPEZAR"


def acento_portada(minijuego_id):
    return ACENTOS_PORTADA.get(minijuego_id, ACENTO_PORTADA_GENERICO)


def rotacion_portada(reducir):
    return 0.0 if reducir else ROTACION_PORTADA


LINEA_COMPACTA = 1.14        # interlineado de los textos del panel de resultado (el normal, 1,32, no cabe)


def limitar_lineas(lineas, maximo):
    """Primeras `maximo` líneas; si sobran, la última acaba en «…» (nunca se corta a media palabra)."""
    lineas = list(lineas)
    if len(lineas) <= maximo:
        return lineas
    salida = lineas[:maximo]
    salida[-1] = salida[-1].rstrip(" ,;:.") + "…"
    return salida
