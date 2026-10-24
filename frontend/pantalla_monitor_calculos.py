# Pantallas del monitor de Civitas en el interior (lógica pura: NO importa ursina; se prueba con pytest).
#
# Dos pantallas «cómic cívico» (docs/DISENO.md) que frontend/pantalla_monitor.py dibuja con Pillow como UNA
# textura de ANCHO_PX x ALTO_PX (16:9, igual que el quad del monitor):
#   inicio de sesión: logo y nombre de Civitas, retrato y nombre del rol, el lugar, una barra de carga y un
#                     mensaje corto con sabor local (elegido sin azar global: siempre el mismo para rol + lugar).
#   cierre de sesión: despedida y resumen de la misión (decisiones, cambio de cada indicador dicho con palabras
#                     además del color, alcance); sin resultado, un mensaje genérico.
# Aquí viven los textos, las cajas en píxeles y la conversión de una caja de la textura a coordenadas locales
# del quad (la barra de carga es un quad hijo que se estira sin regenerar la textura).

from backend.logica.estado_partida import NOMBRES_INDICADORES

ANCHO_PX, ALTO_PX = 1280, 720          # tamaño de la textura (el quad del monitor es 16:9)

TITULO = "Civitas"
SUBTITULO = "la red de Ciudad Nova"
ETIQUETA_INICIO = "INICIANDO SESIÓN"
TEXTO_CARGA = "Cargando tu feed..."
TITULO_CIERRE = "Sesión cerrada"

# Cajas (x0, y0, x1, y1) en píxeles de la textura, con y hacia abajo (convención de Pillow).
CAJA_TARJETA = (72, 250, 1208, 610)
CAJA_RETRATO = (112, 290, 392, 570)
CAJA_BARRA = (432, 520, 1168, 568)     # carril de la barra de carga (con borde de tinta)
BORDE_BARRA_PX = 5
CAJA_MENSAJE = (72, 632, 1208, 700)

# Frases cortas con sabor de la favela (español con guiños en portugués), legibles para cualquiera.
MENSAJES_INICIO = (
    "Bom dia, Ciudad Nova: antes de compartir, pregunta quién lo dice.",
    "Conectando con el morro... la señal sube y baja como las escaleras.",
    "Dica do dia: una foto vieja puede parecer noticia nueva.",
    "En la laje se comenta de todo: verifica la fuente.",
    "Tudo bem? Hoy la red está movida: lee antes de reaccionar.",
    "Un rumor corre más rápido que la moto del mototaxi.",
)
MENSAJES_CIERRE = (
    "Valeu! Lo que decidiste ya circula por el barrio.",
    "Até a próxima: el morro sigue conectado.",
    "Obrigado: cada clic cuenta en Ciudad Nova.",
)
MENSAJE_SIN_RESULTADO = "Tu sesión terminó. Vuelve a la calle: la próxima misión te espera."

# Qué dirección es buena para cada indicador (la desinformación conviene que baje).
SUBIR_ES_BUENO = {"convivencia": True, "confianza": True, "desinformacion": False}


# Índice estable en [0, cantidad) para un texto: suma de códigos (sin hash(), que cambia en cada ejecución).
def _indice(texto, cantidad):
    return sum(ord(c) for c in texto) % cantidad


def mensaje_inicio(rol, lugar):
    return MENSAJES_INICIO[_indice(f"{rol}|{lugar}", len(MENSAJES_INICIO))]


def mensaje_cierre(rol, lugar):
    return MENSAJES_CIERRE[_indice(f"{lugar}|{rol}", len(MENSAJES_CIERRE))]


def despedida(nombre_rol):
    return f"Até logo, {nombre_rol}!"


# Una línea del resumen por indicador: (etiqueta, texto con signo y palabra, «bueno», «malo» o «igual»).
# La palabra (sube / baja / sin cambio) dice lo mismo que el color, para quien no distingue los colores.
def linea_indicador(nombre, delta, etiquetas):
    etiqueta = etiquetas.get(nombre, nombre)
    if delta == 0:
        return etiqueta, "sin cambio", "igual"
    sube = delta > 0
    texto = f"{'+' if sube else '-'}{abs(delta)} ({'sube' if sube else 'baja'})"
    bueno = sube == SUBIR_ES_BUENO.get(nombre, True)
    return etiqueta, texto, "bueno" if bueno else "malo"


# Resumen del cierre a partir del `resultado` de LoteMision (dict o None). Devuelve None si no hay resultado
# usable; si no, {"decisiones": texto, "indicadores": [(etiqueta, texto, tono)], "alcance": texto o None}.
def resumen_cierre(resultado, etiquetas):
    if not isinstance(resultado, dict) or "deltas" not in resultado:
        return None
    decisiones = int(resultado.get("decisiones", 0))
    deltas = resultado.get("deltas") or {}
    indicadores = [linea_indicador(n, int(deltas.get(n, 0)), etiquetas) for n in NOMBRES_INDICADORES]
    alcance = resultado.get("alcance_total")
    texto_alcance = None
    if alcance:
        texto_alcance = f"Tu publicación llegó a {alcance} {'persona' if alcance == 1 else 'personas'}"
    texto = f"{decisiones} {'decisión tomada' if decisiones == 1 else 'decisiones tomadas'}"
    return {"decisiones": texto, "indicadores": indicadores, "alcance": texto_alcance}


# Caja de píxeles (y hacia abajo) -> (x, y, ancho, alto) en las coordenadas locales del quad del monitor, que
# va de -0.5 a 0.5 en ambos ejes con y hacia arriba. `progreso` en [0, 1] recorta el ancho desde la izquierda.
def caja_en_quad(caja, progreso=1.0, ancho_px=ANCHO_PX, alto_px=ALTO_PX):
    x0, y0, x1, y1 = caja
    progreso = min(1.0, max(0.0, progreso))
    ancho = (x1 - x0) * progreso
    cx = x0 + ancho / 2
    cy = (y0 + y1) / 2
    return cx / ancho_px - 0.5, 0.5 - cy / alto_px, ancho / ancho_px, (y1 - y0) / alto_px


# Relleno de la barra (dentro del borde de tinta) en coordenadas del quad, para el avance dado.
def relleno_barra(progreso):
    x0, y0, x1, y1 = CAJA_BARRA
    b = BORDE_BARRA_PX
    return caja_en_quad((x0 + b, y0 + b, x1 - b, y1 - b), progreso)
