# Menú de inicio «estilo BOTW» (sesión G, 24-nov): lógica PURA (sin ursina), con tests en tests/test_menu_botw_calculos.py.
# La vista es frontend/menu_botw.py y la monta frontend/escenas/escena_inicio.py.
#
# Diseño aprobado (lienzo «Alcalde Digital — Menú de inicio»): fondo de la ilustración del póster a pantalla completa con
# un zoom lento (Ken Burns), velos de tinta a la derecha y abajo, logo arriba a la derecha, opciones en cursiva abajo a la
# derecha con la seleccionada en amarillo y una flecha, pie con ayuda de controles y versión.
# Todas las medidas del diseño están en píxeles A 720p: `u(px)` las pasa a unidades de camera.ui (alto de pantalla = 1),
# así todo escala con la ventana. x crece a la derecha, y hacia arriba; (0, 0) es el centro de la pantalla.
#
# BANDERA: ALCALDE_MENU_BOTW (encendida por defecto). =0 deja el menú de siempre, idéntico. Si faltan el fondo o el logo,
# o algo falla al construir, la escena cae sola al menú de siempre y avisa una vez por stderr.
# REDUCIR MOVIMIENTO (Ajustes › Movimiento o ALCALDE_REDUCIR_MOVIMIENTO=1): fondo quieto, logo quieto y entrada con solo
# el fundido.

import math
import os
from pathlib import Path

MENU_BOTW = True
VARIABLE = "ALCALDE_MENU_BOTW"
_APAGADO = ("0", "false", "no", "off")
_ENCENDIDO = ("1", "true", "si", "sí", "on")

RAIZ = Path(__file__).resolve().parent.parent
CARPETA = RAIZ / "assets" / "ui" / "menu"
FONDO = CARPETA / "fondo_menu.jpg"          # reemplazable sin tocar código (misma ruta, 16:9; ideal 2560 × 1440)
LOGO = CARPETA / "logo.png"                 # lo genera tools/generar_logo_menu.py
ASPECTO_FONDO = 16 / 9

# -- Paleta del diseño (RGB 0-255) --
TINTA = (30, 27, 46)              # #1E1B2E: contornos y sombras
VELO = (24, 18, 44)               # rgba(24,18,44) de los velos
AMARILLO = (255, 217, 61)         # #FFD93D: opción seleccionada y flecha
BLANCO = (255, 255, 255)
TEXTO_DETALLE = (237, 231, 255)   # #EDE7FF
TEXTO_PIE = (244, 240, 255)       # #F4F0FF

# -- Medidas a 720p (px) --
ALTO_REF_PX = 720
LOGO_DERECHA_PX, LOGO_ARRIBA_PX = 64, 40
MENU_DERECHA_PX, MENU_ABAJO_PX, MENU_SEPARACION_PX = 72, 112, 14
OPCION_PX = 29                    # cursiva; la seleccionada en negrita
ALTO_LINEA_OPCION_PX = 36         # alto de la línea de una opción (29 px de letra + interlineado)
DETALLE_PX = 14                   # «Partida guardada: …» bajo «Continuar» (solo seleccionada)
ALTO_LINEA_DETALLE_PX = 17
SEPARACION_DETALLE_PX = 2
DESPLAZAMIENTO_SELECCION_PX = 6   # la seleccionada se corre a la izquierda
FLECHA_ANCHO_PX, FLECHA_ALTO_PX, FLECHA_SEPARACION_PX = 26, 18, 12
SOMBRA_TEXTO_PX = 2               # sombra de tinta de las opciones
PIE_MARGEN_PX, PIE_ABAJO_PX = 40, 26
PIE_AYUDA_PX = 14
PIE_VERSION_PX = 13
ALTO_LINEA_PIE_PX = 16
VELO_DERECHA = ((0.0, 0.78), (0.26, 0.45), (0.52, 0.0))    # (fracción del ancho desde el borde derecho, alfa)
VELO_INFERIOR_PX, VELO_INFERIOR_ALFA = 200, 0.55

# -- Logo (PNG generado a 4× de 720p = 2× de 1440p, con margen transparente para las sombras) --
ESCALA_LOGO_PNG = 4
MARGEN_LOGO_PX = 12
SOMBRA_LOGO_PX = 6                 # la sombra plana de «ALCALDE» sobresale a la derecha del cuadro del logo

