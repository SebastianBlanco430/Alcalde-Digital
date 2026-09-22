"""
Escena de partida: muestra la noticia activa (tomada de ArbolNoticias vía
MazoNoticias) y permite al jugador decidir "Compartir" o "Reportar". Cada
decisión consulta ArbolStats.obtener_por_camino con el camino isomorfo
devuelto por la búsqueda en ArbolNoticias, aplica los deltas resultantes a
los indicadores globales y avanza automáticamente a la siguiente noticia.

Esta escena NO implementa lógica de árboles: solo consume
backend/arboles/arbol_noticias.py, backend/arboles/arbol_stats.py,
backend/datos/noticias_seed.py y backend/logica/mazo_noticias.py tal como
están, sin duplicarla.
"""

import pygame

from backend.datos.noticias_seed import construir_arboles
from backend.logica.mazo_noticias import MazoNoticias


# --- Constantes de layout e indicadores ------------------------------------
# Regla de negocio: los indicadores viven en el rango [0, 100]. Cualquier
# delta aplicado (por compartir/reportar) SIEMPRE se recorta (clamp) a ese
# rango; nunca deben quedar por debajo de 0 ni por encima de 100.
INDICADOR_MIN = 0
INDICADOR_MAX = 100

NOMBRES_INDICADORES = ("convivencia", "confianza", "desinformacion")

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


def _clamp(valor, minimo=INDICADOR_MIN, maximo=INDICADOR_MAX):
    """Recorta `valor` al rango [minimo, maximo]."""
    return max(minimo, min(maximo, valor))


def _color_por_valor(valor):
    """Elige un color de barra según qué tan sano está el indicador.

    Decisión de UI: rojo/amarillo/verde en tercios (0-33 / 34-66 / 67-100)
    para que el jugador identifique de un vistazo qué indicador está en
    problemas, sin necesidad de leer el número.
    """
    if valor < 34:
        return COLOR_BARRA_BAJO
    if valor <= 66:
        return COLOR_BARRA_MEDIO
    return COLOR_BARRA_ALTO


def _envolver_texto(texto, fuente, ancho_max):
    """Parte `texto` en líneas que quepan en `ancho_max` píxeles con `fuente`.

    Wrap simple palabra por palabra usando fuente.size() para medir; no
    depende de ninguna librería extra de Pygame.
    """
    palabras = texto.split(" ")
    lineas = []
    linea_actual = ""

    for palabra in palabras:
        candidata = f"{linea_actual} {palabra}".strip()
        ancho_candidata, _ = fuente.size(candidata)
        if ancho_candidata <= ancho_max or not linea_actual:
            linea_actual = candidata
        else:
            lineas.append(linea_actual)
            linea_actual = palabra

    if linea_actual:
        lineas.append(linea_actual)

    return lineas


