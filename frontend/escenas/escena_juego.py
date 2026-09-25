"""
Escena de partida (Ursina): indicadores, noticia activa y botones de decisión.

Replica el comportamiento y la paleta de la pantalla de partida pygame original
(retirada en el Módulo 5). NO contiene lógica de partida: consume
`backend.logica.estado_partida.EstadoPartida` (indicadores, noticia activa y
`decidir`), y solo vuelca su estado a los componentes de `frontend/componentes.py`.

Diseño en camera.ui (16:9: x en [-0.888, 0.888], y en [-0.5, 0.5]): el mismo
orden vertical que la versión pygame de 800x600 (panel superior de
indicadores, tarjeta de noticia, botones debajo, info del jugador abajo a la
derecha); el panel y el texto conservan sus medidas (en proporción a la altura)
y solo la tarjeta y los botones se ensanchan un poco para el ancho 16:9.
"""

from ursina import Entity, Text

from backend.datos.noticias_seed import construir_arboles
from backend.logica.estado_partida import NOMBRES_INDICADORES, EstadoPartida
from frontend import estilo
from frontend.componentes import (
    BarraIndicador,
    BotonAccion,
    TarjetaNoticia,
    a_unidades,
    escala_fuente,
    rgb,
)
from frontend.escenas.escena_base import Escena

ASPECTO = 16 / 9   # la ventana se fija en 16:9 (ver main.py)
ANCHO_UI = ASPECTO  # ancho total de camera.ui (alto = 1)


class EscenaJuego(Escena):
    """Partida en curso.

    `al_entrar(jugador=None, estado=None)`: si no se inyecta un `estado`, crea un
    `EstadoPartida` nuevo con los árboles del seed (así "volver a jugar" reinicia
    la partida). Inyectar uno permite probar la vista con estados controlados.

    Atributos públicos (para pruebas): `estado`, `jugador`, `panel`, `barras`
    (dict indicador -> BarraIndicador), `tarjeta`, `boton_compartir`,
    `boton_reportar`, `texto_jugador`; y el método `refrescar()`.
    """

    # --- Layout (unidades de camera.ui; medidas pygame / 600) ---------------
    ALTO_PANEL = a_unidades(100)
    MARGEN_PANEL = a_unidades(30)
    HOLGURA_BARRA = a_unidades(20)          # la barra es más corta que su bloque

    # 16:9 dispone de más ancho y de más alto libre que 800x600: la tarjeta es
    # algo más ancha y alta, y todo el bloque baja un poco para repartir mejor.
    TARJETA_ANCHO = 1.16
    TARJETA_ALTO = 0.40
    TARJETA_Y = 0.05                         # centro de la tarjeta

    BOTON_ANCHO = a_unidades(220) * 1.15
    BOTON_ALTO = a_unidades(56)
    SEPARACION_BOTONES = a_unidades(40)      # hueco horizontal entre ambos
    SEPARACION_TARJETA_BOTONES = a_unidades(45)

    MARGEN_JUGADOR_X = a_unidades(12)
    MARGEN_JUGADOR_Y = a_unidades(10)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.estado = None
        self.jugador = {}

        # Panel superior con las tres barras.
        self.panel = Entity(
            parent=self, model="quad", color=rgb(estilo.COLOR_PANEL),
            scale=(ANCHO_UI, self.ALTO_PANEL), position=(0, 0.5 - self.ALTO_PANEL / 2, 0.01),
        )
        ancho_bloque = (ANCHO_UI - 2 * self.MARGEN_PANEL) / 3
        self.barras = {}
        for i, nombre in enumerate(NOMBRES_INDICADORES):
            self.barras[nombre] = BarraIndicador(
                estilo.ETIQUETAS_INDICADORES[nombre], ancho_bloque - self.HOLGURA_BARRA,
                parent=self,
                position=(-ANCHO_UI / 2 + self.MARGEN_PANEL + i * ancho_bloque, 0.5, 0),
            )

        # Tarjeta de noticia.
        self.tarjeta = TarjetaNoticia(
            self.TARJETA_ANCHO, self.TARJETA_ALTO, parent=self, position=(0, self.TARJETA_Y),
        )

        # Botones de decisión, bajo la tarjeta (Compartir a la izquierda).
        y_botones = (
            self.TARJETA_Y - self.TARJETA_ALTO / 2
            - self.SEPARACION_TARJETA_BOTONES - self.BOTON_ALTO / 2
        )
        x_botones = (self.SEPARACION_BOTONES + self.BOTON_ANCHO) / 2
        self.boton_compartir = BotonAccion(
            "Compartir", on_click=self._compartir, ancho=self.BOTON_ANCHO, alto=self.BOTON_ALTO,
            parent=self, position=(-x_botones, y_botones),
        )
        self.boton_reportar = BotonAccion(
            "Reportar", on_click=self._reportar, ancho=self.BOTON_ANCHO, alto=self.BOTON_ALTO,
            parent=self, position=(x_botones, y_botones),
        )

        # Info del jugador, abajo a la derecha.
        self.texto_jugador = Text(
            "", parent=self, origin=(0.5, -0.5),
            position=(ANCHO_UI / 2 - self.MARGEN_JUGADOR_X, -0.5 + self.MARGEN_JUGADOR_Y),
            scale=escala_fuente(16), color=rgb(estilo.COLOR_TEXTO_TENUE),
        )

    # -- Ciclo de vida -----------------------------------------------------------

    def al_entrar(self, jugador=None, estado=None, **datos):
        self.jugador = jugador or {}
        if estado is None:
            arbol_noticias, arbol_stats = construir_arboles()
            estado = EstadoPartida(arbol_noticias, arbol_stats)
        self.estado = estado
        self.refrescar()

    # -- Decisiones ------------------------------------------------------------------

    def _compartir(self):
        self._decidir("compartir")

    def _reportar(self):
        self._decidir("reportar")

    def _decidir(self, tipo):
        if self.estado is None or not self.estado.hay_noticia:
            return
        self.estado.decidir(tipo)
        self.refrescar()

    # -- Vista -------------------------------------------------------------------------

    def refrescar(self):
        """Vuelca el estado actual a barras, tarjeta, botones e info del jugador."""
        if self.estado is None:
            return

        indicadores = self.estado.indicadores
        for nombre in NOMBRES_INDICADORES:
            self.barras[nombre].actualizar(indicadores[nombre])

        noticia = self.estado.noticia_actual
        self.tarjeta.mostrar(None if noticia is None else noticia.texto)

        hay_noticia = self.estado.hay_noticia
        self.boton_compartir.habilitado = hay_noticia
        self.boton_reportar.habilitado = hay_noticia

        nombre = self.jugador.get("nombre", "Jugador")
        rol = self.jugador.get("rol", "sin rol")
        self.texto_jugador.text = f"{nombre} ({rol})"
