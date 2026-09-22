"""
Pantalla de inicio TEMPORAL.

Esta escena es intencionalmente simple: solo muestra el título del juego,
un subtítulo y un botón "Comenzar". NO es un menú principal ni un sistema
de selección de jugador/rol -- eso corresponde a una entrega futura del
subagente `arquitectura-mundos`, cuando se diseñe el flujo real de
selección de jugadores para multijugador.

Reusa la paleta de colores y el estilo de botones de
`frontend/escenas/pantalla_juego.py` para que la transición visual entre
ambas escenas sea coherente.
"""

import pygame


# --- Paleta reutilizada de pantalla_juego.py para consistencia visual ------
COLOR_FONDO = (24, 26, 38)
COLOR_TEXTO = (235, 235, 240)
COLOR_TEXTO_TENUE = (170, 172, 190)

COLOR_BOTON = (70, 90, 150)
COLOR_BOTON_HOVER = (95, 118, 185)
COLOR_BOTON_TEXTO = (240, 240, 245)


class PantallaInicio:
    """Pantalla de bienvenida mínima previa a la partida.

    Constructor:
        superficie: la pygame.Surface donde se dibuja (p. ej. la ventana
            principal obtenida con pygame.display.set_mode()).

    Atributo público:
        terminada: bool, empieza en False y pasa a True cuando el jugador
            hace click en el botón "Comenzar". `main.py` debe revisar este
            atributo para decidir cuándo pasar a la siguiente escena.
    """

    def __init__(self, superficie):
        self.superficie = superficie
        self.ancho, self.alto = superficie.get_size()

        self.terminada = False

        pygame.font.init()
        self.fuente_titulo = pygame.font.SysFont("arial", 48, bold=True)
        self.fuente_subtitulo = pygame.font.SysFont("arial", 22)
        self.fuente_boton = pygame.font.SysFont("arial", 24, bold=True)

        # --- Layout ---
        ancho_boton, alto_boton = 220, 56
        self.boton_comenzar = pygame.Rect(0, 0, ancho_boton, alto_boton)
        self.boton_comenzar.center = (self.ancho // 2, self.alto // 2 + 60)

        self._pos_titulo = (self.ancho // 2, self.alto // 2 - 60)
        self._pos_subtitulo = (self.ancho // 2, self.alto // 2 - 10)

        self._hover_comenzar = False

    # -- Eventos ---------------------------------------------------------

    def manejar_evento(self, evento):
        if evento.type == pygame.MOUSEMOTION:
            self._hover_comenzar = self.boton_comenzar.collidepoint(evento.pos)
        elif evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
            if self.boton_comenzar.collidepoint(evento.pos):
                self.terminada = True

    def actualizar(self, dt=0):
        """Reservado para animaciones/transiciones futuras. Por ahora no
        hace nada, igual que en PantallaJuego."""
        pass

    # -- Dibujado ----------------------------------------------------------

    def dibujar(self):
        self.superficie.fill(COLOR_FONDO)
        self._dibujar_titulo()
        self._dibujar_boton()

    def _dibujar_titulo(self):
        titulo = self.fuente_titulo.render("Alcalde Digital", True, COLOR_TEXTO)
        rect_titulo = titulo.get_rect(center=self._pos_titulo)
        self.superficie.blit(titulo, rect_titulo)


    def _dibujar_boton(self):
        color = COLOR_BOTON_HOVER if self._hover_comenzar else COLOR_BOTON
        pygame.draw.rect(self.superficie, color, self.boton_comenzar, border_radius=8)

        texto = self.fuente_boton.render("Comenzar", True, COLOR_BOTON_TEXTO)
        rect_texto = texto.get_rect(center=self.boton_comenzar.center)
        self.superficie.blit(texto, rect_texto)