# -- Movimiento --
ZOOM_ESCALAS = (1.02, 1.09)
ZOOM_DESPLAZAMIENTO = (-0.015, -0.01)   # fracción del tamaño del fondo (x, y), como translate(-1.5 %, -1 %) en CSS
ZOOM_IDA_S = 40.0                       # 40 s de ida y 40 de vuelta
FLOTAR_PX, FLOTAR_S = 6, 3.2            # el logo sube 6 px en 3,2 s y vuelve en otros 3,2
FUNDIDO_S = 0.6
LOGO_INICIO_S, LOGO_DURACION_S = 0.1, 0.5
LOGO_REBOTE = (0.9, 1.03, 1.0)          # escala del logo al entrar: 0,9 → 1,03 → 1
LOGO_PICO = 0.6                         # fracción de la duración en que llega a 1,03
OPCIONES_INICIO_S, OPCIONES_PASO_S, OPCION_DURACION_S = 0.3, 0.06, 0.28
OPCION_ENTRADA_PX = 18                  # cada opción entra desde 18 px a la derecha
DT_MAXIMO = 1 / 30                      # un frame largo (carga) no se come la entrada

# -- Navegación (teclado, cruceta y palo) --
RETARDO_REPETICION_S = 0.38
PERIODO_REPETICION_S = 0.11
UMBRAL_PALO = 0.5                       # el palo cuenta como ↑/↓ al pasar de esto (además de la zona muerta del mando)

# -- Opciones --
CONTINUAR, NUEVA, ONLINE, AJUSTES, SALIR = "continuar", "nueva", "online", "ajustes", "salir"
ORDEN = (CONTINUAR, NUEVA, ONLINE, AJUSTES, SALIR)
TEXTOS = {CONTINUAR: "Continuar", ONLINE: "En línea", AJUSTES: "Ajustes", SALIR: "Salir"}
AYUDA = "↑ ↓ elegir · Enter / A aceptar · Esc / B volver"
VERSION = ("Ver. 1.0 · Feria Gamer 2026", "Universidad del Norte · Estructura de Datos II")
PREFIJO_DETALLE = "Partida guardada: "


def activo(entorno=None):
    """¿Menú BOTW? ALCALDE_MENU_BOTW manda sobre MENU_BOTW."""
    valor = (os.environ if entorno is None else entorno).get(VARIABLE, "").strip().lower()
    if valor in _APAGADO:
        return False
    if valor in _ENCENDIDO:
        return True
    return bool(MENU_BOTW)


def recursos_faltantes(fondo=FONDO, logo=LOGO):
    """Rutas de los recursos que faltan (lista vacía = todo listo)."""
    return [str(r) for r in (fondo, logo) if not Path(r).is_file()]


def u(px):
    """Píxeles a 720p → unidades de camera.ui."""
    return px / ALTO_REF_PX


def px_en_pantalla(px720, alto_ventana_px):
    """Tamaño real en píxeles de algo que mide `px720` a 720p en una ventana de `alto_ventana_px` de alto."""
    return px720 * alto_ventana_px / ALTO_REF_PX


# ---------------------------------------------------------------------------------------------------------------------
# Fondo: ajuste «cover» y zoom lento
# ---------------------------------------------------------------------------------------------------------------------

def cover(aspecto_ventana, aspecto_imagen=ASPECTO_FONDO):
    """(ancho, alto) en unidades UI de la imagen que llena la pantalla (alto 1, ancho = aspecto) sin deformarse:
    sobra por los lados (ventana más estrecha que la imagen) o por arriba y abajo (más ancha)."""
    if aspecto_ventana >= aspecto_imagen:
        ancho = aspecto_ventana
        return ancho, ancho / aspecto_imagen
    return aspecto_imagen, 1.0


def suavizar(x):
    """0..1 → 0..1 con arranque y llegada suaves (coseno)."""
    x = min(1.0, max(0.0, x))
    return 0.5 - 0.5 * math.cos(math.pi * x)


def avance_zoom(t, ida=ZOOM_IDA_S):
    """Fase del Ken Burns a los `t` s: 0 → 1 en `ida` s y vuelta a 0 en otros `ida` (suavizado)."""
    if t <= 0:
        return 0.0
    ciclo = t % (2 * ida)
    lineal = ciclo / ida if ciclo <= ida else 2 - ciclo / ida
    return suavizar(lineal)


def zoom(t, reducido=False):
    """(escala, dx, dy): dx, dy en fracción del tamaño del fondo (CSS: scale(s) translate(dx, dy), y hacia abajo)."""
    if reducido:
        return ZOOM_ESCALAS[0], 0.0, 0.0
    f = avance_zoom(t)
    escala = ZOOM_ESCALAS[0] + (ZOOM_ESCALAS[1] - ZOOM_ESCALAS[0]) * f
    return escala, ZOOM_DESPLAZAMIENTO[0] * f, ZOOM_DESPLAZAMIENTO[1] * f


