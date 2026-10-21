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
from frontend.marco_pc import ESCALA_JUEGO, MarcoPC
from frontend.panel_propagacion import PanelPropagacion
from frontend.panel_resultado_grafo import PanelResultadoGrafo
from frontend.red_social_vista import VistaRedSocial

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
# Resultado de la misión: con `grafo_social` y misión, al terminar el lote se ve ~1 s "Misión
# completada" y luego un panel grande (PanelResultadoGrafo) con el grafo social coloreado por el
# estado final acumulado y el resumen; al_terminar(resultado) se llama RECIÉN al pulsar
# «Continuar» (clic o Enter/Espacio), una sola vez. Sin grafo o sin misión: cierre automático
# tras DEMORA_COMPLETADA, exactamente como antes.
# La regla del lote (contador, deltas, propagaciones, fin y resultado) vive en
# backend/logica/lote_mision.LoteMision; esta escena solo la llama y pinta.
# Marco de monitor (mundo 3D): `al_entrar(marco=True, lugar=...)` dibuja el bisel y la barra
# "Civitas · <Rol> · <Lugar>" detrás del juego y lo reduce para que quepa dentro. Por defecto
# marco=False: la escena es exactamente la de siempre (también sin misión).
# Red social (2026-10-21): con ESTILO_RED_SOCIAL = True la escena se dibuja como un cliente tipo X
# («Civitas»: barra de navegación, feed con la publicación activa y su hilo, tendencias y panel de
# alcance; ver frontend/red_social_vista.py). Con False vuelve EXACTAMENTE al diseño anterior
# (tarjeta de noticia + dos botones), que sigue intacto debajo. Misma API en ambos modos.
class EscenaJuego(Escena):

    ESTILO_RED_SOCIAL = True

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
        self.marco = MarcoPC(parent=self.parent)    # hermano (detrás), no hijo: no se reduce con el juego
        self._reiniciar_mision(None, None)
        if self.ESTILO_RED_SOCIAL:
            self._construir_red_social()
            return

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

        # Pantalla de resultado de la misión (oculta hasta terminar el lote con grafo social).
        self.panel_resultado = PanelResultadoGrafo(parent=self, z=-0.3)

        # Modo misión: progreso arriba de la tarjeta y aviso de fin abajo.
        self.texto_mision = Text(
            "", parent=self, origin=(0, 0), position=(0, self.Y_MISION),
            scale=escala_fuente(20), color=rgb(estilo.COLOR_TEXTO_TENUE),
        )
        self.texto_completada = Text(
            "", parent=self, origin=(0, 0), position=(0, self.Y_MISION_COMPLETADA),
            scale=escala_fuente(28), color=rgb(estilo.COLOR_BARRA_ALTO),
        )

    # Construye la vista de red social con los MISMOS nombres de atributos que el diseño anterior
    # (barras, boton_compartir, boton_reportar, texto_mision, ...), así el resto de la escena no cambia.
    def _construir_red_social(self):
        self.red = VistaRedSocial(NOMBRES_INDICADORES, self.compartir, self.reportar, parent=self)
        self.panel = self.red
        self.barras = self.red.barras
        self.tarjeta = self.red.tarjeta
        self.boton_compartir = self.red.boton_compartir
        self.boton_reportar = self.red.boton_reportar
        self.texto_mision = self.red.texto_mision
        self.texto_completada = self.red.sello.texto
        self.texto_jugador = Text("", parent=self, enabled=False)   # el perfil visible vive en la barra lateral
        self.grafo_social = None
        self.panel_propagacion = self.red.panel_propagacion
        self.panel_resultado = PanelResultadoGrafo(parent=self, z=-0.3)

    # -- Ciclo de vida --

    # `jugador`: dict {"nombre", "rol"} u objeto con .nombre/.rol. `mision` y
    # `al_terminar` activan el modo misión. Cada entrada reinicia el contador.
    # `grafo_social` (opcional, inyectado): activa el panel de propagación en modo misión.
    def al_entrar(self, jugador=None, estado=None, mision=None, al_terminar=None,
                  grafo_social=None, marco=False, lugar="", **datos):
        self.jugador = jugador or {}
        self._poner_marco(marco, lugar)
        if self.ESTILO_RED_SOCIAL:
            self.red.reiniciar()
        if estado is None:
            arbol_noticias, arbol_stats = construir_arboles()
            estado = EstadoPartida(arbol_noticias, arbol_stats)
        self.estado = estado
        self._reiniciar_mision(mision, al_terminar)
        self.grafo_social = grafo_social
        if grafo_social is not None:
            self.panel_propagacion.fijar_grafo(grafo_social)
            self.panel_propagacion.fijar_rol(self._rol_id())
        if mision is not None:
            self.lote = LoteMision(mision, grafo_social, rol=self._rol_id())
        self.refrescar()

    # Al salir se invalida el invoke pendiente: _finalizar_mision no debe disparar
    # (ni completar la misión) si la escena ya no está activa.
    def al_salir(self):
        self._intento += 1
        self.panel_resultado.ocultar()
        if self.ESTILO_RED_SOCIAL:
            self.red.reiniciar()
        self._poner_marco(False, "")

    # Con marco el contenido se reduce y se centra dentro del bisel; sin él, escala normal.
    def _poner_marco(self, activo, lugar):
        if activo:
            nombre, rol = self._nombre_y_rol()
            self.marco.mostrar(rol, lugar)
            self.scale = ESCALA_JUEGO
        else:
            self.marco.ocultar()
            self.scale = 1

    def _reiniciar_mision(self, mision, al_terminar):
        self.mision = mision
        self._al_terminar = al_terminar
        self.lote = None
        self.mision_terminada = False
        if hasattr(self, "panel_propagacion"):
            self.panel_propagacion.ocultar()
        if hasattr(self, "panel_resultado"):
            self.panel_resultado.ocultar()
        self._resultado_entregado = False
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
        if self.ESTILO_RED_SOCIAL and deltas is not None:
            self.red.iniciar_decision(tipo)     # iconos que se llenan, contadores que suben, aviso
        if self.lote is not None:
            self._registrar_decision(tipo, deltas)
        self.refrescar()

    # Avanza la animación del panel (Ursina llama update() solo con la escena activa).
    def update(self):
        if self.ESTILO_RED_SOCIAL:
            self.red.avanzar(time.dt)
        self.panel_propagacion.avanzar(time.dt)
        self.panel_resultado.avanzar(time.dt)

    # Modo misión: el lote acumula y propaga; aquí solo se anima el panel (un clic nuevo
    # reinicia la animación) y, si el lote terminó (también con el mazo agotado, para no
    # dejar al jugador atascado), se programa el cierre tras DEMORA_COMPLETADA.
    def _registrar_decision(self, tipo, deltas):
        propagacion = self.lote.registrar(tipo, deltas, self.estado.hay_noticia())
        if self.lote.terminada():
            self.mision_terminada = True
            if self._usa_pantalla_resultado():
                invoke(self._mostrar_resultado, self._intento, delay=self.DEMORA_COMPLETADA)
            else:
                invoke(self._finalizar_mision, self._intento, delay=self.DEMORA_COMPLETADA)
        if propagacion is not None:
            self.panel_propagacion.mostrar(propagacion)

    # La pantalla de resultado solo existe en modo misión con grafo social inyectado.
    def _usa_pantalla_resultado(self):
        return self.lote is not None and self.grafo_social is not None

    # Tras "Misión completada": muestra el grafo final; «Continuar» entrega el resultado.
    def _mostrar_resultado(self, intento):
        if intento != self._intento or self._al_terminar is None:
            return   # la escena se reinició o se abandonó antes de tiempo
        self.panel_propagacion.ocultar()
        self.panel_resultado.mostrar(
            self.grafo_social, self.lote.propagaciones_con_niveles(), self.lote.deltas_acumulados,
            titulo=self.mision.titulo, indicadores=self.estado.indicadores(),
            al_continuar=lambda: self._continuar_resultado(intento))

    # «Continuar»: entrega el resultado una sola vez (y solo si la escena sigue vigente).
    def _continuar_resultado(self, intento):
        if self._resultado_entregado or intento != self._intento:
            return
        self._resultado_entregado = True
        self._finalizar_mision(intento)

    def _finalizar_mision(self, intento):
        if intento != self._intento or self._al_terminar is None:
            return   # la escena se reinició o se abandonó antes de tiempo
        self._al_terminar(self.lote.resultado())

    # -- Vista --

    def refrescar(self):
        # vuelca el estado actual a barras, tarjeta, botones e info del jugador
        if self.estado is None:
            return
        if self.ESTILO_RED_SOCIAL:
            self._refrescar_red_social()
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

    # Vuelca el estado a la vista de red social (misma información que refrescar() del diseño anterior).
    def _refrescar_red_social(self):
        indicadores = self.estado.indicadores()
        for nombre in NOMBRES_INDICADORES:
            self.barras[nombre].actualizar(indicadores[nombre])

        noticia = self.estado.noticia_actual()
        if not self.mision_terminada:    # al terminar el lote se queda a la vista la última decisión
            self.red.poner_publicacion(None if noticia is None else noticia.texto)

        hay_noticia = self.estado.hay_noticia() and not self.mision_terminada
        self.boton_compartir.fijar_habilitado(hay_noticia)
        self.boton_reportar.fijar_habilitado(hay_noticia)

        nombre, rol = self._nombre_y_rol()
        self.texto_jugador.text = f"{nombre} ({rol})"
        self.red.fijar_jugador(nombre, rol)

        if self.mision is None:
            self.red.fijar_mision("")
            self.red.fijar_completada("")
        else:
            self.red.fijar_mision(
                f"Misión: {self.mision.titulo} ({self.decisiones}/{self.mision.cantidad_noticias})")
            self.red.fijar_completada(self.TEXTO_COMPLETADA if self.mision_terminada else "")

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