class PantallaJuego:
    """Escena principal de partida (primera entrega jugable).

    Constructor:
        superficie: la pygame.Surface donde se dibuja (p. ej. la ventana
            principal obtenida con pygame.display.set_mode()).
        jugador: objeto simple con la info del jugador seleccionado, para
            esta entrega se espera algo como {"nombre": ..., "rol": ...}.
            Solo se usa para mostrar nombre/rol en la UI.
        arbol_noticias / arbol_stats: opcionales; si no se pasan, la escena
            los construye con construir_arboles().
    """

    def __init__(self, superficie, jugador, arbol_noticias=None, arbol_stats=None):
        self.superficie = superficie
        self.ancho, self.alto = superficie.get_size()
        self.jugador = jugador or {}

        if arbol_noticias is None or arbol_stats is None:
            arbol_noticias, arbol_stats = construir_arboles()
        self.arbol_noticias = arbol_noticias
        self.arbol_stats = arbol_stats

        self.mazo = MazoNoticias(self.arbol_noticias)

        # Indicadores globales, arrancan al medio del rango [0, 100].
        self.indicadores = {"convivencia": 50, "confianza": 50, "desinformacion": 50}

        # Noticia activa: se carga una la primera vez, al construir la escena.
        self.noticia_actual = None
        self.camino_actual = None
        self._cargar_siguiente_noticia()

        # Fuentes (se crean una sola vez, no en cada frame).
        pygame.font.init()
        self.fuente_indicadores = pygame.font.SysFont("arial", 20)
        self.fuente_noticia = pygame.font.SysFont("arial", 24)
        self.fuente_boton = pygame.font.SysFont("arial", 24, bold=True)
        self.fuente_jugador = pygame.font.SysFont("arial", 16)
        self.fuente_vacio = pygame.font.SysFont("arial", 22, italic=True)

        # --- Layout ---
        self.panel_indicadores = pygame.Rect(0, 0, self.ancho, 100)

        self.tarjeta_rect = pygame.Rect(0, 0, 600, 220)
        self.tarjeta_rect.center = (self.ancho // 2, 260)

        ancho_boton, alto_boton = 220, 56
        espacio_entre_botones = 40
        y_botones = self.tarjeta_rect.bottom + 40

        x_izq = self.ancho // 2 - espacio_entre_botones // 2 - ancho_boton
        x_der = self.ancho // 2 + espacio_entre_botones // 2

        self.boton_compartir = pygame.Rect(x_izq, y_botones, ancho_boton, alto_boton)
        self.boton_reportar = pygame.Rect(x_der, y_botones, ancho_boton, alto_boton)

        self._hover_compartir = False
        self._hover_reportar = False

    # -- Estado / lógica -----------------------------------------------

    def _cargar_siguiente_noticia(self):
        """Pide la próxima noticia al mazo y actualiza noticia/camino activos.

        MazoNoticias.siguiente() nunca se traba (se reinicia solo cuando se
        agotan los ids), así que aquí solo hay que cubrir el caso teórico de
        un árbol vacío (retorna None).
        """
        resultado = self.mazo.siguiente()
        if resultado is None:
            self.noticia_actual = None
            self.camino_actual = None
            return
        self.noticia_actual, self.camino_actual = resultado

    def _aplicar_deltas(self, deltas):
        for nombre in NOMBRES_INDICADORES:
            delta = deltas.get(nombre, 0)
            nuevo_valor = self.indicadores[nombre] + delta
            self.indicadores[nombre] = _clamp(nuevo_valor)

    def _procesar_decision(self, tipo_decision):
        """tipo_decision: 'compartir' o 'reportar'."""
        if self.noticia_actual is None or self.camino_actual is None:
            return

        nodo_stats = self.arbol_stats.obtener_por_camino(self.camino_actual)
        if nodo_stats is None:
            # No debería pasar si los árboles están bien construidos
            # (isomorfismo roto). Se loguea y se ignora el click sin
            # romper el juego.
            print(
                "[PantallaJuego] ADVERTENCIA: obtener_por_camino devolvió "
                f"None para camino={self.camino_actual} "
                f"(noticia id={self.noticia_actual.id}). Click ignorado."
            )
            return

        if tipo_decision == "compartir":
            deltas = nodo_stats.deltas_compartir
        else:
            deltas = nodo_stats.deltas_reportar

        self._aplicar_deltas(deltas)
        self._cargar_siguiente_noticia()

    # -- Eventos ---------------------------------------------------------

    def manejar_evento(self, evento):
        if evento.type == pygame.MOUSEMOTION:
            self._hover_compartir = self.boton_compartir.collidepoint(evento.pos)
            self._hover_reportar = self.boton_reportar.collidepoint(evento.pos)
        elif evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
            if self.boton_compartir.collidepoint(evento.pos):
                self._procesar_decision("compartir")
            elif self.boton_reportar.collidepoint(evento.pos):
                self._procesar_decision("reportar")

    def actualizar(self, dt=0):
        """Reservado para lógica dependiente del tiempo en módulos futuros
        (p. ej. el reloj de presión viral). Por ahora no hace nada."""
        pass

    # -- Dibujado ----------------------------------------------------------

    def dibujar(self):
        self.superficie.fill(COLOR_FONDO)
        self._dibujar_panel_indicadores()
        self._dibujar_tarjeta_noticia()
        self._dibujar_botones()
        self._dibujar_info_jugador()

    def _dibujar_panel_indicadores(self):
        pygame.draw.rect(self.superficie, COLOR_PANEL, self.panel_indicadores)

        margen = 30
        ancho_bloque = (self.ancho - margen * 2) // 3
        alto_barra = 18

        for i, nombre in enumerate(NOMBRES_INDICADORES):
            valor = self.indicadores[nombre]
            x = margen + i * ancho_bloque
            y_etiqueta = 12
            y_barra = 40

            etiqueta = f"{nombre.capitalize()}: {valor}"
            superficie_texto = self.fuente_indicadores.render(etiqueta, True, COLOR_TEXTO)
            self.superficie.blit(superficie_texto, (x, y_etiqueta))

            ancho_barra = ancho_bloque - 20
            rect_fondo = pygame.Rect(x, y_barra, ancho_barra, alto_barra)
            pygame.draw.rect(self.superficie, COLOR_BARRA_FONDO, rect_fondo, border_radius=4)

            ancho_relleno = int(ancho_barra * (valor / INDICADOR_MAX))
            if ancho_relleno > 0:
                rect_relleno = pygame.Rect(x, y_barra, ancho_relleno, alto_barra)
                pygame.draw.rect(
                    self.superficie, _color_por_valor(valor), rect_relleno, border_radius=4
                )

    def _dibujar_tarjeta_noticia(self):
        pygame.draw.rect(self.superficie, COLOR_TARJETA, self.tarjeta_rect, border_radius=10)

        padding = 24
        ancho_texto = self.tarjeta_rect.width - padding * 2

        if self.noticia_actual is None:
            mensaje = self.fuente_vacio.render(
                "No hay más noticias disponibles.", True, COLOR_TEXTO_TENUE
            )
            rect_mensaje = mensaje.get_rect(center=self.tarjeta_rect.center)
            self.superficie.blit(mensaje, rect_mensaje)
            return

        lineas = _envolver_texto(self.noticia_actual.texto, self.fuente_noticia, ancho_texto)

        alto_linea = self.fuente_noticia.get_linesize()
        alto_total_texto = alto_linea * len(lineas)
        y = self.tarjeta_rect.top + (self.tarjeta_rect.height - alto_total_texto) // 2

        for linea in lineas:
            superficie_linea = self.fuente_noticia.render(linea, True, COLOR_TEXTO)
            rect_linea = superficie_linea.get_rect(
                centerx=self.tarjeta_rect.centerx, top=y
            )
            self.superficie.blit(superficie_linea, rect_linea)
            y += alto_linea

    def _dibujar_botones(self):
        hay_noticia = self.noticia_actual is not None

        self._dibujar_un_boton(
            self.boton_compartir, "Compartir", self._hover_compartir, hay_noticia
        )
        self._dibujar_un_boton(
            self.boton_reportar, "Reportar", self._hover_reportar, hay_noticia
        )

    def _dibujar_un_boton(self, rect, texto, hover, habilitado):
        if not habilitado:
            color = COLOR_BOTON_DESHABILITADO
        elif hover:
            color = COLOR_BOTON_HOVER
        else:
            color = COLOR_BOTON

        pygame.draw.rect(self.superficie, color, rect, border_radius=8)

        color_texto = COLOR_BOTON_TEXTO if habilitado else COLOR_TEXTO_TENUE
        superficie_texto = self.fuente_boton.render(texto, True, color_texto)
        rect_texto = superficie_texto.get_rect(center=rect.center)
        self.superficie.blit(superficie_texto, rect_texto)

    def _dibujar_info_jugador(self):
        nombre = self.jugador.get("nombre", "Jugador")
        rol = self.jugador.get("rol", "sin rol")
        texto = f"{nombre} ({rol})"
        superficie_texto = self.fuente_jugador.render(texto, True, COLOR_TEXTO_TENUE)
        rect_texto = superficie_texto.get_rect(bottomright=(self.ancho - 12, self.alto - 10))
        self.superficie.blit(superficie_texto, rect_texto)