def transformacion_fondo(t, aspecto_ventana, reducido=False, aspecto_imagen=ASPECTO_FONDO):
    """(x, y, ancho, alto) del quad del fondo en unidades UI a los `t` s. El translate va dentro del scale (CSS), y la
    y de CSS crece hacia abajo: por eso dy se invierte."""
    ancho, alto = cover(aspecto_ventana, aspecto_imagen)
    escala, dx, dy = zoom(t, reducido)
    return escala * dx * ancho, -escala * dy * alto, escala * ancho, escala * alto


def cubre_pantalla(x, y, ancho, alto, aspecto_ventana, tolerancia=1e-9):
    """¿El rectángulo (centro x, y; ancho × alto) tapa toda la pantalla? (ningún borde del fondo a la vista)."""
    return (x - ancho / 2 <= -aspecto_ventana / 2 + tolerancia and x + ancho / 2 >= aspecto_ventana / 2 - tolerancia
            and y - alto / 2 <= -0.5 + tolerancia and y + alto / 2 >= 0.5 - tolerancia)


# ---------------------------------------------------------------------------------------------------------------------
# Velos
# ---------------------------------------------------------------------------------------------------------------------

def velo_derecha(aspecto):
    """Paradas del velo lateral: [(x en UI, alfa 0-1)] de izquierda a derecha; a la izquierda de la primera, alfa 0."""
    borde = aspecto / 2
    return [(borde - f * aspecto, a) for f, a in reversed(VELO_DERECHA)]


def velo_inferior():
    """(y_abajo, y_arriba, alfa_abajo) del velo inferior (alfa 0 arriba)."""
    return -0.5, -0.5 + u(VELO_INFERIOR_PX), VELO_INFERIOR_ALFA


def alfa_velo_en(x_ui, y_ui, aspecto):
    """Alfa combinado de los dos velos en un punto (para estimar el contraste del texto sobre el fondo)."""
    paradas = velo_derecha(aspecto)
    if x_ui <= paradas[0][0]:
        a1 = paradas[0][1]
    elif x_ui >= paradas[-1][0]:
        a1 = paradas[-1][1]
    else:
        a1 = 0.0
        for (x0, v0), (x1, v1) in zip(paradas, paradas[1:]):
            if x0 <= x_ui <= x1:
                a1 = v0 + (v1 - v0) * ((x_ui - x0) / (x1 - x0) if x1 > x0 else 0.0)
                break
    y0, y1, a_abajo = velo_inferior()
    a2 = 0.0 if y_ui >= y1 else a_abajo * (y1 - max(y_ui, y0)) / (y1 - y0)
    return 1 - (1 - a1) * (1 - a2)


# ---------------------------------------------------------------------------------------------------------------------
# Logo
# ---------------------------------------------------------------------------------------------------------------------

def rect_logo(aspecto, ancho_png, alto_png):
    """(x, y, ancho, alto) del quad del logo (centro, en UI). El cuadro del logo (sin margen ni la sombra de la derecha)
    queda a LOGO_DERECHA_PX del borde derecho y a LOGO_ARRIBA_PX del de arriba."""
    ancho = u(ancho_png / ESCALA_LOGO_PNG)
    alto = u(alto_png / ESCALA_LOGO_PNG)
    derecha = aspecto / 2 - u(LOGO_DERECHA_PX) + u(MARGEN_LOGO_PX + SOMBRA_LOGO_PX)
    arriba = 0.5 - u(LOGO_ARRIBA_PX) + u(MARGEN_LOGO_PX)
    return derecha - ancho / 2, arriba - alto / 2, ancho, alto


def flotacion(t, reducido=False):
    """Desplazamiento vertical del logo (UI, hacia arriba): sube FLOTAR_PX en FLOTAR_S s y vuelve, suavizado."""
    if reducido or t <= 0:
        return 0.0
    ciclo = t % (2 * FLOTAR_S)
    lineal = ciclo / FLOTAR_S if ciclo <= FLOTAR_S else 2 - ciclo / FLOTAR_S
    return u(FLOTAR_PX) * suavizar(lineal)


# ---------------------------------------------------------------------------------------------------------------------
# Entrada al abrir el juego
# ---------------------------------------------------------------------------------------------------------------------

