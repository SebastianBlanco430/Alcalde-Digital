# Escena de partida (Ursina): indicadores, noticia activa y botones de decisión.
# No contiene lógica de partida: consume EstadoPartida y solo vuelca su estado a
# los componentes de frontend/componentes.py.
# Layout en camera.ui (16:9): panel superior de indicadores, tarjeta de noticia,
# botones debajo e info del jugador abajo a la derecha.

from ursina import Entity, Text, invoke, time

from backend.datos.noticias_semilla import construir_arboles
from backend.logica.estado_partida import NOMBRES_INDICADORES, EstadoPartida
from backend.logica.lote_mision import LoteMision
from backend.logica.roles import ROLES
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
from frontend.panel_propagacion import PanelPropagacion

ASPECTO = 16 / 9   # la ventana se fija en 16:9 (ver main.py)
ANCHO_INTERFAZ = ASPECTO  # ancho total de camera.ui (alto = 1)


# Partida en curso. Al entrar, si no se inyecta un `estado`, crea un EstadoPartida
# nuevo con los árboles del seed (así "volver a jugar" reinicia la partida).
# Modo misión (opcional): si al entrar se pasa `mision`, se cuentan las decisiones y,
# al llegar a `mision.cantidad_noticias`, se muestra "Misión completada" ~1 s y se
# llama `al_terminar(resultado)`. Sin misión el comportamiento es el de siempre.
# Propagación (Fase 7): si además se inyecta `grafo_social`, en modo misión cada decisión
# calcula cómo se propaga la noticia por el grafo desde el ciudadano del rol y el
# PanelPropagacion (abajo a la izquierda) lo anima por saltos. Solo se MUESTRA el
# alcance: no toca los indicadores. El resultado de la misión suma "propagaciones" y
# "alcance_total". La animación corre en update() y nunca retrasa el fin de la misión.
# La regla del lote (contador, deltas, propagaciones, fin y resultado) vive en
# backend/logica/lote_mision.LoteMision; esta escena solo la llama y pinta.
class EscenaJuego(Escena):

    # --- Layout (unidades de camera.ui; medidas pygame / 600) ---
    ALTO_PANEL = a_unidades(100)
    MARGEN_PANEL = a_unidades(30)
    HOLGURA_BARRA = a_unidades(20)          # la barra es más corta que su bloque

    TARJETA_ANCHO = 1.16
    TARJETA_ALTO = 0.40
    TARJETA_Y = 0.05                         # centro de la tarjeta

    BOTON_ANCHO = a_unidades(220) * 1.15
    BOTON_ALTO = a_unidades(56)
    SEPARACION_BOTONES = a_unidades(40)      # hueco horizontal entre ambos
    SEPARACION_TARJETA_BOTONES = a_unidades(45)

    MARGEN_JUGADOR_X = a_unidades(12)
    MARGEN_JUGADOR_Y = a_unidades(10)

    MARGEN_PANEL_PROPAGACION = 0.02          # separación del panel de alcance a los bordes
    Y_MISION = 0.30
    Y_MISION_COMPLETADA = -0.39
    DEMORA_COMPLETADA = 1.0                  # segundos que se ve "Misión completada"
    TEXTO_COMPLETADA = "Misión completada"

    def __init__(self, **opciones):
        super().__init__(**opciones)
        self.estado = None
        self.jugador = {}
        self._reiniciar_mision(None, None)

        # Panel superior con las tres barras.
        self.panel = Entity(
            parent=self, model="quad", color=rgb(estilo.COLOR_PANEL),
            scale=(ANCHO_INTERFAZ, self.ALTO_PANEL), position=(0, 0.5 - self.ALTO_PANEL / 2, 0.01),
        )
        ancho_bloque = (ANCHO_INTERFAZ - 2 * self.MARGEN_PANEL) / 3
        self.barras = {}
        for indice, nombre in enumerate(NOMBRES_INDICADORES):
            self.barras[nombre] = BarraIndicador(
                estilo.ETIQUETAS_INDICADORES[nombre], ancho_bloque - self.HOLGURA_BARRA,
                parent=self,
                position=(-ANCHO_INTERFAZ / 2 + self.MARGEN_PANEL + indice * ancho_bloque, 0.5, 0),
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
            "Compartir", al_clic=self.compartir, ancho=self.BOTON_ANCHO, alto=self.BOTON_ALTO,
            parent=self, position=(-x_botones, y_botones),
        )
        self.boton_reportar = BotonAccion(
            "Reportar", al_clic=self.reportar, ancho=self.BOTON_ANCHO, alto=self.BOTON_ALTO,
            parent=self, position=(x_botones, y_botones),
        )

        # Info del jugador, abajo a la derecha.
        self.texto_jugador = Text(
            "", parent=self, origin=(0.5, -0.5),
            position=(ANCHO_INTERFAZ / 2 - self.MARGEN_JUGADOR_X, -0.5 + self.MARGEN_JUGADOR_Y),
            scale=escala_fuente(16), color=rgb(estilo.COLOR_TEXTO_TENUE),
        )

        # Panel de propagación en el grafo social (oculto hasta la primera decisión).
        self.grafo_social = None
        self.panel_propagacion = PanelPropagacion(
            parent=self, position=(
                -ANCHO_INTERFAZ / 2 + self.MARGEN_PANEL_PROPAGACION + PanelPropagacion.ANCHO / 2,
                -0.5 + self.MARGEN_PANEL_PROPAGACION + PanelPropagacion.ALTO / 2))

        # Modo misión: progreso arriba de la tarjeta y aviso de fin abajo.
        self.texto_mision = Text(
            "", parent=self, origin=(0, 0), position=(0, self.Y_MISION),
            scale=escala_fuente(20), color=rgb(estilo.COLOR_TEXTO_TENUE),
        )
        self.texto_completada = Text(
            "", parent=self, origin=(0, 0), position=(0, self.Y_MISION_COMPLETADA),
            scale=escala_fuente(28), color=rgb(estilo.COLOR_BARRA_ALTO),
        )

    # -- Ciclo de vida --

    # `jugador`: dict {"nombre", "rol"} u objeto con .nombre/.rol. `mision` y
    # `al_terminar` activan el modo misión. Cada entrada reinicia el contador.
    # `grafo_social` (opcional, inyectado): activa el panel de propagación en modo misión.
    def al_entrar(self, jugador=None, estado=None, mision=None, al_terminar=None,
                  grafo_social=None, **datos):
        self.jugador = jugador or {}
        if estado is None:
            arbol_noticias, arbol_stats = construir_arboles()
            estado = EstadoPartida(arbol_noticias, arbol_stats)
        self.estado = estado
        self._reiniciar_mision(mision, al_terminar)
        self.grafo_social = grafo_social
        if grafo_social is not None:
            self.panel_propagacion.fijar_grafo(grafo_social)
        if mision is not None:
            self.lote = LoteMision(mision, grafo_social, rol=self._rol_id())
        self.refrescar()

    # Al salir se invalida el invoke pendiente: _finalizar_mision no debe disparar
    # (ni completar la misión) si la escena ya no está activa.
    def al_salir(self):
        self._intento += 1

    def _reiniciar_mision(self, mision, al_terminar):
        self.mision = mision
        self._al_terminar = al_terminar
        self.lote = None
        self.mision_terminada = False
        if hasattr(self, "panel_propagacion"):
            self.panel_propagacion.ocultar()
        self._intento = getattr(self, "_intento", 0) + 1   # invalida invoke pendientes

    # Contadores del lote en curso (solo lectura); sin misión valen 0 / vacío.
    @property
    def decisiones(self):
        return self.lote.decisiones if self.lote is not None else 0

    @property
    def deltas_acumulados(self):
        if self.lote is not None:
            return self.lote.deltas_acumulados
        return {nombre: 0 for nombre in NOMBRES_INDICADORES}

    @property
    def propagaciones(self):
        return self.lote.propagaciones if self.lote is not None else []

    # -- Decisiones --

    def compartir(self):
        self.decidir("compartir")

    def reportar(self):
        self.decidir("reportar")

    def decidir(self, tipo):
        if self.estado is None or not self.estado.hay_noticia() or self.mision_terminada:
            return
        deltas = self.estado.decidir(tipo)
        if self.lote is not None:
            self._registrar_decision(tipo, deltas)
        self.refrescar()

    # Avanza la animación del panel (Ursina llama update() solo con la escena activa).
    def update(self):
        self.panel_propagacion.avanzar(time.dt)

    # Modo misión: el lote acumula y propaga; aquí solo se anima el panel (un clic nuevo
    # reinicia la animación) y, si el lote terminó (también con el mazo agotado, para no
    # dejar al jugador atascado), se programa el cierre tras DEMORA_COMPLETADA.
    def _registrar_decision(self, tipo, deltas):
        propagacion = self.lote.registrar(tipo, deltas, self.estado.hay_noticia())
        if self.lote.terminada():
            self.mision_terminada = True
            invoke(self._finalizar_mision, self._intento, delay=self.DEMORA_COMPLETADA)
        if propagacion is not None:
            self.panel_propagacion.mostrar(propagacion)

    def _finalizar_mision(self, intento):
        if intento != self._intento or self._al_terminar is None:
            return   # la escena se reinició o se abandonó antes de tiempo
        self._al_terminar(self.lote.resultado())

    # -- Vista --

    def refrescar(self):
        # vuelca el estado actual a barras, tarjeta, botones e info del jugador
        if self.estado is None:
            return

        indicadores = self.estado.indicadores()
        for nombre in NOMBRES_INDICADORES:
            self.barras[nombre].actualizar(indicadores[nombre])

        noticia = self.estado.noticia_actual()
        self.tarjeta.mostrar(None if noticia is None else noticia.texto)

        hay_noticia = self.estado.hay_noticia() and not self.mision_terminada
        self.boton_compartir.fijar_habilitado(hay_noticia)
        self.boton_reportar.fijar_habilitado(hay_noticia)

        nombre, rol = self._nombre_y_rol()
        self.texto_jugador.text = f"{nombre} ({rol})"

        if self.mision is None:
            self.texto_mision.text = ""
            self.texto_completada.text = ""
        else:
            self.texto_mision.text = (
                f"Misión: {self.mision.titulo} ({self.decisiones}/{self.mision.cantidad_noticias})"
            )
            self.texto_completada.text = self.TEXTO_COMPLETADA if self.mision_terminada else ""

    # Id del rol del jugador ("influencer", ...) sea dict u objeto.
    def _rol_id(self):
        if isinstance(self.jugador, dict):
            return self.jugador.get("rol")
        return self.jugador.rol

    # (nombre, rol visible). Un dict se muestra tal cual (id del rol); un objeto
    # con .nombre/.rol muestra el nombre legible del rol (p. ej. "Candidato a alcalde").
    def _nombre_y_rol(self):
        if isinstance(self.jugador, dict):
            return self.jugador.get("nombre", "Jugador"), self.jugador.get("rol", "sin rol")
        rol = self.jugador.rol
        return self.jugador.nombre, ROLES[rol].nombre if rol in ROLES else rol