def fundido(t):
    """Alfa del negro que tapa la pantalla (1 → 0 en FUNDIDO_S s). Igual con «reducir movimiento»."""
    return max(0.0, 1.0 - t / FUNDIDO_S) if t < FUNDIDO_S else 0.0


def escala_logo(t, reducido=False):
    """Rebote del logo: 0,9 → 1,03 → 1 en LOGO_DURACION_S s (empieza a los LOGO_INICIO_S s)."""
    if reducido:
        return 1.0
    x = (t - LOGO_INICIO_S) / LOGO_DURACION_S
    a, pico, fin = LOGO_REBOTE
    if x <= 0:
        return a
    if x >= 1:
        return fin
    if x < LOGO_PICO:
        return a + (pico - a) * suavizar(x / LOGO_PICO)
    return pico + (fin - pico) * suavizar((x - LOGO_PICO) / (1 - LOGO_PICO))


def alfa_logo(t, reducido=False):
    if reducido:
        return 1.0
    return min(1.0, max(0.0, (t - LOGO_INICIO_S) / (LOGO_DURACION_S * 0.4)))


def entrada_opcion(t, indice, reducido=False):
    """(alfa, desplazamiento x en UI) de la opción `indice` (0 = la de arriba): aparecen escalonadas OPCIONES_PASO_S."""
    if reducido:
        return 1.0, 0.0
    x = (t - OPCIONES_INICIO_S - indice * OPCIONES_PASO_S) / OPCION_DURACION_S
    if x <= 0:
        return 0.0, u(OPCION_ENTRADA_PX)
    if x >= 1:
        return 1.0, 0.0
    s = suavizar(x)
    return s, u(OPCION_ENTRADA_PX) * (1 - s)


def entrada_terminada(t, n_opciones, reducido=False):
    fin = FUNDIDO_S if reducido else max(FUNDIDO_S, LOGO_INICIO_S + LOGO_DURACION_S,
                                         OPCIONES_INICIO_S + max(0, n_opciones - 1) * OPCIONES_PASO_S
                                         + OPCION_DURACION_S)
    return t >= fin


def paso_reloj(dt):
    """dt acotado: el primer frame tras la carga puede durar segundos y se comería la entrada."""
    return min(max(0.0, dt), DT_MAXIMO)


# ---------------------------------------------------------------------------------------------------------------------
# Opciones: cuáles, en qué orden, foco inicial y colocación
# ---------------------------------------------------------------------------------------------------------------------

def opciones(hay_guardado, hay_online, hay_ajustes):
    """Ids de las opciones visibles, en orden: Continuar (solo con guardado), Partida nueva, En línea (solo con ONLINE),
    Ajustes (solo si main.py pasa `al_ajustes`) y Salir."""
    visibles = {CONTINUAR: hay_guardado, NUEVA: True, ONLINE: hay_online, AJUSTES: hay_ajustes, SALIR: True}
    return [i for i in ORDEN if visibles[i]]


def texto(id_opcion, hay_guardado):
    if id_opcion == NUEVA:
        return "Partida nueva" if hay_guardado else "Empezar"
    return TEXTOS[id_opcion]


def foco_inicial(ids):
    """Índice inicial: «Continuar» si está; si no, «Partida nueva»."""
    for objetivo in (CONTINUAR, NUEVA):
        if objetivo in ids:
            return ids.index(objetivo)
    return 0


def colocar_opciones(aspecto, n, con_detalle=None):
    """y del centro de la línea de cada opción (índice 0 = arriba), apiladas desde abajo como en el diseño (flex
    column alineado abajo). `con_detalle` = índice de la opción que muestra su detalle debajo (o None): ocupa espacio y
    empuja hacia arriba a esa opción y a las de encima. Devuelve (x_derecha, [y_centro], [y_detalle o None])."""
    x_derecha = aspecto / 2 - u(MENU_DERECHA_PX)
    ys, ys_detalle = [0.0] * n, [None] * n
    fondo = -0.5 + u(MENU_ABAJO_PX)
    for i in reversed(range(n)):
        if i == con_detalle:
            ys_detalle[i] = fondo + u(ALTO_LINEA_DETALLE_PX) / 2
            fondo += u(ALTO_LINEA_DETALLE_PX + SEPARACION_DETALLE_PX)
        ys[i] = fondo + u(ALTO_LINEA_OPCION_PX) / 2
        fondo += u(ALTO_LINEA_OPCION_PX + MENU_SEPARACION_PX)
    return x_derecha, ys, ys_detalle


def x_opcion(x_derecha, seleccionada):
    """Borde derecho del texto de una opción: la seleccionada se corre DESPLAZAMIENTO_SELECCION_PX a la izquierda."""
    return x_derecha - (u(DESPLAZAMIENTO_SELECCION_PX) if seleccionada else 0.0)


def x_flecha(x_izquierda_texto):
    """Centro x de la flecha: a FLECHA_SEPARACION_PX a la izquierda del texto seleccionado."""
    return x_izquierda_texto - u(FLECHA_SEPARACION_PX) - u(FLECHA_ANCHO_PX) / 2


def pie(aspecto):
    """((x_izq, y) de la ayuda, (x_der, y_linea1, y_linea2) de la versión): centros de línea en UI."""
    y_base = -0.5 + u(PIE_ABAJO_PX)
    ayuda = (-aspecto / 2 + u(PIE_MARGEN_PX), y_base + u(ALTO_LINEA_PIE_PX) / 2)
    version = (aspecto / 2 - u(MENU_DERECHA_PX), y_base + u(ALTO_LINEA_PIE_PX) * 1.5 + u(2),
               y_base + u(ALTO_LINEA_PIE_PX) / 2)
    return ayuda, version


# ---------------------------------------------------------------------------------------------------------------------
# Navegación
# ---------------------------------------------------------------------------------------------------------------------

def siguiente(indice, paso, visibles, envolver=True):
    """Índice siguiente en la lista completa saltando las opciones ocultas (`visibles`: lista de bool). Con
    `envolver`, de la última pasa a la primera (y al revés); sin él se queda en el extremo. Sin ninguna visible, None."""
    n = len(visibles)
    if n == 0 or not any(visibles):
        return None
    if not (0 <= indice < n) or not visibles[indice]:
        indice = next(i for i in range(n) if visibles[i])
        return indice
    if paso == 0:
        return indice
    i = indice
    for _ in range(n):
        i += 1 if paso > 0 else -1
        if not 0 <= i < n:
            if not envolver:
                return indice
            i %= n
        if visibles[i]:
            return i
    return indice


def direccion(arriba=False, abajo=False, palo_y=0.0, umbral=UMBRAL_PALO):
    """-1 (subir), +1 (bajar) o 0 según teclas/cruceta sostenidas y el palo (y > 0 = arriba)."""
    d = (1 if abajo else 0) - (1 if arriba else 0)
    if d == 0 and abs(palo_y) >= umbral:
        d = -1 if palo_y > 0 else 1
    return d


class Repetidor:
    """Repetición al sostener ↑/↓ (teclado, cruceta o palo): un paso al pulsar, otro tras RETARDO y luego uno cada
    PERIODO. `pulsar(d)` = evento de tecla (paso inmediato); `avanzar(d, dt)` = estado sostenido de este frame. Devuelve
    pasos [(dirección, es_repeticion)]. Una pulsación ya contada por `pulsar` no se cuenta otra vez al verla sostenida."""

    def __init__(self, retardo=RETARDO_REPETICION_S, periodo=PERIODO_REPETICION_S):
        self.retardo, self.periodo = retardo, periodo
        self.dir = 0
        self.espera = 0.0

    def pulsar(self, d):
        if d == 0:
            return []
        self.dir, self.espera = d, self.retardo
        return [(d, False)]

    def avanzar(self, d, dt):
        if d == 0:
            self.dir, self.espera = 0, 0.0
            return []
        if d != self.dir:                       # recién apretado (palo o cruceta sin evento) o cambio de sentido
            return self.pulsar(d)
        pasos = []
        self.espera -= paso_reloj(dt)           # un tirón (captura, carga, GC) no dispara una ráfaga de pasos
        while self.espera <= 0:
            pasos.append((d, True))
            self.espera += self.periodo
        return pasos

    def soltar(self):
        self.dir, self.espera = 0, 0.0


def navegar(indice, pasos, visibles):
    """Aplica pasos [(dirección, es_repeticion)]: una pulsación nueva envuelve; una repetición se para en el extremo
    (sostener ↓ no da vueltas sin fin)."""
    for d, repeticion in pasos:
        nuevo = siguiente(indice, d, visibles, envolver=not repeticion)
        if nuevo is not None:
            indice = nuevo
    return indice


# ---------------------------------------------------------------------------------------------------------------------
# Reducir movimiento
# ---------------------------------------------------------------------------------------------------------------------

def movimiento(reducido):
    """Qué se mueve: con «reducir movimiento», nada salvo el fundido de entrada."""
    return {"zoom": not reducido, "flotar": not reducido, "rebote_logo": not reducido,
            "escalonado": not reducido, "fundido": True}
